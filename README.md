# piSTAR Landia

## Overview
A 2d game framework designed to provide a simple playground for AI (Reinforcement Learning) agents. Humans are also welcome.

**Version: 0.0.1-dev**: Early release so likely has bugs. Tested on Ubuntu and Windows 10.

## Screen Shots

Infection Tag

<img src="docs/infect.gif" alt="drawing" width="400"/>

<br/>
<br/>

Capture the flag

<img src="docs/ctf.gif" alt="drawing" width="400"/>

<br/>

## Features
- Multi-agent support
- Openai gym interface for pingle agent play
- Network play support (early development)
- Support for concurrent  game modes (eg: Tag + Survival)
- Written in Python and requires only a few dependencies.
- Highly configurable and hackable. Easily add new game modes, objects or maps.
- Admin View for Multi-Agent matches
- Game Modes included:
    - Capture the flag
    - Survival (collect food or die, avoid monsters)
    - Tag
    - Infection Tag
- Crafting System
- Reasonable performance and low memory footprint with plenty of room for future improvements.

## Known Issues
- Limited number of objects
- Network play is laggy and does not scale to more than a few remoe users.
- Incomplete documentation and testing
- Network play uses more bandwidth than needed.
- No runtime full game reset

[Future Imporvements](PLANNED.md)

## Performance
There are many factors that can impact FPS including: map size, number of game objects, resolution, number of agents, and game logic.

Test below are for 1 agent @ 84x84 on an i7 Laptop
 - small maps 2500+ FPS
 - large maps 800+ FPS

Full resolution human players can expect several hundred FPS
## Requirements
- python 3.7 or newer installed
- pygame (rendering)
- l4z (network compression)
- pyinstrument (performance profiling)
- gym (usage of OpenAI Gym spaces and env interface)

## Installation

### Standard (includes package only)
1. Make sure python 3.7 or newer is installed
1. ```pip install https://github.com/pistarlab/landia/archive/refs/heads/main.zip#egg=landia```

### Developer (includes code base)
1. Make sure python 3.7 or newer is installed
1. Download Repo:  ```git clone https://github.com/pistarlab/landia```
1. enter repo directory: ```cd landia```
1. (Optional) if using Anaconda, create conda environment: ```conda create -n landia```
1. Install requirements via pip: ```pip install -e .```


## Usage

### Local Game only (Human play)

```bash
landia
```

### Run Server and Local Client (Human play)

```bash
landia --enable_server --enable_client
```

### Connect to remote host
```bash
landia --enable_client --remote_client --hostname=SERVER_HOSTNAME 
```
### Run Random Agent Test
```bash
landia_test_env --agent_count=2 --max_steps=800000
```

### Controls

Standard player
```
~ : brings up console
wsda : movement: up/down/right/left

CONTROLS:
  console/show help   : ` or h (ESC to return to PLAY MODE
  camera mode         : m (ESC to return to PLAY MODE
  move                : w,s,d,a or UP,DOWN,LEFT,RIGHT
  push                : g
  grab                : e
  item  - menu select : z,c
  item  - use         : r
  craft - menu select : v,b
  craft - create      : q
  game step duration   : \"-\" (faster)/\"=\" (slower) 

CONSOLE COMMANDS:")
  reset             : Reset Game
  spawn <object_config_id> : Spawn Object
  save              : save game state
  load              : load game state

```

## Game Modes
### Capture The Flag

- Rules
    - two teams, red and blue, try to catpure each other flags
    - capture the flag 3 times to win the round
    - round time limit to 1000 timesteps
    - attack opposing players to make them respawn/drop flag
- Rewards
    - +1 when getting opposing teams flag
    - +1 when retrieving agent's own flag
    - +10 when capturing the opposing teams flag

### Infection

- Rules
    - infected players (blue tag) try to infect non infected players
- Rewards
    - -2  if infected at end of round
    - +10 if not infected by end of round
    - +1 when retrieving agent's own flag

### Forager

- Rules
    - Try to collect food and avoid dying of starvation or by being attacked
- Rewards


## Configuration

After running Landia for the first time, a configuration and save directory will be created in your home folder. Example: HOME_DIR/landia.

Files within this folder can override any the default configuration:

- HOME_DIR/landia/assets/ will override the [landia/assets](landia/assets) folder
- HOME_DIR/landia/survival/default/base_config.json will override the [landia/survival/config/base_config.json](landia/survival/config/base_config.json)

### Maps

Maps are loaded from text files where each game tile/game object is represented by a two digit code. (eg r1=rock)  The code lookup index is defined by the game config file.

Example Predefined maps
* [Capture the flag 1](landia/survival/config/ctf_map_1.txt)
* [Capture the flag 2](landia/survival/config/ctf_map_2.txt)
* [Large Map](landia/survival/config/map_layer_1.txt)

**Custom Maps** must be defined in the game config and will be loaded from the HOME_DIR/landia/ directory if found

### Save location
World saves will be stored in the HOME_DIR/landia/survival/default/saves folder


## Reinforcement Learning Environment Usage

MultiAgent and Gym RL interfaces are here:
[env.py]( landia/env.py)

* Observation Spaces: 42x42 RGB Images
* Action Space: 

### Multi-Agent Interfcae with Random Agent
This multi agent interface is compatible on the RAY RLlib project's [multi_agent_env.py](https://github.com/ray-project/ray/blob/master/rllib/env/multi_agent_env.py) interface.

```python
from landia.env import LandiaEnv
agent_map = {str(i):{} for i in range(4)} #define 4 agents
env = LandiaEnv(agent_map=agent_map)
max_steps = 2000

dones = {"__all__":True}
episode_count = 0
actions = {}

for i in range(0,max_steps):
    if dones.get('__all__'):
        obs = env.reset()
        rewards, dones, infos = {}, {'__all__':False},{}
        episode_count+=1
    else:
        obs, rewards, dones, infos = env.step(actions)
    actions = {agent_id:env.action_spaces[agent_id].sample() for agent_id in obs.keys()}

```


### Gym Interface with Random Agent

Single agent [Gym](https://gym.openai.com/) environment interface

```python
from landia.env import LandiaEnvSingle

env = LandiaEnvSingle()
max_steps = 2000
done=True
action = None
for i in range(0,max_steps):
    if done:
        ob = env.reset()
        reward, done, info = None, False, {}
    else:
        ob, reward, done, info = env.step(action)
    action = env.action_space.sample()

```


## Development

The landia code base is divided into two parts two allow support for future games under the same framework
- game code: currently under landia/survival
- framework code: landia/

TODO: More documentation

## Acknowledgments

- My kids for their inspiration and help testing
- Vryell's Tiny Adventure Pack. Currently used for most of the game art
    - See: https://vryell.itch.io/tiny-adventure-pack

