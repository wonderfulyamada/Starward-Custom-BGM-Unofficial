import unittest
from types import SimpleNamespace

from gui import App


class _Canvas:
    def __init__(self):
        self.options = {}
        self.item_options = []
        self.scrolls = []

    def bbox(self, _tag):
        return (0, 0, 640, 1200)

    def configure(self, **options):
        self.options.update(options)

    def itemconfigure(self, item, **options):
        self.item_options.append((item, options))

    def yview_scroll(self, units, mode):
        self.scrolls.append((units, mode))


class GuiScrollTests(unittest.TestCase):
    def make_app(self):
        app = App.__new__(App)
        app.settings_canvas = _Canvas()
        app.settings_content_window = 7
        return app

    def test_content_resize_updates_scrollregion(self):
        app = self.make_app()
        app._update_settings_scrollregion()
        self.assertEqual(app.settings_canvas.options["scrollregion"], (0, 0, 640, 1200))

    def test_canvas_resize_keeps_content_width_and_scrollregion_current(self):
        app = self.make_app()
        app._fit_settings_content_width(SimpleNamespace(width=500))
        self.assertEqual(app.settings_canvas.item_options, [(7, {"width": 500})])
        self.assertEqual(app.settings_canvas.options["scrollregion"], (0, 0, 640, 1200))

    def test_wheel_scrolls_only_inside_settings_canvas(self):
        app = self.make_app()
        child = SimpleNamespace(master=app.settings_canvas)
        self.assertEqual(app._scroll_settings(SimpleNamespace(widget=child, delta=-120)), "break")
        self.assertEqual(app.settings_canvas.scrolls, [(1, "units")])
        outside = SimpleNamespace(master=None)
        self.assertIsNone(app._scroll_settings(SimpleNamespace(widget=outside, delta=-120)))
        self.assertEqual(app.settings_canvas.scrolls, [(1, "units")])
