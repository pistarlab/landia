import pytest
from simpleland.env import SimplelandEnv
import time
from simpleland.clock import clock


def test_env():
    agent_map = {str(i):{} for i in range(1)}
    debug = False
    env = SimplelandEnv(agent_map=agent_map,dry_run=False)
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
        if debug:
            actions={}
            for id, ob in obs.items():
                action = env.action_spaces[id].sample()
                try:
                    action = int(action)
                except:
                    action = None
                actions[id]=action
        else:
            actions = {agent_id:env.action_spaces[agent_id].sample() for agent_id in env.obs.keys()}

    steps_per_sec = max_steps/(time.time()-start_time)
    print(f"total_rewards {sum(all_rewards)}")
    print(f"steps_per_sec {steps_per_sec}")
    assert True
