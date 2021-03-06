import json
import math
import os
import random
import sys
import time
from typing import Any, Dict, List, Tuple

import numpy as np
from gym import spaces
from pygame.key import name
from landia import gamectx
from landia.camera import Camera
from landia.clock import clock
from landia.common import Vector2, get_base_cls_by_name, StateDecoder, StateEncoder
from landia.event import (AdminCommandEvent, DelayedEvent, Event, InputEvent,
                          ObjectEvent, PeriodicEvent, PositionChangeEvent,
                          SoundEvent, ViewEvent)
from landia.object import GObject
from landia.player import Player
from landia.renderer import Renderer
from landia.utils import gen_id, getsize, getsizewl, merged_dict

from .survival_assets import load_asset_bundle
from .survival_behaviors import FleeAnimals, FollowAnimals, PlayingTag
from .survival_controllers import (FoodCollectController, InfectionController,
                                   ObjectCollisionController, CTFController,
                                   PlayerSpawnController, TagController)
from .survival_map import GameMap
from .survival_objects import *
from .survival_utils import (int_map_to_onehot_map, ints_to_multi_hot,
                             vec_to_coord)

############################
# COLLISION HANDLING
############################


def default_collision_callback(obj1: PhysicalObject, obj2: PhysicalObject):
    return obj1.collision_with(obj2)


class GameContent(SurvivalContent):

    def __init__(self, config):
        super().__init__(config)

        self.active_controllers: List[str] = self.config['active_controllers']
        self.map_config = self.config['maps'][self.config['start_map']]
        # TODO, load from game config
        self.default_camera_distance = config['default_camera_distance']
        self.tile_size = self.config['tile_size']

        # Effect Vector Lookup
        self.effect_int_map = {config_id: value.get(
            'obs_id', i) for i, (config_id, value) in enumerate(self.config['effects'].items())}
        self.max_effect_id = len(self.effect_int_map)
        self.effect_vec_map = int_map_to_onehot_map(self.effect_int_map)

        self.tag_list = self.config['tag_list']
        # Static for now to keep observation space same between configuration, #len(self.tag_list)
        self.max_tags = 10
        self.tag_int_map = {tag: i for i, tag in enumerate(self.tag_list)}
        self.tag_effect_map = self.config.get("tag_effect_map", {})

        # Object Vector Lookup
        self.obj_int_map = {config_id: value.get(
            'obs_id', i) for i, (config_id, value) in enumerate(self.config['objects'].items())}
        self.max_obs_id = len(self.obj_int_map)
        self.obj_vec_map = int_map_to_onehot_map(self.obj_int_map)
        self.vision_radius = 2  # Vision info should be moved to objects, possibly predifined

        self.player_count = 0

        self.key_map={
            'UP':23,
            'DOWN':19,
            'RIGHT':4,
            'LEFT':1,
            'GRAB':5,
            'DROP':6,
            'USE':18,
            'INV_MENU_NEXT':3,
            'INV_MENU_PREV':26,
            'CRAFT_MENU_NEXT':2,
            'CRAFT_MENU_PREV':22,
            'CRAFT':17,
            'JUMP':33,
            'PUSH':7
        }

        self.agent_key_list = [self.key_map[k] for k in sorted(list(self.key_map.keys()))]

        self.loaded = False

        self.asset_bundle = load_asset_bundle(
            path=self.config['root_path'],
            asset_bundle_config=self.config['asset_bundle'])

        self.gamemap = GameMap(
            paths=[self.config.get("game_config_root"),
                   self.config.get("mod_path")],
            map_config=self.map_config,
            tile_size=self.tile_size,
            seed=self.config.get("map_seed", 123))

        self._step_duration_factor = self.config['step_duration_factor']

        self._step_duration = None
        self.call_counter = 0

        # All loadable classes should be registered
        self.classes = [Action,
                        Effect, Human, Monster, Inventory,
                        Food, Tool, Animal, Tree, Rock,
                        Liquid, PhysicalObject, Camera,
                        TagController,
                        PlayerSpawnController,
                        ObjectCollisionController,
                        FoodCollectController,
                        InfectionController,
                        CTFController]

        for cls in self.classes:
            gamectx.register_base_class(cls)
        self.obj_class_map = {cls.__name__: cls for cls in self.classes}
        self.controllers: Dict[str, StateController] = {}

        self.behavior_classes = [FleeAnimals, FollowAnimals, PlayingTag]
        self.bevavior_class_map: Dict[str, Behavior] = {
            cls.__name__: cls for cls in self.behavior_classes}

        # Memory Debugging
        self.debug_memory = False
        self.console_report_freq_sec = 4
        self.console_report_last = 0
        self.max_size = {}

    def create_tags_vec(self, tags):
        return ints_to_multi_hot([self.tag_int_map[tag] for tag in tags], self.max_tags)

    def get_game_config(self):
        return self.config

    def load_controllers(self):
        self.controllers = {}
        for cid in self.active_controllers:
            self.controllers[cid] = self.create_controller(cid)

    def reset_controllers(self):
        for cid in self.active_controllers:
            self.controllers[cid].reset()

    def update_controllers(self):
        for cid in self.active_controllers:
            self.controllers[cid].update()

    def get_controller_by_id(self, cid):
        return self.controllers.get(cid)

    # TODO, would be better to have it's own copy of the config but network traffic would increase when object is created
    # def get_effect_sprites(self,config_id):
    #     return self.config['effects'].get(config_id,{}).get('model',{})

    def get_effect_by_tag_id(self, tag, overrides={}):
        effect_id = self.tag_effect_map.get(tag)
        if effect_id is None:
            return None
        else:
            return self.get_effect_by_id(effect_id, overrides)

    def get_effect_by_id(self, effect_id, overrides={}):
        data = self.config['effects'].get(effect_id, None)
        if data is not None:
            config = merged_dict(data['config'], overrides)
            return Effect(config_id=effect_id, **config)
        return None

    # TODO, would be better to have it's own copy of the config but network traffic would increase when object is created
    def get_object_sprites(self, model_id):
        return self.config['models'].get(model_id, {})

    def get_object_sounds(self, config_id):
        return self.config['objects'].get(config_id, {}).get('sounds', {})

    def get_available_location(self, max_tries=200):
        point = None
        tries = 0
        while point is None or tries > max_tries:
            coord = self.gamemap.random_coords(num=1)[0]
            objs = gamectx.get_objects_by_coord(coord)
            if len(objs) == 0:
                point = coord_to_vec(coord)
        return point

    def get_near_location(self, point):
        coord = vec_to_coord(point)

        neighs = self.gamemap.get_neigh_coords(coord)
        point = None
        for neigh in neighs:
            objs = gamectx.get_objects_by_coord(neigh)
            if len(objs) == 0:
                point = coord_to_vec(neigh)
        return point

    # Factory Methods
    def create_behavior(self, name, *args, **kwargs):
        return self.bevavior_class_map[name](*args, **kwargs)

    def create_controller(self, cid):
        info = self.config['controllers'].get(cid)
        if info is None:
            raise Exception(f"{cid} not in game_config['controllers']")
        cls = get_base_cls_by_name(info['class'])
        controller: StateController = cls(cid=cid, config=info['config'])
        return controller

    def create_object_from_config_id(self, config_id):
        info = self.config['objects'].get(config_id)
        if info is None:
            raise Exception(
                f"{config_id} not defined in game_config['objects']")
        cls = get_base_cls_by_name(info['class'])
        obj: PhysicalObject = cls(config_id=config_id, config=info['config'])
        gamectx.object_manager.add(obj)
        return obj

    def get_config_from_config_id(self, config_id):
        return self.config['objects'].get(config_id).get('config')

    def step_duration(self):
        if self._step_duration is not None:
            return self._step_duration
        """
        Step size in ticks
        """
        tick_rate = gamectx.tick_rate
        if not tick_rate or tick_rate == 0:
            tick_rate = 1
        self._step_duration = max(1, tick_rate * self._step_duration_factor)
        return self._step_duration

    def get_asset_bundle(self):
        return self.asset_bundle

    def request_reset(self):
        for player in gamectx.player_manager.players_map.values():
            player.set_data_value("reset_required", True)

    def reset_required(self):
        for player in gamectx.player_manager.players_map.values():
            if not player.get_data_value("reset_required", True):
                return False
        return True

    # **********************************
    # GAME LOAD
    # **********************************
    def load(self, is_client_only=False):
        self.loaded = False
        if not is_client_only:
            if self.config.get("load_from_file") and self.config.get('load_file') is not None:
                logging.info("Loading from save")
                self.gamemap.loaded = True
                self.gamemap.initialize((0, 0))
                self.load_from_save(self.config.get('load_file'))
            else:
                logging.info("Loading from new game")
                self.gamemap.initialize((0, 0))

            self.load_controllers()

        gamectx.physics_engine.set_collision_callback(
            default_collision_callback)
        self.loaded = True

    def reset(self):
        if not self.loaded:
            self.load()

        gamectx.remove_all_events()
        self.reset_controllers()

    #####################
    # RL AGENT METHODS
    #####################
    # TODO: get from player to object
    def get_observation_space(self):
        x_dim = (self.vision_radius * 2 + 1)
        y_dim = x_dim
        chans = self.max_obs_id + self.max_tags
        return spaces.Box(low=0, high=1, shape=(x_dim, y_dim, chans))

    # TODO: get from player to object
    def get_action_space(self):
        return spaces.Discrete(len(self.agent_key_list))

    def get_observation(self, obj: GObject):
        return obj.get_observation()

    def get_step_info(self, player: Player, include_state_observation=True) -> Tuple[np.ndarray, float, bool, Dict[str, Any], bool]:
        observation = None
        done = False
        reward = 0
        info = {}
        if player is not None:
            if not player.get_data_value("allow_obs", False):
                return None, None, None, None, True

            obj_id = player.get_object_id()
            obj: AnimateObject = gamectx.object_manager.get_by_id(obj_id)
            if obj is None:
                return None, reward, done, info, True
            if include_state_observation:
                observation = self.get_observation(obj)
            else:
                observation = None
            done = player.get_data_value("reset_required", False)
            if done:
                player.set_data_value("allow_obs", False)
            reward = obj.reward
            obj.reward = 0
        else:
            info['msg'] = "no player found"
        return observation, reward, done, info, False

    # **********************************
    # NEW PLAYER
    # **********************************
    def new_player(self, client_id, player_id=None, player_type="default", is_human=False, name=None) -> Player:
        if player_id is None:
            for pid, player in gamectx.player_manager.players_map.items():
                if player.client_id == client_id:
                    player_id = pid
        if player_id is None:
            player_id = gen_id()

        player = gamectx.player_manager.get_player(player_id)

        if player is None:
            if player_type == "admin":
                logging.info("Adding admin")
                size_in_pixels = coord_to_vec(self.gamemap.get_size())
                max_len = max(size_in_pixels.x, size_in_pixels.y)

                cam_distance = max_len
                center = coord_to_vec(self.gamemap.get_center())
                player = Player(
                    client_id=client_id,
                    uid=player_id,
                    camera=Camera(
                        distance=cam_distance,
                        view_type=1,
                        center=center),
                    player_type=player_type,
                    is_human=is_human,
                    name=name)
                gamectx.add_player(player)

            else:
                cam_distance = self.default_camera_distance
                player = Player(
                    client_id=client_id,
                    uid=player_id,
                    camera=Camera(distance=cam_distance, view_type=1),
                    player_type=player_type,
                    is_human=is_human,
                    name=name)
                gamectx.add_player(player)
                for controller_id in self.active_controllers:
                    logging.info(
                        f"Adding player to controller: {controller_id}")
                    self.get_controller_by_id(controller_id).join(player)

            # self.get_controller_by_id("pspawn").spawn_player(player,reset=True)
        return player

    def load_from_save(self, savename):
        full_save_path = os.path.join(
            self.config['save_path'], f"{savename}.json")
        print(f"Loading from save file {full_save_path}")
        with open(full_save_path, "r") as f:
            snapshot = json.load(f, cls=StateDecoder)
        gamectx.remove_all_events()
        gamectx.object_manager.clear_objects()
        gamectx.load_snapshot(snapshot)
        for oid, o in gamectx.object_manager.get_objects().items():
            o.sync_position()

    ########################
    # GET INPUT
    ########################
    def process_position_change_event(self, e: PositionChangeEvent):
        if not e.is_player_obj:
            return

        old_scoord = self.gamemap.get_sector_coord_from_pos(e.old_pos)
        new_scoord = self.gamemap.get_sector_coord_from_pos(e.new_pos)
        if old_scoord != new_scoord:
            self.gamemap.load_sectors_near_coord(new_scoord)

    def process_admin_command_event(self, admin_event: AdminCommandEvent):
        value = admin_event.value
        error_message = None
        if value == "reset":
            self.request_reset()
            self.log_console(f"RUNNING COMMAND: {value}")
        elif value.startswith("input_mode"):
            args = value.split(" ")
            if len(args) > 1:
                input_mode_name = args[1]
                if input_mode_name.lower() in set("play", "console", "admin"):
                    p = gamectx.player_manager.get_player(
                        admin_event.player_id)
                    p.set_data_value("INPUT_MODE", input_mode_name.upper())
                else:
                    error_message = f"invalid input mode {input_mode_name}"
            else:
                error_message = "missing argument"

        elif value.startswith("spawn"):
            command_parts = value.split(" ")
            p = gamectx.player_manager.get_player(admin_event.player_id)
            o = gamectx.object_manager.get_by_id(p.get_object_id())
            pos = o.get_view_position()
            spawn_pos = self.get_near_location(pos)
            if spawn_pos is not None:
                config_id = command_parts[1]
                obj = self.create_object_from_config_id(config_id)
                obj.spawn(spawn_pos)
        elif value.startswith("save"):
            command_parts = value.split(" ")
            if len(command_parts) == 2:
                savename = command_parts[1]
            else:
                savename = "default"
            snapshot = gamectx.create_full_snapshot()
            timestamp = snapshot['timestamp']

            full_save_path = os.path.join(
                self.config['save_path'], f"{savename}.json")
            self.log_console(f"Saving to {full_save_path}")
            with open(full_save_path, "w") as f:
                json.dump(snapshot, f, cls=StateEncoder)

        elif value.startswith("load"):
            command_parts = value.split(" ")
            if len(command_parts) == 2:
                savename = command_parts[1]
            else:
                savename = "default"
            self.load_from_save(savename)
            # full_save_path = os.path.join(self.config['save_path'],f"{savename}.json")
            # with open(full_save_path,"r") as f:
            #     snapshot = json.load(f,cls=StateDecoder)
            # gamectx.remove_all_events()
            # gamectx.object_manager.clear_objects()
            # gamectx.load_snapshot(snapshot)
            # for oid, o in gamectx.object_manager.get_objects().items():
            #     o.sync_position()

            # clock.set_start_time(time.time() - snapshot['gametime'] )

        elif value.startswith("run"):
            command_parts = value.split(" ")
            script_name = command_parts[1]
            try:
                exec(open(os.path.join(self.config.get("mod_path"), script_name)).read())
            except Exception as e:
                self.log_console(f"Error running script: {e}")

        elif value.startswith("controller"):
            command_parts = value.split(" ")
            action = command_parts[1]
            controller = command_parts[1]
            if action == "add":
                pass
            p = gamectx.player_manager.get_player(admin_event.player_id)
            o = gamectx.object_manager.get_by_id(p.get_object_id())
            pos = o.get_view_position()
            spawn_pos = self.get_near_location(pos)
            if spawn_pos is not None:
                config_id = command_parts[1]
                obj = self.create_object_from_config_id(config_id)
                obj.spawn(spawn_pos)
        else:
            error_message = "Invalid or unknown"

        if error_message is not None:
            self.log_console(
                f"Command failed :\"{value}\"  Message:{error_message}")

        events = []
        return events

    def camera_update(self, player: Player, input_event: InputEvent):
        keydown = input_event.input_data['keydown']
        events = []
        direction = Vector2(0, 0)
        if 23 in keydown:
            # W UP
            direction = Vector2(0, -1)
            new_angle = 180
        if 19 in keydown:
            # S DOWN
            direction = Vector2(0, 1)
            new_angle = 0
        if 4 in keydown:
            # D RIGHT
            direction = Vector2(1, 0)
            new_angle = 270
        if 1 in keydown:
            # A LEFT
            direction = Vector2(-1, 0)
            new_angle = 90

        camera = player.get_camera()
        camera.position_offset -= direction * 5
        camera.angle = new_angle

        return events

    # def process_admin_input(self,input_event):

    def process_input_event(self, input_event: InputEvent):
        events = []
        player = gamectx.player_manager.get_player(input_event.player_id)
        if player is None:
            return []

        keydown = input_event.input_data['keydown']
        # keyup = set(input_event.input_data['keyup'])

        # TODO: only check for admin client events if player is human
        mode = player.get_data_value("INPUT_MODE", "PLAY")
        # Client Events
        if 27 in keydown:
            logging.info("QUITTING")
            if mode == "PLAY":
                gamectx.change_game_state("STOPPED")
            else:
                player.set_data_value("INPUT_MODE", "PLAY")
            return events

        # ZOOM
        if 32 in keydown:
            events.append(ViewEvent(player.get_id(), 50, Vector2(0, 0)))

        if 31 in keydown:
            events.append(ViewEvent(player.get_id(), -50, Vector2(0, 0)))

        if mode == "CONSOLE":
            return events
        elif mode == "ADMIN":
            # if 28 in keydown:
            #     print(input_event.input_data['mouse_pos'])
            #     obj = self.create_object_from_config_id("tree1")
            #     obj.spawn(Vector2(input_event.input_data['mouse_pos']))

            events.extend(self.camera_update(player, input_event))
            return events

        # minus
        if 80 in keydown:
            self._step_duration_factor = max(
                0, self._step_duration_factor - 0.01)
            self._step_duration = None

        # equals/plus
        if 81 in keydown:
            self._step_duration_factor = self._step_duration_factor + 0.01
            self._step_duration = None

        if 13 in keydown:
            logging.info("ADMIN")
            player.set_data_value("INPUT_MODE", "ADMIN")

        if 99 in keydown:
            logging.info("CONSOLE")
            player.set_data_value("INPUT_MODE", "CONSOLE")

        # If client, dont' process any other events
        if gamectx.config.client_only_mode:
            return events

        obj: AnimateObject = gamectx.object_manager.get_by_id(
            player.get_object_id())

        if obj is None or not obj.enabled:
            return events
        elif player.get_data_value("reset_required", False):
            print("Episode is over. Reset required")
            return events
        elif not player.get_data_value("allow_input", False):
            return events
        elif mode == "PLAY":
            # Process input by object
            obj.assign_input_event(input_event)

        return events

    # Messaging/Loggin Functions
    def message_player(self, p: Player, message, duration=0, clear_messages=False):

        delay = duration*self.step_duration()
        if clear_messages:
            msgs = []
        else:
            msgs = p.get_data_value("messages", [])
        msgs.append((int(delay) + clock.get_ticks(), message))
        p.set_data_value("messages", msgs)

    def log_console(self, message, player_id=None):
        for pid, p in gamectx.player_manager.players_map.items():
            if p is not None and (player_id is None or pid == player_id):
                log = p.get_data_value("log", [])
                log.append(f"{clock.get_ticks()}: {message}")
                p.set_data_value("log", log)

    # Main UPDATE Function
    def update(self):
        objs = list(gamectx.object_manager.get_objects().values())
        for o in objs:
            if not o.enabled or o.sleeping:
                continue
            o.update()
        self.update_controllers()

        if self.debug_memory:
            cur_tick = clock.get_ticks()
            sz = getsize(gamectx.object_manager)
            if sz > self.max_size.get("om", (0, 0))[0]:
                self.max_size['om'] = (sz, cur_tick)

            sz = getsize(gamectx.event_manager)
            if sz > self.max_size.get("em", (0, 0))[0]:
                self.max_size['em'] = (sz, cur_tick)

            sz = getsize(gamectx.physics_engine)
            if sz > self.max_size.get("ph", (0, 0))[0]:
                self.max_size['ph'] = (sz, cur_tick)

            sz = getsize(self.gamemap)
            if sz > self.max_size.get("map", (0, 0))[0]:
                self.max_size['map'] = (sz, cur_tick)

            sz = getsize(self)
            if sz > self.max_size.get("cnt", (0, 0))[0]:
                self.max_size['cnt'] = (sz, cur_tick)

            sz = len(gamectx.object_manager.objects)
            if sz > self.max_size.get("ob_count", (0, 0))[0]:
                self.max_size['ob_count'] = (sz, cur_tick)

            if (time.time() - self.console_report_last) > self.console_report_freq_sec:

                logging.info("--")
                for k, v in self.max_size.items():
                    logging.info(f"{k}:".ljust(
                        10) + f"at:{v[1]}".rjust(15) + f"v:{v[0]}".rjust(15))
                self.console_report_last = time.time()

    def draw_hud(self, player, obj, renderer, display_props):
        bar_height = round(renderer.resolution[1] / 40)
        bar_width_max = round(renderer.resolution[0] / 6)
        bar_padding = round(renderer.resolution[1] / 200)
        info_x = bar_width_max + bar_padding * 3
        info_y = renderer.resolution[1] - bar_height * 4

        tlheight = renderer.resolution[1] - bar_height - bar_padding
        bar_width = round(obj.stamina/obj.stamina_max * bar_width_max)

        # Stamina
        renderer.draw_rectangle(bar_padding, tlheight,
                                bar_width, bar_height, color=(0, 0, 200))

        # Energy
        tlheight = tlheight - bar_height - bar_padding
        bar_width = round(obj.energy/obj.energy_max * bar_width_max)
        renderer.draw_rectangle(bar_padding, tlheight,
                                bar_width, bar_height, color=(200, 200, 0))

        # Health
        tlheight = tlheight - bar_height - bar_padding
        bar_width = round(obj.health/obj.health_max * bar_width_max)
        renderer.draw_rectangle(
            bar_padding,
            tlheight,
            bar_width,
            bar_height,
            color=(200, 0, 0))

        renderer.draw_rectangle(
            bar_width_max + bar_padding,
            tlheight,
            bar_padding/2,
            renderer.resolution[1] - tlheight - bar_padding,
            color=(200, 200, 200))

        # TODO: Need Hud version for Agents
        if player.is_human:
            hud_lines = []
            hud_lines.append(f"Total Reward: {obj.total_reward}")
            hud_lines.append(f"Inventory: {obj.get_inventory().as_string()}")
            hud_lines.append(f"Craft Menu: {obj.get_craftmenu().as_string()}")
            hud_lines.extend([self.get_controller_by_id(controller_id).get_player_object_hud_info(
                obj) for controller_id in self.active_controllers])

            renderer.render_text(hud_lines, x=info_x, y=info_y,
                                 fsize=display_props['fsize'], use_view_port_surface=True)

        # Show Messages
        message_output = []
        remaining_messages = []
        messages = player.get_data_value("messages", [])
        for expires_key, msg in messages:
            if clock.get_ticks() < expires_key:
                remaining_messages.append((expires_key, msg))
                message_output.append(f"{msg}")

        if len(remaining_messages) > 0:
            player.set_data_value("messages", remaining_messages[-3:])
            renderer.render_text(
                message_output,
                x=display_props['pad'],
                y=round(renderer.resolution[1]/2),
                fsize=display_props['msg_fsize'],
                spacing=display_props['msg_fspacing'],
                use_view_port_surface=True)

    def draw_console(self, player, obj, renderer, display_props):
        input_mode = player.get_data_value("INPUT_MODE", "")
        if not input_mode == "CONSOLE" and not renderer.config.show_console:
            return

        lines = []
        lines.append("INPUT_MODE:{}".format(input_mode))
        lines.append("Step Duration Factor (larger = slower) {}".format(
            self._step_duration_factor))
        lines.append("FPS:{}".format(round(renderer.fps_clock.get_fps())))

        if renderer.log_info is not None:
            lines.append(renderer.log_info)
        log = player.get_data_value("log", [])
        if len(log) > 5:
            log = log[-5:]
            player.set_data_value("log", log)
        elif len(log) == 0:
            log.append(" ")
        lines.append("")
        lines.append("--------- LOG -----------")
        lines.extend(log)
        if input_mode == "CONSOLE":
            lines.append("")
            lines.append("$> {}".format(
                player.get_data_value("CONSOLE_TEXT", "_")))
            lines.append("")
            lines.append("--------- HELP ---------")
            lines.append(" ")
            lines.append("  CONTROLS:")
            lines.append(
                "    console/show help   : ` or h (ESC to return to PLAY MODE")
            lines.append(
                "    camera mode         : m (ESC to return to PLAY MODE")
            lines.append(
                "    move                : w,s,d,a or UP,DOWN,LEFT,RIGHT")
            lines.append("    push                : g")
            lines.append("    grab                : e")
            lines.append("    item  - menu select : z,c")
            lines.append("    item  - use         : r")
            lines.append("    craft - menu select : v,b")
            lines.append("    craft - create      : q")
            lines.append(
                "    game step duration   : \"-\" (faster)/\"=\" (slower) ")
            lines.append("")
            lines.append("  CONSOLE COMMANDS:")
            lines.append("    reset             : Reset Game")
            lines.append("    spawn <object_id> : Spawn Object")
        renderer.render_text(
            lines,
            x=display_props['cpad'],
            y=display_props['cpad'],
            fsize=display_props['fsize'],
            # spacing=display_props['fsize'] +2,
            use_view_port_surface=True)

    # Function to manually draw to frame
    def post_process_frame(self, player: Player, renderer: Renderer):
        if player is None:
            return

        pad = round(renderer.resolution[0]/30)
        cpad = round(pad/4)
        fsize = round(renderer.resolution[1]/50)
        msg_fsize = round(renderer.resolution[1]/20)
        msg_fspacing = msg_fsize

        display_props = {
            'pad': pad,
            'cpad': cpad,
            'fsize': fsize,
            'msg_fsize': msg_fsize,
            'msg_fspacing': msg_fspacing,
        }

        obj: AnimateObject = gamectx.object_manager.get_by_id(
            player.get_object_id())

        self.draw_console(
            player=player,
            obj=obj,
            renderer=renderer,
            display_props=display_props
        )

        # HUD
        if obj is not None:
            # TODO: make HUD optional/ configurable
            self.draw_hud(player, obj, renderer, display_props)

        for controller_id in self.active_controllers:
            self.get_controller_by_id(controller_id).post_process_frame(
                player, renderer=renderer)
