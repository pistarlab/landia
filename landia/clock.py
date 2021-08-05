import time
import pygame

class StepClock:
    
    def __init__(self,tick_rate=0):
        self._start_time = time.time()
        self.tick_time = 0
        self.pygame_clock = pygame.time.Clock()
        self.tick_rate = tick_rate

    def get_start_time(self):
        return self._start_time

    def set_start_time(self,start_time):
        self._start_time=start_time

    def set_tick_rate(self,tick_rate):
        self.tick_rate = tick_rate

    def get_tick_size(self):
        return 1.0 / self.tick_rate

    def get_game_time(self):
        return (time.time()- self._start_time)
    
    def tick(self):
        if self.tick_rate: 
            self.pygame_clock.tick(self.tick_rate)
            self.tick_time  = round(self.get_game_time() * self.tick_rate)
        else:
            self.tick_time +=1
        return self.tick_time

    def get_ticks(self):
        return self.tick_time


clock = StepClock()