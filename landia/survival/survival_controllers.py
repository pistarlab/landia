
from typing import List
import random
from landia.common import Base, Vector2
from landia.clock import clock
from .survival_common import Effect, StateController, SurvivalContent
from .survival_objects import AnimateObject, Monster, PhysicalObject, Food
from .survival_behaviors import PlayingInfection, PlayingTag, PlayingCTF
from landia.player import Player
from landia import gamectx
import logging


class PlayerSpawnController(StateController):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content: SurvivalContent = gamectx.content

    def reset_player(self, player: Player):
        player.set_data_value("lives_used", 0)
        player.set_data_value("reset_required", False)
        player.set_data_value("allow_obs", True)
        player.events = []

    def reset(self):
        super().reset()
        self.spawn_players(reset=True)

    def update(self):
        pass

    def join(self, player):
        if not self.started:
            return
        self.spawn_player(player, True)

    def spawn_player(self, player: Player, reset=False):
        if player.get_object_id() is not None:
            player_object = gamectx.object_manager.get_by_id(player.get_object_id())
        else:
            # TODO: get playertype from game mode + client config
            player_config = self.content.get_game_config()['player_types']['default']
            config_id = player_config['config_id']
            player_object: PhysicalObject = self.content.create_object_from_config_id(config_id)
            player_object.set_player(player)

        if reset:
            self.reset_player(player)

        spawn_point = player.get_data_value("spawn_point")
        if spawn_point is None:
            spawn_point = self.content.get_available_location()
        if spawn_point is None:
            logging.error("No spawnpoint available")

        player_object.spawn(spawn_point)
        return player_object

    def spawn_players(self, reset=True):
        for player in gamectx.player_manager.get_players_by_types(type_set={"default"}):
            self.spawn_player(player, reset)


class ObjectCollisionController(StateController):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content: SurvivalContent = gamectx.content
        self.actor_obj_ids = set()
        self.obj_config_ids = set(["rock1"])
        self.reward_delta = -1

    def get_objects(self):
        objs = []
        for obj_id in self.actor_obj_ids:
            obj = gamectx.object_manager.get_by_id(obj_id)
            if obj is not None:
                objs.append(obj)
        return objs

    def collision_with_trigger(self, obj, obj2):
        if obj2.config_id not in self.obj_config_ids:
            return True
        obj.add_reward(self.reward_delta)
        return True

    def reset(self):
        super().reset()
        self.actor_obj_ids = set()
        objs: List[AnimateObject] = []
        for obj in gamectx.object_manager.get_objects_by_config_id("human1"):
            obj.add_trigger("collision_with", "obj_collid", self.collision_with_trigger)
            objs.append(obj)
            self.actor_obj_ids.add(obj.get_id())

    def update(self):
        pass


class FoodCollectController(StateController):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content: SurvivalContent = gamectx.content
        self.actor_obj_ids = set()
        self.food_ids = set()
        self.game_start_tick = 0
        self.last_check = 0
        self.check_freq = 10 * self.content.step_duration()
        self.needed_food = 4

    def get_objects(self):
        objs = []
        for obj_id in self.actor_obj_ids:
            obj = gamectx.object_manager.get_by_id(obj_id)
            if obj is not None:
                objs.append(obj)
        return objs

    def join(self, player: Player):
        if not self.started:
            return
        obj = gamectx.object_manager.get_by_id(player.get_object_id())
        if obj is not None and player.get_object_id() not in self.actor_obj_ids:
            self.add_player_object(obj)

    def add_player_object(self, obj: PhysicalObject):
        obj.add_trigger("collision_with", "collect", self.collision_with_trigger)
        obj.add_trigger("die", "collect", self.die_trigger)
        self.actor_obj_ids.add(obj.get_id())

    def collected_trigger(self, obj: PhysicalObject, actor_obj: PhysicalObject):
        actor_obj.add_reward(1)
        self.food_ids.discard(obj.get_id())
        return True

    def collision_with_trigger(self, obj: PhysicalObject, obj2: PhysicalObject):
        if obj2.get_id() not in self.food_ids:
            return True
        obj.add_reward(1)

        gamectx.remove_object(obj2)
        obj.consume_food(obj2)
        self.food_ids.discard(obj2.get_id())
        gamectx.remove_object(obj2)
        return True

    def die_trigger(self, obj):
        obj.add_reward(-20)
        return True

    def spawn_food(self):
        loc = self.content.get_available_location()
        if loc is not None:
            food: Food = self.content.create_object_from_config_id("apple1")
            food.spawn(loc)
            self.food_ids.add(food.get_id())
            food.add_trigger("receive_grab", "collect", self.collected_trigger)

    def reset(self):
        super().reset()

        # Assign players to tag game
        self.actor_obj_ids = set()
        self.food_ids = set()
        for obj in gamectx.object_manager.get_objects_by_config_id("human1"):
            self.add_player_object(obj)

        # Get All Food in game
        self.actor_obj_ids = set()
        objs: List[Food] = []
        for obj in gamectx.object_manager.get_objects_by_config_id("apple1"):
            obj.add_trigger("receive_grab", "collect", self.collected_trigger)
            self.food_ids.add(obj.get_id())
            objs.append(obj)
        # self.spawn_food()



    def update(self):
        time_since = clock.get_ticks() - self.last_check
        if time_since > self.check_freq:
            if len(self.food_ids) < self.needed_food:
                self.spawn_food()

            self.last_check = clock.get_ticks()


class TagController(StateController):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content: SurvivalContent = gamectx.content
        self.tagged_obj = None
        self.behavior = PlayingTag
        self.obj_ids = set()
        self.game_start_tick = 0
        self.ticks_per_round = 100 * self.content.step_duration()
        self.last_tag = 0
        self.tag_changes = 0
        self.is_tagged_tag = "tagged"
        self.playing_tag_tag = "playingtag"
        self.tags_used = set(self.is_tagged_tag)
        # self.rounds = 0

    def get_objects(self):
        objs = []
        for obj_id in self.obj_ids:
            obj = gamectx.object_manager.get_by_id(obj_id)
            if obj is not None:
                objs.append(obj)
        return objs

    def join(self, player: Player):
        if not self.started:
            return
        obj = gamectx.object_manager.get_by_id(player.get_object_id())
        if obj is not None and player.get_object_id() not in self.obj_ids:
            self.add_player_object(obj)

    def add_player_object(self, obj):
        self.obj_ids.add(obj.get_id())

        obj.remove_tag(self.is_tagged_tag)
        obj.add_tag(self.playing_tag_tag)
        obj.add_trigger("unarmed_attack", "tag", self.tag_trigger)
        p = obj.get_player()
        if p is None:
            obj.default_behavior = PlayingTag(self)

    def reset(self):
        super().reset()

        # Assign players to tag game
        self.obj_ids = set()
        objs: List[AnimateObject] = []
        for obj in gamectx.object_manager.get_objects_by_config_id("human1"):
            objs.append(obj)

        for obj in gamectx.object_manager.get_objects_by_config_id("monster1"):
            objs.append(obj)

        for obj in objs:
            self.add_player_object(obj)

        # Select Who is "it"
        obj = random.choice(objs)

        obj.add_tag(self.is_tagged_tag)
        self.tagged_obj = obj
        self.game_start_tick = clock.get_ticks()
        self.last_tag = clock.get_ticks()

    def tag_trigger(self, source_obj):
        if not self.is_tagged_tag in source_obj.tags:
            return True

        print("Trying to tag")
        direction = Vector2(0, 1).rotate(source_obj.angle)
        target_pos = source_obj.get_position() + (direction * source_obj._l_content.tile_size)
        target_coord = gamectx.physics_engine.vec_to_coord(target_pos)

        target_obj = None
        for oid in gamectx.physics_engine.space.get_objs_at(target_coord):
            obj2: PhysicalObject = gamectx.object_manager.get_by_id(oid)
            if obj2.collision_type > 0 and self.playing_tag_tag in obj2.tags:
                target_obj = obj2
                break

        if target_obj is not None:
            print("Tagging")
            source_obj.remove_tag(self.is_tagged_tag)
            target_obj.add_tag(self.is_tagged_tag)
            target_obj.stunned()
            source_obj.invoke_attacking_action()

            self.tagged_obj = target_obj
            source_obj.remove_tag(self.is_tagged_tag)
            self.last_tag = clock.get_ticks()
            self.tagged_obj.add_reward(-10)
            self.tag_changes += 1
            return False
        else:
            return True

    def update(self):
        tag_time = clock.get_ticks() - self.last_tag
        if tag_time > self.ticks_per_round:
            print("Resetting tag game")
            for obj in self.get_objects():
                if obj is not None and obj.get_id() != self.tagged_obj.get_id():
                    obj.add_reward(10)
            self.content.request_reset()


class InfectionController(StateController):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content: SurvivalContent = gamectx.content
        self.infected_obj_ids = set()
        self.behavior = PlayingInfection
        self.obj_ids = set()
        self.game_start_tick = 0
        self.ticks_per_round = 100 * self.content.step_duration()
        self.last_infect = 0
        self.infect_counter = 0
        self.infected_tag = "infected"
        self.playing_tag = "playinginfection"
        self.tags_used = {self.infected_tag, self.playing_tag}
        self.game_over = False

    def get_objects(self):
        objs = []
        for obj_id in self.obj_ids:
            obj = gamectx.object_manager.get_by_id(obj_id)
            if obj is not None:
                objs.append(obj)
        return objs

    def join(self, player: Player):
        if not self.started:
            return

        obj = gamectx.object_manager.get_by_id(player.get_object_id())
        if obj is not None and player.get_object_id() not in self.obj_ids:
            self.add_player_object(obj)

    def add_player_object(self, obj):
        self.obj_ids.add(obj.get_id())
        p = obj.get_player()
        obj.add_tag(self.playing_tag)
        obj.remove_tag(self.infected_tag)
        obj.add_trigger("unarmed_attack", "infect", self.infect_trigger)
        obj.add_trigger("receive_damage", "infect", self.receive_damage_trigger)
        if p is None:
            obj.default_behavior = PlayingInfection(self)
        else:
            self.content.message_player(p, "Playing Infection", 30)

    def reset(self):
        super().reset()

        # Assign players to tag game
        self.obj_ids = set()
        objs: List[AnimateObject] = []
        for obj in gamectx.object_manager.get_objects_by_config_id("human1"):
            objs.append(obj)
        for obj in gamectx.object_manager.get_objects_by_config_id("monster1"):
            objs.append(obj)

        for obj in objs:
            self.add_player_object(obj)

        # Select Who is "it"
        obj = random.choice(objs)

        obj.add_tag(self.infected_tag)

        self.infected_obj_ids = set()
        self.infected_obj_ids.add(obj.get_id())
        self.game_start_tick = clock.get_ticks()
        self.last_infect = clock.get_ticks()
        self.game_over = False

    def receive_damage_trigger(self, source_obj, attacker_obj: AnimateObject, damage):
        if attacker_obj.get_id() in self.obj_ids:
            self.content.log_console("No Damage")
            return False
        else:
            return True

    def infect_trigger(self, source_obj):
        if not self.infected_tag in source_obj.tags:
            return True

        self.content.log_console("Trying to Infecting")
        direction = Vector2(0, 1).rotate(source_obj.angle)
        target_pos = source_obj.get_position() + (direction * source_obj._l_content.tile_size)
        target_coord = gamectx.physics_engine.vec_to_coord(target_pos)

        target_obj = None
        for oid in gamectx.physics_engine.space.get_objs_at(target_coord):
            obj2: PhysicalObject = gamectx.object_manager.get_by_id(oid)
            if obj2.collision_type > 0 and self.playing_tag in obj2.tags and not self.infected_tag in obj2.tags:
                target_obj = obj2
                break

        if target_obj is not None:
            self.content.log_console("Infecting")
            target_obj.add_tag(self.infected_tag)
            target_obj.stunned()
            source_obj.invoke_attacking_action()

            self.infected_obj_ids.add(target_obj.get_id())
            self.last_infect = clock.get_ticks()

            target_obj.add_reward(-2)
            source_obj.add_reward(2)
            self.infect_counter += 1
            if len(self.infected_obj_ids) == len(self.obj_ids):
                self.game_over = True
            return False
        else:
            return True

    def update(self):
        tag_time = clock.get_ticks() - self.last_infect
        if self.game_over or tag_time > self.ticks_per_round:
            print("Resetting infection game")
            for obj in self.get_objects():
                if obj is not None and not obj.get_id() in self.infected_obj_ids:
                    obj.add_reward(10)
                else:
                    obj.add_reward(-2)

            self.reset()


class CTFTeam:

    def __init__(self,color):
        self.color = color
        self.flag_id = None
        self.flag_zone_id = None
        self.flag_holder_id = None
        self.team_ids = set()
    
    def get_team_tag(self):
        return f"{self.color}team"

    def remove_player_obj_id(self,id):
        if self.flag_holder_id == id:
            self.flag_holder_id = None
        self.team_ids.discard(id)
        

class CTFController(StateController):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content: SurvivalContent = gamectx.content
        self.behavior_class = PlayingCTF

        # self.red_flag_id = None
        # self.red_flag_zone_id = None
        # self.red_flag_holder_id = None
        
        # self.blue_flag_id = None
        # self.blue_flag_zone_id = None        
        # self.blue_flag_holder_id = None


        # self.red_team_ids = set()
        # self.blue_team_ids = set()

        # self.red_team_tag = "redteam"
        # self.blue_team_tag = "blueteam"
        self.teams={
            'red':CTFTeam('red'),
            'blue':CTFTeam('blue')
        }


        self.game_start_tick = 0
        self.ticks_per_round = 100 * self.content.step_duration()
        
        self.playing_tag = "ctf"

        self.has_flag_tag = "hasflag"
        self.tags_used = set([self.playing_tag, self.has_flag_tag] + [t.get_team_tag() for t in self.teams.values()])
        self.game_over = False

    def assign_to_team(self,obj,color):
        team = self.teams.get(color)
        obj.add_tag(team.get_team_tag())
        team.team_ids.add(obj.get_id())

    def get_team(self,obj):
        for team in self.teams.values():
            if obj.get_id() in team.team_ids:
                return team
        return None

    def reset_flags(self):
        for team in self.teams.values():
            self.reset_flag(team.color)

    def reset_flag(self,flag_color):
        team = self.teams.get(flag_color)

        if team.flag_zone_id is None:
            flag_zones= gamectx.object_manager.get_objects_by_config_id(f"{flag_color}_flag_zone")
            flag_zone = flag_zones[0]
        else:
            flag_zone = gamectx.get_object_by_id(team.flag_zone_id)
        
        if team.flag_id is None:      
            flag = self.content.create_object_from_config_id(f'{flag_color}_flag')
            team.flag_id = flag.get_id()
        else:
            flag = gamectx.get_object_by_id(team.flag_id)
        
        flag.spawn(flag_zone.get_position())

    def remove_from_game(self,obj):
        for team in self.teams.values():
            team.remove_player_obj_id(obj.get_id())
            obj.remove_tag(team.get_team_tag())
        
    def assign_team(self,obj):
        self.remove_from_game(obj)       
        min_count = min([ len(team.team_ids) for team in self.teams.values()])
        teamcandidates = [team for team in self.teams.values() if len(team.team_ids) == min_count]
        team = random.choice(teamcandidates)
        self.assign_to_team(obj,team.color)

    def get_objects(self):
        objs = []
        for team in self.teams.values():
            for obj_id in team.team_ids:
                obj = gamectx.object_manager.get_by_id(obj_id)
                if obj is not None:
                    objs.append(obj)
        return objs

    def get_other_teams(self,obj):
        return [team for team in self.teams.values() if obj.get_id() not in team.team_ids]

    def join(self, player: Player):
        if not self.started:
            return

        obj = gamectx.object_manager.get_by_id(player.get_object_id())
        if obj is not None and player.get_object_id() not in self.obj_ids:
            self.add_player_object(obj)

    def add_player_object(self, obj,skip_team_assign=False):
        p = obj.get_player()
        obj.add_trigger("unarmed_attack", "ctf", self.attack_trigger)
        obj.add_trigger("receive_damage", "ctf", self.receive_damage_trigger)
        obj.add_trigger("collision_with", "ctf", self.collision_with_trigger)
        if not skip_team_assign:
            self.assign_team(obj)
        if p is None:
            obj.default_behavior = self.behavior_class(self)
        else:
            self.content.message_player(p, "Playing CTF", 30)

    def reset(self):
        super().reset()
        self.reset_flags()

        # Assign players to tag game
        objs: List[AnimateObject] = []
        for obj in gamectx.object_manager.get_objects_by_config_id("human1"):
            objs.append(obj)
        for obj in gamectx.object_manager.get_objects_by_config_id("monster1"):
            objs.append(obj)
        
        random.shuffle(objs)
        for obj in objs:
            self.add_player_object(obj)
       
        self.game_start_tick = clock.get_ticks()
        self.game_over = False

    def receive_damage_trigger(self, source_obj, attacker_obj: AnimateObject, damage):
        if attacker_obj.get_id() in self.obj_ids:
            self.content.log_console("No Damage")
            return False
        else:
            return True

    def attack_trigger(self, source_obj):

        self.content.log_console("Trying to attack")
        direction = Vector2(0, 1).rotate(source_obj.angle)
        target_pos = source_obj.get_position() + (direction * source_obj._l_content.tile_size)
        target_coord = gamectx.physics_engine.vec_to_coord(target_pos)

        target_obj = None
        for oid in gamectx.physics_engine.space.get_objs_at(target_coord):
            obj2: PhysicalObject = gamectx.object_manager.get_by_id(oid)
            if obj2.collision_type > 0 and self.playing_tag in obj2.tags and obj2.get_id() in self.get_other_team_ids(source_obj):
                target_obj = obj2
                break

        if target_obj is not None:
            self.content.log_console("Attack Successful")
            # target_obj.add_tag(self.infected_tag)
            target_obj.stunned()
            source_obj.invoke_attacking_action()

            # # self.infected_obj_ids.add(target_obj.get_id())

            # target_obj.add_reward(-2)
            # source_obj.add_reward(2)
            # if len(self.infected_obj_ids) == len(self.obj_ids):
            #     self.game_over = True
            return False
        else:
            return True

    # def add_player_object(self, obj: PhysicalObject):
    #     obj.add_trigger("collision_with", "collect", self.collision_with_trigger)
    #     obj.add_trigger("die", "collect", self.die_trigger)
    #     self.actor_obj_ids.add(obj.get_id())

    # def collected_trigger(self, obj: PhysicalObject, actor_obj: PhysicalObject):
    #     actor_obj.add_reward(1)
    #     self.food_ids.discard(obj.get_id())
    #     return True

    def collision_with_trigger(self, obj: AnimateObject, obj2: PhysicalObject):
        other_teams = self.get_other_teams(obj)
        for oteam in other_teams:
            if obj2.get_id() == oteam.flag_id:
                obj.get_inventory().add(obj2)
                obj.add_reward(1)
                obj.add_tag("hasflag")
                oteam.flag_holder_id = obj.get_id()

        if "hasflag" in obj.tags:
            team = self.get_team(obj)
            # if obj2.get_id
        

        return True

    def update(self):
        if self.game_over:
            print("Resetting CTF game")
            for obj in self.get_objects():
                if obj is not None and not obj.get_id() in self.infected_obj_ids:
                    obj.add_reward(10)
                else:
                    obj.add_reward(-2)

            self.reset()
     