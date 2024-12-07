# particle.py

from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, ListProperty
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse
import random

class Particle(Widget):
    color = ListProperty([1, 1, 1, 1])
    velocity_x = NumericProperty(0)
    velocity_y = NumericProperty(0)
    lifetime = NumericProperty(1)

    def __init__(self, **kwargs):
        super(Particle, self).__init__(**kwargs)
        self.age = 0
        # Remove scheduling from __init__
        # Clock.schedule_interval(self.update, 1 / 60)
        self._update_event = None  # To keep track of the scheduled event

    def on_parent(self, instance, parent):
        if parent:
            # Schedule update when added to parent
            self._update_event = Clock.schedule_interval(self.update, 1 / 60)
        else:
            # Unschedule update when removed from parent
            if self._update_event:
                self._update_event.cancel()
                self._update_event = None

    def update(self, dt):
        self.age += dt
        if self.age >= self.lifetime:
            if self.parent:
                self.parent.remove_widget(self)
            if self._update_event:
                self._update_event.cancel()
                self._update_event = None
            return
        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt
        self.velocity_y -= 9.8 * dt  # Gravity effect
        self.color[3] = max(0, 1 - self.age / self.lifetime)  # Fade out
