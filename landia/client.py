
import argparse
import json
import logging
import math
import os
import random
import socket
import struct
import sys
import threading
import time
from multiprocessing import Queue
from typing import List
from typing import Tuple

import lz4.frame

from .common import (TimeLoggingContainer)
from .camera import Camera
from .object import GObject
from .config import ClientConfig, GameConfig
from .content import Content
from .common import StateDecoder, StateEncoder, Base
from .player import Player
from .inputs import get_input_events
from .renderer import Renderer
from .utils import gen_id
from .event import InputEvent, Event
from .utils import TickPerSecCounter
from . import gamectx
from .clock import clock, StepClock
import gym
import sys

HEADER_SIZE = 16
LATENCY_LOG_SIZE = 10000


def receive_data(sock):
    done = False
    all_data = b''
    while not done:
        sock.settimeout(1.0)
        data, server = sock.recvfrom(4096)
        # TODO: Use qq for windows!!, not sure why
        chunk_num, chunks = struct.unpack('ll', data[:HEADER_SIZE])
        all_data += data[HEADER_SIZE:]
        if chunk_num == chunks:
            done = True
    bytes_in = sys.getsizeof(all_data)
    all_data = lz4.frame.decompress(all_data)
    return all_data.decode("utf-8"), bytes_in


def send_request(request_data, server_address):

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        data_st = json.dumps(request_data, cls=StateEncoder)
        # Send data
        data_bytes = bytes(data_st, 'utf-8')
        data_bytes = lz4.frame.compress(data_bytes)
        bytes_out = sys.getsizeof(data_bytes)
        sent = sock.sendto(data_bytes,
                           server_address)
        data, bytes_in = receive_data(sock)
        if data is None:
            raise Exception("No data found")
    finally:
        sock.close()
    return json.loads(data, cls=StateDecoder), bytes_out, bytes_in


class RemoteClient:
    """
    Stores session info 
    """

    def __init__(self, client_id):
        self.id = client_id
        self.last_snapshot_time_ms = 0
        self.latency_history = [None for i in range(LATENCY_LOG_SIZE)]
        self.player_id = None
        self.conn_info = None
        self.request_counter = 0
        self.unconfirmed_messages = set()
        self.outgoing_events: List[Event] = []

    def add_event(self, e: Event):
        self.outgoing_events.append(e)

    def clear_events(self):
        self.outgoing_events = []

    def pull_events_snapshot(self):
        results = []
        for e in self.outgoing_events:
            results.append(e.get_snapshot())
        self.clear_events()
        return results

    def add_latency(self, latency: float):
        self.latency_history[self.request_counter % LATENCY_LOG_SIZE] = latency
        self.request_counter += 1

    def avg(self):
        vals = [i for i in self.latency_history if i is not None]
        return math.fsum(vals)/len(vals)

    def get_id(self):
        return self.id

    def __repr__(self):
        return "Client: id: {}, player_id: {}".format(self.id, self.player_id)


class ClientConnector:
    # TODO, change to client + server connection

    def __init__(self, config: ClientConfig):
        self.config = config
        self.incomming_buffer: Queue = Queue()  # event buffer
        self.outgoing_buffer: Queue = Queue()  # state buffer
        self.running = True
        self.client_id = self.config.client_id
        self.total_bytes_out = 0
        self.total_bytes_in = 0
        self.total_tx = 0

        self.latency_log = [None for i in range(LATENCY_LOG_SIZE)]
        self.last_latency_ms = None
        self.last_latency_ticks = None
        self.request_counter = 0
        self.ticks_per_second = 20

        self.connection_clock = StepClock(self.ticks_per_second)
        self.tick_counter = TickPerSecCounter(2)
        self.last_received_snapshots = []
        self.sync_freq = 0
        self.last_sync = 0

        self.report_freq = 2
        self.last_report = time.time()

    def add_network_info(self, latency: int, success: bool):
        self.latency_log[self.request_counter % LATENCY_LOG_SIZE] = {
            'latency': latency, 'success': success}

    def get_avg_latency(self):
        vals = [i for i in self.latency_log if i is not None]
        return math.fsum(vals['latency'])/len(vals)

    def get_success_rate(self):
        vals = [i for i in self.latency_log if i is not None]
        success = sum([1 for v in vals if v['success']])
        return success/len(vals)

    def create_request(self):
        request_info = {
            'client_id': "" if self.client_id is None else self.client_id,
            "meta": self.config.meta,
            'snapshots_received': self.last_received_snapshots,
            'player_type': self.config.player_type,
            'is_human': self.config.is_human,
            'message': "UPDATE"
        }

        # Get items:
        outgoing_items = []
        done = False
        while (not done):
            if self.outgoing_buffer.qsize() == 0:
                done = True
                break
            outgoing_item = self.outgoing_buffer.get()
            if outgoing_item is None or len(outgoing_item) == 0:
                done = True
            else:
                outgoing_items.append(outgoing_item)

        start_time = time.time()
        try:
            response, bytes_out, bytes_in = send_request({
                'info': request_info,
                'items': outgoing_items},
                server_address=(self.config.server_hostname, self.config.server_port))
        except Exception as e:
            print(f"Error communicating with server [{e}]. \tRetrying...")
            return

        self.total_bytes_in += bytes_in
        self.total_bytes_out += bytes_out
        self.total_tx += 1
        self.last_latency = time.time() - start_time

        if response is None:
            print("Packet loss or error occurred")
            self.add_network_info(self.last_latency_ms, False)
        else:
            # Log latency
            self.add_network_info(self.last_latency_ms, True)
            response_info = response['info']
            self.last_received_snapshots = [
                response_info['snapshot_timestamp']]

            # set clock
            # TODO: also sync fps/clock from server
            if (time.time() - self.last_sync) >= self.sync_freq:
                server_game_time = response_info['server_time'] - 0.03
                # server_game_time = response_info['server_time'] + self.last_latency/2
                if abs(server_game_time - clock.get_game_time()) > 0.02:
                    clock.set_start_time(time.time() - server_game_time)
                self.last_sync = time.time()

            self.client_id = response_info['client_id']
            if response_info['message'] == 'UPDATE':
                self.incomming_buffer.put(response)
            self.request_counter += 1
        self.connection_clock.tick()
        self.tick_counter.tick()

        if (time.time() - self.last_report) > self.report_freq:
            # kbytes_out_summary = self.total_bytes_out/self.total_tx * self.ticks_per_second/1024
            # kbytes_in_summary = self.total_bytes_in/self.total_tx * self.ticks_per_second/1024
            t_delta = time.time() - self.last_report
            kbytes_out_summary = self.total_bytes_out/t_delta/1024
            self.total_bytes_out = 0
            kbytes_in_summary = self.total_bytes_in/t_delta/1024
            self.total_bytes_in = 0
            print(
                f"NET Tick rate {self.tick_counter.avg()},  out:{kbytes_out_summary}kB, in:{kbytes_in_summary}kB")

            self.last_report = time.time()

    def start_connection(self, callback=None):
        print("Starting connection to server")

        while self.running:
            self.create_request()


class GameClient:

    def __init__(self,
                 renderer: Renderer,
                 config: ClientConfig):

        self.config = config
        self.content: Content = gamectx.content
        # renderer.config.render_delay_in_ms  # tick gap + latency
        self.render_delay_in_ms = 0
        self.frames_per_second = config.frames_per_second
        self.frame_limit = False  # self.frames_per_second != gamectx.config.tick_rate

        self.server_info_history = TimeLoggingContainer(100)
        self.snapshot_history = TimeLoggingContainer(500)
        # TODO: move to history data managed for rendering consistency
        self.player: Player = None
        self.step_counter = 0
        self.renderer: Renderer = renderer
        self.tick_counter = TickPerSecCounter(2)
        self.last_obj_sync = 0

        if self.config.is_human:
            self.renderer.initialize()

        self.connector = None
        if self.config.is_remote:
            print("Creating remote connection")
            self.connector = ClientConnector(config=config)
            # TODO, separate process instead?
            self.connector_thread = threading.Thread(
                target=self.connector.start_connection, args=())
            self.connector_thread.daemon = True
            self.connector_thread.start()
        else:
            self.player = self.content.new_player(
                client_id=config.client_id,
                player_type=config.player_type,
                is_human=self.config.is_human,
                name=self.config.player_name)

    def send_local_events(self):
        event_snapshot = gamectx.event_manager.get_client_snapshot()
        if len(event_snapshot) > 0:
            if self.connector.outgoing_buffer.qsize() < 300:
                self.connector.outgoing_buffer.put(event_snapshot)
            else:
                print("Queue is large")
            gamectx.event_manager.clear()

    def sync_with_remote_state(self):
        if self.connector is None:
            return
        done = False
        while (not done):
            if self.connector.incomming_buffer.qsize() == 0:
                incomming_data = None
            else:
                incomming_data = self.connector.incomming_buffer.get()

            if incomming_data is None:
                done = True
                break
            else:
                self.snapshot_history.add(
                    incomming_data['info']['snapshot_timestamp'],
                    incomming_data['snapshot'])
                self.server_info_history.add(
                    incomming_data['info']['snapshot_timestamp'],
                    incomming_data['info'])

    def load_snapshot(self):

        snap1, snap1_timestamp, snap2, snap2_timestamp = self.snapshot_history.get_pair_by_timestamp(
            clock.get_ticks())

        snap = snap1
        if snap is None:
            snap = snap2

        if snap is not None:
            gamectx.load_snapshot(snap)

            if snap1 is not None and snap2 is not None:
                fraction = (clock.get_ticks()-snap1_timestamp) / \
                    (snap2_timestamp-snap1_timestamp)
                for odata in snap2['om']:
                    obj2 = Base.create_from_snapshot(odata)
                    obj1 = gamectx.get_object_by_id(obj2.get_id())
                    if obj1 is not None:
                        p1 = obj1.get_view_position()
                        p2 = obj2.get_view_position()
                        if p1 is not None and p2 is not None:
                            obj1.view_position = (p2 - p1) * fraction + p1

    def update_player_info(self):
        server_info_timestamp, server_info = self.server_info_history.get_latest_with_timestamp()
        if server_info is not None and server_info.get('player_id', "") != "":
            self.player = gamectx.player_manager.get_player(
                str(server_info['player_id']))

    def run_step(self):
        if self.player is not None:
            input_events = self.player.pull_input_events()
            if self.config.is_human:
                input_events.extend(get_input_events(self.player))

            for event in input_events:
                gamectx.event_manager.add_event(event)

        # Send events
        # Get Game Snapshot
        if self.connector is not None:
            self.send_local_events()
            self.sync_with_remote_state()
            self.load_snapshot()
            self.update_player_info()
        self.tick_counter.tick()
        self.step_counter += 1

    def render(self):
        # self.renderer.set_log_info("TPS: {} ".format(self.tick_counter.avg()))
        self.renderer.process_frame(player=self.player)
        self.content.post_process_frame(
            player=self.player, renderer=self.renderer)
        frame_output = self.renderer.render_frame()

        if self.config.is_human:
            self.renderer.play_sounds(gamectx.get_sound_events())
        return frame_output

    def get_rgb_array(self):
        return self.renderer.frame_cache
