
from pathlib import Path

from music_library import LIBRARY_SCOPE, MusicLibrary
from paths import ROOT


class NullAudio:
    def on_event(self, event):
        pass


class PygameAudio:
    """
    Optional audio backend using pygame-ce's mixer.music.

    Requires:
      pip install pygame-ce
    """
    def __init__(self, cfg):
        import pygame

        self.pygame = pygame
        self.cfg = cfg
        root = Path(cfg.get("bgm_root", "BGM"))
        root = root if root.is_absolute() else ROOT / root
        self.library = MusicLibrary(root, ROOT / "bgm_library.json")
        pygame.mixer.init()

    @staticmethod
    def _exists(path):
        return bool(path) and Path(path).exists()

    def _play(self, path):
        if not self._exists(path):
            return
        self.set_volume(self.cfg.get("battle_bgm_volume", 1.0))
        self.pygame.mixer.music.load(path)
        self.pygame.mixer.music.play(loops=-1)

    def on_event(self, event):
        if event == "BATTLE_START":
            scope = self.cfg.get("bgm_playback_scope", LIBRARY_SCOPE)
            group = self.cfg.get("bgm_selected_group", "")
            track = self.library.choose(
                self.cfg.get("bgm_playback_mode", "Fixed"),
                group if scope == "Selected Group" else LIBRARY_SCOPE,
                self.cfg.get("bgm_fixed_track", ""),
            )
            if track is not None:
                self._play(track)

        elif event in ("VICTORY", "DEFEAT"):
            self.fadeout()

    def fadeout(self):
        self.pygame.mixer.music.fadeout(int(self.cfg.get("result_fadeout_ms", 1000)))

    def set_volume(self, volume):
        volume = max(0.0, min(1.0, float(volume)))
        self.cfg["battle_bgm_volume"] = volume
        self.pygame.mixer.music.set_volume(volume)
