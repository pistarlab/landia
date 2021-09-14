from typing import List
import random
from landia.common import Base, Vector2
from landia.clock import clock
from .survival_common import Effect, StateController, SurvivalContent
from .survival_objects import AnimateObject, Monster, PhysicalObject, Food
from .survival_behaviors import PlayingInfection, PlayingTag, PlayingCTF
from landia.player import Player
from landia.renderer import Renderer
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
            player_config = self.content.get_game_config()["player_types"]["default"]
            config_id = player_config["config_id"]
            player_object: PhysicalObject = self.content.create_object_from_config_id(
                config_id
            )
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

    def post_process_frame(self, player: Player, renderer: Renderer):
        if player.player_type == "admin":
            msg_fsize = round(renderer.full_resolution[1] / 40)

            view_port_resolution = renderer.resolution
            view_port_offset = renderer.view_port_offset

            lines = []
            lines.append(f"Landia: Forage")
            lines.append("-----------------------------")

            renderer.render_text(
                lines,
                x=view_port_resolution[0] + view_port_offset[0] * 2,
                y=view_port_offset[1],
                fsize=msg_fsize,
            )


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
        target_pos = source_obj.get_position() + (
            direction * source_obj._l_content.tile_size
        )
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

    def post_process_frame(self, player: Player, renderer: Renderer):
        if player.player_type == "admin":
            msg_fsize = round(renderer.full_resolution[1] / 40)

            view_port_resolution = renderer.resolution
            view_port_offset = renderer.view_port_offset

            lines = []
            lines.append(f"Landia: Tag")
            lines.append("-----------------------------")

            renderer.render_text(
                lines,
                x=view_port_resolution[0] + view_port_offset[0] * 2,
                y=view_port_offset[1],
                fsize=msg_fsize,
            )


class InfectionController(StateController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content: SurvivalContent = gamectx.content
        self.infected_obj_ids = set()
        self.behavior = PlayingInfection
        self.obj_ids = set()
        self.game_start_tick = 0
        self.ticks_per_round = 100 * self.content.step_duration()
        self.reset_delay = 20 * self.content.step_duration()
        self.reset_time = None
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
        if obj is not None:
            self.add_player_object(obj)
        else:
            print("Players obj not found")

    def reset_player_object(self, obj):
        obj.add_tag(self.playing_tag)
        obj.remove_tag(self.infected_tag)
        p = obj.get_player()
        if p is not None:
            self.content.message_player(
                p, "Starting Infection Game", 30, clear_messages=True
            )

    def add_player_object(self, obj):
        self.obj_ids.add(obj.get_id())
        obj.add_tag(self.playing_tag)
        obj.remove_tag(self.infected_tag)
        p = obj.get_player()
        obj.add_trigger("unarmed_attack", "infect", self.infect_trigger)
        obj.add_trigger("receive_damage", "infect", self.receive_damage_trigger)
        if p is None:
            obj.default_behavior = PlayingInfection(self)
        if self.started and p is not None:
            self.content.message_player(
                p, "Joining Infection Game", 30, clear_messages=True
            )

    def add_bot(self):
        obj: PhysicalObject = self.content.create_object_from_config_id("monster1")

        return obj

    def reset(self):
        super().reset()

        # Assign players to tag game
        self.obj_ids = set()
        objs: List[AnimateObject] = []
        for obj in gamectx.object_manager.get_objects_by_config_id("human1"):
            objs.append(obj)
        for obj in gamectx.object_manager.get_objects_by_config_id("monster1"):
            objs.append(obj)

        while len(objs) < 3:
            obj = self.add_bot()
            obj.spawn(self.content.get_available_location())
            objs.append(obj)

        for obj in objs:
            if obj.get_id() in self.obj_ids:
                self.reset_player_object(obj)
            else:
                self.add_player_object(obj)

        # Select Who is "it"
        obj = random.choice(objs)

        obj.add_tag(self.infected_tag)

        self.infected_obj_ids = set()
        self.infected_obj_ids.add(obj.get_id())
        self.game_start_tick = clock.get_ticks()
        self.last_infect = clock.get_ticks()
        self.game_over = False
        self.reset_time = None

    def receive_damage_trigger(self, source_obj, attacker_obj: AnimateObject, damage):
        if attacker_obj.get_id() in self.obj_ids:
            self.content.log_console("No Damage")
            return False
        else:
            return True

    def infect_trigger(self, source_obj):
        if not self.infected_tag in source_obj.tags:
            return True

        direction = Vector2(0, 1).rotate(source_obj.angle)
        target_pos = source_obj.get_position() + (
            direction * source_obj._l_content.tile_size
        )
        target_coord = gamectx.physics_engine.vec_to_coord(target_pos)

        target_obj = None
        for oid in gamectx.physics_engine.space.get_objs_at(target_coord):
            obj2: PhysicalObject = gamectx.object_manager.get_by_id(oid)
            if (
                obj2.collision_type > 0
                and self.playing_tag in obj2.tags
                and not self.infected_tag in obj2.tags
            ):
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
        self.reset_time
        if not self.game_over and tag_time > self.ticks_per_round:
            print("Resetting infection game")
            for obj in self.get_objects():
                if obj is not None and not obj.get_id() in self.infected_obj_ids:
                    obj.add_reward(10)
                else:
                    obj.add_reward(-2)
            self.game_over = True

        if self.game_over:
            if self.reset_time is None:
                for oid in self.obj_ids:
                    o: AnimateObject = gamectx.get_object_by_id(oid)
                    p = o.get_player()
                    if p is not None:
                        self.content.message_player(
                            p, "Game Over", 10, clear_messages=True
                        )
                self.reset_time = clock.get_ticks() + self.reset_delay
            if clock.get_ticks() > self.reset_time:
                self.reset()

    def post_process_frame(self, player: Player, renderer: Renderer):
        if player.player_type == "admin":
            msg_fsize = round(renderer.full_resolution[1] / 40)

            view_port_resolution = renderer.resolution
            view_port_offset = renderer.view_port_offset

            lines = []
            lines.append(f"Landia: Infection Tag")
            lines.append("-----------------------------")

            renderer.render_text(
                lines,
                x=view_port_resolution[0] + view_port_offset[0] * 2,
                y=view_port_offset[1],
                fsize=msg_fsize,
            )


class CTFTeam:
    def __init__(self, color):
        self.color = color
        self.flag_id = None
        self.flag_zone_id = None
        self.flag_holder_id = None
        self.flag_at_home = True
        self.team_ids = set()

        self.spawn_points = []
        self.score = 0
        self.wins = 0

    def get_team_tag(self):
        return f"{self.color}team"

    def remove_player_obj_id(self, id):
        if self.flag_holder_id == id:
            self.flag_holder_id = None
        self.team_ids.discard(id)


class CTFController(StateController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.content: SurvivalContent = gamectx.content
        self.behavior_class = PlayingCTF

        self.teams = {"red": CTFTeam("red"), "blue": CTFTeam("blue")}

        self.playing_tag = "ctf"

        self.has_flag_tag = "hasflag"
        self.tags_used = set(
            [self.playing_tag, self.has_flag_tag]
            + [t.get_team_tag() for t in self.teams.values()]
        )
        self.game_over = False
        self.reset_time = None
        self.reset_delay = 10

        self.ticks_per_round = (
            self.config.get("round_lenght", 200) * self.content.step_duration()
        )
        self.game_start_tick = 0

        self.min_team_size = self.config.get("min_team_size", 2)
        self.bot_config_id = self.config.get("bot_config_id", "monster1")
        self.disabled_actions = self.config.get(
            "disabled_actions", ["jump", "grab", "craft", "drop"]
        )

        self.init_flag_zones()
        self.assign_spawn_points()
        self.player_rewards = {}
        self.max_score = self.config.get("max_score", 3)

    def init_flag_zones(self):

        flag_zones = gamectx.object_manager.get_objects_by_config_id("flag_zone")

        for zone, team in zip(flag_zones, self.teams.values()):
            zone.model_id = f"{team.color}_flag_zone"
            team.flag_zone_id = zone.get_id()

    def update_player_reward(self, obj_id, reward):
        reward = self.player_rewards.get(obj_id, 0) + reward
        self.player_rewards[obj_id] = reward

    def assign_spawn_points(self):
        spawn_points = gamectx.object_manager.get_objects_by_config_id("spawn_point")
        for spawn_point in spawn_points:
            czone = None
            czone_dist = None
            cteam = None
            for team in self.teams.values():
                zone = gamectx.get_object_by_id(team.flag_zone_id)
                zone_dist = zone.get_position().distance_to(spawn_point.get_position())
                if czone is None or zone_dist < czone_dist:
                    czone_dist = zone_dist
                    cteam = team
                    czone = zone
            if cteam is not None:
                cteam.spawn_points.append(spawn_point)

    def assign_to_team(self, obj, color):
        team = self.teams.get(color)
        obj.add_tag(team.get_team_tag())
        team.team_ids.add(obj.get_id())
        return team

    def get_team(self, obj):
        for team in self.teams.values():
            if obj.get_id() in team.team_ids:
                return team
        return None

    def reset_flags(self):
        for team in self.teams.values():
            self.reset_flag(team.color)
            team.score = 0

    def reset_flag(self, color):
        team = self.teams.get(color)

        flag_zone = gamectx.get_object_by_id(team.flag_zone_id)

        if team.flag_id is None:
            flag = self.content.create_object_from_config_id("flag")
            flag.model_id = f"{color}_flag"
            team.flag_id = flag.get_id()
        else:
            flag = gamectx.get_object_by_id(team.flag_id)

        flag.spawn(flag_zone.get_position())
        team.flag_at_home = True

    def reset_player(self, player: Player):
        """
        clear player events and disable observations
        """
        player.set_data_value("allow_obs", True)
        player.set_data_value("reset_required", False)
        player.events = []

    def init_player(self, player: Player):
        """
        Create new player object for player
        """
        obj: PhysicalObject = None
        if player.get_object_id() is None:
            player_config = self.content.get_game_config()["player_types"]["default"]
            config_id = player_config["config_id"]
            obj: PhysicalObject = self.content.create_object_from_config_id(config_id)
            obj.set_player(player)
        else:
            obj = gamectx.get_object_by_id(player.get_object_id())

        self.reset_player(player)

        if "?" in player.client_id:
            player_role, team_info = player.client_id.split("?")
            team_id, player_id = team_info.split("_")
            self.setup_player_object(obj, team_id=team_id)

        else:
            self.setup_player_object(obj)
        return obj

    def add_bot(self, team_id=None):
        obj: PhysicalObject = self.content.create_object_from_config_id(
            self.bot_config_id
        )
        self.setup_player_object(obj, team_id=team_id)
        return obj

    def setup_player_object(
        self, obj: AnimateObject, skip_team_assign=False, team_id=None
    ):
        """
        Setup Player object
        """
        obj.add_trigger("unarmed_attack", "ctf", self.attack_trigger)
        obj.add_trigger("receive_damage", "ctf", self.receive_damage_trigger)
        obj.add_trigger("collision_with", "ctf", self.collision_with_trigger)
        obj.add_trigger("die", "ctf", self.die_trigger)
        obj.disabled_actions = self.disabled_actions
        if team_id is not None or not skip_team_assign:
            team = self.assign_team(obj, team_id)
            flag_zone = gamectx.get_object_by_id(team.flag_zone_id)
            obj.set_data_value("spawn_point", flag_zone.get_position())
        p: Player = obj.get_player()
        if p is None:
            obj.default_behavior = self.behavior_class(self)
        else:
            self.content.message_player(p, "Playing CTF", 30)

    def disable_controller(self):
        # TODO: remove all changes to objects such as triggers
        pass

    def spawn_player_obj(self, obj: AnimateObject, reset=False):
        """
        Spawn Player Object
        """
        player = obj.get_player()
        if player != None and reset:
            self.reset_player(player)
        # else:
        #     obj.default_behavior = self.behavior_class(self)

        team = self.get_team(obj)
        spawn_point_obj = random.choice(team.spawn_points)
        obj.spawn(spawn_point_obj.get_position())
        return obj

    def spawn_player_objs(self, reset=True):
        for team in self.teams.values():
            for obj_id in team.team_ids:
                obj: AnimateObject = gamectx.get_object_by_id(obj_id)
                self.spawn_player_obj(obj, reset)
                p = obj.get_player()
                if reset and p is not None:
                    self.reset_player(p)
                self.remove_flag_from_player_obj(obj)

    def remove_from_game(self, obj):
        for team in self.teams.values():
            team.remove_player_obj_id(obj.get_id())
            obj.remove_tag(team.get_team_tag())

    def assign_team(self, obj: PhysicalObject, team_id=None):
        self.remove_from_game(obj)
        if team_id is None:
            min_count = min([len(team.team_ids) for team in self.teams.values()])
            teamcandidates = [
                team for team in self.teams.values() if len(team.team_ids) == min_count
            ]
            team = random.choice(teamcandidates)
            self.assign_to_team(obj, team.color)
        else:
            team = self.assign_to_team(obj, team_id)
        return team

    def get_objects(self):
        objs = []
        for team in self.teams.values():
            for obj_id in team.team_ids:
                obj = gamectx.object_manager.get_by_id(obj_id)
                if obj is not None:
                    objs.append(obj)
        return objs

    def get_other_teams(self, obj):
        return [
            team for team in self.teams.values() if obj.get_id() not in team.team_ids
        ]

    def get_opponents_team(self, obj, other_obj):
        """
        returns other_obj team if they are an opponent
        """
        other_teams = self.get_other_teams(obj)
        for team in other_teams:
            if other_obj.get_id() in team.team_ids:
                return team
        return None

    def join(self, player: Player):
        obj = self.init_player(player)

        if self.started:
            # Allows drop in players
            self.spawn_player_obj(obj)

    def reset(self):
        super().reset()
        self.reset_flags()

        print("Resetting CTF")

        # Fill with bots
        for team in self.teams.values():
            while len(team.team_ids) < self.min_team_size:
                self.add_bot(team.color)
        self.spawn_player_objs(reset=True)

        self.game_start_tick = clock.get_ticks()
        self.game_over = False

    def receive_damage_trigger(self, source_obj, attacker_obj: AnimateObject, damage):
        source_team = self.get_team(source_obj)
        if source_team is not None:
            attacker_team = self.get_team(attacker_obj)
            if attacker_team is not None:
                return source_team.color != attacker_team.color
            else:
                return True
        else:
            return True

    def attack_trigger(self, source_obj):

        direction = Vector2(0, 1).rotate(source_obj.angle)
        target_pos = source_obj.get_position() + (
            direction * source_obj._l_content.tile_size
        )
        target_coord = gamectx.physics_engine.vec_to_coord(target_pos)

        target_obj = None
        for oid in gamectx.physics_engine.space.get_objs_at(target_coord):
            obj2: PhysicalObject = gamectx.object_manager.get_by_id(oid)
            if (
                obj2.collision_type > 0
                and self.playing_tag in obj2.tags
                and obj2.get_id() in self.get_other_team_ids(source_obj)
            ):
                target_obj = obj2
                break

        if target_obj is not None:
            self.content.log_console("Attack Successful")
            # target_obj.add_tag(self.infected_tag)
            target_obj.stunned()
            source_obj.invoke_attacking_action()

            return False
        else:
            return True

    def die_trigger(self, obj):

        flag, flag_team = self.remove_flag_from_player_obj(obj)
        if flag is not None:
            flag.spawn(obj.get_position())
        self.spawn_player_obj(obj)
        return False

    def remove_flag_from_player_obj(self, obj):
        if self.has_flag_tag in obj.tags:
            flag_inv = obj.get_inventory().find("flag")
            for slot, flag in flag_inv:
                obj.get_inventory().remove_by_slot(slot)
                flag_color = self.get_flag_color(flag)
                obj.remove_tag("hasflag")
                obj.remove_effect(f"has_{flag_color}_flag")
                self.teams[flag_color].flag_holder_id = None
                return flag, self.teams[flag_color]
        return None, None

    def get_flag_color(self, flag_obj):
        for team in self.teams.values():
            if team.flag_id == flag_obj.get_id():
                return team.color

        return None

    def collision_with_trigger(self, obj: AnimateObject, obj2: PhysicalObject):
        if obj2.config_id == "flag":
            flag_color = self.get_flag_color(obj2)
            flag_team = self.teams[flag_color]
            if obj.get_id() in flag_team.team_ids:
                # Retreive team flag
                if flag_team.flag_holder_id is None and not flag_team.flag_at_home:
                    self.reset_flag(flag_color)
                    obj.add_reward(1)
                    self.update_player_reward(obj.get_id(), 1)
                return True

            else:
                # Get Opponent's flag
                obj.get_inventory().add(obj2)
                obj.add_tag("hasflag")
                obj.add_reward(1)
                self.update_player_reward(obj.get_id(), 1)
                obj.add_effect_by_id(f"has_{flag_team.color}_flag")
                flag_team.flag_holder_id = obj.get_id()
                flag_team.flag_at_home = False
                return True

        if obj2.config_id == "flag_zone":
            oteam = self.get_team(obj)
            if oteam.flag_zone_id == obj2.get_id():
                flag, flag_team = self.remove_flag_from_player_obj(obj)

                if flag is not None:
                    # Capture Flag
                    obj.add_reward(10)
                    self.update_player_reward(obj.get_id(), 10)
                    obj_team = self.get_team(obj)
                    obj_team.score += 1
                    if obj_team.score >= self.max_score:
                        self.game_over = True
                        obj_team.wins += 1
                    else:
                        self.reset_flag(flag_team.color)

                    return True

        return True

    def update(self):

        if not self.game_over and self.get_time_left() <= 0:
            print("Out of time, game ending")
            self.game_over = True

        if self.game_over:
            if self.reset_time is None:
                for team in self.teams.values():
                    for oid in team.team_ids:
                        o: AnimateObject = gamectx.get_object_by_id(oid)
                        if team.score < self.max_score:
                            o.add_reward(-2)
                            self.update_player_reward(oid, -2)
                        p = o.get_player()
                        if p is not None:
                            self.content.message_player(
                                p, "Game Over", 10, clear_messages=True
                            )
                self.reset_time = clock.get_ticks() + self.reset_delay
            if clock.get_ticks() > self.reset_time:
                self.reset_time = None
                # self.reset()
                self.content.request_reset()

    def get_time_left(self):
        return max(0, (self.game_start_tick + self.ticks_per_round) - clock.get_ticks())

    def get_player_reward(self, obj_id):
        return self.player_rewards.get(obj_id, 0)

    def get_player_object_hud_info(self, obj):
        oteam = self.get_team(obj)
        scores = [f"[{oteam.color}:{oteam.score}]"]
        for team in self.get_other_teams(obj):
            scores.append(f"{team.color}:{team.score}")

        scores = ", ".join(scores)
        return (
            f"CTF: {scores}, Reward: {self.get_player_reward(obj.get_id)}, Timeleft: {round(self.get_time_left()/gamectx.config.tick_rate)} "
        )

    def post_process_frame(self, player: Player, renderer: Renderer):

        if player.player_type == "admin":
            msg_fsize = round(renderer.full_resolution[1] / 40)
            view_port_resolution = renderer.resolution
            view_port_offset = renderer.view_port_offset
            view_port_resolution = renderer.resolution
            view_port_offset = renderer.view_port_offset

            lines = []
            lines.append(f"Landia: Capture the Flag")
            lines.append("-----------------------------")
            lines.append(f"First to {self.max_score} wins")
            lines.append("")
            for team in self.teams.values():
                lines.append(
                    f"{team.color}: Score {team.score}, Total Wins: {team.wins}"
                )
                for oid in team.team_ids:
                    o: AnimateObject = gamectx.get_object_by_id(oid)
                    p = o.get_player()
                    if p is None:
                        player_name = f"bot: {o.get_id()}"
                    else:
                        name = f"{p.name}:{p.client_id}" if p.name else p.client_id
                        player_name = name
                    lines.append(
                        f"    Player: {player_name} + {self.get_player_reward(oid)}"
                    )
                    o.info_label = player_name
            renderer.render_text(
                lines,
                x=view_port_resolution[0] + view_port_offset[0] * 2,
                y=view_port_offset[1],
                fsize=msg_fsize,
            )
        # else:
        #     msg_fsize = round(renderer.full_resolution[1]/40)
        #     obj_id = player.get_object_id()
        #     pobj = gamectx.get_object_by_id(obj_id)
        #     if pobj is not None:
        #         print("H")

        #         team = self.get_team(pobj)
        #         lines = []
        #         lines.append(f"{team.color}: Score {team.score}, Total Wins: {team.wins}")
        #         renderer.render_text(
        #             lines,
        #             x=0,
        #             y=0,
        #             fsize=msg_fsize,
        #             use_view_port_surface = True
        #             )
        return
