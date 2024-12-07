from kivy.app import App
from kivy.uix.widget import Widget
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.uix.label import Label
from kivy.graphics.texture import Texture
from kivy.graphics import Rectangle, Color, Ellipse, PushMatrix, PopMatrix, Translate, Line
from kivy.core.audio import SoundLoader
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
import random
import json
from colorsys import hsv_to_rgb

def colors_are_equal(color1, color2, tolerance=0.01):
    return all(abs(c1 - c2) <= tolerance for c1, c2 in zip(color1, color2))

class PixelButton(Button):
    border_color = ListProperty([1, 1, 1, 1])

class Particle(Widget):
    color = ListProperty([1, 1, 1, 1])
    velocity_x = NumericProperty(0)
    velocity_y = NumericProperty(0)
    lifetime = NumericProperty(1.0)
    initial_size = NumericProperty(10)

    def __init__(self, **kwargs):
        super(Particle, self).__init__(**kwargs)
        Clock.schedule_interval(self.update, 1 / 60)
        self.elapsed_time = 0

    def update(self, dt):
        self.elapsed_time += dt
        if self.elapsed_time > self.lifetime:
            if self.parent:
                self.parent.remove_widget(self)
            return False

        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt

        remaining_life = max(0, self.lifetime - self.elapsed_time)
        alpha = remaining_life / self.lifetime
        self.color[3] = alpha

        scale = remaining_life / self.lifetime
        self.size = [self.initial_size * scale, self.initial_size * scale]

class Player(Widget):
    color = ListProperty([1, 0, 0, 1])
    scale = NumericProperty(1.0)

    def __init__(self, **kwargs):
        super(Player, self).__init__(**kwargs)
        print("Player created")

    def move(self, touch):
        self.center_x = touch.x

    def start_pulsing(self):
        anim = Animation(scale=1.05, duration=1) + Animation(scale=1.0, duration=1)
        anim.repeat = True
        anim.start(self)


class FallingObject(Widget):
    color = ListProperty([1, 1, 1, 1])
    speed = NumericProperty(200)
    angle = NumericProperty(0)


class PowerUp(Widget):
    effect = StringProperty()
    color = ListProperty([1, 1, 0, 1])
    speed = NumericProperty(200)
    angle = NumericProperty(0)


class MusicToggleButton(Button):
    is_music_on = BooleanProperty(True)

    def __init__(self, **kwargs):
        super(MusicToggleButton, self).__init__(**kwargs)
        self.font_name = 'DejaVuSans.ttf'
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.text = "♪"  # Music on symbol
        self.font_size = 24
        self.size = (50, 50)
        self.size_hint = (None, None)
        self.bind(on_release=self.toggle_music)

    def toggle_music(self, instance):
        app = App.get_running_app()
        if self.is_music_on:
            # Turn music off
            if app.background_music:
                app.background_music.stop()
            self.text = "×"
            self.is_music_on = False
            print("Music turned OFF")
        else:
            # Turn music on
            if app.background_music:
                app.background_music.play()
            self.text = "♪"
            self.is_music_on = True
            print("Music turned ON")


class GameOverScreen(Widget):
    game_screen = ObjectProperty(None)
    bg_opacity = NumericProperty(0)

    def __init__(self, game_screen=None, **kwargs):
        from kivy.animation import Animation
        super(GameOverScreen, self).__init__(**kwargs)
        self.game_screen = game_screen

        anim = Animation(bg_opacity=0.7, duration=1)
        anim.start(self)

        Clock.schedule_once(self.post_init)
        self.bind(parent=self.on_parent)

    def on_parent(self, instance, value):
        if value:
            self.size = self.parent.size
            self.pos = self.parent.pos

    def post_init(self, dt):
        self.animate_glow()

    def animate_glow(self):
        from kivy.animation import Animation
        label = self.ids.game_over_label
        anim = (Animation(font_size=65, duration=1) + Animation(font_size=60, duration=1))
        anim.repeat = True
        anim.start(label)

    def on_touch_down(self, touch):
        print("GameOverScreen received a touch.")
        return super(GameOverScreen, self).on_touch_down(touch)

    def on_replay(self):
        print("Replay button pressed.")
        if self.game_screen:
            self.game_screen.restart_game()


class StatusIndicator(Widget):
    icon_source = StringProperty('')
    value = NumericProperty(0)

    def __init__(self, **kwargs):
        super(StatusIndicator, self).__init__(**kwargs)
        self.bind(value=self.on_value_change)

    def on_value_change(self, instance, value):
        from kivy.animation import Animation
        self.ids.value_label.text = str(value)
        label_anim = (Animation(font_size=24, duration=0.1) + Animation(font_size=20, duration=0.1))
        label_anim.start(self.ids.value_label)


class GameScreen(Screen):
    player_widget = ObjectProperty(None)
    score = NumericProperty(0)
    high_score = NumericProperty(0)
    lives = NumericProperty(3)
    combo_count = NumericProperty(0)
    score_multiplier = NumericProperty(1)
    level = NumericProperty(1)
    speed_multiplier = NumericProperty(1.0)
    spawn_interval = NumericProperty(1.0)
    achievements = {}
    skins_unlocked = []
    background_color = ListProperty([0.1, 0.1, 0.1, 1])
    gradient_texture = ObjectProperty(None)
    background_music = ObjectProperty(None)

    update_event = None
    spawn_event = None
    color_change_event = None
    game_started = False  # To prevent multiple setups

    def __init__(self, **kwargs):
        super(GameScreen, self).__init__(**kwargs)
        self.falling_objects = []
        self.colors = [
            [1, 0, 0, 1],
            [0, 1, 0, 1],
            [0, 0, 1, 1],
            [1, 1, 0, 1],
        ]
        self.game_over_screen = None

        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        if self._keyboard:
            self._keyboard.bind(on_key_down=self.on_key_down)

        self.load_high_score()
        self.load_achievements()
        self.load_skins()
        self.change_background()

    def on_enter(self, *args):
        # Only setup the game if it hasn't started yet
        if not self.game_started:
            self.setup_game()
            self.game_started = True
        return super(GameScreen, self).on_enter(*args)

    def setup_game(self):
        self.update_event = Clock.schedule_interval(self.update_objects, 1 / 60)
        self.spawn_event = Clock.schedule_interval(self.spawn_object, self.spawn_interval)
        self.color_change_event = Clock.schedule_interval(self.auto_change_player_color, 5)

    def pause_game(self):
        if self.update_event:
            Clock.unschedule(self.update_event)
            self.update_event = None
        if self.spawn_event:
            Clock.unschedule(self.spawn_event)
            self.spawn_event = None
        if self.color_change_event:
            Clock.unschedule(self.color_change_event)
            self.color_change_event = None

    def resume_game(self):
        if not self.update_event:
            self.update_event = Clock.schedule_interval(self.update_objects, 1 / 60)
        if not self.spawn_event:
            self.spawn_event = Clock.schedule_interval(self.spawn_object, self.spawn_interval)
        if not self.color_change_event:
            self.color_change_event = Clock.schedule_interval(self.auto_change_player_color, 5)

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self.on_key_down)
        self._keyboard = None

    def on_key_down(self, keyboard, keycode, text, modifiers):
        if self.player_widget:
            if keycode[1] == 'left':
                self.player_widget.x -= 10
            elif keycode[1] == 'right':
                self.player_widget.x += 10

    def on_size(self, *args):
        if self.player_widget:
            self.player_widget.center_x = self.width / 2
            self.player_widget.y = 10

    def change_background(self):
        self.update_background()

    def update_background(self):
        gradient = Texture.create(size=(1, 64), colorfmt='rgba')
        hue = (self.level * 30) % 360
        saturation = 0.7
        value_top = 0.9
        value_bottom = 0.6
        r_top, g_top, b_top = hsv_to_rgb(hue / 360.0, saturation, value_top)
        r_bottom, g_bottom, b_bottom = hsv_to_rgb(hue / 360.0, saturation, value_bottom)
        color_top = [r_top, g_top, b_top, 1]
        color_bottom = [r_bottom, g_bottom, b_bottom, 1]
        buf = bytearray()
        for i in range(64):
            t = i / 63
            r = color_bottom[0] * (1 - t) + color_top[0] * t
            g = color_bottom[1] * (1 - t) + color_top[1] * t
            b = color_bottom[2] * (1 - t) + color_top[2] * t
            a = 255
            buf.extend([int(r * 255), int(g * 255), int(b * 255), a])
        gradient.blit_buffer(bytes(buf), colorfmt='rgba', bufferfmt='ubyte')
        self.gradient_texture = gradient

    def update_objects(self, dt):
        if not self.player_widget:
            return
        for obj in self.falling_objects[:]:
            obj.y -= obj.speed * self.speed_multiplier * dt
            obj.angle += 90 * dt
            if obj.y + obj.height < 0:
                self.remove_object(obj)
                self.combo_count = 0
                self.score_multiplier = 1
                continue
            if self.check_collision(self.player_widget, obj):
                if isinstance(obj, PowerUp):
                    self.activate_power_up(obj.effect)
                    self.remove_object(obj)
                    continue
                if colors_are_equal(self.player_widget.color, obj.color):
                    self.combo_count += 1
                    if self.combo_count % 5 == 0:
                        self.score_multiplier += 1
                    self.score += 1 * self.score_multiplier
                    self.check_achievements()
                    self.check_level_up()
                    self.emit_particles(self.player_widget.center, self.player_widget.color)
                else:
                    self.lives -= 1
                    self.combo_count = 0
                    self.score_multiplier = 1
                    self.emit_particles(self.player_widget.center, [1, 0, 0, 1])
                self.remove_object(obj)
        if self.lives <= 0:
            self.game_over()

    def spawn_object(self, dt):
        if random.random() < 0.1:
            obj = PowerUp()
            obj.effect = random.choice(['slow_motion', 'extra_life', 'double_score'])
            obj.color = [1, 1, 0, 1]
        else:
            obj = FallingObject()
            obj.color = random.choice(self.colors)

        base_speed = random.randint(150, 300)
        obj.speed = base_speed
        obj.size = (40, 40)
        obj.center_x = random.randint(int(obj.width / 2), int(self.width - obj.width / 2))
        obj.y = self.height
        self.add_widget(obj)
        self.falling_objects.append(obj)

    def remove_object(self, obj):
        if obj in self.falling_objects:
            self.falling_objects.remove(obj)
        if obj.parent:
            self.remove_widget(obj)

    def check_collision(self, widget1, widget2):
        return widget1.collide_widget(widget2)

    def on_touch_move(self, touch):
        if self.player_widget:
            self.player_widget.move(touch)

    def on_touch_down(self, touch):
        if self.player_widget:
            self.player_widget.move(touch)
        return super(GameScreen, self).on_touch_down(touch)

    def change_player_color(self):
        possible_colors = [
            color for color in self.colors if not colors_are_equal(color, self.player_widget.color)
        ]
        if possible_colors:
            self.player_widget.color = random.choice(possible_colors)
            anim = Animation(scale=1.2, duration=0.1) + Animation(scale=1.0, duration=0.1)
            anim.start(self.player_widget)

    def auto_change_player_color(self, dt):
        self.change_player_color()

    def game_over(self):
        self.pause_game()
        app = App.get_running_app()
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()
            print(f"New high score: {self.high_score}")
        print("Game Over")
        self.show_game_over_screen()

    def show_game_over_screen(self):
        self.game_over_screen = GameOverScreen(game_screen=self)
        self.add_widget(self.game_over_screen)
        print("GameOverScreen added to GameScreen.")

    def restart_game(self):
        print("Restarting the game...")
        self.pause_game()  # Ensure no old events are running

        if self.game_over_screen and self.game_over_screen.parent:
            self.remove_widget(self.game_over_screen)
            self.game_over_screen = None

        # Reset game state
        self.score = 0
        self.lives = 3
        self.combo_count = 0
        self.score_multiplier = 1
        self.speed_multiplier = 1.0
        self.level = 1
        self.spawn_interval = 1.0
        self.falling_objects.clear()

        # Remove any falling objects currently in the game
        for child in self.children[:]:
            if isinstance(child, FallingObject) or isinstance(child, PowerUp):
                self.remove_widget(child)

        self.change_background()

        # Now schedule events again
        self.update_event = Clock.schedule_interval(self.update_objects, 1 / 60)
        self.spawn_event = Clock.schedule_interval(self.spawn_object, self.spawn_interval)
        self.color_change_event = Clock.schedule_interval(self.auto_change_player_color, 5)

    def load_high_score(self):
        try:
            with open('high_score.json', 'r') as f:
                self.high_score = json.load(f)['high_score']
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            self.high_score = 0
            print("No previous high score found, starting at 0.")

    def save_high_score(self):
        with open('high_score.json', 'w') as f:
            json.dump({'high_score': self.high_score}, f)

    def load_achievements(self):
        try:
            with open('achievements.json', 'r') as f:
                self.achievements = json.load(f)
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            self.achievements = {}
            print("No previous achievements found, starting fresh.")

    def save_achievements(self):
        with open('achievements.json', 'w') as f:
            json.dump(self.achievements, f)

    def load_skins(self):
        try:
            with open('skins.json', 'r') as f:
                self.skins_unlocked = json.load(f)['skins']
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            self.skins_unlocked = []
            print("No skins unlocked yet, starting with default.")

    def check_achievements(self):
        achievement_conditions = {
            'First Blood': {
                'condition': self.score >= 1,
                'message': 'Achievement Unlocked: First Blood!',
            },
            'Combo Master': {
                'condition': self.combo_count >= 10,
                'message': 'Achievement Unlocked: Combo Master!',
            },
            'Survivor': {
                'condition': self.level >= 5,
                'message': 'Achievement Unlocked: Survivor!',
            },
            'High Scorer': {
                'condition': self.score >= 50,
                'message': 'Achievement Unlocked: High Scorer!',
            },
        }

        for key, value in achievement_conditions.items():
            if key not in self.achievements and value['condition']:
                self.achievements[key] = True
                self.save_achievements()
                print(value['message'])
                self.show_achievement_popup(value['message'])

    def show_achievement_popup(self, message):
        from kivy.animation import Animation
        label = Label(text=message, font_size=24, color=(1, 1, 0, 0), bold=True)
        label.center = self.center
        self.add_widget(label)
        anim_in = Animation(color=(1, 1, 0, 1), duration=0.5)
        anim_out = Animation(color=(1, 1, 0, 0), duration=0.5)
        anim_out.start_delay = 1
        anim = anim_in + anim_out
        anim.bind(on_complete=lambda *args: self.remove_widget(label))
        anim.start(label)

    def check_level_up(self):
        new_level = self.score // 10 + 1
        if new_level > self.level:
            self.level = new_level
            self.speed_multiplier *= 1.1
            self.spawn_interval = max(0.2, self.spawn_interval * 0.95)
            if self.spawn_event:
                Clock.unschedule(self.spawn_event)
                self.spawn_event = Clock.schedule_interval(self.spawn_object, self.spawn_interval)
            print(f'Level Up! You are now on level {self.level}')
            self.show_level_up_popup(f'Level {self.level}!')
            self.change_background()

    def show_level_up_popup(self, message):
        from kivy.animation import Animation
        label = Label(text=message, font_size=30, color=(0, 1, 0, 0), bold=True)
        label.center = self.center
        self.add_widget(label)
        anim_in = Animation(color=(0, 1, 0, 1), duration=0.5)
        anim_out = Animation(color=(0, 1, 0, 0), duration=0.5)
        anim_out.start_delay = 1
        anim = anim_in + anim_out
        anim.bind(on_complete=lambda *args: self.remove_widget(label))
        anim.start(label)

    def emit_particles(self, center, color):
        for _ in range(20):
            particle = Particle(color=color)
            particle.center = center
            particle.size = [10, 10]
            particle.initial_size = 10
            particle.velocity_x = random.uniform(-150, 150)
            particle.velocity_y = random.uniform(100, 300)
            particle.lifetime = random.uniform(0.5, 1.0)
            self.add_widget(particle)

    def activate_power_up(self, effect):
        from kivy.clock import Clock
        if effect == 'slow_motion':
            self.speed_multiplier = 0.5
            print('Power-Up Activated: Slow Motion!')
            Clock.schedule_once(self.deactivate_slow_motion, 5)
        elif effect == 'extra_life':
            self.lives += 1
            print('Power-Up Activated: Extra Life!')
        elif effect == 'double_score':
            self.score_multiplier *= 2
            print('Power-Up Activated: Double Score!')
            Clock.schedule_once(self.deactivate_double_score, 5)

    def deactivate_slow_motion(self, dt):
        self.speed_multiplier = 1.0
        print('Power-Up Deactivated: Slow Motion ended')

    def deactivate_double_score(self, dt):
        self.score_multiplier /= 2
        print('Power-Up Deactivated: Double Score ended')

    def show_help(self):
        help_text = (
            "Rules:\n"
            "- Move player left/right to catch objects that match player's color.\n"
            "- Consecutive correct matches boost score multiplier.\n"
            "- Power-ups: extra life, double score, slow motion.\n"
            "- Avoid mismatched colors or lose a life.\n"
            "- Game speeds up over time.\n"
            "- Aim for the highest score!\n\n"
            "Controls:\n"
            "- Touch/mouse drag: move\n"
            "- Keyboard: left/right arrows\n\n"
            "Good luck!"
        )

        scroll_view = ScrollView(size_hint=(1, 1))
        help_label = Label(
            text=help_text,
            color=(1, 1, 1, 1),
            valign='top',
            halign='left',
            font_name='DejaVuSans.ttf',
            font_size=18,
            size_hint_y=None,
            markup=True,
            text_size=(800, None)
        )
        help_label.bind(texture_size=lambda instance, size: setattr(instance, 'height', size[1]))
        scroll_view.add_widget(help_label)

        popup = Popup(
            title="Help",
            content=scroll_view,
            size_hint=(0.8, 0.8),
            background_color=(0, 0, 0, 1),
            title_color=(1, 1, 1, 1),
            title_font='DejaVuSans.ttf'
        )

        def adjust_label_width(*args):
            help_label.text_size = (scroll_view.width * 0.9, None)

        popup.bind(on_open=lambda *args: self.pause_game())   # Pause on open
        popup.bind(on_dismiss=lambda *args: self.resume_game()) # Resume on dismiss
        popup.bind(on_open=adjust_label_width)
        popup.open()


class MenuScreen(Screen):
    music_toggle = ObjectProperty(None)

    def show_help(self):
        help_text = (
            "Rules:\n"
            "- Move player left/right to catch objects that match player's color.\n"
            "- Consecutive correct matches boost score multiplier.\n"
            "- Power-ups: extra life, double score, slow motion.\n"
            "- Avoid mismatched colors or lose a life.\n"
            "- Game speeds up over time.\n"
            "- Aim for the highest score!\n\n"
            "Controls:\n"
            "- Touch/mouse drag: move\n"
            "- Keyboard: left/right arrows\n\n"
            "Good luck!"
        )

        scroll_view = ScrollView(size_hint=(1, 1))
        help_label = Label(
            text=help_text,
            color=(1, 1, 1, 1),
            valign='top',
            halign='left',
            font_name='DejaVuSans.ttf',
            font_size=18,
            size_hint_y=None,
            markup=True,
            text_size=(800, None)
        )
        help_label.bind(texture_size=lambda instance, size: setattr(instance, 'height', size[1]))
        scroll_view.add_widget(help_label)

        popup = Popup(
            title="Help",
            content=scroll_view,
            size_hint=(0.8, 0.8),
            background_color=(0, 0, 0, 1),
            title_color=(1, 1, 1, 1),
            title_font='DejaVuSans.ttf'
        )

        def adjust_label_width(*args):
            help_label.text_size = (scroll_view.width * 0.9, None)
        popup.bind(on_open=adjust_label_width)
        popup.open()

class ColorCatcherApp(App):
    background_music = None

    def build(self):
        sm = ScreenManager()
        menu_screen = MenuScreen(name='menu')
        game_screen = GameScreen(name='game')

        sm.add_widget(menu_screen)
        sm.add_widget(game_screen)

        sm.current = 'menu'

        # Load and start background music
        self.background_music = SoundLoader.load('background.mp3')
        if self.background_music:
            self.background_music.loop = True
            self.background_music.volume = 1.0

        # We'll start music after the app is built.
        Clock.schedule_once(self.start_music, 0)

        return sm

    def start_music(self, dt):
        # Access menu's toggle
        menu_screen = self.root.get_screen('menu')
        if menu_screen.music_toggle.is_music_on and self.background_music:
            self.background_music.play()

if __name__ == '__main__':
    ColorCatcherApp().run()
