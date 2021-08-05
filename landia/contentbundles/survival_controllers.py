
from typing import List
import random
from ..common import Base, Vector2
from ..clock import clock
from .survival_common import Effect, StateController, SurvivalContent
from .survival_objects import AnimateObject, Monster, PhysicalObject, Food
from .survival_behaviors import PlayingInfection, PlayingTag
from ..player import Player
from .. import gamectx
import logging


class PlayerSpawnController(StateController):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content: SurvivalContent = gamectx.content

    def reset_player(self, player: Player):
        player.set_data_value("lives_used", 0)
        player.set_data_value("food_reward_count", 0)
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
            player_config = self.content.get_game_config()['player_types']['1']
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
        for player in gamectx.player_manager.players_map.values():
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
        self.spawn_food()

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
        self.behavior = "PlayingTag"
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
        self.behavior = "PlayingInfection"
        self.obj_ids = set()
        self.game_start_tick = 0
        self.ticks_per_round = 100 * self.content.step_duration()
        self.last_infect = 0
        self.infect_counter = 0
        self.infected_tag = "infected"
        self.playing_tag = "playinginfection"
        self.tags_used = {self.infected_tag, self.playing_tag}

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
            target_obj.add_reward(-10)
            self.infect_counter += 1
            return False
        else:
            return True

    def update(self):
        tag_time = clock.get_ticks() - self.last_infect
        if tag_time > self.ticks_per_round:
            print("Resetting infection game")
            for obj in self.get_objects():
                if obj is not None and not obj.get_id() in self.infected_obj_ids:
                    obj.add_reward(10)
                else:
                    obj.add_reward(-2)

            self.reset()


# class TagController2(StateController):

#     def __init__(self,*args,**kwargs):
#         super().__init__(*args,**kwargs)
#         self.content:SurvivalContent = gamectx.content
#         self.tag_tool:TagTool = None
#         self.tagged_obj = None
#         self.behavior = "PlayingTag"
#         self.obj_ids = set()
#         self.game_start_tick = 0
#         self.ticks_per_round = 100 * self.content.step_duration()
#         self.last_tag = 0
#         self.tag_changes = 0
#         self.is_tagged_tag = "tagged"
#         self.tags_used = set(self.is_tagged_tag)
#         # self.rounds = 0


#     def get_objects(self):
#         objs = []
#         for obj_id in self.obj_ids:
#             obj = gamectx.object_manager.get_by_id(obj_id)
#             if obj is not None:
#                 objs.append(obj)
#         return objs

#     def reset(self):
#         # Create Tag Tool
#         if self.tag_tool is None:
#             self.tag_tool = self.content.create_object_from_config_id("tag_tool")
#             self.tag_tool.spawn(Vector2(0,0))
#             self.tag_tool.disable()
#             self.tag_tool.add_trigger("tag_user","tag_user",self.tag_trigger)

#         if self.tagged_obj is not None:
#             slot_tools = self.tagged_obj.get_inventory().find("tag_tool")
#             for i, tool in slot_tools:
#                 self.tagged_obj.get_inventory().remove_by_slot(i)
#             self.tag_tool.remove_effect(self.tagged_obj)

#         # Assign players to tag game
#         self.obj_ids = set()
#         objs:List[AnimateObject] = []
#         for obj in gamectx.object_manager.get_objects_by_config_id("human1"):
#             objs.append(obj)
#             self.obj_ids.add(obj.get_id())
#             obj.remove_tag(self.is_tagged_tag)
#         for obj in gamectx.object_manager.get_objects_by_config_id("monster1"):
#             objs.append(obj)
#             obj.remove_tag(self.is_tagged_tag)
#             self.obj_ids.add(obj.get_id())

#         for obj in objs:
#             p= obj.get_player()
#             obj.add_effect(Effect("tag",type="tag", data={'color':[0,255,0],"index":1}))

#             if p is None:
#                 obj.default_behavior = PlayingTag(self)
#         # Select Who is "it"
#         obj = random.choice(objs)
#         obj.add_effect(Effect("tag",type="tag", data={'color':[0,255,255],"index":0}))

#         obj.add_tag(self.is_tagged_tag)
#         obj.get_inventory().add(self.tag_tool, True)
#         self.tag_tool.add_effect(obj)
#         self.tagged_obj = obj
#         self.game_start_tick = clock.get_tick_counter()
#         self.last_tag = clock.get_tick_counter()

#     def tag_trigger(self,tag_tool, source_obj, target_obj):
#         self.tagged_obj = target_obj
#         source_obj.remove_tag(self.is_tagged_tag)
#         self.last_tag = clock.get_tick_counter()
#         self.tagged_obj.add_reward(-10)
#         self.tag_changes+=1
#         return True

#     def update(self):
#         tag_time = clock.get_tick_counter() - self.last_tag
#         if tag_time > self.ticks_per_round:
#             print("Resetting tag game")
#             for obj in self.get_objects():
#                 if obj is not None and obj.get_id() != self.tagged_obj.get_id():
#                     obj.add_reward(10)
#             self.content.request_reset()
