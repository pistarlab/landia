import time
from typing import List, Dict

import numpy as np
import pygame
from .utils import gen_id
from .event_manager import EventManager
from .event import Event

from .player import Player

class PlayerManager:

    def __init__(self):
        self.players_map: Dict[str, Player] = {}

    def add_player(self, player: Player):
        """

        :param player:
        :return:
        """
        self.players_map[str(player.uid)] = player

    def get_player(self, uid) -> Player:
        return self.players_map.get(str(uid), None)

    def pull_events(self) -> List[Event]:
        all_player_events: List[Event] = []
        for player in self.players_map.values():
            all_player_events.extend(player.pull_input_events())
        return all_player_events

    def get_snapshot(self):
        players = list(self.players_map.values())
        results = {}
        for p in players:
            results[p.get_id()]= p.get_snapshot()
        return results

    def load_snapshot(self,data):
        new_players = []
        for k,p_data in data.items():
            if k in self.players_map:
                self.players_map[k].load_snapshot(p_data)
            else:
                new_p = Player.build_from_dict(p_data)
                self.players_map[str(k)] = new_p
                new_players.append(new_p)
        return new_players