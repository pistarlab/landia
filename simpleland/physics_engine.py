from typing import Any, Dict, List

import numpy
import pygame
from .common import (Circle,  Line,
                     Polygon, Vector2,  COLLISION_TYPE)
from .object import GObject
# from .player import Player
from .utils import gen_id
from .config import PhysicsConfig
import math
from .clock import clock
from .event_manager import EventManager
from .event import PositionChangeEvent

class GridSpace:


    def __init__(self):
        self.coord_to_obj= {}
        self.obj_to_coord = {}
        self.tracked_objs ={}
        # NOT USED
        self.sectors = {}

    def get_sector_id(self,coord):
        return coord[0] // 20, coord[1] // 20

    def get_objs_at(self,coord):
        return self.coord_to_obj.get(coord,[])

    def move_obj_to(self,coord,obj:GObject):
        obj_id = obj.get_id()
        self.remove_obj(obj_id)
        obj_ids = self.coord_to_obj.get(coord,[])
        obj_ids.append(obj_id)
        self.coord_to_obj[coord] = obj_ids
        self.obj_to_coord[obj_id] = coord
        self.tracked_objs[obj_id] = obj

    def remove_obj(self,obj_id):
        last_coord = self.obj_to_coord.get(obj_id)
        ids = self.coord_to_obj.get(last_coord,[])
        if last_coord is None:
            return
        
        if len(ids) <=1:
            del self.coord_to_obj[last_coord]
        else:
            try:
                ids.remove(obj_id)
                self.coord_to_obj[last_coord] = ids
            except:
                pass
        del self.obj_to_coord[obj_id]
        del self.tracked_objs[obj_id]

    def get_obj_by_id(self,obj_id):
        return self.tracked_objs.get(obj_id)

    def debug_draw(self,*args,**kwargs):
        raise NotImplementedError("debug_draw Not supported for this space type")


class GridPhysicsEngine:
    """
    Handles physics events and collision
    """

    def __init__(self,config:PhysicsConfig, em:EventManager):
        self.config = config
        self.tile_size = self.config.tile_size
        self.space = GridSpace()
        self.position_updates = {}
        self.collision_callbacks ={}
        self.em  = em

    def vec_to_coord(self,v):
        
        return (round(v.x / self.tile_size),round(v.y / self.tile_size))#(round(v.x / self.tile_size),round(v.y / self.tile_size))

    def coord_to_vec(self,coord):
        return Vector2(coord[0] * self.tile_size, coord[1] * self.tile_size)

    def set_collision_callback(self, 
            callback, 
            collision_type_a=COLLISION_TYPE['default'], 
            collision_type_b=COLLISION_TYPE['default']):

        self.collision_callbacks[(collision_type_a,collision_type_b)] = callback
        self.collision_callbacks[(collision_type_b,collision_type_a)] = callback


    def add_object(self, obj: GObject):
        obj.last_change = clock.get_ticks()
        obj.set_update_position_callback(self.update_obj_position)
        self.update_obj_position(obj,obj.get_position(),skip_collision_check=True)

    def update_obj_position(self,obj:GObject,new_pos,skip_collision_check=False,callback=None):
        if skip_collision_check:
            self.create_change_position_event(
                    obj,
                    old_pos = obj.position,
                    new_pos=new_pos)
            if new_pos is not None:
                coord =self.vec_to_coord(new_pos)
                self.space.move_obj_to(coord,obj)
            else:
                self.space.remove_obj(obj.get_id())
            obj.set_position(new_pos)
            if callback is not None:
                callback(True)
        else:
            self.position_updates[obj.get_id()] = (obj,new_pos,callback)

    def create_change_position_event(self,obj:GObject,old_pos,new_pos):
        e = PositionChangeEvent(
            obj.get_id(),old_pos=old_pos,new_pos=new_pos,
            is_player_obj= obj.player_id is not None)
        self.em.add_event(e)

    def remove_object(self,obj):
        self.space.remove_obj(obj.get_id())

    def update(self):
        obj:GObject

        for obj,new_pos,callback in self.position_updates.values():
            if not obj.enabled:
                continue
            new_pos = Vector2(round(new_pos.x),round(new_pos.y))
            coord =self.vec_to_coord(new_pos)
            coll_objs_ids = self.space.get_objs_at(coord)
            collision_effect = False
            for obj_id_2 in coll_objs_ids:
                if obj_id_2 != obj.get_id():
                    obj2:GObject = self.space.get_obj_by_id(obj_id_2)
                    if not obj2.enabled:
                        continue
                    collition_types1 = [shape.collision_type for shape in obj.get_shapes()]
                    collition_types2 = [shape.collision_type for shape in obj2.get_shapes()]
                    for col_type1 in collition_types1:
                        for col_type2 in collition_types2:                            
                            cb = self.collision_callbacks.get((col_type1,col_type2))
                            if cb is not None and cb(obj,obj2):
                                collision_effect = True
                    
            if not collision_effect:
                self.space.move_obj_to(coord,obj)
                self.create_change_position_event(
                    obj,
                    old_pos = obj.position,
                    new_pos=new_pos)

                obj.set_position(new_pos)

                if callback is not None:
                    callback(True)

        self.position_updates = {}
