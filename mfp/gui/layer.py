#! /usr/bin/env python
'''
layer.py
A layer in the patch window
'''
from .backend_interfaces import LayerBackend
from mfp import log

class Layer:
    def __init__(self, app_window, patch, name, scope="__patch__"):
        self.app_window = app_window
        self.patch = patch
        self.name = name
        self.scope = scope
        self.objects = []

        factory = LayerBackend.get_backend(app_window.backend_name)
        self.backend = factory(self)

    def resort(self, obj):
        if obj in self.objects:
            self.objects.remove(obj)
        self.add(obj)

    def add(self, obj):
        BAD = 1000000
        obj.layer = self

        def distance(left, right):
            d1 = ((obj.position_x - left.position_x) ** 2
                  + (obj.position_y - left.position_y) ** 2) ** 0.5
            d2 = ((obj.position_x - right.position_x) ** 2
                  + (obj.position_y - right.position_y) ** 2) ** 0.5
            return d1 + d2

        if not len(self.objects):
            self.objects = [obj]
        elif ((obj.position_x < self.objects[0].position_x)
              and (obj.position_y < self.objects[0].position_y)):
            self.objects[:0] = [obj]
        elif ((obj.position_x > self.objects[-1].position_x)
              and (obj.position_y > self.objects[-1].position_y)):
            self.objects.append(obj)
        else:
            distances = []
            for i in range(len(self.objects) - 1):
                distances.append(distance(self.objects[i], self.objects[i + 1]))

            if ((obj.position_x < self.objects[0].position_x)
                    or (obj.position_y < self.objects[0].position_y)):
                distances[0:0] = [distance(self.objects[0], self.objects[0])]
            else:
                distances[0:0] = [BAD]

            if ((obj.position_x > self.objects[-1].position_x)
                    or (obj.position_y > self.objects[-1].position_y)):
                distances.append(distance(self.objects[-1], self.objects[-1]))
            else:
                distances.append(BAD)

            newloc = distances.index(min(distances))
            self.objects[newloc:newloc] = [obj]

        self.backend.add(obj)

    def remove(self, obj):
        if obj in self.objects:
            self.objects.remove(obj)
        obj.layer = None
        self.backend.remove(obj)

    def delete(self):
        self.backend.delete()


