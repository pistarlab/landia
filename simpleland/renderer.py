from simpleland.utils import TickPerSecCounter
from typing import Dict, Any

import pygame
from .object import GObject
from .common import Vector2, Line, Circle, Polygon, Rectangle
from .object_manager import GObjectManager
from PIL import Image
import numpy as np
import os

from .config import RendererConfig
from .asset_bundle import AssetBundle
from .player import Player
from . import gamectx
import math
from math import ceil
import time
import pkg_resources
import logging
from .player import Camera
from .spritesheet import Spritesheet
from .content import Content
from .utils import colormap



def scale(vec, vec2):
    return Vector2(vec.x * vec2.x, vec.y * vec2.y)


class Renderer:

    def __init__(self, config: RendererConfig, asset_bundle: AssetBundle):
        if config.sdl_audio_driver:
            os.environ['SDL_AUDIODRIVER'] = config.sdl_audio_driver
        if config.sdl_video_driver:
            os.environ["SDL_VIDEODRIVER"] = config.sdl_video_driver
        self.asset_bundle = asset_bundle
        self.config: RendererConfig = config
        self.format = config.format
        self._display_surf = None
        self.resolution = self.width, self.height = config.resolution
        self.aspect_ratio = (self.width * 1.0) / self.height

        self.initialized = False
        self.frame_cache = None
        self.debug = config.debug_render_bodies
        # These will be source object properties eventually
        self.view_height = 600000.0
        self.view_width = self.view_height * self.aspect_ratio
        self.min_distance = self.config.tile_size*5
        self.max_distance = self.config.tile_size*100

        self.images = {}
        self.image_cache = {}
        self.sounds = {}
        self.sprite_sheets = {}

        self.log_info = None
        self.font = {}
        self.fps_clock = pygame.time.Clock()
        self.background = None
        self.background_center = None
        self.background_size = None
        self.background_updates = 0
        self.background_screen_factor = None

    def set_log_info(self, log_info):
        self.log_info = log_info

    def load_sounds(self):
        if self.config.sound_enabled:
            pass
            for k, sound_data in self.asset_bundle.sound_assets.items():
                path = sound_data[0]
                vol = sound_data[1]
                sound = pygame.mixer.Sound(pkg_resources.resource_filename(__name__, path))
                sound.set_volume(vol)
                self.sounds[k] = sound

    def load_images(self):
        self.images = {}
        for k, (path, frame_id) in self.asset_bundle.image_assets.items():
            full_path = pkg_resources.resource_filename(__name__, path)
            if frame_id is None:
                image = pygame.image.load(full_path).convert_alpha()
            else:
                if path not in self.sprite_sheets:
                    self.sprite_sheets[path] = Spritesheet(full_path)
                image = self.sprite_sheets[path].parse_sprite(frame_id)
            self.images[k] = image

    def play_sounds(self, sound_ids):
        if self.config.sound_enabled:
            for sid in sound_ids:
                self.sounds[sid].play()

    def play_music(self, music_id):
        if self.config.sound_enabled:
            if self.config.sound_enabled:
                data = self.asset_bundle.music_assets[music_id]
                full_path = pkg_resources.resource_filename(__name__, data[0])
                print(f"Loading Music from: {full_path}")
                pygame.mixer.music.load(full_path)
                pygame.mixer.music.play(-1)
                pygame.mixer.music.set_volume(data[1])

    def get_image_by_id(self, image_id):
        return self.images.get(image_id)

    def get_scaled_image_by_id(self, image_id, scale_x, scale_y):
        image_sizes = self.image_cache.get(image_id, {})
        img = image_sizes.get((scale_x, scale_y))
        if img is None:
            img_orig = self.get_image_by_id(image_id)
            if img_orig is None:
                return None
            body_w, body_h = img_orig.get_size()
            image_size = ceil(body_w*scale_x), ceil(body_h*scale_y)
            if image_size[0] > 500:
                image_size = 500, 500
            img = pygame.transform.scale(img_orig, image_size)
            image_sizes[(scale_x, scale_y)] = img
            self.image_cache[image_id] = image_sizes
        return img

    def update_view(self, view_height):
        self.view_height = max(view_height, 10)
        self.view_width = self.view_height * self.aspect_ratio

    def initialize(self):
        if self.config.sound_enabled:
            pygame.mixer.pre_init(44100, -16, 4, 2048)
            pygame.mixer.init()
        pygame.init()

        if self.config.enable_resize:
            flags = pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.RESIZABLE | pygame.SCALED
        else:
            flags = pygame.DOUBLEBUF

        self._display_surf = pygame.display.set_mode(self.resolution, flags)
        self.load_sounds()
        self.load_images()
        self.play_music("background")
        pygame.key.set_repeat(1000,1)

        self.initialized = True

    def render_to_console(self, lines, x, y, fsize=14, spacing=12, color=(255, 255, 255)):
        font = self.font.get(fsize)
        if font is None:
            font = pygame.font.SysFont("consolas", fsize)
            self.font[fsize] = font
        for i, l in enumerate(lines):
            self._display_surf.blit(font.render(l, True, color), (x, y + spacing * i))

    def _draw_grid_line(self, p1, p2, angle, center, screen_view_center, color, screen_factor):
        p1 = (p1 - center).rotate(angle)
        p1 = scale(screen_factor, (p1)) + screen_view_center
        p1 = p1

        p2 = (p2 - center).rotate(angle)
        p2 = scale(screen_factor, (p2)) + screen_view_center
        pygame.draw.line(self._display_surf,
                         color,
                         p1,
                         p2,
                         1)

    def _draw_grid(self, center, angle, screen_factor, screen_view_center, color=(50, 50, 50), size=20, view_type=0):
        line_num = int(self.view_width/size) + 4

        x = int(center.x/size) * size - size/2
        y = int(center.y/size) * size - size/2

        y_start = -(y - size * line_num)
        y_center = Vector2(center.x, -center.y)
        for line in range(line_num * 2):
            y_pos = y_start - size * line
            p1 = Vector2(x-self.view_width, y_pos)
            p2 = Vector2(x+self.view_width, y_pos)
            self._draw_grid_line(p1, p2, angle, y_center, screen_view_center, color, screen_factor)

        x_start = x - size * line_num
        for line in range(line_num * 2):
            x_pos = x_start + size * line
            p1 = Vector2(x_pos, y-self.view_height)
            p2 = Vector2(x_pos, y+self.view_height)
            self._draw_grid_line(p1, p2, angle, center, screen_view_center, color, screen_factor)

    def draw_rectangle(self, x, y, width, height, color):
        rect = pygame.Rect(x, y, width, height)
        # rect.center = Vector2(x,y)
        pygame.draw.rect(self._display_surf, color, rect)

    def _draw_image(self, pos, center, image_id, angle, screen_factor, screen_view_center, color=(255, 0, 0)):
        image = self.get_scaled_image_by_id(image_id, screen_factor[0], screen_factor[1])
        image_loc = scale(screen_factor, pos - center) + screen_view_center
        if image is not None:
            if angle != 0:
                image = pygame.transform.rotate(image, angle % 360)
            rect = image.get_rect()
            rect.center = image_loc
            self._display_surf.blit(image, rect)
        else:
            rect = pygame.Rect(0, 0, self.config.tile_size * screen_factor[0], self.config.tile_size * screen_factor[1])
            rect.center = image_loc
            pygame.draw.rect(self._display_surf, color, rect)

    def _draw_infobox(self, infobox, surface:pygame.Surface, screen_factor):
        
        w,h = surface.get_size()
        padding = infobox.get("padding",1) * screen_factor[0]
        rows = len(infobox['value'])

        row_h = round ((h -(padding * (rows +1))) / rows )
        
        x_max = w - padding * 2
        x = padding
        for i,renderable in enumerate(infobox['value']):
            y = row_h * i + padding *(i+1)
            
            bg_color = renderable.get("bg_color")
            color = renderable.get("color")
            label = renderable.get("label")
            loc = x,y
            barw = x_max
            if label is not None:
                fsize=row_h
                font = self.font.get(fsize)
                if font is None:
                    font = pygame.font.SysFont(None, fsize)
                    self.font[fsize] = font
                twidth,_ = font.size(label)

                surface.blit(font.render(label, True, (200,200,200)), loc)
                loc = x + twidth,y
                barw = barw - twidth
            
            
            if bg_color is not None:
                rect = pygame.Rect(loc[0], loc[1],
                                    barw,
                                    row_h)

                pygame.draw.rect(surface, bg_color, rect)
                
            if renderable.get("type") == "bar":
                width = round(barw * renderable.get("value"))

                rect = pygame.Rect(loc[0], loc[1],
                                    width,
                                    row_h)

                pygame.draw.rect(surface, color, rect)

            elif renderable.get("type") == "block_list":    
                size = renderable.get("size",3)
                chunk = barw/size
                pygame.draw.rect(surface, bg_color, rect)
                for val in renderable.get('value'):
                    bloc = loc[0] + chunk * val,loc[1]
                    blockw = chunk

                    # Bar
                    rect = pygame.Rect(bloc[0], bloc[1],
                                        blockw,
                                        row_h)

                    pygame.draw.rect(surface, colormap[round((val/size)*len(colormap))], rect)

            elif renderable.get('type') == 'icon':                    
                if renderable['value'] is not None:
                    image_id = renderable['value'][0]
                    image_orig  = self.get_image_by_id(image_id)
                    iw,ih = image_orig.get_rect().size

                    image = self.get_scaled_image_by_id(image_id, row_h/iw,row_h/iw)
                    rect = image.get_rect()
                    rect.center = loc[0] + barw/2, loc[1] + row_h /2
                    surface.blit(image, rect)
            elif renderable.get("type") is "text":
                fsize=row_h
                font = self.font.get(fsize)
                if font is None:
                    font = pygame.font.SysFont(None, fsize)
                    self.font[fsize] = font
                text = renderable['value']
                twidth,_ = font.size(text)
                loc = loc[0]+ barw/2 - twidth /2, loc[1]

                surface.blit(font.render(text, True, (200,200,200)), loc)
 

    def _draw_object(self, center, obj: GObject, screen_angle, screen_factor, screen_view_center, color=None):

        renderables = obj.get_renderables(screen_angle,exclude_info=self.config.exclude_info_box)
        for renderable in renderables:
            if renderable.get("type") is "text":
                fsize = round(3 * screen_factor[0])
                spacing = 12
                color = (255, 255, 255)
                pos = obj.get_view_position() - Vector2(self.config.tile_size/2, self.config.tile_size/2)
                loc = scale(screen_factor, pos - center) + screen_view_center

                font = self.font.get(fsize)
                if font is None:
                    font = pygame.font.SysFont(None, fsize)
                    self.font[fsize] = font
        # for i, l in enumerate(lines):
                self._display_surf.blit(font.render(renderable.get("value"), True, color), loc)
            elif renderable.get("type") is "infobox":
                boxscale = renderable.get("scale",(1.0,1.0))
                background_color = renderable.get("background_color",(0,0,0))
                pos = obj.get_view_position() - Vector2(self.config.tile_size/2, self.config.tile_size/2)
                loc = scale(screen_factor, pos - center) + screen_view_center
                size = (self.config.tile_size * screen_factor[0] * boxscale[0],self.config.tile_size * screen_factor[1] * boxscale[1])                
                surface = pygame.Surface(size)

                if background_color is None:
                    surface.set_colorkey((0,0,0))
                else:               
                    surface.fill(background_color)
                self._draw_infobox(renderable, surface=surface, screen_factor=screen_factor)

                self._display_surf.blit(surface,loc)

            elif renderable.get("type") is "bar":
                color = renderable.get("color")
                bg_color = renderable.get("bg_color")
                pos = obj.get_view_position() - Vector2(self.config.tile_size/2, self.config.tile_size/2)
                loc = scale(screen_factor, pos - center) + screen_view_center
                barw = round(self.config.tile_size * screen_factor[0] /2)
                barh = 1 * screen_factor[0]
                # Bar BG
                rect = pygame.Rect(loc[0], loc[1],
                                   barw,
                                   barh)

                pygame.draw.rect(self._display_surf, bg_color, rect)
                width = round(barw * renderable.get("value"))
                # Bar
                rect = pygame.Rect(loc[0], loc[1],
                                   width,
                                   barh)

                pygame.draw.rect(self._display_surf, color, rect)
            elif renderable.get("type") is "tag":
                color = renderable.get("color")
                index = renderable.get("index",0)
                # bg_color = renderable.get("bg_color")
                tw = 1.2 * screen_factor[0]#round(self.config.tile_size * screen_factor[0] /2)
                th = 1.2 * screen_factor[1]
                pos = obj.get_view_position() - Vector2(self.config.tile_size/2 - 1.2 * index, 0)
                loc = scale(screen_factor, pos - center) + screen_view_center

                # Bar
                rect = pygame.Rect(loc[0], loc[1],
                                   tw,
                                   th)

                pygame.draw.rect(self._display_surf, color, rect)            
            else:
                position = renderable['position']
                image_id = renderable['image_id']
                angle = renderable['angle']
                pos = obj.get_view_position() - position - obj.image_offset
                self._draw_image(pos, center, image_id, angle, screen_factor, screen_view_center)

    def filter_objects_for_rendering(self, objs, camera: Camera):
        center = camera.get_center()
        object_list_visheight_sorted = [[], [], [], []]
        if center is None:
            return []
        for k, o in objs.items():
            o: GObject = o
            if o is not None and o.is_enabled() and o.is_visible():
                view_position = o.get_view_position()
                if view_position is not None:
                    within_range = o.get_view_position().distance_to(center) < self.view_width
                    if within_range:
                        object_list_visheight_sorted[o.visheight].append(o)

        # TODO: Need to adjust with angle
        center_bottom = center - Vector2(0, 100)

        for lst in object_list_visheight_sorted:
            lst.sort(key=lambda o: o.get_position().distance_to(center_bottom))
        return object_list_visheight_sorted

    def ta(self, val):
        return int((val//self.config.tile_size) * self.config.tile_size)

    def _draw_background_image(self, image, center,  angle, screen_factor, screen_view_center):

        rect = image.get_rect()
        image_loc = scale(
            Vector2(self.background_center[0] - center.x,
                    self.background_center[1] - center.y),
            screen_factor) + screen_view_center
        rect.center = image_loc
        self._display_surf.blit(image, rect)

    def check_bounds(self, cv, cs, bv, bs):
        return ((bv - bs/2) >= (cv - cs/2)) or ((bv+bs/2) <= (cv + cs/2))

    def get_background_image(self, center, screen_factor):
        #TODO: occationally shows black areas when moving right or down, but only during movement

        # Align with tile coords
        center = Vector2(self.ta(center.x), self.ta(center.y))

        # Align and make sure odd number of tiles so center can be a single tile
        surface_width = self.ta(self.view_width/2) * 5 + self.config.tile_size
        surface_height = self.ta(self.view_height/2) * 5 + self.config.tile_size

        if screen_factor == self.background_screen_factor and self.background is not None:
            need_update = self.check_bounds(
                center.x,
                self.view_width,
                self.background_center[0],
                self.background_size[0])
            if not need_update:
                need_update = self.check_bounds(
                    center.y,
                    self.view_height,
                    self.background_center[1],
                    self.background_size[1])
                if not need_update:
                    return self.background

        gamemap = self.asset_bundle.maploader.get("")

        # Center tile for tile image id lookup
        sur_center_x = surface_width/2 - center.x
        sur_center_y = surface_height/2 - center.y
        sur_center_tile_x = sur_center_x // self.config.tile_size
        sur_center_tile_y = sur_center_y // self.config.tile_size

        tmp_surface = pygame.Surface((surface_width, surface_height))
        for z in gamemap.get_layers():
            for tile_x in range(surface_width//self.config.tile_size):
                ltile_x = (tile_x - sur_center_tile_x)
                for tile_y in range(surface_height//self.config.tile_size):
                    ltile_y = (tile_y - sur_center_tile_y)
                    background_image_id = gamemap.get_image_by_loc(ltile_x, ltile_y, z)
                    if background_image_id is not None:
                        tile_image = self.get_image_by_id(background_image_id)

                        rect = tile_image.get_rect()
                        tile_pos = (int(tile_x * self.config.tile_size), int(tile_y * self.config.tile_size))
                        rect.topleft = tile_pos
                        tmp_surface.blit(tile_image, rect)

        image_size = int(surface_width*screen_factor[0]), int(surface_height*screen_factor[1])

        tmp_surface = pygame.transform.scale(tmp_surface, image_size)
        self.background = tmp_surface
        self.background_center = center
        self.background_size = surface_width, surface_height
        self.background_screen_factor = screen_factor
        self.background_updates += 1
        return self.background

    # TODO: Clean this up
    def process_frame(self,
                      player: Player):

        if not self.initialized:
            self.initialize()

        # import pdb;pdb.set_trace()
        self._display_surf.fill((0, 0, 0))

        angle = 0
        camera: Camera = None
        center: Vector2 = None
        if player:
            camera = player.get_camera()
        else:
            camera = Camera(center=Vector2(self.view_width/2, self.view_height/2))

        if camera.distance > self.max_distance:
            camera.distance = self.max_distance
        elif camera.distance < self.min_distance:
            camera.distance = self.min_distance

        center = camera.get_center()
        if center is None:
            center = Vector2(self.view_width/2, self.view_height/2)
        angle = camera.get_angle()

        # TODO: View Width/Height should only be in camera
        self.update_view(camera.get_distance())

        center = center - camera.position_offset
        screen_factor = Vector2(self.width / self.view_width, self.height / self.view_height)
        screen_view_center = scale(screen_factor, Vector2(self.view_width, self.view_height) / 2.0)

        background = self.get_background_image(center, screen_factor)
        self._draw_background_image(background, center, 0, screen_factor, screen_view_center)

        if self.config.draw_grid:
            self._draw_grid(center,
                            angle,
                            screen_factor,
                            screen_view_center,
                            size=self.config.tile_size,
                            view_type=self.config.view_type,
                            color=(20, 20, 20))

        obj_list_sorted_by_visheight = self.filter_objects_for_rendering(gamectx.object_manager.get_objects(), camera)

        for visheight, render_obj_dict in enumerate(obj_list_sorted_by_visheight):
            obj: GObject
            for obj in render_obj_dict:
                if not obj.enabled or not obj.is_visible():
                    continue
                self._draw_object(center, obj, angle, screen_factor, screen_view_center, obj.shape_color)

        if self.debug:
            pygame.draw.rect(self._display_surf,
                             (0, 250, 250),
                             pygame.Rect(center.x + self.width/2, center.y+self.height/2, 5, 5))

            pygame.draw.rect(self._display_surf,
                             (255, 255, 50),
                             pygame.Rect(self.width/2, self.height/2, 5, 5))

    def render_frame(self):
        self.fps_clock.tick()
        if self.config.save_observation:
            self.get_last_frame()
        frame = self.frame_cache
        self.frame_cache = None
        if self.config.render_to_screen:
            pygame.display.flip()
        return frame

    def get_last_frame(self):

        img_st = pygame.image.tostring(self._display_surf, self.format)
        data = Image.frombytes(self.format, self.config.resolution, img_st)
        np_data = np.array(data)

        # cache
        self.frame_cache = np_data
        return np_data
