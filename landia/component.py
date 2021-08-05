from .common import Base


class Component(Base):

    def __init__(self,gobj):
        self.gobj = gobj
        self.enabled=True

    def update(self):
        pass


