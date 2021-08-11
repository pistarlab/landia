
from landia import content
from landia.config import GameDef
from landia.utils import merged_dict
import pkg_resources
import json
import os
from pathlib import Path
import pprint

CONTENT_ID = "survival"
DEFAULT_TILE_SIZE = 16

def read_json_file(path):
    try:
        
        with open(path,'r') as f:
            return json.load(f)
    except Exception as e:
        return {}

def read_game_config(path, config_filename):
    game_config = read_json_file(os.path.join(path,config_filename))
    game_config['asset_bundle'] = read_json_file(
            os.path.join(path,game_config['asset_bundle']))
    for id, obj_data in game_config['controllers'].items():
        if "config" not in obj_data:
            obj_data['config'] = read_json_file(os.path.join(path,obj_data.get('config',f"{id}_config.json")))
    for id, obj_data in game_config['objects'].items():
        obj_data['config'] = merged_dict(obj_data.get('config',{}),read_json_file(os.path.join(path,obj_data.get('config_file',f"{id}_config.json"))))
        obj_data['sounds'] = merged_dict(obj_data.get('sounds',{}),read_json_file(os.path.join(path,obj_data.get('sounds_file',f"{id}_sounds.json"))))
        obj_data['model'] = merged_dict(obj_data.get('model',{}),read_json_file(os.path.join(path,obj_data.get('model_file',f"{id}_model.json"))))
    for id, data in game_config['effects'].items():
        data['config'] = read_json_file(os.path.join(path,data.get('config_file',f"{id}_config.json")))
        data['sounds'] = read_json_file(os.path.join(path,data.get('sounds_file',f"{id}_sounds.json")))
        data['model'] = read_json_file(os.path.join(path,data.get('model_file',f"{id}_model.json")))
    return game_config


def game_def(content_overrides={}):
    # TODO: convoluted: add separate arguments for overriding and loading of paths
   
    root_path = os.path.join(Path.home(),"landia")
    data_path = os.path.join(root_path,CONTENT_ID)
    mod_name = "default"
    mod_path = os.path.join(data_path,mod_name)
    game_config_filename = 'game_config.json'
    game_config_root ="config"
    
    content_config = {
        "tile_size": DEFAULT_TILE_SIZE,
        "game_config_root":game_config_root,
        "root_path":root_path,
        "data_path":data_path,
        "mod_name":mod_name,
        "mod_path":mod_path,
        "save_path":os.path.join(mod_path,"saves"),
        "load_save":False,
        "load_file":None
    }

    content_config = merged_dict(content_config, content_overrides)
    
    full_game_config_root = pkg_resources.resource_filename(__name__,game_config_root)

    default_game_config = read_game_config(full_game_config_root,game_config_filename)
    content_config = merged_dict(content_config, default_game_config)
    
    mod_path = content_overrides.get("mod_path",content_config.get("mod_path"))
    os.makedirs(mod_path,exist_ok=True)

    mod_path_full =os.path.join(mod_path,game_config_filename)
    if os.path.exists(mod_path_full):
        try:
            mod_game_config = read_game_config(mod_path,game_config_filename)
            content_config = merged_dict(content_config, mod_game_config)
        except Exception as e:
            print(f"Error loading config from file {mod_path_full}: {e}")
    else:
        with open(mod_path_full,'w') as fp:
            json.dump(read_json_file(os.path.join(full_game_config_root,game_config_filename)),fp,indent=4)

    content_config = merged_dict(content_config, content_overrides)
    save_path = content_config.get("save_path")
    os.makedirs(save_path,exist_ok=True)

    camera_distance = content_config.get('default_camera_distance')
    if camera_distance is None:
        content_config['default_camera_distance'] = content_config['tile_size']


    game_def = GameDef(
        content_id=CONTENT_ID,
        content_config=content_config
    )
    game_def.physics_config.tile_size = content_config.get("tile_size")
    game_def.physics_config.engine = "grid"
    
    return game_def