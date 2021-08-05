from simpleland.contentbundles.survival_common import StateController
from ..asset_bundle import AssetBundle
import math
import random

from typing import List, Dict
from .. import gamectx
from ..clock import clock
from ..common import Vector2


from ..itemfactory import ShapeFactory
from ..object import GObject

from ..player import Player
from ..event import (DelayedEvent)
from .survival_utils import coord_to_vec
import numpy as np
from gym import spaces
import os
import pkg_resources
from ..event import SoundEvent
import hashlib
import logging
from ..common import Base
from .survival_utils import angle_to_sprite_direction
from .survival_behaviors import Behavior,FollowAnimals,FleeAnimals,PlayingTag

class GameMapLoader:

    def __init__(self):
        self.gamemap = None
    
    def get(self,name):
        if self.gamemap is None:
            self.gamemap = gamectx.content.gamemap
        return self.gamemap

def load_asset_bundle(asset_bundle):

    return AssetBundle(
        image_assets=asset_bundle['images'],
        sound_assets=asset_bundle['sounds'],
        music_assets=asset_bundle['music'],
        maploader = GameMapLoader())

