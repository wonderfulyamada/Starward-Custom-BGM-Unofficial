import unittest

from gui import App


class _Value:
    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


class ContextPlaybackModeLocalizationTests(unittest.TestCase):
    def make_app(self, language="ja"):
        app = App.__new__(App)
        labels = {
            "ja": {"fixed": "固定", "balanced": "均等ランダム", "true_random": "完全ランダム"},
            "en": {"fixed": "Fixed", "balanced": "Balanced Random", "true_random": "True Random"},
        }
        app.t = lambda key: labels[language][key]
        return app

    def test_codes_display_as_japanese_labels_for_lobby_and_match(self):
        app = self.make_app()
        for code, label in (("Fixed", "固定"), ("Balanced Random", "均等ランダム"), ("True Random", "完全ランダム")):
            self.assertEqual(app.mode_label(code), label)

    def test_japanese_and_english_labels_normalize_to_codes(self):
        app = self.make_app()
        for label, code in (("固定", "Fixed"), ("均等ランダム", "Balanced Random"), ("完全ランダム", "True Random"), ("Fixed", "Fixed"), ("Balanced Random", "Balanced Random"), ("True Random", "True Random")):
            self.assertEqual(app.context_mode_code(label), code)

    def test_language_switch_preserves_context_codes(self):
        japanese = self.make_app("ja")
        english = self.make_app("en")
        for code in ("Fixed", "Balanced Random", "True Random"):
            self.assertEqual(japanese.context_mode_code(japanese.mode_label(code)), code)
            self.assertEqual(english.context_mode_code(english.mode_label(code)), code)
