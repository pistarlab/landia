from typing import Any, Dict, List, Tuple


from .object import GObject


class GObjectManager:

    def __init__(self):
        self.objects: Dict[str, GObject] = {}
        self.configs_id_index: Dict[str, set] = {}
        # self.obj_history: Dict[str,str] = {}

    def add(self, obj: GObject):
        self.objects[obj.get_id()] = obj
        obj_id_set = self.configs_id_index.get(obj.config_id, set())
        obj_id_set.add(obj.get_id())
        self.configs_id_index[obj.config_id] = obj_id_set

    def clear_objects(self):
        self.objects: Dict[str, GObject] = {}
        self.configs_id_index: Dict[str, set] = {}

    def get_objects_by_config_id(self, config_id):
        return [self.objects[oid] for oid in self.configs_id_index.get(config_id, set())]

    def get_by_id(self, obj_id) -> GObject:
        return self.objects.get(obj_id, None)

    def remove_by_id(self, obj_id):
        obj = self.objects[obj_id]
        del self.objects[obj_id]
        obj_id_set = self.configs_id_index.get(obj.config_id, set())
        obj_id_set.discard(obj.get_id())

    def get_objects(self) -> Dict[str, GObject]:
        return self.objects

    def get_snapshot_update(self, changed_since):
        snapshot_list = []
        for obj in list(self.get_objects().values()):
            if obj.get_last_change() >= changed_since:
                snapshot_list.append(obj.get_snapshot())
        return snapshot_list

    def get_snapshot_full(self):
        snapshot_list = []
        for obj in list(self.get_objects().values()):
            snapshot_list.append(obj.get_snapshot())
        return snapshot_list
