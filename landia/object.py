
from .utils import gen_id
from typing import Callable, List, Dict
import time

from .common import Shape, Vector2, load_dict_snapshot, Base,get_shape_from_dict
from .common import create_dict_snapshot, state_to_dict, ShapeGroup, TimeLoggingContainer
from .common import COLLISION_TYPE
from .component import Component
from .clock import clock
import copy


class GObject(Base):
    #TODO: Add component suport


    def __init__(self,
                 id= None,
                 data = None,
                 visheight = 2):
        super().__init__()
        if id is None:
            self.id = gen_id()
        else:
            self.id = id
        self.position = None
        self.view_position = None
        self.angle = 0
        self.config_id = None
        self.created_tick = clock.get_ticks()
        self.player_id = None

        self.sleeping = False # if true, do not update

        self.shape_group: ShapeGroup = ShapeGroup()
        self.data = {} if data is None else data
        self.last_change = None
        self.enabled=True
        self.visheight=visheight
        self.visible=True
        self.image_width, self.image_height = 80,80
        self.shape_color = None
        self._update_position_callback = lambda obj,new_pos, skip_collision_check,callback: None

        self.image_id_default = None
        self.rotate_sprites = False
        self.image_offset = Vector2(0,0)
        self.child_object_ids =set()


    def get_types(self):
        return set()     

    def update(self):
        pass
        # for component in self.components:
        #     if component.enabled:
        #         component.update()

    def get_view_position(self):
        if self.view_position is None:
            return self.position
        else:
            return self.view_position

    def get_image_id(self, angle):
        return self.image_id_default

    def set_visiblity(self,visible):
        self.visible=visible

    def set_image_offset(self,v):
        self.image_offset = v    

    def is_visible(self):
        return self.visible

    def set_image_id(self,id):
        self.image_id_default = id

    def update_last_change(self):
        self.set_last_change(clock.get_ticks())
    
    def set_update_position_callback(self,callback):
        self._update_position_callback = callback

    def get_data_value(self,k, default_value=None):
        return self.data.get(k,default_value)

    def disable(self):
        self.enabled=False
        # self.update_position(None, skip_collision_check=True)

    def enable(self):
        self.enabled=True

    def is_enabled(self):
        return self.enabled

    def set_shape_color(self,color):
        self.shape_color = color
    
    def set_data_value(self,k,value):
        self.data[k] = value
        self.update_last_change()

    def get_id(self):
        return self.id

    def get_image_dims(self):
        return self.image_width, self.image_height
    
    def set_image_dims(self,height,width):
        self.image_width, self.image_height = (height,width)

    # TODO, make tiggerable
    def update_position(self, position: Vector2,skip_collision_check=False,callback=None):
        self._update_position_callback(
            self,
            position,
            skip_collision_check=skip_collision_check,
            callback=callback)

    def sync_position(self):
        self.update_position(self.position,True)

    def set_position(self, position: Vector2):
        self.position = position
        self.set_last_change(clock.get_ticks())
        # self.update_position(position,True)

    def get_position(self):
        return self.position

    def __repr__(self) -> str:
        return f"{super().__repr__()}, id:{self.id}, data:{self.data}, dict_data:{self.__dict__}"

    def add_shape(self,shape:Shape, collision_type=1):
        shape.set_object_id(self.get_id())
        shape.collision_type = collision_type
        if collision_type == COLLISION_TYPE['sensor']:
            shape.sensor = True
        self.shape_group.add(shape)

    def get_shapes(self):
        return self.shape_group.get_shapes()

    def set_last_change(self,timestamp):
        self.last_change = timestamp

    def mark_updated(self):
        self.set_last_change(clock.get_ticks())

    def get_last_change(self):
        return self.last_change

    def get_snapshot(self):
        data = create_dict_snapshot(self, exclude_keys={'on_change_func'})
        data['data']['last_change']= self.get_last_change()
        data['data']['data'] = self.data
        return data

    def load_snapshot(self, data_dict,exclude_keys=set()):
        load_dict_snapshot(self, data_dict, exclude_keys={'shape_group'}.union(exclude_keys))
        data = data_dict['data']
        
        # TODO: using word "data" too much!! rename somethings
        for k,v in data['shape_group']['data'].items():
            self.add_shape(get_shape_from_dict(v))
        
        if "data" in data:
            self.data = data['data']

    
def update_view_position(obj1:GObject,obj2:GObject,fraction=0.5):
    p1 = obj1.get_view_position()
    p2 = obj2.get_view_position()
    obj1.view_position = (p2 - p1) * fraction  + p1
