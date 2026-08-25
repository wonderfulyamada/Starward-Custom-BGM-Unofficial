import unittest

from gui import App


class _Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Scale:
    def __init__(self):
        self.options = {}

    def configure(self, **options):
        self.options.update(options)


class AwakeningOffsetSliderTests(unittest.TestCase):
    def make_app(self, duration=120.0):
        app = App.__new__(App)
        app.awakening_track_duration = duration
        app.awakening_start_offset = _Value("0")
        app.awakening_offset_slider = _Value(0.0)
        app.awakening_offset_time = _Value("")
        return app

    def test_slider_updates_numeric_input(self):
        app = self.make_app()
        app.on_awakening_offset_slider("84.5")
        self.assertEqual(app.awakening_start_offset.get(), "84.5")
        self.assertEqual(app.awakening_offset_time.get(), "01:24.5")

    def test_numeric_input_updates_slider_and_clamps_to_duration(self):
        app = self.make_app(duration=10.0)
        app.awakening_start_offset.set("12.5")
        app.on_awakening_offset_input()
        self.assertEqual(app.awakening_offset_slider.get(), 10.0)
        self.assertEqual(app.awakening_start_offset.get(), "10.0")

    def test_missing_duration_keeps_numeric_offset_usable(self):
        app = self.make_app(duration=None)
        app.awakening_start_offset.set("42.25")
        app.on_awakening_offset_input()
        self.assertEqual(app.awakening_offset_slider.get(), 42.25)
        self.assertEqual(app.awakening_offset_time.get(), "00:42.2")

    def test_result_offset_clamps_to_its_selected_track_duration(self):
        app = App.__new__(App)
        app.victory_track_duration = 10.0
        app.victory_start_offset = _Value("12.5")
        app.victory_offset_slider = _Value(0.0)
        app.victory_offset_time = _Value("")

        app._set_result_offset("victory", app._result_offset("victory"))

        self.assertEqual(app.victory_start_offset.get(), "10.0")
        self.assertEqual(app.victory_offset_slider.get(), 10.0)

    def test_track_change_loads_saved_offset_and_duration_range(self):
        app = self.make_app(duration=None)
        app.awakening_bgm_track = _Value("Awakening/track.wav")
        app.awakening_bgm_group = _Value("Awakening")
        app.awakening_offset_scale = _Scale()
        track = object()

        class Library:
            def resolve_track(self, reference, group):
                return track

            def awakening_offset(self, selected):
                return 12.5

            def track_duration(self, selected):
                return 60.0

        app.library = Library()
        app.on_awakening_track_change(save=False)
        self.assertEqual(app.awakening_start_offset.get(), "12.5")
        self.assertEqual(app.awakening_offset_slider.get(), 12.5)
        self.assertEqual(app.awakening_offset_scale.options, {"to": 60.0, "state": "normal"})

    def test_runtime_bgm_settings_contains_crossfade_once_with_gui_value(self):
        app = App.__new__(App)
        app.playback_settings = lambda: {"bgm_selected_group": "Default"}
        app.result_bgm_settings = lambda: {"awakening_crossfade_ms": 375}
        app.volume = _Value(0.25)
        app.fadeout = _Value(900)

        settings = app.runtime_bgm_settings()

        self.assertEqual(settings["awakening_crossfade_ms"], 375)
        self.assertEqual(list(settings).count("awakening_crossfade_ms"), 1)
