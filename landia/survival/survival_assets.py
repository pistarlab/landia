from landia.asset_bundle import AssetBundle
from landia import gamectx

class GameMapLoader:

    def __init__(self):
        self.gamemap = None
    
    def get(self,name):
        if self.gamemap is None:
            self.gamemap = gamectx.content.gamemap
        return self.gamemap

def load_asset_bundle(path,asset_bundle_config):

    return AssetBundle(
        image_assets=asset_bundle_config['images'],
        sound_assets=asset_bundle_config['sounds'],
        music_assets=asset_bundle_config['music'],
        maploader = GameMapLoader(),
        path =path)

