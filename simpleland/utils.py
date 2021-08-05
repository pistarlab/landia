import time
import copy

uid = 0
def gen_id():
    global uid
    uid+=1
    return uid
class TickPerSecCounter:

    def __init__(self,size=2):
        # FPS Counter
        self.size = size
        self.counts = [0 for i in range(self.size)]
        self.last_spot = 0

    def tick(self):
        spot = int(time.time()) % self.size
        if spot != self.last_spot:
            self.counts[spot]=1
            self.last_spot = spot
        else:
            self.counts[spot]+=1

    def avg(self):
        return sum([v for i, v in enumerate(self.counts) if self.last_spot != i])/(self.size -1)


def merged_dict(d1,d2,visheight=0):
    if visheight==0:
        if d1 is None:
            d1 = {}
        d1 = copy.deepcopy(d1)
    if d2 is None:
        return d1
    for k,v in d2.items():
        if k in d1:
            if isinstance(v,dict) and isinstance(d1[k],dict):
                d1[k] = merged_dict(d1[k],v,visheight+1)
            else:
                d1[k] = v
        else:
            d1[k] = v
    return d1



# Used for looking for memory leaks
# Source: https://stackoverflow.com/questions/449560/how-do-i-determine-the-size-of-an-object-in-python
import sys
from types import ModuleType, FunctionType
from gc import get_referents

# Custom objects know their class.
# Function objects seem to know way too much, including modules.
# Exclude modules as well.
BLACKLIST = type, ModuleType, FunctionType


def getsize(obj):
    """sum size of object & members."""
    if isinstance(obj, BLACKLIST):
        raise TypeError('getsize() does not take argument of type: '+ str(type(obj)))
    seen_ids = set()
    size = 0
    objects = [obj]
    while objects:
        need_referents = []
        for obj in objects:
            if not isinstance(obj, BLACKLIST) and id(obj) not in seen_ids:
                seen_ids.add(id(obj))
                size += sys.getsizeof(obj)
                need_referents.append(obj)
        objects = get_referents(*need_referents)
    return size

import sys
from numbers import Number
from collections import deque
from collections.abc import Set, Mapping
ZERO_DEPTH_BASES = (str, bytes, Number, range, bytearray)


def getsizewl(obj_0):
    """Recursively iterate to sum size of object & members."""
    _seen_ids = set()
    def inner(obj):
        obj_id = id(obj)
        if obj_id in _seen_ids:
            return 0
        _seen_ids.add(obj_id)
        size = sys.getsizeof(obj)
        if isinstance(obj, ZERO_DEPTH_BASES):
            pass # bypass remaining control flow and return
        elif isinstance(obj, (tuple, list, Set, deque)):
            size += sum(inner(i) for i in obj)
        elif isinstance(obj, Mapping) or hasattr(obj, 'items'):
            size += sum(inner(k) + inner(v) for k, v in getattr(obj, 'items')())
        # Check for custom object instances - may subclass above too
        if hasattr(obj, '__dict__'):
            size += inner(vars(obj))
        if hasattr(obj, '__slots__'): # can have __slots__ with __dict__
            size += sum(inner(getattr(obj, s)) for s in obj.__slots__ if hasattr(obj, s))
        return size
    return inner(obj_0)

colormap = []
colormap.append((128,0,0))
colormap.append((139,0,0))
colormap.append((165,42,42))
colormap.append((178,34,34))
colormap.append((220,20,60))
colormap.append((255,0,0))
colormap.append((255,99,71))
colormap.append((255,127,80))
colormap.append((205,92,92))
colormap.append((240,128,128))
colormap.append((233,150,122))
colormap.append((250,128,114))
colormap.append((255,160,122))
colormap.append((255,69,0))
colormap.append((255,140,0))
colormap.append((255,165,0))
colormap.append((255,215,0))
colormap.append((184,134,11))
colormap.append((218,165,32))
colormap.append((238,232,170))
colormap.append((189,183,107))
colormap.append((240,230,140))
colormap.append((128,128,0))
#colormap.append((255,255,0))
#colormap.append((154,205,50))
#colormap.append((85,107,47))
#colormap.append((107,142,35))
#colormap.append((124,252,0))
#colormap.append((127,255,0))
#colormap.append((173,255,47))
#colormap.append((0,100,0))
#colormap.append((0,128,0))
#colormap.append((34,139,34))
#colormap.append((0,255,0))
#colormap.append((50,205,50))
#colormap.append((144,238,144))
#colormap.append((152,251,152))
#colormap.append((143,188,143))
#colormap.append((0,250,154))
#colormap.append((0,255,127))
#colormap.append((46,139,87))
#colormap.append((102,205,170))
#colormap.append((60,179,113))
#colormap.append((32,178,170))
#colormap.append((47,79,79))
#colormap.append((0,128,128))
#colormap.append((0,139,139))
#colormap.append((0,255,255))
#colormap.append((0,255,255))
#colormap.append((224,255,255))
#colormap.append((0,206,209))
#colormap.append((64,224,208))
#colormap.append((72,209,204))
#colormap.append((175,238,238))
#colormap.append((127,255,212))
#colormap.append((176,224,230))
#colormap.append((95,158,160))
#colormap.append((70,130,180))
#colormap.append((100,149,237))
#colormap.append((0,191,255))
#colormap.append((30,144,255))
#colormap.append((173,216,230))
#colormap.append((135,206,235))
#colormap.append((135,206,250))
#colormap.append((25,25,112))
#colormap.append((0,0,128))
#colormap.append((0,0,139))
#colormap.append((0,0,205))
#colormap.append((0,0,255))
#colormap.append((65,105,225))
#colormap.append((138,43,226))
#colormap.append((75,0,130))
#colormap.append((72,61,139))
#colormap.append((106,90,205))
#colormap.append((123,104,238))
#colormap.append((147,112,219))
#colormap.append((139,0,139))
#colormap.append((148,0,211))
#colormap.append((153,50,204))
#colormap.append((186,85,211))
#colormap.append((128,0,128))
#colormap.append((216,191,216))
#colormap.append((221,160,221))
#colormap.append((238,130,238))
#colormap.append((255,0,255))
#colormap.append((218,112,214))
#colormap.append((199,21,133))
#colormap.append((219,112,147))
#colormap.append((255,20,147))
#colormap.append((255,105,180))
#colormap.append((255,182,193))
#colormap.append((255,192,203))
#colormap.append((250,235,215))
#colormap.append((245,245,220))
#colormap.append((255,228,196))
#colormap.append((255,235,205))
#colormap.append((245,222,179))
#colormap.append((255,248,220))
#colormap.append((255,250,205))
#colormap.append((250,250,210))
#colormap.append((255,255,224))
#colormap.append((139,69,19))
#colormap.append((160,82,45))
#colormap.append((210,105,30))
#colormap.append((205,133,63))
#colormap.append((244,164,96))
#colormap.append((222,184,135))
#colormap.append((210,180,140))
#colormap.append((188,143,143))
#colormap.append((255,228,181))
#colormap.append((255,222,173))
#colormap.append((255,218,185))
#colormap.append((255,228,225))
#colormap.append((255,240,245))
#colormap.append((250,240,230))
#colormap.append((253,245,230))
#colormap.append((255,239,213))
#colormap.append((255,245,238))
#colormap.append((245,255,250))