"""Minimal Tk interface for choosing a detector frame source."""
import ctypes
import ctypes.wintypes
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import main
from diagnostics import APP_VERSION, create_diagnostics_logger
from audio import PygameAudio
from detector import ScreenDetector, TemplateBank
from gamepad_input import GamepadInputAssist
from hotkey import GlobalPauseHotkey
from localization import LANGUAGES, text
from music_library import LIBRARY_SCOPE, MusicLibrary
from state_machine import BattleStateMachine


def visible_windows():
    windows = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def collect(hwnd, _):
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        if user32.IsWindowVisible(hwnd) and length:
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title, length + 1)
            windows.append((int(hwnd), title.value))
        return True

    ctypes.windll.user32.EnumWindows(callback_type(collect), 0)
    return windows


class App:
    def __init__(self, root, debug=False):
        self.root = root
        self.debug = debug
        self.root.title(f"Starward BGM Detector v{APP_VERSION}")
        self.window_choice = tk.StringVar()
        cfg = main.load_config()
        cfg["_debug"] = debug
        self.language = tk.StringVar(value=cfg.get("ui_language", "en") if cfg.get("ui_language", "en") in LANGUAGES else "en")
        self.language_choice = tk.StringVar(value=LANGUAGES[self.language.get()])
        self.playback_mode_code = cfg.get("bgm_playback_mode", "Fixed")
        self.playback_scope_code = cfg.get("bgm_playback_scope", LIBRARY_SCOPE)
        self.playback_mode = tk.StringVar()
        self.playback_scope = tk.StringVar()
        self.group_choice = tk.StringVar(value=cfg.get("bgm_selected_group", ""))
        self.fixed_track = tk.StringVar(value=cfg.get("bgm_fixed_track", ""))
        self.volume = tk.DoubleVar(value=cfg.get("battle_bgm_volume", 1.0))
        self.fadeout = tk.IntVar(value=cfg.get("result_fadeout_ms", 1000))
        self.awakening_crossfade = tk.IntVar(value=cfg.get("awakening_crossfade_ms", 500))
        self.result_bgm_enabled = tk.BooleanVar(value=cfg.get("result_bgm_enabled", False))
        self.game_log_monitor_enabled = tk.BooleanVar(value=cfg.get("game_log_monitor_enabled", False))
        self.game_log_folder = tk.StringVar(value=cfg.get("starward_logs_dir", ""))
        self.gamepad_input_assist_enabled = tk.BooleanVar(value=cfg.get("gamepad_input_assist_enabled", False))
        self.gamepad_binding_text = tk.StringVar()
        self.gamepad_preview_text = tk.StringVar()
        self.gamepad_remove_choice = tk.StringVar()
        self.go_threshold = tk.DoubleVar(value=cfg.get("go_threshold", 0.42))
        self.victory_threshold = tk.DoubleVar(value=cfg.get("victory_threshold", 0.38))
        self.defeat_threshold = tk.DoubleVar(value=cfg.get("defeat_threshold", 0.38))
        self.recognition_score_text = tk.StringVar(value="GO 0.000 / V 0.000 / D 0.000")
        self.awakening_bgm_enabled = tk.BooleanVar(value=cfg.get("awakening_bgm_enabled", False))
        self.awakening_bgm_group = tk.StringVar(value=cfg.get("awakening_bgm_group", ""))
        self.awakening_bgm_track = tk.StringVar(value=cfg.get("awakening_bgm_track", ""))
        self.awakening_start_offset = tk.StringVar(value="0")
        self.awakening_offset_slider = tk.DoubleVar(value=0.0)
        self.awakening_offset_time = tk.StringVar(value="00:00.0")
        self.awakening_track_duration = None
        self.victory_bgm_group = tk.StringVar(value=cfg.get("victory_bgm_group", "Default"))
        self.victory_bgm_track = tk.StringVar(value=cfg.get("victory_bgm_track", cfg.get("victory_bgm", "")))
        self.victory_start_offset = tk.StringVar(value="0")
        self.victory_offset_slider = tk.DoubleVar(value=0.0)
        self.victory_offset_time = tk.StringVar(value="00:00.0")
        self.victory_track_duration = None
        self.defeat_bgm_group = tk.StringVar(value=cfg.get("defeat_bgm_group", "Default"))
        self.defeat_bgm_track = tk.StringVar(value=cfg.get("defeat_bgm_track", cfg.get("defeat_bgm", "")))
        self.lobby_bgm_enabled = tk.BooleanVar(value=cfg.get("lobby_bgm_enabled", False))
        self.lobby_bgm_group = tk.StringVar(value=cfg.get("lobby_bgm_group", "Default"))
        self.lobby_bgm_track = tk.StringVar(value=cfg.get("lobby_bgm_track", ""))
        self.lobby_bgm_playback_mode = tk.StringVar(value=cfg.get("lobby_bgm_playback_mode", "Fixed"))
        self.match_bgm_enabled = tk.BooleanVar(value=cfg.get("match_bgm_enabled", False))
        self.match_bgm_group = tk.StringVar(value=cfg.get("match_bgm_group", "Default"))
        self.match_bgm_track = tk.StringVar(value=cfg.get("match_bgm_track", ""))
        self.match_bgm_playback_mode = tk.StringVar(value=cfg.get("match_bgm_playback_mode", "Fixed"))
        self.match_start_offset = tk.StringVar(value="0")
        self.match_offset_slider = tk.DoubleVar(value=0.0)
        self.match_offset_time = tk.StringVar(value="00:00.0")
        self.match_track_duration = None
        self.defeat_start_offset = tk.StringVar(value="0")
        self.defeat_offset_slider = tk.DoubleVar(value=0.0)
        self.defeat_offset_time = tk.StringVar(value="00:00.0")
        self.defeat_track_duration = None
        self.detection_text = tk.StringVar(value="IDLE")
        self.detection_code = "IDLE"
        self.runtime_text = tk.StringVar(value="")
        self.runtime_code = "STOPPED"
        self.localized_widgets = []
        self.windows = {}
        self.library = MusicLibrary(main.ROOT / "BGM")
        self.gamepad_assist = GamepadInputAssist(cfg, logger=create_diagnostics_logger())
        self.stop_event = None
        self.worker = None
        self.audio = None
        self.preview_audio = None
        self.gamepad_registration_active = False
        self.runtime_cfg = None
        self.pause_requested = False
        self.resume_pending = False
        self.state_updates = queue.Queue()
        self._build()
        self.apply_language()
        self.update_gamepad_binding_text()
        self.root.after(100, self.refresh_gamepad_preview)
        self.refresh_windows()
        self.refresh_music()
        self.hotkey = GlobalPauseHotkey(
            lambda: self.state_updates.put("__toggle_pause__"), debug=debug,
        )
        self.hotkey.start()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._drain_state_updates)

    def t(self, key):
        return text(self.language.get(), key)

    def _localized(self, widget, key):
        self.localized_widgets.append((widget, key))
        return widget

    def apply_language(self):
        for widget, key in self.localized_widgets:
            widget.configure(text=self.t(key))
        self.mode_box["values"] = [self.t("fixed"), self.t("balanced"), self.t("true_random")]
        self.scope_box["values"] = [self.t("all_bgm"), self.t("selected_group")]
        self.playback_mode.set(self.mode_label(self.playback_mode_code))
        self.playback_scope.set(self.scope_label(self.playback_scope_code))
        self.lobby_bgm_playback_mode.set(self.mode_label(self.context_mode_code(self.lobby_bgm_playback_mode.get())))
        self.match_bgm_playback_mode.set(self.mode_label(self.context_mode_code(self.match_bgm_playback_mode.get())))
        self.update_fixed_track_state()
        self.set_detection_state(self.detection_code)
        self.set_runtime_status(self.runtime_code)

    def mode_label(self, code):
        return self.t({"Fixed": "fixed", "Balanced Random": "balanced", "True Random": "true_random"}[code])

    def mode_code(self):
        return {self.t("fixed"): "Fixed", self.t("balanced"): "Balanced Random", self.t("true_random"): "True Random"}[self.playback_mode.get()]

    def context_mode_code(self, value):
        labels = {
            "Fixed": "Fixed", "Balanced Random": "Balanced Random", "True Random": "True Random",
            "固定": "Fixed", "均等ランダム": "Balanced Random", "完全ランダム": "True Random",
            self.t("fixed"): "Fixed", self.t("balanced"): "Balanced Random", self.t("true_random"): "True Random",
        }
        return labels.get(value, "Fixed")

    def scope_label(self, code):
        return self.t("all_bgm") if code == LIBRARY_SCOPE else self.t("selected_group")

    def scope_code(self):
        return LIBRARY_SCOPE if self.playback_scope.get() == self.t("all_bgm") else "Selected Group"

    def update_fixed_track_state(self, _event=None):
        self.playback_mode_code = self.mode_code()
        self.track_box.configure(state="readonly" if self.playback_mode_code == "Fixed" else "disabled")
        if _event is not None:
            self.save_playback_settings()

    def playback_settings(self):
        return {
            "bgm_playback_mode": self.mode_code(),
            "bgm_playback_scope": self.scope_code(),
            "bgm_selected_group": self.group_choice.get(),
            "bgm_fixed_track": self.fixed_track.get(),
        }

    def result_bgm_settings(self):
        return {
            "result_bgm_enabled": self.result_bgm_enabled.get(),
            "game_log_monitor_enabled": self.game_log_monitor_enabled.get(),
            "starward_logs_dir": self.game_log_folder.get().strip(),
            "gamepad_input_assist_enabled": self.gamepad_input_assist_enabled.get(),
            "gamepad_awakening_buttons": list(self.gamepad_assist.buttons),
            "go_threshold": self.go_threshold.get(),
            "victory_threshold": self.victory_threshold.get(),
            "defeat_threshold": self.defeat_threshold.get(),
            "awakening_bgm_enabled": self.awakening_bgm_enabled.get(),
            "awakening_bgm_group": self.awakening_bgm_group.get(),
            "awakening_bgm_track": self.awakening_bgm_track.get(),
            "awakening_crossfade_ms": max(0, self.awakening_crossfade.get()),
            "victory_bgm_group": self.victory_bgm_group.get(),
            "victory_bgm_track": self.victory_bgm_track.get(),
            "defeat_bgm_group": self.defeat_bgm_group.get(),
            "defeat_bgm_track": self.defeat_bgm_track.get(),
            "lobby_bgm_enabled": self.lobby_bgm_enabled.get(),
            "lobby_bgm_group": self.lobby_bgm_group.get(),
            "lobby_bgm_track": self.lobby_bgm_track.get(),
            "lobby_bgm_playback_mode": self.context_mode_code(self.lobby_bgm_playback_mode.get()),
            "match_bgm_enabled": self.match_bgm_enabled.get(),
            "match_bgm_group": self.match_bgm_group.get(),
            "match_bgm_track": self.match_bgm_track.get(),
            "match_bgm_playback_mode": self.context_mode_code(self.match_bgm_playback_mode.get()),
        }

    def runtime_bgm_settings(self):
        return {
            **self.playback_settings(),
            **self.result_bgm_settings(),
            "battle_bgm_volume": self.volume.get(),
            "result_fadeout_ms": self.fadeout.get(),
        }

    def save_playback_settings(self, _event=None):
        settings = {**self.playback_settings(), **self.result_bgm_settings()}
        cfg = main.load_config()
        cfg.update(settings)
        cfg.pop("victory_bgm", None)
        cfg.pop("defeat_bgm", None)
        main.save_config(cfg)
        self.gamepad_assist.cfg.update(settings)
        if self.runtime_cfg is not None:
            self.runtime_cfg.update(settings)

    def restore_detection_defaults(self):
        self.go_threshold.set(0.42)
        self.victory_threshold.set(0.38)
        self.defeat_threshold.set(0.38)
        self.save_playback_settings()

    def browse_game_log_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title=self.t("game_log_folder"))
        if folder:
            self.game_log_folder.set(folder)
            self.save_playback_settings()

    def set_detection_state(self, code):
        self.detection_code = code
        self.detection_text.set(code)

    def set_runtime_status(self, code):
        self.runtime_code = code
        self.runtime_text.set(self.t(code.lower()))
        stopped = code == "STOPPED"
        self.start_button.configure(state="normal" if stopped else "disabled")
        self.stop_button.configure(state="disabled" if stopped else "normal")

    def change_language(self, _value=None):
        self.language.set(next(code for code, name in LANGUAGES.items() if name == self.language_choice.get()))
        cfg = main.load_config()
        cfg["ui_language"] = self.language.get()
        main.save_config(cfg)
        self.apply_language()

    def _drain_state_updates(self):
        while True:
            try:
                update = self.state_updates.get_nowait()
                if update == "__toggle_pause__":
                    if self.debug:
                        print("Ctrl+F8 action_dispatch=toggle_pause")
                    self.toggle_pause()
                elif update == "__worker_finished__":
                    self.root.after(10, self._handle_worker_finished)
                elif isinstance(update, tuple) and update[0] == "__recognition__":
                    self.recognition_score_text.set(
                        f"GO {update[1]:.3f} / V {update[2]:.3f} / D {update[3]:.3f}"
                    )
                else:
                    self.set_detection_state(update)
            except queue.Empty:
                break
        self.root.after(100, self._drain_state_updates)

    def _handle_worker_finished(self):
        if self.worker and self.worker.is_alive():
            self.root.after(10, self._handle_worker_finished)
            return
        self.worker = None
        self.audio = None
        self.runtime_cfg = None
        if self.debug:
            print(f"Ctrl+F8 worker_finished resume_pending={self.resume_pending}")
        if self.resume_pending:
            self.resume_pending = False
            self.start()
        elif not self.pause_requested:
            self.set_runtime_status("STOPPED")

    def _build(self):
        frame = ttk.Frame(self.root, padding=12)
        frame.grid(sticky="nsew")
        self._localized(ttk.Label(frame), "window").grid(row=0, column=0, sticky="w")
        self.window_box = ttk.Combobox(frame, textvariable=self.window_choice, width=52, state="readonly")
        self.window_box.grid(row=0, column=1, sticky="ew")
        self._localized(ttk.Button(frame, command=self.refresh_windows), "refresh").grid(row=0, column=2)
        self._localized(ttk.Label(frame), "language").grid(row=1, column=0, sticky="w")
        ttk.Combobox(frame, textvariable=self.language_choice, values=list(LANGUAGES.values()), state="readonly").grid(row=1, column=1, sticky="ew")
        language_box = frame.grid_slaves(row=1, column=1)[0]
        language_box.bind("<<ComboboxSelected>>", self.change_language)
        self._localized(ttk.Label(frame), "playback_mode").grid(row=2, column=0, sticky="w")
        self.mode_box = ttk.Combobox(frame, textvariable=self.playback_mode, state="readonly")
        self.mode_box.grid(row=2, column=1, sticky="ew")
        self.mode_box.bind("<<ComboboxSelected>>", self.update_fixed_track_state)
        self._localized(ttk.Label(frame), "playback_scope").grid(row=3, column=0, sticky="w")
        self.scope_box = ttk.Combobox(frame, textvariable=self.playback_scope, state="readonly")
        self.scope_box.grid(row=3, column=1, sticky="ew")
        self.scope_box.bind("<<ComboboxSelected>>", self.on_scope_change)
        self._localized(ttk.Label(frame), "group").grid(row=4, column=0, sticky="w")
        self.group_box = ttk.Combobox(frame, textvariable=self.group_choice, state="readonly")
        self.group_box.grid(row=4, column=1, sticky="ew")
        self.group_box.bind("<<ComboboxSelected>>", self.on_group_change)
        group_actions = ttk.Frame(frame)
        group_actions.grid(row=4, column=2)
        self._localized(ttk.Button(group_actions, command=self.create_group), "new").grid(row=0, column=0)
        self._localized(ttk.Button(group_actions, command=self.rename_group), "rename").grid(row=0, column=1)
        self._localized(ttk.Button(group_actions, command=self.delete_group), "delete").grid(row=0, column=2)
        self._localized(ttk.Label(frame), "fixed_track").grid(row=5, column=0, sticky="w")
        self.track_box = ttk.Combobox(frame, textvariable=self.fixed_track, state="readonly")
        self.track_box.grid(row=5, column=1, sticky="ew")
        self.track_box.bind("<<ComboboxSelected>>", self.save_playback_settings)
        self._localized(ttk.Label(frame), "volume").grid(row=6, column=0, sticky="w")
        ttk.Scale(frame, variable=self.volume, from_=0.0, to=1.0, command=self.on_volume_change).grid(row=6, column=1, sticky="ew")
        self._localized(ttk.Label(frame), "fadeout").grid(row=7, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.fadeout, width=12).grid(row=7, column=1, sticky="w")
        self._localized(ttk.Label(frame), "awakening_crossfade").grid(row=8, column=0, sticky="w")
        self.awakening_crossfade_entry = ttk.Entry(frame, textvariable=self.awakening_crossfade, width=12)
        self.awakening_crossfade_entry.grid(row=8, column=1, sticky="w")
        self.awakening_crossfade_entry.bind("<FocusOut>", self.save_playback_settings)
        self._localized(ttk.Checkbutton(frame, variable=self.result_bgm_enabled, command=self.save_playback_settings), "result_bgm_enabled").grid(row=9, column=0, columnspan=2, sticky="w")
        self._localized(ttk.Checkbutton(frame, variable=self.game_log_monitor_enabled, command=self.save_playback_settings), "game_log_monitor_enabled").grid(row=10, column=0, columnspan=2, sticky="w")
        self._localized(ttk.Label(frame), "game_log_folder").grid(row=11, column=0, sticky="w")
        self.game_log_folder_entry = ttk.Entry(frame, textvariable=self.game_log_folder)
        self.game_log_folder_entry.grid(row=11, column=1, sticky="ew")
        self.game_log_folder_entry.bind("<FocusOut>", self.save_playback_settings)
        self._localized(ttk.Button(frame, command=self.browse_game_log_folder), "browse").grid(row=11, column=2)
        self._localized(ttk.Checkbutton(frame, variable=self.gamepad_input_assist_enabled, command=self.save_playback_settings), "gamepad_input_assist_enabled").grid(row=12, column=0, columnspan=2, sticky="w")
        self._localized(ttk.Label(frame), "detection_thresholds").grid(row=12, column=2, sticky="w")
        for row, key, value in ((13, "battle_start_threshold", self.go_threshold), (14, "victory_threshold", self.victory_threshold), (15, "defeat_threshold", self.defeat_threshold)):
            self._localized(ttk.Label(frame), key).grid(row=row, column=3, sticky="w")
            ttk.Scale(frame, variable=value, from_=0.0, to=1.0, command=self.save_playback_settings).grid(row=row, column=4, sticky="ew")
            ttk.Label(frame, textvariable=value).grid(row=row, column=5, sticky="w")
        self._localized(ttk.Button(frame, command=self.restore_detection_defaults), "restore_detection_defaults").grid(row=16, column=3, columnspan=2, sticky="w")
        self._localized(ttk.Label(frame), "current_match_rate").grid(row=17, column=3, sticky="w")
        ttk.Label(frame, textvariable=self.recognition_score_text).grid(row=17, column=4, columnspan=2, sticky="w")
        self._localized(ttk.Label(frame), "gamepad_binding").grid(row=13, column=0, sticky="w")
        ttk.Label(frame, textvariable=self.gamepad_binding_text).grid(row=13, column=1, sticky="w")
        gamepad_actions = ttk.Frame(frame)
        gamepad_actions.grid(row=13, column=2)
        self._localized(ttk.Button(gamepad_actions, command=self.register_gamepad_buttons), "register_gamepad").grid(row=0, column=0)
        self._localized(ttk.Button(gamepad_actions, command=self.clear_gamepad_buttons), "clear_gamepad").grid(row=0, column=1)
        self.gamepad_remove_box = ttk.Combobox(gamepad_actions, textvariable=self.gamepad_remove_choice, state="readonly", width=10)
        self.gamepad_remove_box.grid(row=1, column=0)
        self._localized(ttk.Button(gamepad_actions, command=self.remove_gamepad_button), "remove_gamepad").grid(row=1, column=1)
        self._localized(ttk.Checkbutton(frame, variable=self.awakening_bgm_enabled, command=self.save_playback_settings), "awakening_bgm_enabled").grid(row=14, column=0, columnspan=2, sticky="w")
        self._localized(ttk.Label(frame), "awakening_bgm_group").grid(row=15, column=0, sticky="w")
        self.awakening_group_box = ttk.Combobox(frame, textvariable=self.awakening_bgm_group, state="readonly")
        self.awakening_group_box.grid(row=15, column=1, sticky="ew")
        self.awakening_group_box.bind("<<ComboboxSelected>>", self.on_awakening_group_change)
        self._localized(ttk.Label(frame), "awakening_bgm_track").grid(row=16, column=0, sticky="w")
        self.awakening_track_box = ttk.Combobox(frame, textvariable=self.awakening_bgm_track, state="readonly")
        self.awakening_track_box.grid(row=16, column=1, sticky="ew")
        self.awakening_track_box.bind("<<ComboboxSelected>>", self.on_awakening_track_change)
        self._localized(ttk.Label(frame), "awakening_start_offset").grid(row=17, column=0, sticky="w")
        self.awakening_offset_entry = ttk.Entry(frame, textvariable=self.awakening_start_offset, width=12)
        self.awakening_offset_entry.grid(row=17, column=1, sticky="w")
        self.awakening_offset_entry.bind("<FocusOut>", self.save_awakening_offset)
        self.awakening_offset_entry.bind("<KeyRelease>", self.on_awakening_offset_input)
        self.awakening_offset_scale = ttk.Scale(
            frame, variable=self.awakening_offset_slider, from_=0, to=1,
            orient="horizontal", command=self.on_awakening_offset_slider,
        )
        self.awakening_offset_scale.grid(row=18, column=1, sticky="ew")
        ttk.Label(frame, textvariable=self.awakening_offset_time).grid(row=18, column=2, sticky="w")
        preview_actions = ttk.Frame(frame)
        preview_actions.grid(row=17, column=2)
        self._localized(ttk.Button(preview_actions, command=self.preview_awakening), "preview").grid(row=0, column=0)
        self._localized(ttk.Button(preview_actions, command=self.stop_preview), "stop_preview").grid(row=0, column=1)
        self._localized(ttk.Label(frame), "victory_bgm_group").grid(row=19, column=0, sticky="w")
        self.victory_group_box = ttk.Combobox(frame, textvariable=self.victory_bgm_group, state="readonly")
        self.victory_group_box.grid(row=19, column=1, sticky="ew")
        self.victory_group_box.bind("<<ComboboxSelected>>", self.on_result_group_change)
        self._localized(ttk.Label(frame), "victory_bgm_track").grid(row=20, column=0, sticky="w")
        self.victory_track_box = ttk.Combobox(frame, textvariable=self.victory_bgm_track, state="readonly")
        self.victory_track_box.grid(row=20, column=1, sticky="ew")
        self.victory_track_box.bind("<<ComboboxSelected>>", lambda event: self.on_result_track_change("victory", event))
        self._localized(ttk.Label(frame), "victory_start_offset").grid(row=21, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.victory_start_offset, width=12).grid(row=21, column=1, sticky="w")
        frame.grid_slaves(row=21, column=1)[0].bind("<FocusOut>", lambda event: self.save_result_offset("victory", event))
        self._localized(ttk.Button(frame, command=lambda: self.preview_result("victory")), "preview").grid(row=21, column=2)
        self.victory_offset_scale = ttk.Scale(frame, variable=self.victory_offset_slider, from_=0, to=1, orient="horizontal", command=lambda value: self._set_result_offset("victory", value))
        self.victory_offset_scale.grid(row=22, column=1, sticky="ew")
        ttk.Label(frame, textvariable=self.victory_offset_time).grid(row=22, column=2, sticky="w")
        self._localized(ttk.Label(frame), "defeat_bgm_group").grid(row=23, column=0, sticky="w")
        self.defeat_group_box = ttk.Combobox(frame, textvariable=self.defeat_bgm_group, state="readonly")
        self.defeat_group_box.grid(row=23, column=1, sticky="ew")
        self.defeat_group_box.bind("<<ComboboxSelected>>", self.on_result_group_change)
        self._localized(ttk.Label(frame), "defeat_bgm_track").grid(row=24, column=0, sticky="w")
        self.defeat_track_box = ttk.Combobox(frame, textvariable=self.defeat_bgm_track, state="readonly")
        self.defeat_track_box.grid(row=24, column=1, sticky="ew")
        self.defeat_track_box.bind("<<ComboboxSelected>>", lambda event: self.on_result_track_change("defeat", event))
        self._localized(ttk.Label(frame), "defeat_start_offset").grid(row=25, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.defeat_start_offset, width=12).grid(row=25, column=1, sticky="w")
        frame.grid_slaves(row=25, column=1)[0].bind("<FocusOut>", lambda event: self.save_result_offset("defeat", event))
        self._localized(ttk.Button(frame, command=lambda: self.preview_result("defeat")), "preview").grid(row=25, column=2)
        self.defeat_offset_scale = ttk.Scale(frame, variable=self.defeat_offset_slider, from_=0, to=1, orient="horizontal", command=lambda value: self._set_result_offset("defeat", value))
        self.defeat_offset_scale.grid(row=26, column=1, sticky="ew")
        ttk.Label(frame, textvariable=self.defeat_offset_time).grid(row=26, column=2, sticky="w")
        self.start_button = self._localized(ttk.Button(frame, command=self.start), "start")
        self.start_button.grid(row=27, column=0, pady=(10, 0))
        self.stop_button = self._localized(ttk.Button(frame, command=self.stop), "stop")
        self.stop_button.grid(row=27, column=1, sticky="w", pady=(10, 0))
        self._localized(ttk.Label(frame), "runtime_status").grid(row=28, column=0, sticky="w", pady=(10, 0))
        ttk.Label(frame, textvariable=self.runtime_text).grid(row=28, column=1, sticky="w", pady=(10, 0))
        self._localized(ttk.Label(frame), "detection_state").grid(row=29, column=0, sticky="w")
        ttk.Label(frame, textvariable=self.detection_text).grid(row=29, column=1, sticky="w")
        for row, kind, label in ((30, "lobby", "lobby_bgm"), (34, "match", "match_bgm")):
            self._localized(ttk.Checkbutton(frame, variable=getattr(self, f"{kind}_bgm_enabled"), command=self.save_playback_settings), label).grid(row=row, column=0, columnspan=2, sticky="w")
            mode_box = ttk.Combobox(frame, textvariable=getattr(self, f"{kind}_bgm_playback_mode"), values=(self.t("fixed"), self.t("balanced"), self.t("true_random")), state="readonly", width=18)
            mode_box.grid(row=row, column=2, sticky="e")
            mode_box.bind("<<ComboboxSelected>>", self.save_playback_settings)
            box = ttk.Combobox(frame, textvariable=getattr(self, f"{kind}_bgm_group"), state="readonly")
            box.grid(row=row + 1, column=1, sticky="ew")
            box.bind("<<ComboboxSelected>>", self.on_result_group_change)
            setattr(self, f"{kind}_group_box", box)
            track_box = ttk.Combobox(frame, textvariable=getattr(self, f"{kind}_bgm_track"), state="readonly")
            track_box.grid(row=row + 2, column=1, sticky="ew")
            track_box.bind("<<ComboboxSelected>>", self.save_playback_settings)
            setattr(self, f"{kind}_track_box", track_box)
            self._localized(ttk.Label(frame), f"{kind}_bgm_group").grid(row=row + 1, column=0, sticky="w")
            self._localized(ttk.Label(frame), f"{kind}_bgm_track").grid(row=row + 2, column=0, sticky="w")
        frame.columnconfigure(1, weight=1)

    def refresh_windows(self):
        items = visible_windows()
        self.windows = {f"{title} [{hwnd}]": hwnd for hwnd, title in items}
        self.window_box["values"] = list(self.windows)
        if self.windows and self.window_choice.get() not in self.windows:
            self.window_choice.set(next(iter(self.windows)))

    def refresh_music(self):
        self.library.refresh()
        groups = self.library.groups()
        self.group_box["values"] = groups
        self.awakening_group_box["values"] = groups
        self.victory_group_box["values"] = groups
        self.defeat_group_box["values"] = groups
        self.lobby_group_box["values"] = groups
        self.match_group_box["values"] = groups
        if self.group_choice.get() not in groups:
            self.group_choice.set(groups[0] if groups else "")
        if self.awakening_bgm_group.get() not in groups:
            self.awakening_bgm_group.set(groups[0] if groups else "")
        if self.victory_bgm_group.get() not in groups:
            self.victory_bgm_group.set(groups[0] if groups else "")
        if self.defeat_bgm_group.get() not in groups:
            self.defeat_bgm_group.set(groups[0] if groups else "")
        if self.lobby_bgm_group.get() not in groups:
            self.lobby_bgm_group.set(groups[0] if groups else "")
        if self.match_bgm_group.get() not in groups:
            self.match_bgm_group.set(groups[0] if groups else "")
        scope = self.scope_code()
        tracks = [self.library.track_reference(track) for track in self.library.tracks(self.group_choice.get() if scope == "Selected Group" else LIBRARY_SCOPE)]
        awakening_tracks = [self.library.track_reference(track) for track in self.library.tracks(self.awakening_bgm_group.get())]
        victory_tracks = [self.library.track_reference(track) for track in self.library.tracks(self.victory_bgm_group.get())]
        defeat_tracks = [self.library.track_reference(track) for track in self.library.tracks(self.defeat_bgm_group.get())]
        lobby_tracks = [self.library.track_reference(track) for track in self.library.tracks(self.lobby_bgm_group.get())]
        match_tracks = [self.library.track_reference(track) for track in self.library.tracks(self.match_bgm_group.get())]
        self.track_box["values"] = tracks
        self.awakening_track_box["values"] = awakening_tracks
        self.victory_track_box["values"] = victory_tracks
        self.defeat_track_box["values"] = defeat_tracks
        self.lobby_track_box["values"] = lobby_tracks
        self.match_track_box["values"] = match_tracks
        fixed = self.library.resolve_track(self.fixed_track.get(), self.group_choice.get() if scope == "Selected Group" else LIBRARY_SCOPE)
        victory = self.library.resolve_track(self.victory_bgm_track.get(), self.victory_bgm_group.get())
        defeat = self.library.resolve_track(self.defeat_bgm_track.get(), self.defeat_bgm_group.get())
        lobby = self.library.resolve_track(self.lobby_bgm_track.get(), self.lobby_bgm_group.get())
        match = self.library.resolve_track(self.match_bgm_track.get(), self.match_bgm_group.get())
        self.fixed_track.set(self.library.track_reference(fixed) if fixed else (tracks[0] if tracks else ""))
        self.victory_bgm_track.set(self.library.track_reference(victory) if victory else (victory_tracks[0] if victory_tracks else ""))
        self.defeat_bgm_track.set(self.library.track_reference(defeat) if defeat else (defeat_tracks[0] if defeat_tracks else ""))
        self.lobby_bgm_track.set(self.library.track_reference(lobby) if lobby else (lobby_tracks[0] if lobby_tracks else ""))
        self.match_bgm_track.set(self.library.track_reference(match) if match else (match_tracks[0] if match_tracks else ""))
        awakening = self.library.resolve_track(self.awakening_bgm_track.get(), self.awakening_bgm_group.get())
        self.awakening_bgm_track.set(self.library.track_reference(awakening) if awakening else (awakening_tracks[0] if awakening_tracks else ""))
        self.on_awakening_track_change(save=False)
        self.on_result_track_change("victory", save=False)
        self.on_result_track_change("defeat", save=False)

    def on_scope_change(self, _event=None):
        self.refresh_music()
        self.save_playback_settings()

    def on_group_change(self, _event=None):
        self.refresh_music()
        self.save_playback_settings()

    def on_awakening_track_change(self, _event=None, save=True):
        track = self.library.resolve_track(self.awakening_bgm_track.get(), self.awakening_bgm_group.get())
        offset = self.library.awakening_offset(track) if track else 0.0
        self.awakening_track_duration = self.library.track_duration(track) if track else None
        self.awakening_offset_scale.configure(
            to=self.awakening_track_duration or 1,
            state="normal" if self.awakening_track_duration is not None else "disabled",
        )
        self._set_awakening_offset(offset)
        if save:
            self.save_playback_settings()

    def on_awakening_group_change(self, _event=None):
        self.refresh_music()
        self.save_playback_settings()

    def on_result_group_change(self, _event=None):
        self.refresh_music()
        self.save_playback_settings()

    def on_result_track_change(self, kind, _event=None, save=True):
        track = self.library.resolve_track(getattr(self, f"{kind}_bgm_track").get(), getattr(self, f"{kind}_bgm_group").get())
        setattr(self, f"{kind}_track_duration", self.library.track_duration(track) if track else None)
        duration = getattr(self, f"{kind}_track_duration")
        getattr(self, f"{kind}_offset_scale").configure(to=duration or 1, state="normal" if duration is not None else "disabled")
        self._set_result_offset(kind, self.library.awakening_offset(track) if track else 0.0)
        if save:
            self.save_playback_settings()

    def update_gamepad_binding_text(self):
        buttons = self.gamepad_assist.buttons
        self.gamepad_remove_box["values"] = [str(button) for button in buttons]
        if self.gamepad_remove_choice.get() not in self.gamepad_remove_box["values"]:
            self.gamepad_remove_choice.set(self.gamepad_remove_box["values"][0] if buttons else "")
        binding = " + ".join(f"Button {button}" for button in buttons) if buttons else self.t("gamepad_unbound")
        self.gamepad_binding_text.set(f"{binding}\n{self.gamepad_preview_text.get()}")

    def register_gamepad_buttons(self):
        if self.gamepad_registration_active:
            return
        if self.debug:
            print("GAMEPAD GUI registration_button=start_capture")
        self.gamepad_registration_active = True
        self.gamepad_assist.begin_capture()
        self.gamepad_binding_text.set(self.t("gamepad_registering"))
        self.root.after(25, self.poll_gamepad_registration)
        self.root.after(1000, self.finish_gamepad_registration)

    def poll_gamepad_registration(self):
        if not self.gamepad_registration_active:
            return
        self.gamepad_assist.poll()
        if self.gamepad_assist.capture_complete:
            self.finish_gamepad_registration()
            return
        self.root.after(25, self.poll_gamepad_registration)

    def finish_gamepad_registration(self):
        if not self.gamepad_registration_active:
            return
        self.gamepad_registration_active = False
        buttons = self.gamepad_assist.finish_capture()
        if buttons:
            existing = set(self.gamepad_assist.buttons)
            existing.add(buttons[0])
            self.gamepad_assist.cfg["gamepad_awakening_buttons"] = sorted(existing)
            self.update_gamepad_binding_text()
            self.save_playback_settings()
        else:
            if self.debug:
                print("GAMEPAD GUI registration_timeout reason=no_buttons_captured")
            self.update_gamepad_binding_text()

    def clear_gamepad_buttons(self):
        if self.debug:
            print("GAMEPAD GUI registration_cancel reason=clear_binding")
        self.gamepad_assist.cfg["gamepad_awakening_buttons"] = []
        self.gamepad_registration_active = False
        self.update_gamepad_binding_text()
        self.save_playback_settings()

    def remove_gamepad_button(self):
        try:
            button = int(self.gamepad_remove_choice.get())
        except ValueError:
            return
        self.gamepad_assist.cfg["gamepad_awakening_buttons"] = [
            registered for registered in self.gamepad_assist.buttons if registered != button
        ]
        self.update_gamepad_binding_text()
        self.save_playback_settings()

    def refresh_gamepad_preview(self):
        self.gamepad_assist.poll()
        buttons = self.gamepad_assist.buttons
        states = " ".join(
            f"Button {button}={'ON' if button in self.gamepad_assist.buttons_down else 'OFF'}"
            for button in buttons
        ) or self.t("gamepad_unbound")
        status = "ACTIVE" if self.gamepad_assist.active else "INACTIVE"
        self.gamepad_preview_text.set(f"{self.t('gamepad_preview')}: {status} [{states}]")
        self.update_gamepad_binding_text()
        self.root.after(100, self.refresh_gamepad_preview)

    def _awakening_offset(self):
        try:
            offset = max(0.0, float(self.awakening_start_offset.get()))
        except ValueError:
            offset = 0.0
        return min(offset, self.awakening_track_duration) if self.awakening_track_duration is not None else offset

    @staticmethod
    def _format_offset(seconds):
        minutes, seconds = divmod(max(0.0, float(seconds)), 60)
        return f"{int(minutes):02d}:{seconds:04.1f}"

    def _set_awakening_offset(self, offset):
        offset = max(0.0, float(offset))
        if self.awakening_track_duration is not None:
            offset = min(offset, self.awakening_track_duration)
        self.awakening_start_offset.set(str(offset))
        self.awakening_offset_slider.set(offset)
        self.awakening_offset_time.set(self._format_offset(offset))

    def on_awakening_offset_slider(self, value):
        self._set_awakening_offset(float(value))

    def on_awakening_offset_input(self, _event=None):
        self._set_awakening_offset(self._awakening_offset())

    def save_awakening_offset(self, _event=None):
        track = self.library.resolve_track(self.awakening_bgm_track.get(), self.awakening_bgm_group.get())
        if track is not None:
            offset = self._awakening_offset()
            self._set_awakening_offset(offset)
            self.library.set_awakening_offset(track, offset)

    def preview_awakening(self):
        if self.runtime_code != "STOPPED":
            return
        track = self.library.resolve_track(self.awakening_bgm_track.get(), self.awakening_bgm_group.get())
        if track is None:
            return
        offset = self._awakening_offset()
        self.awakening_start_offset.set(str(offset))
        self.library.set_awakening_offset(track, offset)
        if self.preview_audio is None:
            cfg = main.load_config()
            cfg["_debug"] = self.debug
            self.preview_audio = PygameAudio(cfg)
        self.preview_audio.preview_awakening_track(track, offset)

    def _result_offset(self, kind):
        try:
            offset = max(0.0, float(getattr(self, f"{kind}_start_offset").get()))
        except ValueError:
            offset = 0.0
        duration = getattr(self, f"{kind}_track_duration")
        return min(offset, duration) if duration is not None else offset

    def _set_result_offset(self, kind, offset):
        duration = getattr(self, f"{kind}_track_duration")
        offset = min(max(0.0, float(offset)), duration) if duration is not None else max(0.0, float(offset))
        getattr(self, f"{kind}_start_offset").set(str(offset))
        getattr(self, f"{kind}_offset_slider").set(offset)
        getattr(self, f"{kind}_offset_time").set(self._format_offset(offset))

    def save_result_offset(self, kind, _event=None):
        track = self.library.resolve_track(getattr(self, f"{kind}_bgm_track").get(), getattr(self, f"{kind}_bgm_group").get())
        if track is not None:
            offset = self._result_offset(kind)
            self._set_result_offset(kind, offset)
            self.library.set_awakening_offset(track, offset)

    def preview_result(self, kind):
        if self.runtime_code != "STOPPED":
            return
        track = self.library.resolve_track(getattr(self, f"{kind}_bgm_track").get(), getattr(self, f"{kind}_bgm_group").get())
        if track is None:
            return
        offset = self._result_offset(kind)
        self.library.set_awakening_offset(track, offset)
        if self.preview_audio is None:
            cfg = main.load_config()
            cfg["_debug"] = self.debug
            self.preview_audio = PygameAudio(cfg)
        self.preview_audio.preview_awakening_track(track, offset)

    def stop_preview(self):
        if self.preview_audio is not None:
            self.preview_audio.stop()

    def create_group(self):
        name = simpledialog.askstring(self.t("new_group"), self.t("group_name"), parent=self.root)
        if name:
            try:
                self.library.create_group(name)
                self.group_choice.set(name)
                self.refresh_music()
            except ValueError as exc:
                messagebox.showerror(self.t("group_error"), str(exc))

    def rename_group(self):
        old_name = self.group_choice.get()
        name = simpledialog.askstring(self.t("rename_group"), self.t("new_group_name"), initialvalue=old_name, parent=self.root)
        if name:
            try:
                self.library.rename_group(old_name, name)
                self.group_choice.set(name)
                self.refresh_music()
            except ValueError as exc:
                messagebox.showerror(self.t("group_error"), str(exc))

    def delete_group(self):
        name = self.group_choice.get()
        try:
            self.library.delete_group(name)
            self.group_choice.set("")
            self.refresh_music()
        except ValueError as exc:
            messagebox.showerror(self.t("group_error"), str(exc))

    def on_volume_change(self, value):
        volume = max(0.0, min(1.0, float(value)))
        cfg = main.load_config()
        cfg["battle_bgm_volume"] = volume
        main.save_config(cfg)
        if self.audio is not None:
            self.audio.set_volume(volume)

    def start(self):
        if self.worker and self.worker.is_alive(): return
        cfg = main.load_config()
        cfg["_debug"] = self.debug
        self.refresh_music()
        track = self.library.resolve_track(self.awakening_bgm_track.get(), self.awakening_bgm_group.get())
        if track is not None:
            self.library.set_awakening_offset(track, self._awakening_offset())
        cfg.update(self.runtime_bgm_settings())
        self.runtime_cfg = cfg
        cfg["_recognition_callback"] = lambda go, victory, defeat: self.state_updates.put(
            ("__recognition__", go, victory, defeat)
        )
        if self.game_log_monitor_enabled.get() or self.lobby_bgm_enabled.get() or self.match_bgm_enabled.get():
            logs_dir = main.starward_logs_dir(cfg)
            if (not self.game_log_monitor_enabled.get()) or logs_dir is None or not logs_dir.is_dir():
                messagebox.showerror(
                    self.t("game_log_folder_error"),
                    self.t("game_log_folder_invalid"),
                )
                if self.debug:
                    reason = "path_empty" if logs_dir is None else f"path_invalid path={logs_dir}"
                    print(f"GAME_LOG monitor_not_started reason={reason}")
        hwnd = self.windows.get(self.window_choice.get())
        if not hwnd: return messagebox.showerror(self.t("window_error"), self.t("choose_window"))
        try:
            logger = create_diagnostics_logger()
            templates = TemplateBank(main.ROOT / "templates", logger=logger)
            detector = ScreenDetector(cfg, templates, logger=logger)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Template warning: {exc}")
            return messagebox.showwarning(self.t("template_warning"), self.t("template_missing"))
        print(f"GUI selected window: {self.window_choice.get()}")
        self.stop_event = threading.Event()
        self.pause_requested = False
        audio = None
        state = None
        def on_event(timestamp, event):
            logger.info("state_transition event=%s state=%s", event, state.state)
            logger.info("bgm_operation event=%s", event)
            if audio is not None:
                audio.on_event(event)
            self.state_updates.put(state.state)
        state = BattleStateMachine(cfg, on_event)
        state.diagnostic_logger = logger
        state.input_assist = GamepadInputAssist(cfg, logger=logger)
        self.set_detection_state(state.state)
        self.set_runtime_status("RUNNING")
        def run_source():
            nonlocal audio
            print("GUI window capture worker starting")
            audio = PygameAudio(cfg)
            self.audio = audio
            try:
                main.run_window(
                    hwnd, cfg, detector, state, False, self.stop_event,
                )
            except Exception:
                logger.exception("runtime_exception")
                raise
            finally:
                if self.debug:
                    print(f"Ctrl+F8 worker_exit pause_requested={self.pause_requested}")
                if self.pause_requested:
                    audio.fadeout()
                    if self.debug:
                        print("Ctrl+F8 audio_fadeout=requested")
                self.state_updates.put("__worker_finished__")
        self.worker = threading.Thread(target=run_source, daemon=True)
        self.worker.start()

    def stop(self):
        self.pause_requested = False
        self.resume_pending = False
        if self.audio is not None:
            self.audio.fadeout()
        if self.stop_event: self.stop_event.set()
        self.set_runtime_status("STOPPED")

    def toggle_pause(self):
        if self.runtime_code == "PAUSED":
            if self.debug:
                print("Ctrl+F8 action=resume")
            self.set_runtime_status("RUNNING")
            if self.worker and self.worker.is_alive():
                self.resume_pending = True
            else:
                self.start()
            return
        if self.worker and self.worker.is_alive():
            if self.debug:
                print("Ctrl+F8 action=pause")
            self.pause_requested = True
            self.stop_event.set()
            if self.debug:
                print("Ctrl+F8 worker_stop_event=set")
            self.set_runtime_status("PAUSED")

    def close(self):
        self.stop()
        self.hotkey.stop()
        self.root.destroy()


def launch(debug=False):
    root = tk.Tk()
    App(root, debug=debug)
    root.mainloop()
