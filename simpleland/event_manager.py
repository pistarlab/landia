from typing import Any, Dict, List
from .utils import gen_id
from .common import Base, Vector2

from .event import Event, InputEvent, build_event_from_dict


class EventManager:
    """
    Contains references to all game events
    """

    def __init__(self):

        self.events: Dict[str, Event] = {}

    def add_event(self, e: Event):
        self.events[e.get_id()] = e

    def add_events(self, events: List[Event]):
        for e in events:
            self.add_event(e)

    def get_events(self):
        return self.events.values()

    def get_event_dict(self):
        return self.events

    def get_event_by_id(self, id):
        return self.events[id]

    def remove_event_by_id(self, id):
        self.events.pop(id,None)

    def clear(self):
        self.events: Dict[str, Event] = {}

    def get_snapshot(self):
        events = list(self.get_events())
        results = []
        for e in events:
            results.append(e.get_snapshot())
        return results

    def get_client_snapshot(self):
        events = list(self.get_events())
        results = []
        for e in events:
            if type(e) == InputEvent:
                results.append(e.get_snapshot())
        return results

    def load_snapshot(self,data):
        for e_data in data:
            k = e_data['data']['id']
            if k in self.events:
                self.events[k].load_snapshot(e_data)
            else:
                try:
                    self.events[k] = build_event_from_dict(e_data)
                except Exception as e:
                    print(e_data)
                    print(e)