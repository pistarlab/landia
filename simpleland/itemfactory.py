from typing import Any, Dict, List

from .common import (
                     Circle, 
                     Polygon,
                      Vector2, COLLISION_TYPE)
from .object import GObject

import math


class ShapeFactory:

    @classmethod
    def attach_circle(cls, obj: GObject, radius=5, pos=(0, 0), collision_type=COLLISION_TYPE['default'], friction=0.2):
        circle = Circle(radius=radius)
        obj.set_image_dims(radius*2,radius*2)
        obj.add_shape(circle, collision_type=collision_type)

    @classmethod
    def attach_rectangle(cls, obj: GObject, width=32, height=32, collision_type=COLLISION_TYPE['default']):
        h = height/2
        w = width/2
        p1 = Vector2(-w, -1 * h)
        p2 = Vector2(-1 * w, h)
        p3 = Vector2(w, h)
        p4 = Vector2(w, -1 * h)
        obj.set_image_dims(width,height)
        p = Polygon(vertices=[p1, p2, p3, p4])
        obj.add_shape(p, collision_type=collision_type)

    @classmethod
    def attach_triangle(cls, obj: GObject, side_length=12, collision_type=COLLISION_TYPE['default']):
        p1 = Vector2(0, side_length)
        p2 = Vector2(side_length / 2, 0)
        p3 = Vector2(-1 / 2 * side_length, 0)
        obj.set_image_dims(side_length/2,side_length/2)
        p = Polygon( vertices=[p1, p2, p3])
        obj.add_shape(p, collision_type=collision_type)

    @classmethod
    def attach_poly(cls, obj: GObject, size=10, num_sides=3, collision_type=COLLISION_TYPE['default']):
        verts = []
        for i in range(num_sides):
            angle = math.pi + 2.0 * math.pi * i / num_sides
            x = (size/2.0) * math.sin(angle)
            y = (size/2.0) * math.cos(angle)
            verts.append(Vector2(x, y))

        p = Polygon(vertices=verts)
        obj.set_image_dims(size,size)
        obj.add_shape(p, collision_type=collision_type)

