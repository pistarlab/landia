
from landia.common import Vector2
from .survival_utils import normalize_angle, normalized_direction
from landia import gamectx
from .survival_common import Behavior
from .survival_objects import AnimateObject, PhysicalObject
from landia.clock import clock
import random


def get_blocking_object(obj,direction)->PhysicalObject:
    target_pos = obj.get_position() + (direction * gamectx.content.tile_size)
    target_coord = gamectx.physics_engine.vec_to_coord(target_pos)
    blocking_obj:PhysicalObject = None
    for blocking_obj in gamectx.get_objects_by_coord(target_coord):
        if blocking_obj.collision_type == 1:
            return blocking_obj
    return None

class FollowAnimals(Behavior):


    def __init__(self):
        
        self.following_obj = None
        
        self.last_check = 0
        self.check_freq = 10 * gamectx.content.step_duration()
    
    def on_update(self,obj:AnimateObject):
        if self.following_obj is None or (clock.get_ticks() - self.last_check) > self.check_freq:
            for obj2 in obj.get_visible_objects():
                if obj.config_id != obj2.config_id and 'animal' in obj2.get_types():
                    self.following_obj = obj2
            self.last_check = clock.get_ticks()

        if self.following_obj is not None:
            orig_direction: Vector2 = self.following_obj.get_position() - obj.get_position()
            direction = normalized_direction(orig_direction)
            new_angle = normalize_angle(Vector2(0, 1).angle_to(direction))
            mag = orig_direction.magnitude()
            if mag <= gamectx.content.tile_size:
                direction = Vector2(0, 0)
            if mag <= gamectx.content.tile_size and new_angle == obj.angle:
                obj.use()
            else:
                obj.walk(direction, new_angle)


class FleeAnimals(Behavior):
    
    def on_update(self,obj:AnimateObject):
        for obj2 in obj.get_visible_objects():
            if  obj.config_id != obj2.config_id and 'animal' in obj2.get_types():
                orig_direction: Vector2 = obj2.get_position() - obj.get_position()
                direction = normalized_direction(orig_direction)
                new_angle = normalize_angle(Vector2(0, 1).angle_to(direction))
                obj.walk(direction * -1, new_angle + 180 % 360)   

class PlayingTag(Behavior):

    def __init__(self,tagcontroller):
        self.tagcontroller = tagcontroller
        self.following_obj = None
        self.recent_pos = set()
        
        self.last_freq = 0
        self.check_freq = 100

    def find_follow_object(self,obj):
        objs = []
        closest_distance = None
        closest_obj = None
        for obj2 in self.tagcontroller.get_objects():
            if  obj.get_id() != obj2.get_id() and obj2.get_id() in self.tagcontroller.obj_ids and obj2.get_position() is not None:
                distance = obj2.get_position().distance_to(obj.get_position())
                objs.append((obj2,distance))
                if closest_obj is None or closest_distance > distance:
                    closest_obj = obj2
                    closest_distance = distance

        self.following_obj = closest_obj


    def on_it(self,obj:AnimateObject):
        # position = obj.get_position()

        if self.following_obj is None:
            self.find_follow_object(obj)
            self.recent_pos = set()
        elif clock.get_ticks() - self.last_freq >self.check_freq:
            self.find_follow_object(obj)

        orig_direction: Vector2 = self.following_obj.get_position() - obj.get_position()
        direction = normalized_direction(orig_direction)
        new_angle = normalize_angle(Vector2(0, 1).angle_to(direction))
        mag = orig_direction.magnitude()
        if mag <= gamectx.content.tile_size:
            direction = Vector2(0, 0)
        if mag <= gamectx.content.tile_size and new_angle == normalize_angle(obj.angle):
            obj.use()
        else:

            obj.walk(direction, new_angle)


    def on_notit(self,obj:AnimateObject):
        self.following_obj = None
        obj2 = self.tagcontroller.tagged_obj
        if obj2 is not None and obj2.get_position() is not None and obj.get_position() is not None:
            distance = obj.get_position().distance_to(obj2.get_position())
            if distance < gamectx.content.tile_size * 4:
                orig_direction: Vector2 = obj2.get_position() - obj.get_position()
                direction = normalized_direction(orig_direction)
                new_angle = normalize_angle(Vector2(0, 1).angle_to(direction))
                obj.walk(direction * -1, (new_angle +180) % 360)

    def on_update(self,obj:AnimateObject):
        it = True
        if self.tagcontroller.tagged_obj.get_id() == obj.get_id():
            self.on_it(obj)
        else:
            self.on_notit(obj)



class PlayingInfection(Behavior):

    def __init__(self,controller):
        self.controller = controller
        self.following_obj = None
        self.recent_pos = set()
        
        self.last_freq = 0
        self.check_freq = 100
        self.last_move_blocked=False
        self.last_move_direction = None
        self.last_explore_direction = random.choice([-1,1])


    def find_closest_object(self,obj,find_infected=True):
        objs = []
        closest_distance = None
        closest_obj = None
        for obj2 in self.controller.get_objects():
            if find_infected:
                # if looking for infected, then skip those not infected
                if not self.controller.infected_tag in obj2.tags:
                    continue
            else:
                # if looking for those NOT infected, then skip those infected
                if self.controller.infected_tag in obj2.tags:
                    continue
            
            if  obj.get_id() != obj2.get_id() and obj2.get_id() in self.controller.obj_ids and obj2.get_position() is not None:
                distance = obj2.get_position().distance_to(obj.get_position())
                objs.append((obj2,distance))
                if closest_obj is None or closest_distance > distance:
                    closest_obj = obj2
                    closest_distance = distance

        return closest_obj

    def find_follow_object(self,obj):
        self.following_obj = self.find_closest_object(obj,find_infected=False)


    def find_nearest_infected(self,obj):
        return self.find_closest_object(obj,find_infected=True)


    def on_infected(self,obj:AnimateObject):
        # position = obj.get_position()

        if self.following_obj is None:
            self.find_follow_object(obj)
            self.recent_pos = set()
        elif clock.get_ticks() - self.last_freq >self.check_freq:
            self.find_follow_object(obj)
        
        if self.following_obj is None:
            # TODO: roam?
            return 

        orig_direction: Vector2 = self.following_obj.get_position() - obj.get_position()
        direction = normalized_direction(orig_direction)
        new_angle = normalize_angle(Vector2(0, 1).angle_to(direction))
        mag = orig_direction.magnitude()
        if mag <= gamectx.content.tile_size:
            direction = Vector2(0, 0)
        if mag <= gamectx.content.tile_size and new_angle == normalize_angle(obj.angle):
            obj.use()
        else:

            if self.last_move_blocked and random.random()>0.9:
                direction = self.last_move_direction.rotate(90 * self.last_explore_direction)
    
                new_angle = normalize_angle(Vector2(0, 1).angle_to(direction))
            else:
                direction = normalized_direction(orig_direction)
                new_angle = normalize_angle(Vector2(0, 1).angle_to(direction))

            blocking_obj = get_blocking_object(obj,direction)

            if blocking_obj != None and self.following_obj is not None and blocking_obj.get_id() != self.following_obj.get_id():
                if not self.last_move_blocked and random.random() > 0.8:
                    self.last_explore_direction *=-1
                self.last_move_blocked = True
                self.last_move_direction = direction
            else:
                self.last_move_blocked = False
                self.last_move_direction = direction            
                obj.walk(direction, new_angle)


    def on_not_infected(self,obj:AnimateObject):
        self.following_obj = None
        obj2 = self.find_nearest_infected(obj)
        if obj2 is not None and obj2.get_position() is not None and obj.get_position() is not None:
            distance = obj.get_position().distance_to(obj2.get_position())
            if distance < gamectx.content.tile_size * 4:
                orig_direction: Vector2 = obj2.get_position() - obj.get_position()
                direction = normalized_direction(orig_direction)
                new_angle = normalize_angle(Vector2(0, 1).angle_to(direction))
                obj.walk(direction * -1, (new_angle +180) % 360)

    def on_update(self,obj:AnimateObject):
        it = True
        if self.controller.infected_tag in obj.tags:
            self.on_infected(obj)
        else:
            self.on_not_infected(obj)



class PlayingCTF(Behavior):

    def __init__(self,controller):
        from .survival_controllers import CTFController
        self.controller:CTFController = controller
        self.following_obj = None
        self.recent_pos = set()
        
        self.last_freq = 0
        self.check_freq = 100
        self.last_move_blocked=False
        self.last_move_direction = None
        self.last_explore_direction = random.choice([-1,1])
        self.attacking = False


    def follow_obj(self,obj:AnimateObject,target_obj:PhysicalObject):

        orig_direction: Vector2 = target_obj.get_position() - obj.get_position()

        if not self.attacking and self.last_move_blocked and random.random()>0.9:
            direction = self.last_move_direction.rotate(90 * self.last_explore_direction)
 
            new_angle = normalize_angle(Vector2(0, 1).angle_to(direction))
        else:
            direction = normalized_direction(orig_direction)
            new_angle = normalize_angle(Vector2(0, 1).angle_to(direction))

        blocking_obj = get_blocking_object(obj,direction)

        if blocking_obj != None:
            if not self.last_move_blocked and random.random() > 0.8:
                self.last_explore_direction *=-1
                
            team = self.controller.get_opponents_team(obj, blocking_obj)
            if team is not None and random.random()>0.2:
                if not self.attacking:
                    obj.walk(direction, new_angle)
                    self.attacking = True
                else:
                    obj.unarmed_attack()
            else:
                self.attacking = False
   
            self.last_move_blocked = True
            self.last_move_direction = direction
        else:
            self.last_move_blocked = False
            self.last_move_direction = direction
            self.attacking = False
            
            obj.walk(direction, new_angle)

    def get_other_teams_flag(self,obj:AnimateObject):
        other_team = random.choice(self.controller.get_other_teams(obj))
        if other_team.flag_holder_id is None:
            flag = gamectx.get_object_by_id(other_team.flag_id)
            self.follow_obj(obj,target_obj=flag)
        else:
            flag_holder = gamectx.get_object_by_id(other_team.flag_holder_id)
            self.follow_obj(obj,target_obj=flag_holder)

    def capture_other_teams_flag(self,obj):
        team = self.controller.get_team(obj)
        zone = gamectx.get_object_by_id(team.flag_zone_id)
        self.follow_obj(obj,target_obj=zone)       

    def on_update(self,obj:AnimateObject):
        
        if self.controller.has_flag_tag in obj.tags:
            self.capture_other_teams_flag(obj)
        else:
            self.get_other_teams_flag(obj)