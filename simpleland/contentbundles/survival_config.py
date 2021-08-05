
from simpleland import camera
from ..config import GameDef
from ..utils import merged_dict
import pkg_resources
import json
import os


CONTENT_ID = "survival_grid"
DEFAULT_TILE_SIZE = 16

def read_json_file(path):
    try:
        full_path = pkg_resources.resource_filename(__name__,path)
        with open(full_path,'r') as f:
            return json.load(f)
    except Exception as e:
        return {}

def read_game_config(sub_dir, game_config):
    game_config = read_json_file(os.path.join(sub_dir,game_config))
    game_config['asset_bundle'] = read_json_file(
            os.path.join(sub_dir,game_config['asset_bundle']))
    for id, obj_data in game_config['controllers'].items():
        if "config" not in obj_data:
            obj_data['config'] = read_json_file(os.path.join(sub_dir,obj_data.get('config',f"{id}_config.json")))
    for id, obj_data in game_config['objects'].items():
        obj_data['config'] = merged_dict(obj_data.get('config',{}),read_json_file(os.path.join(sub_dir,obj_data.get('config_file',f"{id}_config.json"))))
        obj_data['sounds'] = merged_dict(obj_data.get('sounds',{}),read_json_file(os.path.join(sub_dir,obj_data.get('sounds_file',f"{id}_sounds.json"))))
        obj_data['model'] = merged_dict(obj_data.get('model',{}),read_json_file(os.path.join(sub_dir,obj_data.get('model_file',f"{id}_model.json"))))
    for id, data in game_config['effects'].items():
        data['config'] = read_json_file(os.path.join(sub_dir,data.get('config_file',f"{id}_config.json")))
        data['sounds'] = read_json_file(os.path.join(sub_dir,data.get('sounds_file',f"{id}_sounds.json")))
        data['model'] = read_json_file(os.path.join(sub_dir,data.get('model_file',f"{id}_model.json")))
    return game_config


def game_def(content_overrides={}):

    content_config = {
        "tile_size": DEFAULT_TILE_SIZE,
        "game_config_root": CONTENT_ID,
        "game_config_file": 'game_config.json'
    }
    content_config = merged_dict(content_config, content_overrides)
    config_root = content_config.get("game_config_root")
    config_filename = content_config.get("game_config_file")

    content_config = merged_dict(content_config, read_game_config(config_root,config_filename))
    content_config = merged_dict(content_config, content_overrides)
    camera_distance = content_config.get('default_camera_distance')
    if camera_distance is None:
        content_config['default_camera_distance'] = content_config['tile_size']


    game_def = GameDef(
        content_id=CONTENT_ID,
        content_config=content_config
    )
    game_def.physics_config.tile_size = content_config.get("tile_size")
    game_def.physics_config.engine = "grid"
    game_def.game_config.wait_for_user_input = False
    return game_def