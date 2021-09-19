
import argparse
import logging
import re
from landia.registry import load_game_content, GameDef
import gym
from gym import spaces
import logging
from landia.runner import get_game_def, get_player_def, UDPHandler, GameUDPServer, LOG_LEVELS
from landia.event import InputEvent
import threading
import sys
from landia.player import Player
from landia.renderer import Renderer
from landia.utils import gen_id
from landia import gamectx
from landia.client import GameClient
from landia.registry import load_game_def, load_game_content
import time
from typing import Dict, Any
import numpy as np
from landia.utils import merged_dict
from pyinstrument import Profiler
from landia.clock import clock
import os
import random

class LandiaEnv:

    def __init__(self,
                 resolution=(42, 42),
                 admin_resolution=[1280, 720],
                 game_id="survival",
                 hostname='localhost',
                 port=10001,
                 dry_run=False,
                 agent_map={'1': {}, '2': {}},
                 tick_rate=0,
                 enable_server=False,
                 view_type=0,
                 render_shapes=False,
                 player_type="default",
                 include_state_observation=False,
                 remote_client=False,
                 render_to_screen=False,
                 setup_config={},
                 content_overrides={},
                 config_filename="base_config.json",
                 seed=1):
        random.seed(seed)
        game_def = get_game_def(
            game_id=game_id,
            enable_server=enable_server,
            port=port,
            remote_client=remote_client,
            tick_rate=tick_rate,
            content_overrides=content_overrides,
            config_filename=config_filename)

        self.content = load_game_content(game_def)

        gamectx.initialize(
            game_def=game_def,
            content=self.content)

        # Build Clients
        self.agent_map = agent_map
        self.agent_clients = {}
        self.remote_client = remote_client

        # PISTARLAB REQUIREMENTS
        self.players = list(self.agent_map.keys())
        self.num_players = len(self.players)
        self.possible_players = self.players
        self.max_num_players = self.num_players
        self.min_num_players = 1

        self.admin_player_def = get_player_def(
            enable_client=False,
            client_id="admin",
            remote_client=remote_client,
            hostname=hostname,
            port=port,
            resolution=admin_resolution,
            fps=tick_rate,
            sound_enabled=False,
            render_shapes=render_shapes,
            render_to_screen=True,
            player_type="admin",
            is_human=False,
            view_type=view_type,
            include_state_observation=include_state_observation)
        self.admin_player_def.renderer_config.show_console = False

        if not render_to_screen:
            self.admin_player_def.renderer_config.sdl_video_driver = "dummy"

        self.admin_client = GameClient(
            renderer=Renderer(
                self.admin_player_def.renderer_config,
                asset_bundle=self.content.get_asset_bundle()
            ),
            config=self.admin_player_def.client_config)
        self.admin_client.renderer.initialize()

        player_def = None
        for agent_id, info in agent_map.items():
            player_name = info.get("name")
            skip = info.get("skip", False)
            if skip:
                continue
            team_name = info.get("team_name")
            role = info.get("role", "player")
            ignore_team_assignments = setup_config.get(
                "ignore_team_assignments", False)
            if team_name is None or ignore_team_assignments:
                client_id = agent_id
            else:
                client_id = f"{role}?{team_name}_{agent_id}"
            player_def = get_player_def(
                enable_client=True,
                client_id=client_id,
                player_name=player_name,
                remote_client=remote_client,
                hostname=hostname,
                port=port,
                sound_enabled=False,
                resolution=resolution,
                fps=tick_rate,
                render_shapes=render_shapes,
                render_to_screen=False,
                player_type=player_type,
                is_human=False,
                view_type=view_type,
                include_state_observation=include_state_observation)

            # Render config changes
            player_def.renderer_config.sdl_audio_driver = 'dsp'
            player_def.renderer_config.sound_enabled = False
            player_def.renderer_config.show_console = False

            renderer = Renderer(
                player_def.renderer_config,
                asset_bundle=self.content.get_asset_bundle()
            )

            # print(player_def.client_config)
            client = GameClient(
                renderer=renderer,
                config=player_def.client_config)
            gamectx.add_local_client(client)
            self.agent_clients[agent_id] = client

        self.dry_run = dry_run

        # TODO: make different for each client
        self.action_spaces = {agent_id: self.content.get_action_space(
        ) for agent_id in self.agent_clients.keys()}
        if include_state_observation:
            self.observation_spaces = {agent_id: self.content.get_observation_space(agent_id
                                                                                    ) for agent_id in self.agent_clients.keys()}
        else:
            # TODO: Not working at momement
            self.observation_spaces = {agent_id: spaces.Box(low=0, high=255, shape=(
                resolution[0], resolution[1], 3)) for agent_id in self.agent_clients.keys()}

        self.step_counter = 0

        self.ob = None
        self.safe_mode = True
        self.running = True
        self.server = None
        self.first_start = True

        if game_def.server_config.enabled:
            self.server = GameUDPServer(
                conn=(game_def.server_config.hostname,
                      game_def.server_config.port),
                handler=UDPHandler,
                config=game_def.server_config)

            server_thread = threading.Thread(target=self.server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            logging.info(
                f"Server started at {game_def.server_config.hostname} port {game_def.server_config.port}")

    def step(self, actions):

        # get actions from agents
        for agent_id, action in actions.items():
            client: GameClient = self.agent_clients[agent_id]
            if self.dry_run:
                return self.observation_spaces[agent_id], 1, False, None
            if client.player is not None:
                event = InputEvent(
                    player_id=client.player.get_id(),
                    input_data={
                        'keydown': [self.content.agent_key_list[action]],
                        'keyup': [],
                        'mouse_pos': "",
                        'mouse_rel': "",
                        'focused': ""
                    })
                client.player.add_event(event)
            client.run_step()

        gamectx.run_step()

        obs = {}
        dones = {}
        rewards = {}
        infos = {}

        for agent_id, client in self.agent_clients.items():
            ob, reward, done, info, skip = self.content.get_step_info(
                player=client.player, include_state_observation=client.config.include_state_observation)
            if skip:
                continue
            if not client.config.include_state_observation:
                client.render()
                ob = client.get_rgb_array()
            obs[agent_id] = ob
            dones[agent_id] = done
            rewards[agent_id] = reward
            infos[agent_id] = info

        dones['__all__'] = self.content.reset_required()

        self.step_counter += 1

        return obs, rewards, dones, infos

    def stats(self, player_id=None):
        return {'step_counter': self.step_counter}

    def runtime_config(self):
        return {'hi': self.step_counter}

    def runtime_config_update(self):
        return True, "msg"

    def render(self, mode=None, player_id=None):
        if player_id is None:
            self.admin_client.run_step()
            self.admin_client.render()
            return self.admin_client.get_rgb_array()
        else:
            client = self.agent_clients[player_id]
            return client.get_rgb_array()

    def reset(self) -> Dict[str, Any]:
        if not self.remote_client:
            self.content.reset()
        self.obs, _, _, _ = self.step({})
        return self.obs

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()


class LandiaEnvSingle(gym.Env):

    def __init__(self,
                 resolution=(42, 42),
                 admin_resolution=(1280, 720),
                 content_overrides={},
                 config_filename="base_config.json",
                 render_shapes=True,
                 dry_run=False,
                 player_type="default",
                 render_to_screen=False,
                 view_type=1,
                 tick_rate=0):
        self.agent_id = "1"
        self.env_main = LandiaEnv(
            resolution=resolution,
            admin_resolution=admin_resolution,
            agent_map={self.agent_id: {}},
            enable_server=False,
            dry_run=dry_run,
            tick_rate=tick_rate,
            config_filename=config_filename,
            content_overrides=content_overrides,
            view_type=view_type,
            player_type=player_type,
            render_shapes=render_shapes,
            render_to_screen=render_to_screen)
        self.observation_space = self.env_main.observation_spaces[self.agent_id]
        self.action_space = self.env_main.action_spaces[self.agent_id]

    def reset(self):
        obs = self.env_main.reset()
        return obs.get(self.agent_id)

    def step(self, action):
        obs, rewards, dones, infos = self.env_main.step(
            {self.agent_id: action})
        ob, reward, done, info = obs[self.agent_id], rewards[self.agent_id], dones[self.agent_id], infos[self.agent_id]
        return ob, reward, done, info

    def close(self):
        self.env_main.close()

    def render(self, mode=None):
        return self.env_main.render(mode=mode)


def multi_agent_run(resolution, admin_resolution, args):

    max_steps = args.max_steps

    agent_map = {str(i): {} for i in range(args.agent_count)}
    verbose = args.verbose
    compute_profile = args.compute_profile
    mem_profile = args.mem_profile
    render = args.render
    if mem_profile:
        import tracemalloc
        tracemalloc.start()

    env = LandiaEnv(
        agent_map=agent_map,
        remote_client=args.remote_client,
        resolution=resolution,
        admin_resolution=admin_resolution,
        dry_run=False,
        tick_rate=args.tick_rate,
        config_filename=args.config_filename,
        content_overrides={},
        render_to_screen=render)

    start_time = time.time()
    profiler = None
    if compute_profile:
        profiler = Profiler()
        profiler.start()
    dones = {"__all__": True}
    episode_count = 0
    actions = {}

    logging.info("OBSERVATION SPACES")
    for name, space in env.observation_spaces.items():
        logging.info(f"\t{name}: {space.__class__.__name__}")

    logging.info("ACTION SPACES")
    for name, space in env.action_spaces.items():
        logging.info(f"\t{name}: {space.__class__.__name__}")

    i = 0
    while i < max_steps or max_steps == 0:
        if dones.get('__all__'):
            obs = env.reset()
            rewards, dones, infos = {}, {'__all__': False}, {}
            episode_count += 1
        else:
            obs, rewards, dones, infos = env.step(actions)
        actions = {
            agent_id: env.action_spaces[agent_id].sample() for agent_id in obs.keys()}
        if verbose:
            for id, ob in obs.items():
                if render:
                    env.render(player_id=id)
                reward = None
                done = None
                info = None
                if len(rewards) > 0:
                    reward = rewards[id]
                    done = dones[id]
                    info = infos[id]

                if id in actions:
                    action = actions[id]
                    logging.info(
                        f"Episode {episode_count} Game Step:{clock.get_ticks()}, Reward: {reward}, {done}, {info} -> Action {action}")

        if render:
            env.render()

        if mem_profile and (env.step_counter % 100 == 0):
            current, peak = tracemalloc.get_traced_memory()
            logging.info(
                f"Current memory usage is {current / 10**6}MB; Peak was {peak / 10**6}MB")
        i += 1

    if mem_profile:
        current, peak = tracemalloc.get_traced_memory()
        logging.info(
            f"Current memory usage is {current / 10**6}MB; Peak was {peak / 10**6}MB")
        tracemalloc.stop()
    steps_per_sec = max_steps/(time.time()-start_time)
    logging.info(f"steps_per_sec {steps_per_sec}")
    if compute_profile:
        profiler.stop()
        logging.info(profiler.output_text(
            unicode=True, color=True, show_all=True))


def single_agent_run(resolution, admin_resolution, args):
    """
    Test random agent
    """

    max_steps = args.max_steps
    verbose = args.verbose
    compute_profile = args.compute_profile
    mem_profile = args.mem_profile
    render = args.render
    if mem_profile:
        import tracemalloc
        tracemalloc.start()

    env = LandiaEnvSingle(
        resolution=resolution,
        admin_resolution=admin_resolution,
        dry_run=False,
        tick_rate=args.tick_rate,
        content_overrides={},
        config_filename=args.config_filename,
        render_to_screen=render)

    start_time = time.time()
    profiler = None
    if compute_profile:
        profiler = Profiler()
        profiler.start()
    done = True
    episode_count = 0
    action = None

    logging.info("OBSERVATION SPACE")
    logging.info(f"{env.observation_space.__class__.__name__}")

    logging.info("---")

    logging.info("ACTION SPACE")
    logging.info(f"{env.action_space.__class__.__name__}")

    i = 0
    while i < max_steps or max_steps == 0:
        if done:
            ob = env.reset()
            reward, done, info = None, False, {}
            episode_count += 1
        else:
            ob, reward, done, info = env.step(action)
        action = env.action_space.sample()
        if verbose:
            logging.info(
                f"Episode {episode_count} Game Step:{clock.get_ticks()}, Reward: {reward}, {done}, {info} -> Action {action}")
        else:
            if render:
                env.render()

        if mem_profile and (env.step_counter % 1000 == 0):
            current, peak = tracemalloc.get_traced_memory()
            logging.info(
                f"Current memory usage is {current / 10**6}MB; Peak was {peak / 10**6}MB")
        i += 1

    if mem_profile:
        current, peak = tracemalloc.get_traced_memory()
        logging.info(
            f"Current memory usage is {current / 10**6}MB; Peak was {peak / 10**6}MB")
        tracemalloc.stop()
    steps_per_sec = max_steps/(time.time()-start_time)
    logging.info(f"steps_per_sec {steps_per_sec}")
    if compute_profile:
        profiler.stop()
        logging.info(profiler.output_text(
            unicode=True, color=True, show_all=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--single_mode", action="store_true")
    parser.add_argument("--render", action="store_true", help="Render")
    parser.add_argument("--mem_profile", action="store_true")
    parser.add_argument("--max_steps", default=10000, type=int)
    parser.add_argument("--compute_profile", action="store_true")
    parser.add_argument("--agent_count", default=4,
                        type=int, help="Number test of agents")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--remote_client", action="store_true")
    parser.add_argument("--tick_rate", default=0, type=int)
    parser.add_argument("--resolution", default="42x42", type=str)
    parser.add_argument("--admin_resolution", default="400x400", type=str)
    parser.add_argument("--config_filename",
                        default="base_config.json", type=str)

    parser.add_argument("--log_level", default="info",
                        help=", ".join(list(LOG_LEVELS.keys())), type=str)

    args = parser.parse_args()

    logging.getLogger().setLevel(LOG_LEVELS.get(args.log_level))

    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    res_string = args.resolution.split("x")
    resolution = (int(res_string[0]), int(res_string[1]))
    admin_res_string = args.admin_resolution.split("x")
    admin_resolution = (int(admin_res_string[0]), int(admin_res_string[1]))

    if args.single_mode:
        logging.info("Single-Agent Mode")
        single_agent_run(resolution, admin_resolution, args)
    else:
        logging.info("Multi-Agent Mode")
        multi_agent_run(resolution, admin_resolution, args)


if __name__ == "__main__":
    main()
