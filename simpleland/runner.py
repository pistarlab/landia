
import argparse
import json
import logging
import math
import socketserver
import struct
import threading

import lz4.frame
from pyinstrument import Profiler
from simpleland.client import GameClient

from simpleland.config import GameDef, PlayerDefinition, ServerConfig
from simpleland.content import Content
from simpleland.common import StateDecoder, StateEncoder


from simpleland.registry import load_game_content, load_game_def
from simpleland.renderer import Renderer
from simpleland.utils import gen_id
import traceback
from simpleland import gamectx
from simpleland.server import GameUDPServer, UDPHandler 
import signal
import sys

LOG_LEVELS = {
    'critical': logging.CRITICAL,
    'error': logging.ERROR,
    'warn': logging.WARNING,
    'warning': logging.WARNING,
    'info': logging.INFO,
    'debug': logging.DEBUG
}

def get_game_def(
        game_id,
        enable_server,
        remote_client,
        port,
        tick_rate=None,
        content_overrides={}
) -> GameDef:
    game_def = load_game_def(game_id, content_overrides)

    game_def.server_config.enabled = enable_server
    game_def.server_config.hostname = '0.0.0.0'
    game_def.server_config.port = port

    # Game
    game_def.game_config.tick_rate = tick_rate

    game_def.game_config.client_only_mode = not enable_server and remote_client
    return game_def


def get_player_def(
        enable_client,
        client_id,
        remote_client,
        hostname,
        port,
        player_type,
        resolution=None,
        fps=None,
        render_shapes=None,
        is_human=True,
        draw_grid = False,
        tile_size=16,
        debug_render_bodies=False,
        view_type=0,
        sound_enabled = True,
        show_console = True,
        enable_resize=False,
        include_state_observation = False,
        disable_hud = False) -> PlayerDefinition:
    player_def = PlayerDefinition()

    player_def.client_config.player_type = player_type
    player_def.client_config.client_id = client_id

    player_def.client_config.enabled = enable_client
    player_def.client_config.server_hostname = hostname
    player_def.client_config.server_port = port
    player_def.client_config.frames_per_second = fps
    player_def.client_config.is_remote = remote_client
    player_def.client_config.is_human = is_human
    player_def.client_config.include_state_observation = include_state_observation

    player_def.renderer_config.resolution = resolution
    player_def.renderer_config.render_shapes = render_shapes
    player_def.renderer_config.draw_grid = draw_grid
    player_def.renderer_config.tile_size = tile_size
    player_def.renderer_config.debug_render_bodies = debug_render_bodies
    player_def.renderer_config.view_type = view_type
    player_def.renderer_config.sound_enabled =sound_enabled
    player_def.renderer_config.show_console =show_console
    player_def.renderer_config.enable_resize = enable_resize
    player_def.renderer_config.disable_hud = disable_hud
    return player_def

def get_arguments(override_args=None):
    parser = argparse.ArgumentParser()

    # Server
    parser.add_argument("--enable_server",  action="store_true", help="Accepts remote clients")

    # Client
    parser.add_argument("--enable_client",  action="store_true", help="Run Client")
    parser.add_argument("--remote_client",   action="store_true", help="client uses server")

    parser.add_argument("--resolution", default="800x600", help="resolution eg, [f,640x480]")
    parser.add_argument("--hostname", default="localhost", help="hostname or ip, default is localhost")
    parser.add_argument("--client_id", default=gen_id(), help="user id, default is random")
    parser.add_argument("--render_shapes", action='store_true', help="render actual shapes")
    parser.add_argument("--fps", default=60, type=int, help="fps")
    parser.add_argument("--player_type", default=0, type=int, help="Player type (0=default, 10=observer_only)")
    parser.add_argument("--view_type", default=0, type=int, help="NOT USED at moment: View type (0=perspective, 1=world)")
    parser.add_argument("--tile_size", default=16, type=int, help="not = no grid")
    parser.add_argument("--debug_render_bodies", action="store_true", help=" render")
    parser.add_argument("--disable_sound", action="store_true", help="disable_sound")
    parser.add_argument("--draw_grid", action="store_true", help="draw_grid")
    parser.add_argument("--show_console", action="store_true", help="Show on screen info")
    parser.add_argument("--disable_hud", action="store_true", help="Disable all screen printing")
    parser.add_argument("--enable_resize", action="store_true", help="Enable Screen Resize")

    # used for both client and server
    parser.add_argument("--port", default=10001, help="the port the server is running on")

    # Game Options
    parser.add_argument("--enable_profiler", action="store_true", help="Enable Performance profiler")
    parser.add_argument("--tick_rate", default=60, type=int, help="tick_rate")

    parser.add_argument("--game_id", default="survival_grid", help="id of game")
    parser.add_argument("--content_overrides", default="{}", type=str,help="JSON string containing content updates. eg --content_overrides='{\"player_start_energy\":35}'")
    parser.add_argument("--log_level",default="info",help=", ".join(list(LOG_LEVELS.keys())),type=str)
    return  parser.parse_args(override_args)


def run(args):
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
    
    logging.getLogger().setLevel(LOG_LEVELS.get(args.log_level))
    print(args.__dict__)

    if not args.enable_server and not args.enable_client and not args.remote_client:
        args.enable_client = True

    if args.enable_server and args.enable_client and args.remote_client:
        print("Error: Server and Remote Client cannot be started from the same process. Please run seperately.")
        exit(1)

    profiler = None
    if args.enable_profiler:
        print("Profiling Enabled..")
        profiler = Profiler()
        profiler.start()

    game_def = get_game_def(
        game_id=args.game_id,
        enable_server=args.enable_server,
        remote_client=args.remote_client,
        port=args.port,
        tick_rate=args.tick_rate,
        content_overrides = json.loads(args.content_overrides)
    )

    # Get resolution
    if args.enable_client and args.resolution == 'f':
        import pygame
        pygame.init()
        infoObject = pygame.display.Info()
        resolution = (infoObject.current_w, infoObject.current_h)
    else:
        res_string = args.resolution.split("x")
        resolution = (int(res_string[0]), int(res_string[1]))

    player_def = get_player_def(
        enable_client=args.enable_client,
        client_id=args.client_id,
        remote_client=args.remote_client,
        hostname=args.hostname,
        port=args.port,
        render_shapes=args.render_shapes,
        resolution=resolution,
        fps=args.fps,
        draw_grid = args.draw_grid,
        player_type=args.player_type,
        tile_size=args.tile_size,
        debug_render_bodies = args.debug_render_bodies,
        view_type = args.view_type,
        sound_enabled= not args.disable_sound,
        show_console= args.show_console,
        enable_resize = args.enable_resize,
        disable_hud = args.disable_hud

    )

    content: Content = load_game_content(game_def)

    gamectx.initialize(
        game_def,
        content=content)

    if player_def.client_config.enabled:
        renderer = Renderer(
            config = player_def.renderer_config,
            asset_bundle=content.get_asset_bundle())

        client = GameClient(
            renderer=renderer,
            config=player_def.client_config)

        gamectx.add_local_client(client)

    server = None

    def graceful_exit(signum=None, frame=None):
        print("Shutting down")
        if game_def.server_config.enabled:
            # server.shutdown()
            server.server_close()

        if args.enable_profiler:
            profiler.stop()
            print(profiler.output_text(unicode=True, color=True))
        exit()
    signal.signal(signal.SIGINT, graceful_exit)

    try:
        if game_def.server_config.enabled:
            
            server = GameUDPServer(
                conn=(game_def.server_config.hostname, game_def.server_config.port),
                config=game_def.server_config)

            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            print("Server started at {} port {}".format(game_def.server_config.hostname, game_def.server_config.port))

        gamectx.run()
    except (Exception,KeyboardInterrupt) as e:
        print(traceback.format_exc())
        print(e)
    finally:        
        graceful_exit()

if __name__ == "__main__":
    args = get_arguments()
    run(args)

    

