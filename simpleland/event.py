
from simpleland.object import GObject
from typing import Any, Dict, List
from .utils import gen_id
from .common import Base, Vector2
from .clock import clock

def build_event_from_dict(data_dict):
    cls = globals()[data_dict['_type']]
    event = cls(**data_dict['data'])
    return event

class Event(Base):

    def __init__(self, 
                id=None,
                creation_time = None,
                is_client_event=False,
                is_server_event=True):
        if id is None:
            self.id = gen_id()
        else:
            self.id = id
        self.creation_time = creation_time or clock.get_ticks()
        self.is_client_event = is_client_event
        self.is_server_event = is_server_event

    def get_id(self):
        return self.id


class ContentEvent(Event):

    def __init__(self,
                id=None,
                data={},
                is_client_event=False,
                **kwargs):

        super().__init__(id,is_client_event=is_client_event,**kwargs)
        self.data=data

    def get_id(self):
        return self.id

class ObjectEvent(Event):

    def __init__(self,
                obj_id,
                obj_method_name,
                *args,
                **kwargs):

        super().__init__()
        self.obj_id =obj_id
        self.obj_method_name = obj_method_name
        self.args=args
        self.kwargs=kwargs

    def get_id(self):
        return self.id


class PeriodicEvent(Event):

    def __init__(self,
                func, 
                id=None, 
                execution_step_interval=None, 
                run_immediately = False,
                data={},
                **kwargs):

        super().__init__(id,**kwargs)
        self.execution_step_interval = execution_step_interval
        self.last_run = None if run_immediately else clock.get_ticks()
        self.data=data
        self.func = func

    def get_id(self):
        return self.id

    def run(self):
        game_step = clock.get_ticks()
        new_events = []
        remove_event = None
        if self.last_run is None or self.last_run + self.execution_step_interval <= game_step:
            new_events, remove_event = self.func(self,self.data)
            self.last_run = game_step

        return [], False

class DelayedEvent(Event):

    def __init__(self,
                func, 
                execution_step, 
                id=None,
                data={},
                is_client_event=False,
                **kwargs):

        super().__init__(id,is_client_event=is_client_event,**kwargs)
        self.execution_step = execution_step + clock.get_ticks()
        self.data=data
        self.func = func

    def get_id(self):
        return self.id

    def run(self):
        game_step = clock.get_ticks()

        new_events = []
        if  self.execution_step <= game_step:
            new_events = self.func(self,self.data)
            return new_events, True
        return new_events, False


class RemoveObjectEvent(Event):

    def __init__(self,
                object_id,
                id=None,
                data={},
                is_client_event=True,
                **kwargs):

        super().__init__(id,is_client_event=is_client_event,**kwargs)
        self.data=data
        self.object_id = object_id

    def get_id(self):
        return self.id


class SoundEvent(Event):

    def __init__(self,
                id=None, 
                sound_id = None,
                is_client_event=True,
                position = None,
                **kwargs):
        super().__init__(id,
            is_client_event=is_client_event,
            **kwargs)
        self.sound_id = sound_id
        self.position = position

    def get_id(self):
        return self.id

class InputEvent(Event):

    @classmethod
    def build_from_dict(cls,dict_data, **kwargs):
        return cls(
            player_id = dict_data['player_id'],
            input_data = dict_data['input_data'],
            id = dict_data['id'],
            **kwargs)

    def __init__(self, 
                player_id: str,
                input_data: Dict[str,Any] ,
                id=None,
                **kwargs):
        super().__init__(id,**kwargs)
        self.player_id = player_id
        self.input_data = input_data

    def __repr__(self):
        return str(self.input_data)


class PositionChangeEvent(Event):

    @classmethod
    def build_from_dict(cls,dict_data, **kwargs):
        return cls(
            id = dict_data['id'],
            obj_id = dict_data['obj_id'],
            old_pos = dict_data['old_pos'],
            new_pos = dict_data['new_pos'],
            is_player_obj = dict_data['is_player_obj'],
            **kwargs)

    def __init__(self, 
                obj_id:str,
                old_pos: Vector2,              
                new_pos: Vector2,
                is_player_obj = False,              
                id=None,
                **kwargs):
        super().__init__(id,**kwargs)
        self.obj_id = obj_id
        self.old_pos = old_pos
        self.new_pos = new_pos
        self.is_player_obj = is_player_obj

    def __repr__(self):
        return f"pos change event for obj{self.obj_id} {self.old_pos} to {self.new_pos}"

class AdminCommandEvent(Event):

    def __init__(self, value, player_id:str=None,id=None, **kwargs):
        super().__init__(id,**kwargs)
        self.player_id = player_id
        self.value = value

class ViewEvent(Event):

    def __init__(self, player_id: str,
                 distance_diff: float = 0,
                 center_diff: Vector2 = None,
                 orientation_diff: float = 0.0, 
                 id=None,
                 **kwargs):
        super().__init__(id, **kwargs)
        self.player_id = player_id
        self.distance_diff = distance_diff
        self.center_diff =  Vector.zero() if center_diff is None else center_diff
        self.orientation_diff = orientation_diff