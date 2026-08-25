
import threading
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
        self.normal_battle_track = None
        self.normal_battle_position_ms = None
        self.awakening_active = False
        self.crossfade_timer = None
        self.handoff_generation = 0
        self.context_track = None
        pygame.mixer.init()

    @staticmethod
    def _exists(path):
        return bool(path) and Path(path).is_file()

    def _play(self, path, loops=-1, start_seconds=0.0, fade_ms=0):
        if not self._exists(path):
            return False
        self.set_volume(self.cfg.get("battle_bgm_volume", 1.0))
        try:
            self.pygame.mixer.music.load(path)
            kwargs = {"loops": loops}
            if start_seconds > 0:
                kwargs["start"] = start_seconds
            if fade_ms > 0:
                kwargs["fade_ms"] = fade_ms
            self.pygame.mixer.music.play(**kwargs)
            return True
        except Exception as exc:
            print(f"BGM playback error: {exc}")
            return False

    def _legacy_track_path(self, setting):
        resolved = getattr(self.library, "resolve_track", lambda *_: None)(setting)
        if resolved is not None:
            return resolved
        path = Path(setting)
        return path if path.is_absolute() else self.library.root / path

    def _special_track(self, event):
        name = event.lower()
        group = self.cfg.get(f"{name}_bgm_group", "")
        selected = self.cfg.get(f"{name}_bgm_track", "")
        resolve = getattr(self.library, "resolve_track", None)
        if resolve and selected:
            track = resolve(selected, group)
            if track is not None:
                return track
        # Filename-only result settings were used before group selectors.
        legacy = self.cfg.get(f"{name}_bgm", "")
        return self._legacy_track_path(legacy) if legacy else None

    def _remember_battle_track(self, track):
        self.normal_battle_track = track
        self.normal_battle_position_ms = None
        self.awakening_active = False

    def _cancel_crossfade(self):
        self.handoff_generation = getattr(self, "handoff_generation", 0) + 1
        timer = getattr(self, "crossfade_timer", None)
        if timer is not None:
            timer.cancel()
            if self.cfg.get("_debug", False):
                print("AUDIO result_handoff_cancelled")
            self.crossfade_timer = None

    def _schedule_handoff(self, name, callback, debug_message):
        self._cancel_crossfade()
        duration = max(0, int(self.cfg.get("awakening_crossfade_ms", 0)))
        generation = self.handoff_generation
        self.fadeout(duration)

        def guarded_callback():
            if generation != self.handoff_generation:
                return
            self.crossfade_timer = None
            callback()

        if duration:
            self.crossfade_timer = threading.Timer(duration / 1000.0, guarded_callback)
            self.crossfade_timer.daemon = True
            if self.cfg.get("_debug", False):
                print(f"AUDIO {debug_message} duration_ms={duration}")
            self.crossfade_timer.start()
        else:
            guarded_callback()

    def _start_awakening_bgm(self):
        if not self.cfg.get("awakening_bgm_enabled", False):
            return
        group = self.cfg.get("awakening_bgm_group", "")
        self._cancel_crossfade()
        selected = self.cfg.get("awakening_bgm_track", "")
        track = self.library.choose("Fixed", group, selected) if selected else None
        track = track or self.library.choose("Balanced Random", group)
        if track is None:
            return
        get_pos = getattr(self.pygame.mixer.music, "get_pos", None)
        position = get_pos() if get_pos else None
        self.normal_battle_position_ms = position if position is not None and position >= 0 else None
        offset = self.library.awakening_offset(track)
        self.awakening_active = self._play(track, start_seconds=offset)

    def preview_awakening_track(self, track, offset):
        """Play a configuration preview without touching battle state."""
        try:
            offset = max(0.0, float(offset))
        except (TypeError, ValueError):
            offset = 0.0
        return self._play(track, loops=0, start_seconds=offset)

    def _end_awakening_bgm(self):
        if not self.awakening_active:
            return
        self.awakening_active = False
        track = self.normal_battle_track
        if track is None:
            return
        duration = max(0, int(self.cfg.get("awakening_crossfade_ms", 0)))
        self.fadeout(duration)
        if duration:
            self.crossfade_timer = threading.Timer(duration / 1000.0, self._resume_normal_battle, args=(track, duration))
            self.crossfade_timer.daemon = True
            self.crossfade_timer.start()
        else:
            self._resume_normal_battle(track, 0)

    def _resume_normal_battle(self, track, fade_ms):
        self.crossfade_timer = None
        position = (self.normal_battle_position_ms or 0) / 1000.0
        self._play(track, start_seconds=position, fade_ms=fade_ms)

    def _clear_awakening_bgm(self):
        self._cancel_crossfade()
        self.awakening_active = False
        self.normal_battle_position_ms = None

    def _start_result_bgm(self, track, offset):
        duration = max(0, int(self.cfg.get("awakening_crossfade_ms", 0)))
        self.fadeout(duration)
        def play_result():
            self.crossfade_timer = None
            if self.cfg.get("_debug", False):
                print(f"AUDIO result_start track={track} offset={offset} loops=0")
            if offset:
                self._play(track, loops=0, start_seconds=offset)
            else:
                self._play(track, loops=0)
        if duration:
            self.crossfade_timer = threading.Timer(duration / 1000.0, play_result)
            if self.cfg.get("_debug", False):
                print(f"AUDIO result_handoff_pending duration_ms={duration}")
            self.crossfade_timer.daemon = True
            self.crossfade_timer.start()
        else:
            play_result()

    def _start_context_bgm(self, name):
        if not self.cfg.get(f"{name}_bgm_enabled", False) or getattr(self, "context_track", None) == name:
            return
        group = self.cfg.get(f"{name}_bgm_group", "")
        selected = self.cfg.get(f"{name}_bgm_track", "")
        mode = self.cfg.get(f"{name}_bgm_playback_mode", "Fixed")
        choose = getattr(self.library, "choose", None)
        track = choose(mode, group, selected) if choose else self._special_track(name.upper())
        if track is None:
            return
        self.context_track = name

        def play_context():
            if getattr(self, "context_track", None) != name:
                return
            if self.cfg.get("_debug", False):
                print(f"AUDIO {name}_start track={track} offset=0.0 loops=-1")
            self._play(track, loops=-1, start_seconds=0.0)

        self._schedule_handoff(name, play_context, f"{name}_handoff_pending")

    def on_event(self, event):
        if event == "BATTLE_START":
            previous_context = getattr(self, "context_track", None)
            self._cancel_crossfade()
            self.context_track = None
            scope = self.cfg.get("bgm_playback_scope", LIBRARY_SCOPE)
            group = self.cfg.get("bgm_selected_group", "")
            track = self.library.choose(
                self.cfg.get("bgm_playback_mode", "Fixed"),
                group if scope == "Selected Group" else LIBRARY_SCOPE,
                self.cfg.get("bgm_fixed_track", ""),
            )
            if track is not None:
                def play_battle():
                    if self.cfg.get("_debug", False):
                        print("AUDIO battle_start source=screen_go")
                    self._play(track)
                    self._remember_battle_track(track)
                if previous_context in ("lobby", "match"):
                    self._schedule_handoff("battle", play_battle, "battle_handoff_pending source=screen_go")
                else:
                    play_battle()

        elif event == "AWAKENING_START":
            self._start_awakening_bgm()

        elif event == "AWAKENING_END":
            self._end_awakening_bgm()

        elif event in ("VICTORY", "DEFEAT"):
            self._clear_awakening_bgm()
            self.context_track = None
            if not self.cfg.get("result_bgm_enabled", False):
                self.fadeout()
                return
            track = self._special_track(event)
            offset = getattr(self.library, "awakening_offset", lambda _track: 0.0)(track)
            self._start_result_bgm(track, offset)

        elif event == "RESULT_END" and self.cfg.get("result_bgm_enabled", False):
            self._clear_awakening_bgm()
            if self.cfg.get("_debug", False):
                print(f"AUDIO result_exit event={event} action=stop")
            self.stop()

        if event == "LOBBY":
            self._start_context_bgm("lobby")
        elif event == "MATCH_CONFIRMED":
            self._start_context_bgm("match")

    def fadeout(self, duration_ms=None):
        if self.cfg.get("_debug", False):
            print("AUDIO action=fadeout")
        duration = self.cfg.get("result_fadeout_ms", 1000) if duration_ms is None else duration_ms
        self.pygame.mixer.music.fadeout(int(duration))

    def stop(self):
        self._cancel_crossfade()
        if self.cfg.get("_debug", False):
            print("AUDIO action=stop")
        self.pygame.mixer.music.stop()

    def set_volume(self, volume):
        volume = max(0.0, min(1.0, float(volume)))
        self.cfg["battle_bgm_volume"] = volume
        self.pygame.mixer.music.set_volume(volume)
