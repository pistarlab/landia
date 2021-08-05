
from collections import defaultdict
from queue import Queue
from ..asset_bundle import AssetBundle
import math
import random
import logging

from typing import List, Dict, Any, Callable
from .. import gamectx
from ..clock import clock
from ..common import Vector2


from ..itemfactory import ShapeFactory
from ..object import GObject

from ..player import Player
from ..event import (DelayedEvent)
from .survival_utils import coord_to_vec
import numpy as np
from gym import spaces

from ..event import SoundEvent, InputEvent
from ..common import Base
from .survival_utils import angle_to_sprite_direction, ints_to_multi_hot
from .survival_common import SurvivalContent, StateController, Behavior, Action, Effect, Trigger

ACTION_IDLE = "idle"
ACTION_ATTACK = "attack"
ACTION_UNARMED_ATTACK = "unarmed_attack"
ACTION_USE = "use"
ACTION_GRAB = "grab"
ACTION_DROP = "drop"
ACTION_CRAFT = "craft"
ACTION_SPAWN = "spawn"
ACTION_MOVE = "move"
ACTION_PUSH = "push"
ACTION_EAT = "eat"
ACTION_WALK = "walk"
ACTION_JUMP = "jump"
ACTION_STUNNED = "stunned"

ACTION_LIST = [
    ACTION_IDLE,ACTION_ATTACK,
    ACTION_UNARMED_ATTACK,ACTION_USE,
    ACTION_GRAB,ACTION_DROP, ACTION_CRAFT,
    ACTION_SPAWN,ACTION_MOVE,ACTION_PUSH,ACTION_EAT,
    ACTION_WALK,ACTION_JUMP,ACTION_STUNNED]
ACTION_MAP = { a:i for i,a in enumerate(ACTION_LIST)}

type_tree = {
    'physical_object': None,
    'plant': 'physical_object',
    'tree': 'plant',
    'bush': 'plant',
    'animal': 'animate',
    'monster': 'animal',
    'human': 'animal',
    'deer': 'animal',
    'rock': 'physical_object',
}


def get_types(cur_type):
    all_types = set()
    done = False
    while not done:
        all_types.add(cur_type)
        new_type = type_tree.get(cur_type)
        if new_type is None:
            break
        else:
            cur_type = new_type
    return all_types

# TODO, need to avoid calling more than once if overridden by child
def invoke_triggers(func):
    def inner(self, *args, **kwargs):
        if func.__name__ in self.disabled_actions:
            return False
        cancel = self._invoke_triggers(func.__name__, *args, **kwargs)
        if cancel:
            return False
        else:
            return func(self, *args, **kwargs)
    return inner

# class MenuObject(Base):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

class PhysicalObject(GObject):

    def __init__(self, config_id="", config={}, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nattrs = {}
        self.config: Dict[str, Any] = config
        self.config_id = config_id
        self._l_content: SurvivalContent = gamectx.content

        self._l_triggers: Dict[str, Dict[str, Callable]] = {}
        self.input_events: List[InputEvent] = []

        self.type = "physical_object"
        self._types = None
        self.image_id_default = None
        self.health_max = self.config.get('health_max', 100)
        self.health = self.config.get('health_start', 100)
        self.show_info_bar = self.config.get('show_info_bar',False)
        self.permanent = self.config.get('permanent', False)
        self.remove_on_destroy = self.config.get('remove_on_destroy', True)
        self.pushable = self.config.get('pushable', False)
        self.collision_type = self.config.get('collision_type', 1)
        self.height = self.config.get('height', 1)
        self.tags = set(self.config.get('tags', []))
        self.tag_effect_map = self._l_content.config.get("tag_effect_map",{})
        self.collectable = self.config.get('collectable', False)
        self.count_max = self.config.get('count_max', 1)
        self.count = self.config.get('count', 1)


        self._l_model = None
        self._l_sounds = None

        self.default_action_type = self.config.get('default_action_type', ACTION_IDLE)
        self._action: Action = None
        self._action_queue = Queue()
        self._effects: Dict[str, Effect] = {}
        self.disabled_actions = set(self.config.get('disabled_actions', []))
        self.created_tick = clock.get_ticks()
        


        self.view_position = None

        self.default_action()
        self.disable()
        ShapeFactory.attach_rectangle(self, width=self._l_content.tile_size, height=self._l_content.tile_size)

    def assign_input_event(self, e: InputEvent):
        self.input_events.append(e)

    def process_input_events(self):
        for e in self.input_events:
            self.process_input_event(e)
        self.input_events = []

    def process_input_event(self, e):
        pass

    def _invoke_triggers(self, fn_name, *args, **kwargs):
        cancel = False
        triggers = self._l_triggers.get(fn_name)
        if triggers is not None:
            trigger: Trigger = None
            for trigger in triggers.values():
                if not trigger.func(self, *args, **kwargs):
                    cancel = True
        return cancel

    def add_trigger(self, fn_name, id, func):
        # to check if fn exists
        getattr(self, fn_name)
        trigger = Trigger(id, func)
        fn_triggers = self._l_triggers.get(fn_name, {})
        fn_triggers[id] = trigger
        self._l_triggers[fn_name] = fn_triggers

    def remove_trigger(self, fn_name, id):
        del self._l_triggers.get(fn_name)[id]

    def add_tag(self,tag):        
        self.tags.add(tag)
        if tag in self.tag_effect_map:
            self.add_effect(Effect(self.tag_effect_map.get(tag)))
        
    def remove_tag(self,tag):
        self.tags.discard(tag)
        if tag in self.tag_effect_map:
            self.remove_effect(self.tag_effect_map.get(tag))

    def add_effect(self, effect: Effect):
        self._effects[effect.config_id] = effect

    def remove_effect(self, config_id):
        if config_id in self._effects:
            del self._effects[config_id]


    def get_effect_sprites(self, effect_config_id):
        return self._l_content.get_effect_sprites(effect_config_id).get('default')

    def get_info_box(self):
        rows=[]

        health_info = {
            'name':"health",
            'type': 'bar',
            'label': 'Health: ',
            'value':self.health/self.health_max,                    
            'color':(255,0,0),
            'bg_color':(100,100,100)}
        tag_info = {
            'name': "tags",
            'label': 'Tags: ',
            'type' : 'block_list',
            'bg_color':(100,100,100),
            'value': [self._l_content.tag_int_map[tag] for tag in self.tags],
            "size": self._l_content.max_tags
        }
        action_info = {
            'name': "action_list",
            'label': 'Actions: ',
            'type' : 'block_list',
            'bg_color':(100,100,100),
            'value': [ACTION_MAP[self.get_action().type]],
            "size": len(ACTION_LIST)
        }
        action_name = {
            'name': "action_name",
            'type' : 'text',
            "value": self.get_action().type
        }

        rows.append(health_info)
        rows.append(tag_info)
        rows.append(action_info)
        rows.append(action_name)

        # TODO: Move to animate objects
        selected_item = self.get_inventory().get_selected()
        
        item_selected = {
            'name': "selected_item",
            'type' : 'icon',
            'label' : 'Item: ',
            'value': selected_item.get_default_image() if selected_item else None,
        }

        rows.append(item_selected)
        return rows

    def get_info_renderables(self):
        if not self.show_info_bar:
            return []
        return [{
            'type':'infobox',
            'padding':0.5,
            "value":self.get_info_box(),
            "scale": (0.5,.5)}]
        

    def get_effect_renderables(self):
        effects = dict(self.get_effects())
        renderables = []
        for name, effect in effects.items():
            if effect.is_expired():
                self.remove_effect(name)
                continue
            if effect.type == "sprite":
                sprites = self.get_effect_sprites(effect.config_id)
                cur_tick = clock.get_ticks()
                idx = cur_tick - effect.start_tick
                total_sprite_images = len(sprites)
                sprite_idx = int((idx/effect.ticks) * total_sprite_images) % total_sprite_images
                angle = effect.angle_step_size * idx
                renderables.append({'position': Vector2(0, 0), 'image_id': sprites[sprite_idx], 'angle': angle})
            
        return renderables

    def get_default_image(self):
        if self._l_model is None:
            self._l_model = self._l_content.get_object_sprites(self.config_id)
        return self._l_model.get('default', [self.image_id_default])

    def get_sprites(self, action: Action, angle):
        if self._l_model is None:
            self._l_model = self._l_content.get_object_sprites(self.config_id)

        action_sprite = self._l_model.get(action)
        if action_sprite is None:
            action_sprite = self._l_model.get(self.default_action_type)
            if action_sprite is None:
                return self._l_model.get('default', [self.image_id_default])
        direction = angle_to_sprite_direction(angle)
        return action_sprite[direction]

    def get_age(self):
        return clock.get_ticks() - self.created_tick

    def get_action_renderables(self, angle=0):
        action = self.get_action()
        sprites = self.get_sprites(action.type, self.angle)
        if sprites is None or len(sprites) == 0:
            return None
        cur_tick = clock.get_ticks()
        action_idx = (cur_tick - action.start_tick)
        if action_idx ==0:
            sprite_idx=0
        else:
            total_sprite_images = len(sprites)
            sprite_idx = int((action_idx/action.ticks) * total_sprite_images) % total_sprite_images
        return [{'position': Vector2(0, 0), 'image_id': sprites[sprite_idx], 'angle':0}]

    def get_renderables(self, angle=0, exclude_info=False):
        action_renderables = self.get_action_renderables(angle)
        effect_renderables = self.get_effect_renderables()
        info_renderables = []
        if not exclude_info:
            info_renderables = self.get_info_renderables()

        return action_renderables + effect_renderables + info_renderables

    def play_sound(self, name):
        if self._l_sounds is None:
            self._l_sounds = self._l_content.get_object_sounds(self.config_id)
        sound_id = self._l_sounds.get(name)
        if sound_id is not None:
            gamectx.add_event(SoundEvent(sound_id=sound_id,
                                         position=self.get_view_position()))
    
    @invoke_triggers
    def spawn(self, position):
        gamectx.add_object(self)
        self.set_image_offset(Vector2(0, 0))
        self._action = Action(ACTION_SPAWN, ticks=1, step_size=1, blocking=True)
        self.health = self.config.get('health_start', 100)
        self.show_info_bar = self.config.get('show_info_bar', False)
        self.created_tick = clock.get_ticks()
        self.enable()
        self.update_position(position=position, skip_collision_check=True)
        self.play_sound("spawn")

    def get_types(self):
        if self._types is None:
            self._types = get_types(self.type)
        return self._types

    def get_action(self) -> Action:
        if self._action.is_expired():
            if not self._action_queue.empty():
                # TODO: Updating act
                # ion until better solution is implemented
                self._action = self._action_queue.get()
                self._action.start_tick = clock.get_ticks()
                self._action.start_position = self.position
            else:
                self.default_action()
        return self._action

    def queue_action(self,action:Action):
        self._action_queue.put(action)

    def get_effects(self):
        return self._effects

    def default_action(self, blocking=False, continuous=True):
        ticks_in_action = 3 * self._l_content.step_duration()
        self._action = Action(
            type=ACTION_IDLE,
            ticks=ticks_in_action,
            step_size=self._l_content.tile_size/ticks_in_action,
            start_tick=clock.get_ticks(),
            blocking=blocking,
            continuous=continuous)

    @invoke_triggers
    def collision_with(self, obj2):

        if self.collision_type > 0 and self.collision_type == obj2.collision_type:
            ticks_in_action = 1 * self._l_content.step_duration()
            self._action = Action(
                type=ACTION_IDLE,
                ticks=ticks_in_action,
                step_size=self._l_content.tile_size/ticks_in_action,
                start_tick=clock.get_ticks(),
                blocking=True,
                continuous=False)
            return True
        else:
            return False

    def update_view_position(self):
        cur_tick = clock.get_ticks()
        action = self.get_action()
        if cur_tick >= action.start_tick and action.start_position is not None and self.position is not None:
            idx = cur_tick - action.start_tick
            direction: Vector2 = (self.position - action.start_position)
            if direction.magnitude() != 0:
                direction = direction.normalize()
            new_view_position = action.step_size * idx * direction + action.start_position
        else:
            new_view_position = self.get_position()
        if new_view_position != self.view_position:
            self.view_position = new_view_position
            self.mark_updated()

    @invoke_triggers
    def move(self, direction, new_angle, move_speed=1):

        direction = direction * 1
        if new_angle is not None and self.angle != new_angle:
            ticks_in_action = self._l_content.step_duration()/move_speed
            self.angle = new_angle
            return []
        ticks_in_action = self._l_content.step_duration()/move_speed

        new_pos = self._l_content.tile_size * direction + self.get_position()
        self._action = Action(ACTION_MOVE, ticks=ticks_in_action, step_size=self._l_content.tile_size/ticks_in_action, blocking=True, start_position=self.position)

        self.update_position(new_pos)
        self.play_sound("move")

    @invoke_triggers
    def receive_damage(self, attacker_obj, damage):
        if not self.permanent:
            self.health -= damage

        self.play_sound("receive_damage")

    @invoke_triggers
    def receive_push(self, pusher_obj, power, direction):
        if not self.pushable or not self.collision_type:
            return
        self.move(direction, None)
        self.play_sound("receive_push")

    @invoke_triggers
    def receive_grab(self, actor_obj):
        if self.collectable:
            return True
        else:
            return False

    def update(self):
        self.process_input_events()
        self.update_view_position()
        if self.health <= 0:
            self.destroy()

    def destroy(self):
        if self.remove_on_destroy:
            for child_id in self.child_object_ids:
                gamectx.remove_object_by_id(child_id)
            gamectx.remove_object(self)
        else:
            self.disable()
        self.play_sound("destroy")


class Inventory(PhysicalObject):

    def __init__(self, start_inventory={}, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slots = 10
        self.items = []
        for i in range(0, self.slots - len(self.items)):
            self.items.append(None)
        for i, (config_id, item_count) in enumerate(start_inventory.items()):
            obj: PhysicalObject = self._l_content.create_object_from_config_id(config_id)
            obj.spawn(Vector2(0, 0))
            obj.count = item_count
            self.add(obj)

        self.selected_slot = 0
        self.owner_obj_id = None

    def set_owner_obj_id(self, obj_id):
        self.owner_obj_id = obj_id

    def get_selected(self):
        return gamectx.get_object_by_id(self.items[self.selected_slot])

    @invoke_triggers
    def select_item(self, prev=False):
        if prev:
            if self.selected_slot == 0:
                self.selected_slot = self.slots - 1
            else:
                self.selected_slot -= 1
        else:
            if self.selected_slot == self.slots + 1:
                self.selected_slot = 0
            else:
                self.selected_slot += 1
                self.selected_slot = self.selected_slot % self.slots

    def get_objects(self) -> List[PhysicalObject]:
        objs = []
        for i, inv_obj_id in enumerate(self.items):
            inv_obj = gamectx.get_object_by_id(inv_obj_id)
            objs.append(inv_obj)
        return objs

    def add(self, obj: PhysicalObject, select_on_add=False):
        if obj.count_max > 1:
            for i, inv_obj_id in enumerate(self.items):
                if inv_obj_id is not None:
                    inv_obj = gamectx.get_object_by_id(inv_obj_id)
                    if inv_obj is not None and inv_obj.config_id == obj.config_id and inv_obj.count < inv_obj.count_max:
                        inv_obj.count += 1
                        gamectx.remove_object(obj)
                        if select_on_add:
                            self.selected_slot = i
                        return True

        for i, inv_obj_id in enumerate(self.items):
            if i != 0 and inv_obj_id is None:
                self.items[i] = obj.get_id()
                if select_on_add:
                    self.selected_slot = i
                obj.disable()
                return True
        return False

    def find(self, config_id):
        objs = []
        for i, inv_obj_id in enumerate(self.items):

            if inv_obj_id is not None:
                inv_obj = gamectx.get_object_by_id(inv_obj_id)
                if inv_obj is not None and inv_obj.config_id == config_id:
                    objs.append((i, inv_obj))
        return objs

    def remove_selected(self, remove_all=False):
        return self.remove_by_slot(self.selected_slot, remove_all=remove_all)

    def remove_by_slot(self, slot_id, remove_all=False):
        if slot_id == 0:
            return None
        obj_id = self.items[slot_id]
        if obj_id is None:
            return None
        else:
            obj: PhysicalObject = gamectx.get_object_by_id(obj_id)
            if obj is not None and not remove_all and obj.count > 1:
                obj.count -= 1
                newobj = self._l_content.create_object_from_config_id(obj.config_id)
                newobj.spawn(position=Vector2(0, 0))
                newobj.disable()
                return newobj
            else:
                self.items[slot_id] = None
                return obj

    def as_string(self):
        inv_info = []
        for i, obj in enumerate(self.get_objects()):
            if obj is None:
                item_name = "self" if i is 0 else "x"
                if i == self.selected_slot:
                    inv_info.append(f"[{item_name}]")
                else:
                    inv_info.append(f" {item_name} ")
            elif i == self.selected_slot:
                inv_info.append(f"[{obj.config_id}:{obj.count}]")
            else:
                inv_info.append(f" {obj.config_id}:{obj.count} ")
        return ', '.join(inv_info)


class CraftMenu:

    def __init__(self, items):
        self.slots = 10
        self.items = items
        self._l_content: SurvivalContent = gamectx.content


        self.selected_slot = 0

    def get_selected(self):
        return self.items[self.selected_slot]

    def select_item(self, prev=False):
        if prev:
            if self.selected_slot == 0:
                self.selected_slot = len(self.items) - 1
            else:
                self.selected_slot -= 1

        else:
            if self.selected_slot == len(self.items) - 1:
                self.selected_slot = 0
            else:
                self.selected_slot += 1

    def craft_selected(self, inventory: Inventory):
        config_id = self.get_selected()
        reqs = self._l_content.get_config_from_config_id(config_id).get("craft_requirements")
        print(reqs)
        if reqs is not None:
            have_reqs = True
            # Check requirements
            for req_id, count in reqs.items():
                objs = inventory.find(req_id)
                if len(objs) == 0:
                    print("NON FOUND")
                    have_reqs = False
                    break
                else:
                    inv_count = sum([o.count for _, o in objs])
                    if inv_count < count:
                        have_reqs = False
                        break
            if not have_reqs:
                print("Dont have req")
                return None

            # Remove requirements
            for req_id, count in reqs.items():
                objs = inventory.find(req_id)

                for i, obj in objs:
                    remainder = count - obj.count
                    if remainder >= 0:
                        inventory.remove_by_slot(i)
                        gamectx.remove_object(obj)
                        count = remainder
                    else:
                        obj.count = obj.count - count
                    if count == 0:
                        break
        obj: PhysicalObject = self._l_content.create_object_from_config_id(config_id)
        obj.spawn(position=Vector2(0, 0))
        obj.disable()
        inventory.add(obj)

    def as_string(self):
        info = []
        for i, craft_type in enumerate(self.items):
            if i == self.selected_slot:
                info.append(f"[{craft_type}]")
            else:
                info.append(f" {craft_type} ")
        return " ,".join(info)


class AnimateObject(PhysicalObject):

    def __init__(self, player: Player = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = "animate"
        if player is not None:
            self.set_player(player)

        self.rotation_multiplier = 1
        self.velocity_multiplier = 1
        self.walk_speed = 1/3

        self.attack_strength = self.config.get('attack_strength', 10)
        self.energy_max = self.config.get('energy_max', 100)
        self.stamina_max = self.config.get('stamina_max', 100)
        self.energy = 0
        self.stamina = 0

        self.next_energy_decay = 0
        self.next_health_gen = 0
        self.next_stamina_gen = 0
        self.attack_speed = .3
        self.height = 2
        self.pushable = True

        self.default_behavior: Behavior = None

        self.reward = 0
        self.total_reward = 0

        # Visual Range in x and y direction
        self.vision_radius = self.config.get('vision_radius', 2)

        self._inventory = Inventory(self.config.get('start_inventory', {}))
        self._inventory.set_owner_obj_id(self.get_id())

        self._l_craftmenu = CraftMenu(self.config.get('craft_items', []))

    def add_reward(self,r):
        self.reward += r
        self.total_reward +=r

    def process_input_event(self, e: InputEvent):
        if self.get_action().blocking:
            return
        # keydown = set(e.input_data['pressed'])
        keydown = set(e.input_data['keydown'])
        # Object Movement
        direction = None
        angle_update = None

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

        if 5 in keydown:
            self.grab()
        elif 6 in keydown:
            self.drop()
        elif 18 in keydown:
            self.use()
        elif 3 in keydown:
            self.select_item()
        elif 26 in keydown:
            self.select_item(prev=True)
        elif 2 in keydown:
            self.select_craft_type()
        elif 22 in keydown:
            self.select_craft_type(prev=True)
        elif 17 in keydown:
            self.craft()
        elif 33 in keydown:
            self.jump()
        elif 7 in keydown:
            self.push()
        elif direction is not None:
            self.walk(direction=direction, angle_update=angle_update)

    def get_inventory(self):
        return self._inventory

    @invoke_triggers
    def spawn(self, position: Vector2):
        super().spawn(position)
        
        self.energy  = self.config.get('energy_start', 100)
        self.stamina = self.config.get('stamina_start', 100)
        self.attack_speed = self.config.get('attack_speed', 0.3)
        self.walk_speed = self.config.get('walk_speed', 0.3)
        self.next_energy_decay = 0
        self.next_health_gen = 0
        self.next_stamina_gen = 0

    @invoke_triggers
    def select_item(self, prev=False):
        self._inventory.select_item(prev)
        ticks_in_action = self._l_content.step_duration()
        self._action = Action(
            ACTION_IDLE, 
                ticks=ticks_in_action)

    @invoke_triggers
    def remove_selected_item(self):
        return self._inventory.remove_selected()

    def get_craftmenu(self):
        return self._l_craftmenu

    @invoke_triggers
    def craft(self):
        self.get_craftmenu().craft_selected(self.get_inventory())
        ticks_in_action = self._l_content.step_duration()
        self._action = Action(
            ACTION_IDLE, 
                ticks=ticks_in_action)

    @invoke_triggers
    def select_craft_type(self, prev=False):
        self._l_craftmenu.select_item(prev)
        ticks_in_action = self._l_content.step_duration()
        self._action = Action(
            ACTION_IDLE, 
                ticks=ticks_in_action)

    # TODO: get from player to object
    # def get_observation_space(self):
    #     x_dim = (self.vision_radius * 2 + 1)
    #     chans = len(self._l_content.item_types) + 1
    #     return spaces.Box(low=0, high=1, shape=(self.vision_radius, self.vision_radius, chans))

    def get_object_observation(self, obj: PhysicalObject):

        obj_vec = self._l_content.obj_vec_map.get(obj.config_id)

        group_vec = self._l_content.create_tags_vec(obj.tags)  # TODO: memoize
        return np.concatenate([obj_vec, group_vec])

    def get_default_observation(self):

        obj_vec = self._l_content.obj_vec_map.get(None)  # np.zeros(self._l_content.max_obs_id)
        group_vec = ints_to_multi_hot(None, 3)
        return np.concatenate([obj_vec, group_vec])

    # TODO: not in use
    def get_observation(self):
        # Additional Info to add
        # Health
        # something underneath player
        obj_coord = gamectx.physics_engine.vec_to_coord(self.get_position())
        col_min = obj_coord[0] - self._l_content.vision_radius
        col_max = obj_coord[0] + self._l_content.vision_radius
        row_min = obj_coord[1] - self._l_content.vision_radius
        row_max = obj_coord[1] + self._l_content.vision_radius
        results = []
        empty_loc_vec = self.get_default_observation()
        for r in range(row_max, row_min-1, -1):
            row_results = []
            for c in range(col_min, col_max+1):
                obj_ids = gamectx.physics_engine.space.get_objs_at((c, r))
                obs_at_loc = empty_loc_vec
                if len(obj_ids) > 0:
                    obj_id = obj_ids[0]  # TODO: Switch to use TOP
                    obj = gamectx.object_manager.get_by_id(obj_id)
                    obs_at_loc = self.get_object_observation(obj)
                row_results.append(obs_at_loc)
            results.append(row_results)
        return np.array(results)

    def set_player(self, player: Player):
        self.player_id = player.get_id()
        if player is not None:
            player.attach_object(self)

    def get_player(self) -> Player:
        if self.player_id is None:
            return None
        else:
            return gamectx.player_manager.get_player(self.player_id)

    def get_visible_objects(self) -> List[PhysicalObject]:
        obj_coord = gamectx.physics_engine.vec_to_coord(self.get_position())

        col_min = obj_coord[0] - self.vision_radius
        col_max = obj_coord[0] + self.vision_radius
        row_min = obj_coord[1] - self.vision_radius
        row_max = obj_coord[1] + self.vision_radius
        obj_list = []
        for r in range(row_max, row_min-1, -1):
            for c in range(col_min, col_max+1):
                obj_ids = gamectx.physics_engine.space.get_objs_at((c, r))
                for obj_id in obj_ids:
                    obj_seen = gamectx.object_manager.get_by_id(obj_id)
                    if obj_seen is not None and obj_seen.is_visible() and obj_seen.is_enabled():
                        obj_list.append(obj_seen)

        return obj_list

    @invoke_triggers
    def receive_push(self, *args, **kwargs):
        super().receive_push(*args, **kwargs)
        self.stunned()

    @invoke_triggers
    def consume_food(self, food_obj: PhysicalObject):
        self.energy += food_obj.energy
        self.energy = min(self.energy,self.energy_max)
        self.play_sound("eat")
        # ticks_in_action = self._l_content.step_duration()/0.5
        self.queue_action(Action(ACTION_EAT, ticks=0, step_size=0))

    @invoke_triggers
    def walk(self, direction, angle_update):


        move_action = self.angle == angle_update
        walk_speed = self.walk_speed
        if self.stamina <= 0:
            walk_speed = walk_speed/2
        else:
            self.stamina -= self.config.get('walk_stamina_usage', 1)
        ticks_in_action = self._l_content.step_duration()/walk_speed
        self.angle = angle_update
        if move_action:

            direction = direction * self.velocity_multiplier
            position = self.get_position()
            if position is None:
                return
            new_pos = self._l_content.tile_size * direction + position
            self._action = Action(ACTION_WALK, 
                ticks=ticks_in_action, 
                step_size=self._l_content.tile_size/ticks_in_action, 
                start_position=self.position)

            self.update_position(new_pos, callback=lambda suc: self.play_sound('walk') if suc else None)
        else:
            ticks_in_action=self._l_content.step_duration()  / 3
            self._action = Action(ACTION_WALK, ticks=round(ticks_in_action))
            # self._action = Action(ACTION_WALK, ticks=round(ticks_in_action), step_size=self._l_content.tile_size/ticks_in_action, start_position=self.position)
            self.angle = angle_update

    @invoke_triggers
    def jump(self):

        direction = Vector2(0, 1).rotate(self.angle)

        target_pos = self.get_position() + (direction * self._l_content.tile_size * 2)
        target_coord = gamectx.physics_engine.vec_to_coord(target_pos)
        oids = gamectx.physics_engine.space.get_objs_at(target_coord)

        if len(oids) == 0:
            ticks_in_action = self._l_content.step_duration() * 2
            self._action = self._action = Action(
                ACTION_JUMP,
                ticks=ticks_in_action,
                step_size=(self._l_content.tile_size * 2)/ticks_in_action,
                start_position=self.position)

            self.update_position(target_pos, callback=lambda suc: self.play_sound('walk') if suc else None)

    @invoke_triggers
    def grab(self):
        

        received_obj = None

        target_coord = gamectx.physics_engine.vec_to_coord(self.get_position())
        for oid in gamectx.physics_engine.space.get_objs_at(target_coord):
            target_obj: PhysicalObject = gamectx.object_manager.get_by_id(oid)
            if target_obj.receive_grab(self):
                received_obj = target_obj
                break

        if received_obj is None:
            direction = Vector2(0, 1).rotate(self.angle).normalize()

            target_pos = self.get_position() + (direction * self._l_content.tile_size)
            target_coord = gamectx.physics_engine.vec_to_coord(target_pos)

            for oid in gamectx.physics_engine.space.get_objs_at(target_coord):
                target_obj: PhysicalObject = gamectx.object_manager.get_by_id(oid)
                if target_obj.receive_grab(self):
                    received_obj = target_obj
                    break

        if received_obj is not None:
            self.invoke_grab_action(received_obj)

        return True

    def invoke_grab_action(self,received_obj):
        if received_obj is not None:
            ticks_in_action = int(self._l_content.step_duration())
            self.get_inventory().add(received_obj)
            self.play_sound("grab")
            self._action = self._action = Action(
                ACTION_GRAB,
                ticks=ticks_in_action,
                step_size=self._l_content.tile_size/ticks_in_action)


    @invoke_triggers
    def stunned(self):
        ticks_in_action = int(self._l_content.step_duration()) * 10
        self._action = Action(
            ACTION_STUNNED,
            ticks=ticks_in_action,
            step_size=self._l_content.tile_size/ticks_in_action)

        self.play_sound("stunned")

    @invoke_triggers
    def drop(self):

        ticks_in_action = int(self._l_content.step_duration())

        direction = Vector2(0, 1).rotate(self.angle)

        target_pos = self.get_position() + (direction * self._l_content.tile_size)
        target_coord = gamectx.physics_engine.vec_to_coord(target_pos)

        oids = gamectx.physics_engine.space.get_objs_at(target_coord)

        if len(oids) == 0:
            obj = self.remove_selected_item()
            if obj is not None:
                obj.enable()
                obj.update_position(target_pos)

        self._action = Action(
            ACTION_DROP,
            ticks=ticks_in_action,
            step_size=self._l_content.tile_size/ticks_in_action)
        self.play_sound("drop")

    @invoke_triggers
    def use(self):
        selected_obj: PhysicalObject = self.get_inventory().get_selected()
        if self.get_inventory().selected_slot == 0 or selected_obj is None:
            self.unarmed_attack()
            return
        elif selected_obj.type == "tool":
            selected_obj.use_by(self)
        elif selected_obj.type == "food":
            self.consume_food(selected_obj)
            self.get_inventory().remove_selected()

    @invoke_triggers
    def unarmed_attack(self):
        direction = Vector2(0, 1).rotate(self.angle)
        target_pos = self.get_position() + (direction * self._l_content.tile_size)
        target_coord = gamectx.physics_engine.vec_to_coord(target_pos)

        target_objs = []
        for oid in gamectx.physics_engine.space.get_objs_at(target_coord):
            obj2: PhysicalObject = gamectx.object_manager.get_by_id(oid)
            if obj2.collision_type > 0:
                target_objs.append(obj2)

        for obj2 in target_objs:
            obj2.receive_damage(self, self.attack_strength)

        self.invoke_attacking_action()


    def invoke_attacking_action(self): #rename to invoke attacking 'animation'?
        attack_speed = self.attack_speed

        if self.stamina <= 0:
            attack_speed = attack_speed/2
        else:
            self.stamina -= 15
        ticks_in_action = round(self._l_content.step_duration()/attack_speed)
        self._action = Action(
            ACTION_ATTACK,
            ticks=ticks_in_action,
            step_size=self._l_content.tile_size/ticks_in_action)
        self.play_sound("attack")


    @invoke_triggers
    def push(self):
        attack_speed = self.attack_speed

        if self.stamina <= 0:
            attack_speed = attack_speed/2
        else:
            self.stamina -= 15

        ticks_in_action = round(self._l_content.step_duration()/attack_speed)
        direction = Vector2(0, 1).rotate(self.angle)
        target_pos = self.get_position() + (direction * self._l_content.tile_size)
        target_coord = gamectx.physics_engine.vec_to_coord(target_pos)

        for oid in gamectx.physics_engine.space.get_objs_at(target_coord):
            obj2: PhysicalObject = gamectx.object_manager.get_by_id(oid)
            obj2.receive_push(self, self.attack_strength, direction)

        self._action = Action(ACTION_PUSH, ticks=ticks_in_action, step_size=self._l_content.tile_size/ticks_in_action)

        self.play_sound("push")

    @invoke_triggers
    def die(self):
        self.disable()
        p = self.get_player()
        if p is not None:
            lives_used = p.get_data_value("lives_used", 0)
            lives_used += 1
            p.set_data_value("lives_used", lives_used)
            p.set_data_value("allow_input", False)
            self._l_content.message_player(p,"You Died!",20)
            delay = 10*self._l_content.step_duration()

            def event_fn(event: DelayedEvent, data):
                p.set_data_value("reset_required", True)
                return []
            
            event = DelayedEvent(event_fn, delay)
            gamectx.add_event(event)

    def update(self):
        # TODO: move properties like energry_decay_period, etc to object so they can be changed temporarily without modifying config
        cur_time = clock.get_ticks()
        self.set_last_change(cur_time)
        if cur_time > self.next_energy_decay:
            self.energy = max(0, self.energy - self.config.get('energy_decay', 0))
            if self.energy <= 0:
                self.health -= self.config.get('low_energy_health_penalty', 0)

            self.next_energy_decay = cur_time + (self.config.get('energy_decay_period', 0) * self._l_content.step_duration())

        # Health regen
        if cur_time > self.next_health_gen:
            self.health = min(self.health_max, self.health + self.config.get('health_gen', 0))
            self.next_health_gen = cur_time + (self.config.get('health_gen_period', 0) * self._l_content.step_duration())

        # Stamina regen
        if cur_time > self.next_stamina_gen and self.stamina < self.config.get('stamina_max', 50):
            self.stamina = min(self.stamina_max, self.stamina + self.config.get('stamina_gen', 5))
            gen_delay = (self.config.get('stamina_gen_period', 0) * self._l_content.step_duration())
            self.next_stamina_gen = cur_time + gen_delay

        if self.health <= 0:
            drop_on_death = self.config.get("drop_on_death")
            if drop_on_death is not None:
                for config_id, count in drop_on_death.items():
                    obj = self._l_content.create_object_from_config_id(config_id)
                    obj.spawn(self.position)
            # Check for death
            self.die()
        else:
            p = self.get_player()

            if p is not None:
                p.set_data_value("allow_input", True)
            elif self.default_behavior is not None and not self.get_action().blocking:
                self.default_behavior.on_update(self)

        super().update()

    def destroy(self):
        if self.get_player() is not None:
            self.disable()
        else:
            super().destroy()


class Equipment(PhysicalObject):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = "equipment"


class BodyArmor(Equipment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = "body_armor"


class Tool(Equipment):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attack_speed = 2
        self.type = "tool"

    def use_by(self, user_object: AnimateObject):
        pass

class Monster(AnimateObject):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = "monster"
        self.height = 2
        self.default_behavior = self._l_content.create_behavior(self.config.get('default_behavior_class', 'FollowAnimals'))


class Animal(AnimateObject):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = "animal"
        self.default_behavior = self._l_content.create_behavior(self.config.get('default_behavior_class', 'FleeAnimals'))


class Human(Animal):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type = "human"
        self.height = 2

    def update(self):
        super().update()


#TODO Replace with "Plant" type/or component which has stages for growth. Should have similar for animal
class Tree(PhysicalObject):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.type = "tree"
        self.set_visiblity(False)
        self.pushable = False
        self.remove_on_destroy = True
        self.top_id = None
        self.trunk_id = None
        self.height = 3
        self.__fruit = []

    def spawn(self, position):
        super().spawn(position=position)
        self.add_tree_trunk()
        self.add_tree_top()
        for i in range(0, random.randint(0, 3)):
            self.add_fruit()

    def update_position(self,*args,**kwargs):
        super().update_position(*args,**kwargs)
        for cid in self.child_object_ids:
            part = gamectx.object_manager.get_by_id(cid)
            if part is not None:
                part.update_position(*args,**kwargs)

    def add_tree_trunk(self):
        o = PhysicalObject(visheight=1)
        o.type = "part"
        o.pushable = False
        o.collision_type = 0
        o.set_image_id('tree_trunk')
        o.spawn(position=self.get_position())
        self.trunk_id = o.get_id()
        self.child_object_ids.add(self.trunk_id)

    def add_fruit(self):
        o = self._l_content.create_object_from_config_id('apple1')
        o.spawn(position=self.get_position())
        o.visheight = 3
        o.collectable = 1
        y = random.random() * self._l_content.tile_size*1.8
        x = random.random() * self._l_content.tile_size - self._l_content.tile_size/2
        o.set_image_offset(Vector2(x, y))
        self.__fruit.append(o)
        self.child_object_ids.add(o.get_id())

    def add_tree_top(self):
        o = PhysicalObject()
        o.visheight = 2
        o.type = "part"
        o.set_image_id('tree_top')
        o.pushable = False
        o.collision_type = 0
        o.spawn(position=self.get_position())
        o.set_image_offset(Vector2(0, self._l_content.tile_size*1.4))
        self.top_id = o.get_id()
        self.child_object_ids.add(self.top_id)

    def enable(self):
        super().enable()
        for cid in self.child_object_ids:
            part = gamectx.object_manager.get_by_id(cid)
            if part is not None:
                part.enable()
        
    def get_trunk(self) -> PhysicalObject:
        return gamectx.object_manager.get_by_id(self.trunk_id)

    def get_top(self) -> PhysicalObject:
        return gamectx.object_manager.get_by_id(self.top_id)

    @invoke_triggers # TODO: (BUG) will call triggers twice
    def receive_damage(self, attacker_obj, damage):
        super().receive_damage(attacker_obj, damage)
        if self.health <= 0:
            gamectx.remove_object_by_id(self.trunk_id)
            self.child_object_ids.discard(self.trunk_id)
            gamectx.remove_object(self)
            obj = self._l_content.create_object_from_config_id('wood1')
            obj.spawn(self.position)
        
        if self.health < 30:
            gamectx.remove_object_by_id(self.top_id)
            self.child_object_ids.discard(self.top_id)
            for fruit in self.__fruit:
                self.child_object_ids.discard(fruit.get_id())
                gamectx.remove_object(fruit)
            self.__fruit = []

    @invoke_triggers # TODO: (BUG) will call triggers twice
    def receive_grab(self, actor_obj):
        if len(self.__fruit) > 0:
            fruit = self.__fruit.pop()
            self.child_object_ids.discard(fruit.get_id())
            actor_obj.invoke_grab_action(fruit)
        
        return False

class Food(PhysicalObject):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.visheight = 1
        self.energy = self.config.get("energy", 10)
        self.type = 'food'

    def spawn(self, position):
        super().spawn(position=position)
        self.visheight = 1

class Rock(PhysicalObject):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.visheight = 1
        self.type = 'rock'
        self.sleeping = self.config.get("sleeping", True)


class Liquid(PhysicalObject):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.visheight = 0
        self.type = 'liquid'
        self.permanent = True
        self.set_shape_color(color=(30, 30, 150))
