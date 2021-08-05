from typing import List, Dict
from .common import (create_dict_snapshot, load_dict_snapshot, Base)
from .camera import Camera

from .object import GObject
from .event import Event

class Player(Base):

    @classmethod
    def build_from_dict(cls,data_dict):
        data = data_dict['data']
        player = cls()
        player.uid = data['uid']
        player.obj_id = data['obj_id']
        player.is_human = data['is_human']
        player.client_id = data['client_id']
        player.player_type = data['player_type']
        player.data = data.get('data',{})
        
        if data['camera'] :
            player.camera = Camera(**data['camera']['data'])
        return player

    def __init__(self, client_id=None, uid=None, data=None, player_type =0, camera=None, is_human=False):
        """
        :return:
        """
        self.uid = uid
        self.client_id = client_id
        self.player_type = player_type
        self.camera:Camera = camera
        self.obj_id = None
        self.is_human = is_human
        self.events=[]
        self.data = {} if data is None else data

    def get_id(self):
        return self.uid    

    def get_data_value(self,k, default_value=None):
        return self.data.get(k,default_value)
    
    def set_data_value(self,k,value):
        self.data[k] = value

    def attach_object(self, obj: GObject):
        self.obj_id = obj.get_id()
        self.camera.set_follow_object(obj)

    def get_object_id(self) -> str:
        return self.obj_id

    def add_event(self, event: Event):
        self.events.append(event)
    
    def pull_input_events(self) -> List[Event]:
        events =  self.events
        self.events = []
        return events

    def get_snapshot(self):
        data =  create_dict_snapshot(self, exclude_keys={'events'})
        return data

    def load_snapshot(self, data):
        load_dict_snapshot(self, data, exclude_keys={"events"})

    def get_camera(self) -> Camera:
        return self.camera

    def __repr__(self):
        return "Player: {}, Type: {}".format(self.uid,self.player_type)