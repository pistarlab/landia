import pygame
from typing import List, Dict
from .event import (Event, ViewEvent,InputEvent,AdminCommandEvent)

from .common import Vector2
from simpleland.player import Player

def get_default_key_map():
    key_map = {}
    key_map[pygame.K_a] = 1
    key_map[pygame.K_LEFT] = 1
    key_map[pygame.K_b] = 2
    key_map[pygame.K_c] = 3
    key_map[pygame.K_d] = 4
    key_map[pygame.K_RIGHT] = 4
    key_map[pygame.K_e] = 5
    key_map[pygame.K_f] = 6
    key_map[pygame.K_g] = 7
    key_map[pygame.K_h] = 99
    key_map[pygame.K_i] = 9
    key_map[pygame.K_j] = 10
    key_map[pygame.K_k] = 11
    key_map[pygame.K_l] = 12
    key_map[pygame.K_m] = 13
    key_map[pygame.K_n] = 14
    key_map[pygame.K_o] = 15
    key_map[pygame.K_p] = 16
    key_map[pygame.K_q] = 17
    key_map[pygame.K_r] = 18
    key_map[pygame.K_s] = 19
    key_map[pygame.K_DOWN] = 19
    key_map[pygame.K_t] = 20
    key_map[pygame.K_u] = 21
    key_map[pygame.K_v] = 22
    key_map[pygame.K_w] = 23
    key_map[pygame.K_UP] = 23
    key_map[pygame.K_x] = 24
    key_map[pygame.K_y] = 25
    key_map[pygame.K_z] = 26
    key_map[pygame.K_MINUS] = 80
    key_map[pygame.K_EQUALS] = 81
    key_map[pygame.K_ESCAPE] = 27
    key_map[pygame.K_SPACE] = 33
    key_map[pygame.K_LSHIFT] = 90
    key_map[pygame.K_BACKQUOTE] = 99
    key_map["QUIT"] = 27
    key_map["MOUSE_DOWN_1"] = 28
    key_map["MOUSE_DOWN_2"] = 29
    key_map["MOUSE_DOWN_3"] = 30
    key_map["MOUSE_DOWN_4"] = 31
    key_map["MOUSE_DOWN_5"] = 32


    return key_map
    
DEFAULT_KEYMAP = get_default_key_map()

# Used to check for key press
# Note: keys that should be checked for being press state should be added here
# key_down event will occur when another key is pressed. For example. if moving is iterrupted by an attack
key_list = []
key_list.append(pygame.K_q)
key_list.append(pygame.K_LEFT)
key_list.append(pygame.K_RIGHT)
key_list.append(pygame.K_DOWN)
key_list.append(pygame.K_LSHIFT)
key_list.append(pygame.K_UP)
key_list.append(pygame.K_e)
key_list.append(pygame.K_f)
key_list.append(pygame.K_r)
key_list.append(pygame.K_w)
key_list.append(pygame.K_q)
key_list.append(pygame.K_g)
key_list.append(pygame.K_x)
key_list.append(pygame.K_z)
key_list.append(pygame.K_v)
key_list.append(pygame.K_b)
key_list.append(pygame.K_c)
key_list.append(pygame.K_s)
key_list.append(pygame.K_a)
key_list.append(pygame.K_d)

import sys
def get_input_events(player:Player) -> List[Event]:

    player_id = player.get_id()
    events: List[Event] = []

    # GATHER CONSOLE INPUT
    if player.get_data_value("INPUT_MODE") == "CONSOLE":
        text = player.get_data_value("CONSOLE_TEXT","")
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    player.set_data_value("INPUT_MODE","PLAY")
                    print("Exiting console mode")
                    break
                elif event.key == pygame.K_RETURN:
                    player.set_data_value("CONSOLE_RUN",True)
                    events.append(AdminCommandEvent(value=text,player_id=player_id))
                    player.set_data_value("CONSOLE_TEXT","")
                    player.set_data_value("INPUT_MODE","PLAY")
                    break
                elif event.key == pygame.K_BACKSPACE:
                    player.set_data_value("CONSOLE_TEXT",text[:-1]) 
                else:
                    text+= event.unicode
                    player.set_data_value("CONSOLE_RUN",False)
                    player.set_data_value("CONSOLE_TEXT",text)                  
        return events

    key_down = set()
    key_up = set()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            key_down.add(27)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            key_down.add(DEFAULT_KEYMAP.get("MOUSE_DOWN_{}".format(event.button)))
        elif event.type == pygame.KEYDOWN:
            key_down.add(DEFAULT_KEYMAP.get(event.key))
        elif event.type == pygame.KEYUP:
            key_up.add(DEFAULT_KEYMAP.get(event.key))

    key_press_state = pygame.key.get_pressed()
    for key in key_list:
        if key_press_state[key]:
            key_down.add(DEFAULT_KEYMAP[key])

    input_received = len(key_down) >0 or len(key_down) >0 or len(key_up)
    if input_received :
        event = InputEvent(
            player_id  = player_id, 
            input_data = {
                'keyup':list(key_up),
                'keydown':list(key_down),
                'mouse_pos': pygame.mouse.get_pos(),
                'mouse_rel': pygame.mouse.get_rel(),
                'focused': pygame.mouse.get_focused()
                })
        events.append(event)

    return events