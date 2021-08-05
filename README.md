# SimpleLand

## Overview
A 2d game framework designed to provide playground for reinforcement learning agents. Humans can play too.

**Version: 0.0.1-dev**: Early release not ready for general use.

## Screen Shots
<img src="docs/screen_shot0.png" alt="drawing" width="400"/>
<br/>
<br/>

<img src="docs/screen_shot_zoomout1.png" alt="drawing" width="400"/>
<br/>
<br/>

## Features
- Multi Agent Support
- Openai gym interface for Single Agent Play
- Network Play support (Early Development)
- Crafting Support
- Support for concurrent modes (eg: Tag + Survival)
- Written in Python and requires only a few dependencies.
- Highly configurable and hackable. Easily add new game modes, objects or maps.
- Included Game Modes:
    - Survival (collect food or die, avoid monsters)
    - Tag
    - Infection Tag
- Good Performance and low memory footprint with room for improvement.

### Planned Features
- Game Modes
    - Survival with Crafting/Hunting
    - Random Mazes/Terrian
    - Multi Task Obstatcle courses
    - Block moving puzzles
    - Physics puzzles
    - Crafting tasks
- More observation modes
- 1st person perspective view
- 2d physics support
- Admin UI for dynamic world changes
- World state saving
- Support for concurrent RL agent and human players
- Better/faster network play
- Async agent play i.e. environment doesn't block when waiting for action form agent
- Better HUD
- Ingame menus

## Known Issues
- Network play does not scale well.
- Incomplete documentation and testing
- Network play uses more bandwidth than needed.
- No runtime full game reset

## Performance
There are many factors that can impact FPS, including map size, number of game objects, resolution, number of agents.

Test below are for 1 agent @ 84x84 on an i7 Laptop
 - small maps 2500+ FPS
 - large maps 800+ FPS

Full resolution human players can expect several hundred FPS
## Requirements
- python 3.7
- pygame (rendering)
- l4z (network compression)
- pyinstrument (performance profiling)
- gym (usage of OpenAI Gym spaces and env interface)

## Installation

1. Make sure python 3.7 is installed
1. Download Repo:  ```git clone https://github.com/pistarlab/simpleland```
1. enter repo directory: ```cd simpleland```
1. (Optional) if using Anaconda, create conda environment: ```conda create -n simpleland python=3.7```
1. Install requirements via pip: ```pip install -e .```
1. Update path: ```export PYTHONPATH=${PYTHONPATH}:./```


## Usage


### Run Random Agent Test
```bash
PYTHONPATH=${PYTHONPATH}:./  python simpleland/env.py  --agent_count=2 --max_steps=800000
```

### Local Game only (Human play)

```bash
PYTHONPATH=${PYTHONPATH}:./  python simpleland/runner.py
```

### Run Server and Local Client (Human play)

```bash
PYTHONPATH=${PYTHONPATH}:./  python simpleland/runner.py --enable_server --enable_client
```

### Connect to remote host
```bash
 python simpleland/runner.py --enable_client --remote_client --hostname=SERVER_HOSTNAME 
```

### Using the Reinforcement learning Env interfaces


MultiAgent and Gym RL interfaces are here:
[env.py]( simpleland/env.py)

TODO: Document

