# piSTAR Landia

## Overview
A 2d game framework designed to provide playground for AI (Reinforcement Learning) agents. Humans are also welcome.

**Version: 0.0.1-dev**: Early release not ready for general use. Only tested on Ubuntu and Windows 10.

## Screen Shots
<img src="docs/screen_shot0.png" alt="drawing" width="400"/>
<br/>
<br/>

<img src="docs/screen_shot_zoomout1.png" alt="drawing" width="400"/>
<br/>
<br/>


<!-- <img src="docs/ctf.gif" alt="drawing" width="400"/> -->
<!-- <br/>
<br/> -->
<!-- 
![sfasdfx](docs/infect.mp4) -->
 <video width="400"  poster="docs/screen_shot0.png" >
  <source src="docs/infect.mp4" type="video/mp4">
  Your browser does not support the video tag.
</video> 


## Features
- Multi-agent support
- Openai gym interface for pingle agent play
- Network play support (early development)
- Support for concurrent  game modes (eg: Tag + Survival)
- Written in Python and requires only a few dependencies.
- Highly configurable and hackable. Easily add new game modes, objects or maps.
- Game Modes included:
    - Capture the flag
    - Survival (collect food or die, avoid monsters)
    - Tag
    - Infection Tag
- Crafting System
- Reasonable performance and low memory footprint with plenty of room for future improvements.

## Known Issues
- Limited number of objects
- No argument to set the game seed
- Network play is laggy and does not scale to more than a few remoe users.
- Incomplete documentation and testing
- Network play uses more bandwidth than needed.
- No runtime full game reset

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

## Configuration/Maps

After running Landia for the first time, a configuration and save directory will be created in your home folder. Example: HOME_DIR/landia.

Files within this folder can override any the default configuration:

- HOME_DIR/landia/assets/ will override the landia/assets folder
- HOME_DIR/landia/assets/ will override the landia/assets folder
- HOME_DIR/landia//survival/default/game_config.json will override the landia/survival/config/game_config.json


### Save location
World saves will be stored in the HOME_DIR/landia//survival/default/saves folder


## Reinforcement Learning Environment Usage

###  Using the RL Env interfaces

MultiAgent and Gym RL interfaces are here:
[env.py]( landia/env.py)

TODO: More documentation


## Development

The landia code base is divided into two parts two allow support for future games under the same framework
- game code: currently under landia/survival
- framework code: landia/

TODO: More documentation

## Acknowledgments

- My kids for their inspiration and help testing
- Vryell's Tiny Adventure Pack. Currently used for most of the game art
    - See: https://vryell.itch.io/tiny-adventure-pack

