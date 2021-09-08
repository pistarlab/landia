import time
from .inputs import get_input_events
from .common import register_base_cls, Base
from .content import Content
import sys
import pygame
from .event import RemoveObjectEvent
from .event import (AdminCommandEvent, ContentEvent, Event, ObjectEvent,
                    PeriodicEvent, PositionChangeEvent, ViewEvent, SoundEvent, DelayedEvent, InputEvent)
from .physics_engine import GridPhysicsEngine
from .player_manager import PlayerManager
from .object_manager import GObjectManager
from .event_manager import EventManager
from .clock import clock
import json
from typing import List, Set, Dict, Any
from uuid import UUID


from .object import (GObject)

# from .renderer import SLRenderer
from .utils import gen_id
from .config import GameDef, GameConfig, PhysicsConfig
import math
LATENCY_LOG_SIZE = 100


class GameContext:

    def __init__(self):

        self.game_def: GameDef = None
        self.config: GameConfig = None
        self.physics_config: PhysicsConfig = None

        self.object_manager: GObjectManager = None
        self.physics_engine: GridPhysicsEngine = None
        self.player_manager: PlayerManager = None
        self.event_manager: EventManager = None
        self.content: Content = None
        self.state = None
        self.step_counter = 0

        self.tick_rate = None
        self.pre_event_callback = lambda: []
        self.input_event_callback = lambda event: []
        self.remote_clients: Dict[str, Any] = {}
        self.local_clients = []
        self.data = {}

    def initialize(self,
                   game_def: GameDef = None,
                   content=None):
        self.game_def = game_def

        self.config = game_def.game_config
        self.physics_config = game_def.physics_config
        self.event_manager = EventManager()
        self.object_manager = GObjectManager()
        self.physics_engine = GridPhysicsEngine(
            self.physics_config,
            self.event_manager)
        self.player_manager = PlayerManager()

        self.state = "RUNNING"
        self.tick_rate = self.config.tick_rate
        clock.set_tick_rate(self.tick_rate)
        self.step_counter = 0

        self.content = content

        self.content.load(self.config.client_only_mode)

    def tick(self):
        clock.tick()

    def get_content(self) -> Content:
        return self.content

    def add_local_client(self, client):
        self.local_clients.append(client)

    def get_remote_client(self, client_id):
        from .client import RemoteClient
        client = self.remote_clients.get(client_id, None)
        if client is None:
            client = RemoteClient(client_id)
            self.remote_clients[client.id] = client
        return client

    def change_game_state(self, new_state):
        self.state = new_state

    def register_base_class(self, cls):
        register_base_cls(cls)

    # Snapshot Methods
    def create_snapshot_for_client(self, client):
        from .client import RemoteClient
        client: RemoteClient = client
        snapshot_timestamp = clock.get_ticks()
        om_snapshot = self.object_manager.get_snapshot_update(
            client.last_snapshot_time_ms)
        # om_snapshot = self.object_manager.get_snapshot_full()
        # TODO: Only send relevent Players
        pm_snapshot = self.player_manager.get_snapshot()
        eventsnapshot = client.pull_events_snapshot()
        return snapshot_timestamp, {
            'om': om_snapshot,
            'pm': pm_snapshot,
            'em': eventsnapshot,
            'timestamp': snapshot_timestamp,
        }

    def create_full_snapshot(self):

        om_snapshot = self.object_manager.get_snapshot_full()
        pm_snapshot = self.player_manager.get_snapshot()
        em_snapshot = self.event_manager.get_snapshot()
        return  {
            'om': om_snapshot,
            'pm': pm_snapshot,
            'em': em_snapshot,
            'timestamp': clock.get_ticks(),
            'gametime': clock.get_game_time(),
        }

    def load_object_snapshot(self, data):
        for odata in data:
            obj_id = odata['data']['id']
            current_obj = self.object_manager.get_by_id(obj_id)
            if current_obj is None:
                obj = Base.create_from_snapshot(odata)
                self.add_object(obj)
            else:
                current_obj.load_snapshot(odata)

    def load_snapshot(self, snapshot):
        if 'om' in snapshot:
            self.load_object_snapshot(snapshot['om'])
        if 'pm' in snapshot:
            self.player_manager.load_snapshot(snapshot['pm'])
        if 'em' in snapshot:
            self.event_manager.load_snapshot(snapshot['em'])

    # Player Methods
    def get_player(self, client, player_type, is_human,name=None):
        """
        Get existing player or create new one
        """
        if client.player_id is None:
            player = self.content.new_player(
                client.id, player_id=None, player_type=player_type, is_human=is_human,name=name)
            client.player_id = player.get_id()
        else:
            player = self.player_manager.get_player(client.player_id)
        return player

    def add_player(self, player):
        self.player_manager.add_player(player)

    # Object Methods
    def add_object(self, obj: GObject):
        obj.set_last_change(clock.get_ticks())
        self.object_manager.add(obj)
        self.physics_engine.add_object(obj)

    def remove_object(self, obj: GObject):
        self.remove_object_by_id(obj.get_id())

    def remove_object_by_id(self, obj_id):
        event = RemoveObjectEvent(object_id=obj_id)
        self.add_event(event)

    def remove_all_objects(self):
        for o in list(self.object_manager.get_objects().values()):
            self.remove_object(o)

    def get_object_by_id(self, obj_id):
        return self.object_manager.get_by_id(obj_id)

    # Event Methods
    def add_event(self, e: Event):
        self.event_manager.add_event(e)
        if e.is_client_event:
            for client_id, client in self.remote_clients.items():
                client.add_event(e)

    def remove_all_events(self):
        self.event_manager.clear()

    def get_sound_events(self):
        events_to_remove = []
        sound_ids = []
        for e in self.event_manager.get_events():
            if type(e) == SoundEvent:
                e: SoundEvent = e
                sound_ids.append(e.sound_id)
                events_to_remove.append(e)

        for e in events_to_remove:
            self.event_manager.remove_event_by_id(e.get_id())
        return sound_ids

    def _process_view_event(self, e):
        player = self.player_manager.get_player(e.player_id)
        player.get_camera().distance += e.distance_diff
        return []

    def _process_remove_object_event(self, e: RemoveObjectEvent):
        obj = self.object_manager.get_by_id(e.object_id)
        if obj is not None:
            obj.set_last_change(clock.get_ticks())
            self.physics_engine.remove_object(obj)
            self.object_manager.remove_by_id(obj.get_id())
            # print(f"****Object     found,     deleting {clock.get_ticks()} {e.object_id}")
        else:
            # TODO: Caused by multiple actions on same tick issue
            pass
            # print(f"****Object not found, not deleting {clock.get_ticks()} {e.object_id}")

        return True

    def run_pre_event_processing(self):
        if self.pre_event_callback is not None:
            events = self.pre_event_callback()
            self.event_manager.add_events(events)

    def run_event_processing(self):
        # Main Event Processing Bus
        all_new_events = []
        events_to_remove = []
        events_set = set(self.event_manager.get_events())
        while len(events_set) > 0:
            e = events_set.pop()
            new_events = []
            if type(e) == InputEvent:
                new_events = self.content.process_input_event(e)
                events_to_remove.append(e)
            elif type(e) == AdminCommandEvent:
                new_events = self.content.process_admin_command_event(e)
                events_to_remove.append(e)
            elif type(e) == ContentEvent:
                new_events = self.content.process_event(e)
                events_to_remove.append(e)
            elif type(e) == ViewEvent:
                new_events = self._process_view_event(e)
                events_to_remove.append(e)
            elif type(e) == RemoveObjectEvent:
                self._process_remove_object_event(e)
                events_to_remove.append(e)
            elif type(e) == DelayedEvent:
                e: DelayedEvent = e
                new_events, remove_event = e.run()
                if remove_event:
                    events_to_remove.append(e)
            elif type(e) == PeriodicEvent:
                e: PeriodicEvent = e
                new_events, remove_event = e.run()
                if remove_event:
                    events_to_remove.append(e)
            elif type(e) == PositionChangeEvent:
                e: PositionChangeEvent = e
                self.content.process_position_change_event(e)
                events_to_remove.append(e)
            elif type(e) == ObjectEvent:
                e: ObjectEvent = e
                obj = self.get_object_by_id(e.obj_id)
                func = getattr(obj, e.obj_method_name)
                # TODO: Add listeners
                new_events = func(*e.args, **e.kwargs)
                events_to_remove.append(e)
            for new_e in new_events:
                events_set.add(new_e)
            all_new_events.extend(new_events)

        self.event_manager.add_events(all_new_events)

        for e in events_to_remove:
            self.event_manager.remove_event_by_id(e.get_id())

    # Client Steps
    def process_client_step(self):
        for client in self.local_clients:
            client.run_step()

    def render_client_step(self):
        for client in self.local_clients:
            client.render()

    def wait_for_input_and_confirm(self):

        wait = True

        pygame.event.clear()
        last_keydown_event = None
        while wait:
            event = pygame.event.wait()
            wait = True
            if event.type == pygame.KEYDOWN:
                if (event.key == pygame.K_ESCAPE) or (event.type == pygame.QUIT):
                    pygame.quit()
                    sys.exit()
                elif (event.key == pygame.K_p):
                    wait = False
                    if last_keydown_event is not None:
                        print("Adding event")
                        pygame.event.post(last_keydown_event)
                else:
                    last_keydown_event = event
                    print(f"Keydown event: {last_keydown_event}")

            elif event.type == pygame.MOUSEBUTTONDOWN:
                wait = False

    def wait_for_input(self):
        time.sleep(0.2)
        wait = True
        pygame.event.clear()
        while wait:
            event = pygame.event.wait()
            wait = True
            if event.type == pygame.KEYDOWN:
                if (event.key == pygame.K_ESCAPE) or (event.type == pygame.QUIT):
                    pygame.quit()
                    sys.exit()
                else:
                    wait = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                wait = False

    def run_physics_processing(self):
        self.physics_engine.update()

    def run_update(self):
        self.content.update()

    def run_step(self):

        self.run_event_processing()
        if not self.config.client_only_mode:
            self.run_physics_processing()
            self.run_update()
        self.tick()
        self.step_counter += 1

    def run(self):
        done = True
        while self.state == "RUNNING":
            if done:
                if not self.config.client_only_mode:
                    self.content.reset()
                    print("RESETTING")
            self.process_client_step()
            self.run_step()
            self.render_client_step()
            for player in list(self.player_manager.players_map.values()):
                # print(f"Player: {player.get_id()} {player.get_object_id()}")
                observation, reward, done, info, _ = self.content.get_step_info(
                    player)
            if self.config.step_mode:
                print(f"Waiting for input: t={clock.get_ticks()}")

                self.wait_for_input()


gamectx = GameContext()
