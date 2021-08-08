import queue
from pygame import Vector2
from .utils import gen_id
from typing import List, Dict
import json
base_class_registry = {}

# def queue_to_list(q):
#     l = []
#     while q.qsize() >0:
#         l.append(q.get())
#     return l


def register_base_cls(cls):
    base_class_registry[cls.__name__] = cls


def get_base_cls_by_name(name):
    return base_class_registry.get(name)


class StateEncoder(json.JSONEncoder):
    def default(self, obj):  # pylint: disable=E0202
        if isinstance(obj, (Vector2)):
            return {
                "_type": "Vector2",
                "x": obj.x,
                "y": obj.y}
        return json.JSONEncoder.default(self, obj)


class StateDecoder(json.JSONDecoder):

    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(
            self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):  # pylint: disable=E0202
        if '_type' not in obj:
            return obj
        type = obj['_type']
        if type == 'Vector2':
            return Vector2(obj['x'], obj['y'])
        return obj


def create_dict_snapshot(obj, exclude_keys={}):
    _type = type(obj).__name__

    data = {}
    for k, v in obj.__dict__.items():
        if k in exclude_keys or k.startswith("_l_"):
            continue
        if issubclass(type(v), Base):
            data[k] = v.get_snapshot()
        elif v is None or isinstance(v, (int, float, str, Vector2)):
            data[k] = v
        elif isinstance(v, tuple):
            data[k] = {'_type': "tuple", 'value': v}
        elif isinstance(v, set):
            data[k] = {'_type': "set", 'value': list(v)}
        elif isinstance(v, queue.Queue):
            pass

            # data[k] = {'_type':"queue", 'value':list(v.queue)}
        elif isinstance(v, dict):
            data[k] = {}
            for kk, vv in v.items():
                if hasattr(vv, "__dict__"):
                    data[k][kk] = create_dict_snapshot(vv)
                else:
                    data[k][kk] = vv
        elif isinstance(v, list):
            data[k] = []
            for vv in v:
                if hasattr(vv, "__dict__"):
                    data[k].append(create_dict_snapshot(vv))
                else:
                    data[k].append(vv)
        else:
            # print("Skipping snapshotting of:{} with value {}".format(k, v))
            pass
            
    return {"_type": _type, "data": data}


def parse_inner_val(v):
    result = None
    if v is None or isinstance(v, (int, float, str, Vector2, tuple)):
        result = v
    elif isinstance(v, dict):
        if v.get("_type") == "tuple":
            result = tuple(v.get("value", None))
        elif v.get("_type") == "set":
            result = set(v.get("value", []))
        elif v.get("_type") == "queue":
            result = queue.Queue(v.get("value", []))
        elif "_type" not in v:
            result = {}
            for kk, vv in v.items():
                result[kk] = parse_inner_val(vv)
        elif "_type" in v:
            cls = get_base_cls_by_name(v['_type'])
            o = cls()
            o.load_snapshot(v)
            result = o

    elif isinstance(v, list):
        result = v
    else:
        raise TypeError("")
    return result


def parse_inner_val_old(v):
    result = None
    if v is None or isinstance(v, (int, float, str, Vector2, tuple)):
        result = v
    elif (isinstance(v, dict) and v.get("_type") == "tuple"):
        result = tuple(v.get("value", None))

    elif v is None or (isinstance(v, dict) and ("_type" not in v)):
        result = {}
        for kk, vv in v.items():
            result[kk] = parse_inner_val(vv)
    elif v is None or (isinstance(v, dict) and ("_type" in v)):
        cls = get_base_cls_by_name(v['_type'])
        o = cls()
        o.load_snapshot(v)
        result = o
    elif v is None or (isinstance(v, list)):
        result = v
    else:
        print("Type error")
        raise TypeError("")
    return result


def load_dict_snapshot(obj, dict_data, exclude_keys={}):
    for k, v in dict_data['data'].items():
        if k in exclude_keys or k.startswith("_l_"):
            continue
        try:
            obj.__dict__[k] = parse_inner_val(v)
        except TypeError as e:
            pass


def get_shape_from_dict(dict_data):
    cls = globals()[dict_data['_type']]
    shape: Shape = cls(**dict_data['params'])
    shape.load_snapshot(dict_data)
    return shape


class Base:

    def __init__(self):
        self.net_blacklist = set()
        self.net_whitelist = set()

    @staticmethod
    def create_from_snapshot(snapshot):
        cls = get_base_cls_by_name(snapshot['_type'])
        o = cls()
        o.load_snapshot(snapshot)
        return o

    def get_snapshot(self):
        return create_dict_snapshot(self)

    def load_snapshot(self, data):
        load_dict_snapshot(self, data)


class PlayerConfig(Base):

    def __init__(self):
        """
        """


def state_to_dict(state):
    new_state = {}
    for k, tuplist in state.items():
        new_state[k] = {}
        for kk, vv in tuplist:
            new_state[k][kk] = vv
    return new_state


def dict_to_state(data):
    state = {}
    for k, d in data.items():
        state[k] = []
        for kk, vv in d.items():
            state[k].append((kk, vv))
    return state


class Shape(Base):

    def __init__(self):
        self.label = "default"
        self.object_id = None

    def set_label(self, label):
        self.label = label

    def get_label(self):
        return self.label

    def set_object_id(self, object_id):
        self.object_id = object_id

    def get_object_id(self):
        return self.object_id

    def get_common_info(self):
        return create_dict_snapshot(self, exclude_keys={})


class Line(Shape):

    def __init__(self, a, b, radius, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.a = a
        self.b = b
        self.radius = radius

    def get_snapshot(self):
        data = self.get_common_info()
        data['params'] = {
            "a": self.a,
            "b": self.b,
            "radius": self.radius}
        return data


class Polygon(Shape):

    def __init__(self, vertices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vertices = vertices

    def get_vertices(self):
        return self.vertices

    def get_snapshot(self):
        data = self.get_common_info()
        data['params'] = {
            "vertices": [v for v in self.get_vertices()]
        }
        return data


class Rectangle(Polygon):

    def __init__(self, center, width, height, *args, **kwargs):
        super().__init__(*args, **kwargs)
        w = width/2
        h = height/2
        v1 = Vector2(center.x - w, center.y + h)
        v2 = Vector2(center.x + w, center.y + h)
        v3 = Vector2(center.x + w, center.y - h)
        v4 = Vector2(center.x - w, center.y - h)
        vertices = [v1, v2, v3, v4]
        super(vertices)

    def get_snapshot(self):
        data = self.get_common_info()
        data['params'] = {
            "vertices": [v for v in self.get_vertices()],
        }
        return data


class Circle(Shape):

    def __init__(self, radius, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.radius = radius

    def get_snapshot(self):
        data = self.get_common_info()
        data['params'] = {'radius': self.radius}
        return data


class TimeLoggingContainer:

    def __init__(self, log_size):
        self.log_size = log_size
        self.log = [None for i in range(log_size)]
        self.timestamps = [None for i in range(log_size)]
        self.counter = 0

    def get_id(self):
        obj = self.get_latest()
        return obj.get_id()

    def add(self, timestamp, obj):
        self.log[self.counter % self.log_size] = obj
        self.timestamps[self.counter % self.log_size] = timestamp
        self.counter += 1

    def link_to_latest(self, timestamp):
        self.add(timestamp, self.get_latest_with_timestamp())

    def get_bordering_timestamps(self, timestamp):
        # TODO binary search is faster
        timestamp_lookup = {v: i for i, v in enumerate(self.timestamps)}
        lst = sorted([i for i in self.timestamps if i is not None])
        next_idx = None
        previous_idx = None
        for i, v in enumerate(lst):
            if v >= timestamp:
                next_idx = v
                break
            elif v < timestamp:
                previous_idx = lst[i]
        return (timestamp_lookup.get(previous_idx, None),
                previous_idx,
                timestamp_lookup.get(next_idx, None),
                next_idx)

    def get_pair_by_timestamp(self, timestamp):
        prev_idx, prev_timestamp, next_idx, next_timestamp = self.get_bordering_timestamps(
            timestamp)
        next_obj = None if next_idx is None else self.log[next_idx]
        prev_obj = None if prev_idx is None else self.log[prev_idx]
        return prev_obj, prev_timestamp, next_obj, next_timestamp

    def get_prev_entry(self, timestamp):
        prev_obj, prev_timestamp, next_obj, next_timestamp = self.get_pair_by_timestamp(
            timestamp)
        return prev_timestamp, prev_obj

    def get_next_entry(self, timestamp):
        prev_obj, prev_timestamp, next_obj, next_timestamp = self.get_pair_by_timestamp(
            timestamp)
        return next_timestamp, next_obj

    def get_latest(self):

        if self.counter == 0:
            return None, None
        idx = (self.counter-1) % self.log_size
        return self.log[idx]

    def get_latest_with_timestamp(self):
        if self.counter == 0:
            return None, None
        idx = (self.counter-1) % self.log_size
        obj = self.log[idx]
        timestamp = self.timestamps[idx]
        return timestamp, obj


class ShapeGroup(Base):

    def __init__(self):
        self._shapes: Dict[str, Shape] = {}

    def add(self, shape: Shape):
        self._shapes[shape.get_label()] = shape

    def get_shapes(self) -> List[Shape]:
        return self._shapes.values()

    def get_snapshot(self):
        data = {}
        for k, s in self._shapes.items():
            data[k] = s.get_snapshot()
        dict_data = {}
        dict_data['data'] = data
        return dict_data

    def load_snapshot(self, dict_data: Dict[str, Dict]):
        data = dict_data['data']
        for k, shape_dict in data:
            self._shapes[k].load_snapshot(shape_dict)
