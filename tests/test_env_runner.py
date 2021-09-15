import pytest
from landia.env import LandiaEnv, LandiaEnvSingle
import time
from landia.clock import clock


def test_env():
    agent_map = {str(i):{} for i in range(4)}
    env = LandiaEnv(agent_map=agent_map,dry_run=False)
    start_time = time.time()
    max_steps = 2000

    dones = {"__all__":True}
    episode_count = 0
    actions = {}
    all_rewards = []

    for i in range(0,max_steps):
        if dones.get('__all__'):
            obs = env.reset()
            rewards, dones, infos = {}, {'__all__':False},{}
            episode_count+=1
        else:
            obs, rewards, dones, infos = env.step(actions)
        
        all_rewards.extend(rewards.values())
            
        actions = {agent_id:env.action_spaces[agent_id].sample() for agent_id in obs.keys()}

    steps_per_sec = max_steps/(time.time()-start_time)
    print(f"total_rewards {sum(all_rewards)}")
    print(f"steps_per_sec {steps_per_sec}")
    assert True


def test_gym_env():
    env = LandiaEnvSingle()
    start_time = time.time()
    max_steps = 2000

    all_rewards = []
    done=True
    action=None

    for i in range(0,max_steps):
        if done:
            ob = env.reset()
            reward, done, info = None, False, {}
        else:
            ob, reward, done, info = env.step(action)
        action = env.action_space.sample()


    steps_per_sec = max_steps/(time.time()-start_time)
    print(f"total_rewards {sum(all_rewards)}")
    print(f"steps_per_sec {steps_per_sec}")
    assert True