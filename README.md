# SimpleLand

## TODO:
Better design would be:
- create references for objects during serialization and reassign during deserialization.
- only send updated data
- use event listners
- object event listender

## Overview
A 2d game engine written in python designed to provide a flexilble test-bed for **reinforcement learning** research.

**Version: 0.0.1-dev**: Early release not ready for general use. 

![Game Screenshot](xxx "Game screenshot")

## Features
- Openai gym interface for Single Agent Play
- Multi Agent Support
- Configuration driven
- Reasonably good FPS for software rendering
- 3rd person perspective view
- Game Modes Available
    - Survival (collect food or die, avoid monsters)
    - Tag
    - Infection Tag
- Network Play support (Early Development)
- Crafting Support
- Support for concurrent games
- Hackable, easy to add:
    - game object types
    - game modes
    - maps

### Planned Features
- Game Modes
    - Tag
    - Infection Tag
    - Survival with Crafting/Hunting
    - Random Mazes
    - Multi Task Obstatcle courses
    - Block moving puzzles   
- 1st person perspective view
- 2d physics support
- Admin UI for dynamic world changes
- World state saving
- Support for concurrent RL agent and human players
- Better/faster network play
- Async agent play i.e. environment doesn't block when waiting for action form agent
- Better HUD
- Ingame menus

### Performance
When tested on i7 laptop
- 300+ RGB frame observations per second
- Small memory footprint. Less than 1MB per instance

## Known Issues
- Network play does not scale well.
- Incomplete documentation and testing
- Network play uses more bandwidth than needed.

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
PYTHONPATH=${PYTHONPATH}:./  python simpleland/env.py  --agent_count=2 --mem_profile --max_steps=800000
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

TODO: See simpleland/env.py

