import math
from simpleland.contentbundles.survival_config import CONTENT_ID
from simpleland.contentbundles.survival_behaviors import FleeAnimals, FollowAnimals, PlayingTag
from simpleland import physics_engine
import random
from collections import defaultdict
from typing import Dict, Any, Tuple

from ..camera import Camera
from ..event import (AdminCommandEvent, DelayedEvent, Event, InputEvent, ObjectEvent,ViewEvent,
                     PeriodicEvent, PositionChangeEvent, SoundEvent)
from ..object import GObject

from ..player import Player
from ..renderer import Renderer
from ..utils import gen_id, getsize, getsizewl

from ..asset_bundle import AssetBundle
from ..common import COLLISION_TYPE
import numpy as np
from ..clock import clock
from typing import List,Dict,Any
from ..event import InputEvent, Event, DelayedEvent
from .. import gamectx
from ..common import  Vector2, get_base_cls_by_name
import pygame
from ..clock import clock
from gym import spaces
import sys
import math

import pkg_resources
import json
import os
from .survival_assets import load_asset_bundle
from .survival_map import GameMap
from .survival_controllers import FoodCollectController,ObjectCollisionController, PlayerSpawnController, TagController,InfectionController
from .survival_objects import *
from .survival_utils import int_map_to_onehot_map,ints_to_multi_hot, vec_to_coord
import time

############################
# COLLISION HANDLING
############################
def default_collision_callback(obj1: PhysicalObject, obj2: PhysicalObject):
    return obj1.collision_with(obj2)

class GameContent(SurvivalContent):

    def __init__(self, config):
        super().__init__(config)
        self.asset_bundle = load_asset_bundle(self.config['asset_bundle'])
        self.active_controllers:List[str] = self.config['active_controllers']
        self.map_config = self.config['maps'][self.config['start_map']]
        # TODO, load from game config
        self.default_camera_distance = config['default_camera_distance']
        self.tile_size = self.config['tile_size']

        # Effect Vector Lookup
        self.effect_int_map = {config_id:value.get('obs_id',i) for i, (config_id, value) in enumerate(self.config['effects'].items())}
        self.max_effect_id = len(self.effect_int_map)
        self.effect_vec_map = int_map_to_onehot_map(self.effect_int_map)

        self.tag_list = self.config['tag_list']
        self.max_tags = 10 #Static for now to keep observation space same between configuration, #len(self.tag_list)
        self.tag_int_map = { tag:i for i,tag in enumerate(self.tag_list)}

        # Object Vector Lookup
        self.obj_int_map = {config_id:value.get('obs_id',i) for i, (config_id, value) in enumerate(self.config['objects'].items())}
        self.max_obs_id = len(self.obj_int_map)
        self.obj_vec_map = int_map_to_onehot_map(self.obj_int_map)   
        self.vision_radius = 2 # Vision info should be moved to objects, possibly predifined

        self.player_count = 0
        self.keymap = [23, 19, 4, 1, 5, 6, 18,0, 26,3, 24]

        self.loaded = False
        self.gamemap = GameMap(
            path = self.config.get("game_config_root"),
            map_config=self.map_config,
            tile_size = self.tile_size,
            seed = self.config.get("map_seed",123))
        
        
        # self._default_speed_factor_multiplier = self.config['default_speed_factor_multiplier']
        self._step_duration_factor = self.config['step_duration_factor']
        
        self._step_duration = None
        self.call_counter = 0

        # All loadable classes should be registered
        self.classes = [Action,
            Effect, Human, Monster, Inventory,
            Food,Tool, Animal, Tree, Rock, 
            Liquid, PhysicalObject, Camera,
            TagController, 
            PlayerSpawnController,
            ObjectCollisionController,
            FoodCollectController,InfectionController]

        for cls in self.classes:
            gamectx.register_base_class(cls)
        self.obj_class_map= {cls.__name__: cls for cls  in self.classes}
        self.controllers:Dict[str,StateController] = {}

        self.behavior_classes = [FleeAnimals,FollowAnimals,PlayingTag]
        self.bevavior_class_map:Dict[str,Behavior] = {cls.__name__: cls for cls  in self.behavior_classes}

        # Memory Debugging
        self.debug_memory = False
        self.console_report_freq_sec = 4
        self.console_report_last = 0
        self.max_size = {}

    def create_tags_vec(self,tags):
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

    def get_effect_sprites(self,config_id):
        return self.config['effects'].get(config_id,{}).get('model',{})

    def get_object_sprites(self,config_id):
        return self.config['objects'].get(config_id,{}).get('model',{})
    
    def get_object_sounds(self,config_id):
        return self.config['objects'].get(config_id,{}).get('sounds',{})

    def get_available_location(self,max_tries = 200):
        point= None
        tries = 0
        while point is None or tries > max_tries:
            coord = self.gamemap.random_coords(num=1)[0]
            objs = gamectx.physics_engine.space.get_objs_at(coord)
            if len(objs) == 0:
                point = coord_to_vec(coord)
        return point

    def get_near_location(self,point):
        coord = vec_to_coord(point)

        neighs = self.gamemap.get_neigh_coords(coord)
        point = None
        for neigh in neighs:
            objs = gamectx.physics_engine.space.get_objs_at(neigh)
            if len(objs) == 0:
                point = coord_to_vec(neigh)
        return point

    # Factory Methods
    def create_behavior(self,name,*args,**kwargs):
        return self.bevavior_class_map[name](*args,**kwargs)

    def create_controller(self,cid):
        info = self.config['controllers'].get(cid)
        if info is None:
            raise Exception(f"{cid} not in game_config['controllers']")
        cls = get_base_cls_by_name(info['class'])
        controller:StateController = cls(cid=cid,config=info['config'])
        return controller

    def create_object_from_config_id(self,config_id):
        info = self.config['objects'].get(config_id)
        if info is None:
            raise Exception(f"{config_id} not defined in game_config['objects']")
        cls = get_base_cls_by_name(info['class'])
        obj:PhysicalObject = cls(config_id=config_id,config=info['config'])
        return obj

    def get_config_from_config_id(self,config_id):
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
        self._step_duration = max(1,tick_rate * self._step_duration_factor)
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
            self.gamemap.initialize((0,0))
            self.load_controllers()

        gamectx.physics_engine.set_collision_callback(
            default_collision_callback,
            COLLISION_TYPE['default'],
            COLLISION_TYPE['default'])
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
        return spaces.Discrete(len(self.keymap))

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
                observation =  None
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
    def new_player(self, client_id, player_id=None, player_type=0, is_human=False) -> Player:
        if player_id is None:
            player_id = gen_id()
        player = gamectx.player_manager.get_player(player_id)
        if player is None:
            cam_distance = self.default_camera_distance
            player = Player(
                client_id=client_id,
                uid=player_id,
                camera=Camera(distance=cam_distance,view_type=1),
                player_type=player_type,
                is_human = is_human)
            gamectx.add_player(player)
            for controller_id in self.active_controllers:
                logging.info(f"Adding player to {controller_id}")
                self.get_controller_by_id(controller_id).join(player)
            # self.get_controller_by_id("pspawn").spawn_player(player,reset=True)
        return player

    ########################
    # GET INPUT
    ########################
    def process_position_change_event(self,e:PositionChangeEvent):
        if not e.is_player_obj:
            return            
        
        old_scoord = self.gamemap.get_sector_coord_from_pos(e.old_pos)
        new_scoord = self.gamemap.get_sector_coord_from_pos(e.new_pos)
        if old_scoord != new_scoord:
            self.gamemap.load_sectors_near_coord(new_scoord)

    def process_admin_command_event(self,admin_event:AdminCommandEvent):
        value = admin_event.value
        error_message = None
        if value == "reset":
            self.request_reset()
            self.log_console(f"RUNNING COMMAND: {value}")
        elif value.startswith("input_mode"):
            args = value.split(" ")
            if len(args) >1:
                input_mode_name = args[1]
                if input_mode_name.lower() in set("play","console","admin"):
                    p = gamectx.player_manager.get_player(admin_event.player_id)
                    p.set_data_value("INPUT_MODE", input_mode_name.upper())
                else:
                    error_message=f"invalid input mode {input_mode_name}"
            else:
                error_message="missing argument"

        elif value.startswith("spawn"):
            command_parts = value.split(" ")
            p = gamectx.player_manager.get_player(admin_event.player_id)
            o = gamectx.object_manager.get_by_id(p.get_object_id())
            pos = o.get_view_position()
            print(pos)
            spawn_pos = self.get_near_location(pos)
            if spawn_pos is not None:
                config_id = command_parts[1]
                obj = self.create_object_from_config_id(config_id)
                obj.spawn(spawn_pos)
        elif value.startswith("controller"):
            command_parts = value.split(" ")
            action =command_parts[1]
            controller =command_parts[1]
            if action == "add":
                pass
            p = gamectx.player_manager.get_player(admin_event.player_id)
            o = gamectx.object_manager.get_by_id(p.get_object_id())
            pos = o.get_view_position()
            print(pos)
            spawn_pos = self.get_near_location(pos)
            if spawn_pos is not None:
                config_id = command_parts[1]
                obj = self.create_object_from_config_id(config_id)
                obj.spawn(spawn_pos)
        else:
            error_message = "Invalid or unknown"
        
        self.log_console(f"Command failed :\"{value}\"  Message:{error_message}")

        events = []
        return events

    def camera_update(self,player:Player,input_event:InputEvent):
        keydown = input_event.input_data['keydown']
        events = []
        direction = Vector2(0,0)
        if 23 in keydown:
            # W UP
            direction = Vector2(0, -1)
            angle_update = 180
        if 19 in keydown:
            # S DOWN
            direction = Vector2(0, 1)
            angle_update = 0
        if 4 in keydown:
            # D RIGHT
            direction = Vector2(1, 0)
            angle_update = 270
        if 1 in keydown:
            # A LEFT
            direction = Vector2(-1, 0)
            angle_update = 90
        
        camera = player.get_camera()
        camera.position_offset -= direction

        return events


    def process_input_event(self, input_event:InputEvent):
        events= []
        player = gamectx.player_manager.get_player(input_event.player_id)
        if player is None:
            return []
        if not player.get_data_value("allow_input",False):
            return []
        # keydown = input_event.input_data['pressed']
        keydown = input_event.input_data['keydown']
        # keyup = set(input_event.input_data['keyup'])

        # TODO: only check for admin client events if player is human
        mode = player.get_data_value("INPUT_MODE","PLAY")
        # Client Events
        if 27 in keydown:
            logging.info("QUITTING")
            if mode == "PLAY":
                gamectx.change_game_state("STOPPED")
            else:
                player.set_data_value("INPUT_MODE","PLAY")
            return events
        # ZOOM
        if 32 in keydown:
            events.append(ViewEvent(player.get_id(), 50, Vector2(0,0)))
            
        if 31 in keydown:
            events.append(ViewEvent(player.get_id(), -50, Vector2(0,0)))

        if mode == "CONSOLE":
            return events
        elif mode == "ADMIN":
            events.extend(self.camera_update(player,input_event))
            return events

        # minus        
        if 80 in keydown:
            self._step_duration_factor = max(0, self._step_duration_factor - 0.01)
            self._step_duration = None

        # equals/plus
        if 81 in keydown:
            self._step_duration_factor = self._step_duration_factor + 0.01
            self._step_duration = None

        if 13 in keydown:
            logging.info("ADMIN")
            player.set_data_value("INPUT_MODE","ADMIN")

        if 99 in keydown:
            logging.info("CONSOLE")
            player.set_data_value("INPUT_MODE","CONSOLE")
            
        # If client, dont' process any other events
        if gamectx.config.client_only_mode:
            return events

        obj:AnimateObject = gamectx.object_manager.get_by_id(player.get_object_id())

        if obj is None or not obj.enabled:
            return events
        
        elif player.get_data_value("reset_required",False):
            print("Episode is over. Reset required")
            return events

        player = gamectx.player_manager.get_player(input_event.player_id)
        
        if player is None or not player.get_data_value("allow_input",False) or player.get_data_value("reset_required",False):
            return events

        if mode == "PLAY":
            obj.assign_input_event(input_event)     

        return events

    # Messaging/Loggin Functions
    def message_player(self,p:Player,message, duration=0):

        delay = duration*self.step_duration()
        msgs = p.get_data_value("messages",[])
        msgs.append((int(delay) + clock.get_ticks(),message))
        p.set_data_value("messages",msgs)

    def log_console(self,message,player_id=None):
        for pid,p in gamectx.player_manager.players_map.items():
            if p is not None and (player_id is None or pid == player_id):
                log = p.get_data_value("log",[])
                log.append(f"{clock.get_ticks()}: {message}")
                p.set_data_value("log",log)

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
            if sz > self.max_size.get("om",(0,0))[0]:
                self.max_size['om'] = (sz,cur_tick)

            sz = getsize(gamectx.event_manager)  
            if sz > self.max_size.get("em",(0,0))[0]:
                self.max_size['em'] = (sz,cur_tick)

            sz = getsize(gamectx.physics_engine)  
            if sz > self.max_size.get("ph",(0,0))[0]:
                self.max_size['ph'] = (sz,cur_tick)

            sz = getsize(self.gamemap)  
            if sz > self.max_size.get("map",(0,0))[0]:
                self.max_size['map'] = (sz,cur_tick)

            sz = getsize(self)  
            if sz > self.max_size.get("cnt",(0,0))[0]:
                self.max_size['cnt'] = (sz,cur_tick)

            sz = len(gamectx.object_manager.objects)
            if sz > self.max_size.get("ob_count",(0,0))[0]:
                self.max_size['ob_count'] = (sz,cur_tick)

            if (time.time() - self.console_report_last) > self.console_report_freq_sec:

                logging.info("--")
                for k,v in self.max_size.items():
                    logging.info(f"{k}:".ljust(10)+ f"at:{v[1]}".rjust(15) +f"v:{v[0]}".rjust(15))
                self.console_report_last = time.time()

    # Function to manually draw to frame
    def post_process_frame(self, player: Player, renderer: Renderer):
        if renderer.config.disable_hud:
            return
        pad = round(renderer.resolution[0]/30)
        cpad = round(pad/4)
        if player is not None and player.player_type == 0:
            input_mode = player.get_data_value("INPUT_MODE", "")
            
            lines = []
            lines.append("Lives Used: {}".format(player.get_data_value("lives_used", 0)))
            lines.append("INPUT_MODE:{}".format(input_mode))
            lines.append("Step Duration Factor (larger = slower) {}".format(self._step_duration_factor))

            obj:AnimateObject = gamectx.object_manager.get_by_id(player.get_object_id())
            obj_health = 0
            show_console = input_mode == "CONSOLE" or renderer.config.show_console
            #TODO: instead render as part of hud via infobox
            if obj is not None:
                obj_health = obj.health
                lines.append(f"Total Reward: {obj.total_reward}")
                lines.append(f"Inventory: {obj.get_inventory().as_string()}")
                lines.append(f"Craft Menu: {obj.get_craftmenu().as_string()}")

                # TODO: make HUD optional/ configurable
                bar_height = round(renderer.resolution[1] /40)
                bar_width_max = round(renderer.resolution[0] /6)
                bar_padding = round(renderer.resolution[1] /200)

                tlheight = renderer.resolution[1] - bar_height - bar_padding
                bar_width = round(obj.stamina/obj.stamina_max * bar_width_max)

                # Stamina
                renderer.draw_rectangle(bar_padding,tlheight, bar_width,bar_height, color=(0,0,200))

                # Energy
                tlheight = tlheight - bar_height - bar_padding
                bar_width = round(obj.energy/obj.energy_max * bar_width_max)
                renderer.draw_rectangle(bar_padding,tlheight, bar_width,bar_height, color=(200,200,0))

                # Health
                tlheight = tlheight - bar_height - bar_padding
                bar_width = round(obj.health/obj.health_max * bar_width_max)
                renderer.draw_rectangle(
                    bar_padding,
                    tlheight, 
                    bar_width,
                    bar_height, 
                    color=(200,0,0))

                renderer.draw_rectangle(
                    bar_width_max + bar_padding,
                    tlheight, 
                    bar_padding/2,
                    renderer.resolution[1] - tlheight - bar_padding, 
                    color=(200,200,200))
            
            if show_console:
                lines.append("FPS:{}".format(round(renderer.fps_clock.get_fps())))
                if renderer.log_info is not None:
                    lines.append(renderer.log_info)
                log = player.get_data_value("log",[])
                if len(log) > 5:
                    log = log[-5:]
                    player.set_data_value("log",log)
                lines.append("")
                lines.append("--------- LOG -----------")
                lines.extend(log)
                if input_mode == "CONSOLE":
                    lines.append("$> {}".format(player.get_data_value("CONSOLE_TEXT", "_")))
                    lines.append("")
                    lines.append("--------- HELP ---------")
                    lines.append(" ")
                    lines.append("  CONTROLS:")
                    lines.append("    console/show help   : ` or h (ESC to return to PLAY MODE")
                    lines.append("    camera mode         : m (ESC to return to PLAY MODE")
                    lines.append("    move                : w,s,d,a or UP,DOWN,LEFT,RIGHT")
                    lines.append("    push                : g")
                    lines.append("    grab                : e")
                    lines.append("    item  - menu select : z,c")
                    lines.append("    item  - use         : r")
                    lines.append("    craft - menu select : v,b")
                    lines.append("    craft - create      : q")
                    lines.append("    game step duration   : \"-\" (faster)/\"=\" (slower) ")
                    lines.append("")
                    lines.append("  CONSOLE COMMANDS:")
                    lines.append("    reset             : Reset Game")
                    lines.append("    spawn <object_id> : Spawn Object")
                    # lines.append("    controller disable <controler_id>  : ")
                    
            renderer.render_to_console(lines, x=cpad, y=cpad)

            # Show Messages
            message_output=[]
            remaining_messages = []
            messages = player.get_data_value("messages",[])
            for expires_key, msg in messages:
                if clock.get_ticks()< expires_key:
                    remaining_messages.append((expires_key, msg))
                    message_output.append(f"{msg}")
            
            if len(remaining_messages)>0:
                player.set_data_value("messages",remaining_messages[-3:])
                renderer.render_to_console(message_output, x=pad, y=round(renderer.resolution[1]/2), fsize=50)
            
