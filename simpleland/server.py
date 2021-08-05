
import json
import logging
import math
import socketserver
import struct
import threading

import lz4.frame

from simpleland.config import  ServerConfig
from simpleland.common import StateDecoder, StateEncoder

from simpleland import gamectx
from .clock import clock

class UDPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        config: ServerConfig = self.server.config

        # Process Request data
        request_st = self.request[0]
        request_st = lz4.frame.decompress(request_st)
        request_st = request_st.decode('utf-8').strip()
        try:
            request_data = json.loads(request_st, cls=StateDecoder)
        except Exception as e:
            print(request_st)
            raise e

        request_info = request_data['info']

        request_message = request_info['message']
        client = gamectx.get_remote_client(request_info['client_id'])
        player = gamectx.get_player(client, player_type=request_info['player_type'],is_human=request_info['is_human'])
        snapshots_received = request_info['snapshots_received']

        # simulate missing parts
        skip_remove = False  # random.random() < 0.01

        # Reconnect?
        if len(snapshots_received) == 0:
            client.last_snapshot_time_ms = 0 

        for t in snapshots_received:
            if t in client.unconfirmed_messages:
                if skip_remove:
                    print("Skipping remove confirmation")
                    continue
                else:
                    client.unconfirmed_messages.remove(t)

        # Load events from client
        all_events_data = []
        for event_dict in request_data['items']:
            all_events_data.extend(event_dict)

        if len(all_events_data) > 0:
            gamectx.event_manager.load_snapshot(all_events_data)

        if len(client.unconfirmed_messages) >= config.max_unconfirmed_messages_before_new_snapshot:
            client.last_snapshot_time_ms = 0
            client.unconfirmed_messages = set()
        
        snapshot_timestamp, snapshot = gamectx.create_snapshot_for_client(client)
        
        client.unconfirmed_messages.add(snapshot_timestamp)

        # Build response data

        response_data = {}
        response_data['info'] = {
            'server_tick': clock.get_ticks(),
            'server_time': clock.get_game_time(),
            'message': "UPDATE",
            'client_id': client.get_id(),
            'player_id': player.get_id(),
            'snapshot_timestamp': snapshot_timestamp}
        response_data['snapshot'] = snapshot

        # Convert response to json then compress and send in chunks
        response_data_st = json.dumps(response_data, cls=StateEncoder)
        response_data_st = bytes(response_data_st, 'utf-8')
        response_data_st = lz4.frame.compress(response_data_st)

        chunk_size = config.outgoing_chunk_size
        chunks = math.ceil(len(response_data_st)/chunk_size)
        socket = self.request[1]
        for i in range(chunks+1):  # TODO: +1 ??? why
            header = struct.pack('ll', i+1, chunks)
            data_chunk = header + response_data_st[i*chunk_size:(i+1)*chunk_size]
            # current_thread = threading.current_thread()
            # Simulate packet loss
            # if random.random() < 0.01:
            #     print("random skip chunk")
            #     continue
            socket.sendto(data_chunk, self.client_address)

        client.last_snapshot_time_ms = snapshot_timestamp


# TODO: Have a thread snapshot at regular intervals
class GameUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):

    def __init__(self, conn, config, handler = UDPHandler):
        socketserver.UDPServer.__init__(self, conn, handler)
        self.config = config