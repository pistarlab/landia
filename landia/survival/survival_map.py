import hashlib
import logging
import os

import numpy as np
import pkg_resources
from pygame.display import update
from landia import gamectx

from .survival_utils import coord_to_vec


def rand_int_from_coord(x, y, seed=123):
    v = (x + y * seed) % 12783723
    h = hashlib.sha1()
    h.update(str.encode(f"{v}"))
    return int(h.hexdigest(), 16) % 172837


def get_tile_image_id(x, y, seed):
    v = rand_int_from_coord(x, y, seed) % 3 + 1
    return f"grass{v}"


class Sector:

    def __init__(self, scoord, height, width):
        self.height = height
        self.width = width
        self.scoord = scoord
        self.items = {}

    def add(self, coord, info):
        local_items = self.items.get(coord, [])
        local_items.append(info)
        self.items[coord] = local_items


class GameMap:

    def __init__(self, paths, map_config, tile_size=16, seed=123):

        self.seed = seed
        full_paths = []
        for path in paths:
            if os.path.isabs(path)      :
                full_path = path
            else:
                full_path = pkg_resources.resource_filename(__name__, path)
            full_paths.append(full_path)
        self.static_layers = []
        static_layer_paths = {}

        # Find files
        for layer_filename in map_config['static_layers']:
            for full_path in full_paths:
                layer_path = os.path.join(full_path, layer_filename)
                if os.path.exists(layer_path):
                    static_layer_paths[layer_filename] = layer_path

        for layer_filename,layer_path in static_layer_paths.items():
            with open(layer_path, 'r') as f:
                layer = f.readlines()
                self.static_layers.append(layer)
        self.index = map_config['index']
        self.boundary = map_config.get('boundary',{})
        self.tile_size = tile_size
        self.sector_size = self.tile_size * 4
        self.sectors = {}
        self.sectors_loaded = set()
        self.loaded = False
        self.spawn_points = {}

    def get_sector_coord(self, coord):
        if coord is None:
            return 0, 0
        return coord[0]//self.sector_size, coord[1]//self.sector_size

    def get_sector_coord_from_pos(self, pos):
        if pos is None:
            return 0, 0
        return pos[0]//self.tile_size//self.sector_size, pos[1]//self.tile_size//self.sector_size

    def add(self, coord, info=None):
        scoord = self.get_sector_coord(coord)
        sector: Sector = self.sectors.get(scoord)
        if sector is None:
            sector = Sector(scoord, self.sector_size, self.sector_size)
        if info is not None:
            sector.add(coord, info)
        self.sectors[scoord] = sector
        return sector

    def load_boundary(self):
        if self.boundary is None:
            return
        xmin = self.boundary['x'][0]
        xmax = self.boundary['x'][1]
        ymin = self.boundary['y'][0]
        ymax = self.boundary['y'][1]
        boundary_obj_config_id = self.boundary.get('obj')
        if boundary_obj_config_id is None:
            return
        keys = set(self.index.keys())
        for x in range(xmin, xmax+1):
            self.spawn_locations = []
            objtop = gamectx.content.create_object_from_config_id(
                boundary_obj_config_id)
            objtop.spawn(position=coord_to_vec((x, ymin)))
            objbot = gamectx.content.create_object_from_config_id(
                boundary_obj_config_id)
            objbot.spawn(position=coord_to_vec((x, ymax)))

        for y in range(ymin+1, ymax):
            self.spawn_locations = []
            objtop = gamectx.content.create_object_from_config_id(
                boundary_obj_config_id)
            objtop.spawn(position=coord_to_vec((xmin, y)))
            objbot = gamectx.content.create_object_from_config_id(
                boundary_obj_config_id)
            objbot.spawn(position=coord_to_vec((xmax, y)))

    def random_coords(self, num=1):
        xrange = self.boundary.get('x')
        yrange = self.boundary.get('y')
        xs = np.random.randint(
            xrange[0] + 1, xrange[1]-1, num)
        ys = np.random.randint(
            yrange[0]+1, yrange[1]-1, num)
        return [((xs[i], ys[i])) for i in range(num)]

    def get_center(self):
        x = round((self.boundary["x"][1] - self.boundary["x"][0])/2) + self.boundary["x"][0]
        y = round((self.boundary["y"][1] - self.boundary["y"][0])/2)  + self.boundary["y"][0]
        print(self.boundary)
        print(f"Size ({x},{y})")
        return (x,y)
        
    def get_size(self):
        x = (self.boundary["x"][1] - self.boundary["x"][0])
        y = (self.boundary["y"][1] - self.boundary["y"][0])
        return x,y


    def load_static_layers(self, update_boundary = True):
        keys = set(self.index.keys())
        xmin = 0
        xmax = 0
        ymin = 0
        ymax = 0
        for i, lines in enumerate(self.static_layers):
            self.spawn_locations = []
            for ridx, line in enumerate(lines):
                linel = len(line)
                for cidx in range(0, linel, 2):
                    key = line[cidx:cidx+2]
                    coord = (cidx//2, ridx)
                    if coord[0] > xmax:
                        xmax = coord[0]
                    if coord[1] > ymax:
                        ymax = coord[1]

                    if key in keys:
                        info = self.index.get(key)
                        self.add(coord, info)

        if update_boundary:
            self.boundary['x'] = [xmin-1, xmax]
            self.boundary['y'] = [ymin-1, ymax+1]

    def initialize(self, coord):
        if not self.loaded:
            self.load_static_layers()
            self.load_boundary()
            self.loaded = True
        else:
            if "x" not in self.boundary:
                self.boundary['x']=[4,20]
            if "y" not in self.boundary:
                self.boundary['y']=[4,20]
        self.load_sectors_near_coord(self.get_sector_coord(coord))

    def get_neigh_coords(self, scoord) -> set:
        x, y = scoord
        dirs = {
            (x, y+1),
            (x, y-1),
            (x-1, y),
            (x+1, y),
            (x-1, y-1),
            (x+1, y-1),
            (x-1, y+1),
            (x+1, y+1)}
        return dirs

    def load_sectors_near_coord(self, scoord):
        nei_scoords = self.get_neigh_coords(scoord)
        not_loaded_scoords = nei_scoords.difference(self.sectors_loaded)
        if scoord not in self.sectors_loaded:
            self.load_sector(scoord)
        for new_scoord in not_loaded_scoords:
            self.load_sector(new_scoord)

    def load_sector(self, scoord):
        sector: Sector = self.sectors.get(scoord)
        if sector is None:
            coord = scoord[0] * self.sector_size, scoord[1] * self.sector_size
            # sector = self.add(coord, info = {'type':'obj','obj':'water1'})
            sector = self.add(coord)
        self.sectors_loaded.add(scoord)
        for coord, item_list in sector.items.items():
            for info in item_list:
                self.load_obj_from_info(info, coord)

    def load_obj_from_info(self, info, coord):
        
        # TODO: remove spawn_points as special objects, instead add border points and border areas
        if info.get('type') == "spawn_point":
            sid = info['id']
            self.add_spawn_point(sid, coord_to_vec(coord))
        else:
            config_id = info['obj']
            obj = gamectx.content.create_object_from_config_id(config_id)
            obj.spawn(position=coord_to_vec(coord))

    def get_layers(self):
        return range(2)

    def get_image_by_loc(self, x, y, layer_id):
        if layer_id == 0:
            return get_tile_image_id(x, y, self.seed)

        loc_id = rand_int_from_coord(x, y, self.seed)
        if x == 0 and y == 0:
            return "baby_tree"
        if x == 2 and y == 3:
            return "baby_tree"
        return None
