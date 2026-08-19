"""Minimal Tk interface for choosing a detector frame source."""
import ctypes
import ctypes.wintypes
import queue
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import main
from audio import PygameAudio
from detector import ScreenDetector, TemplateBank
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
    def __init__(self, root):
        self.root = root
        self.root.title("Starward BGM Detector")
        self.window_choice = tk.StringVar()
        cfg = main.load_config()
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
        self.detection_text = tk.StringVar(value="IDLE")
        self.detection_code = "IDLE"
        self.runtime_text = tk.StringVar(value="")
        self.runtime_code = "STOPPED"
        self.localized_widgets = []
        self.windows = {}
        self.library = MusicLibrary(main.ROOT / "BGM")
        self.stop_event = None
        self.worker = None
        self.audio = None
        self.runtime_cfg = None
        self.pause_requested = False
        self.resume_pending = False
        self.state_updates = queue.Queue()
        self._build()
        self.apply_language()
        self.refresh_windows()
        self.refresh_music()
        self.hotkey = GlobalPauseHotkey(lambda: self.state_updates.put("__toggle_pause__"))
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
        self.update_fixed_track_state()
        self.set_detection_state(self.detection_code)
        self.set_runtime_status(self.runtime_code)

    def mode_label(self, code):
        return self.t({"Fixed": "fixed", "Balanced Random": "balanced", "True Random": "true_random"}[code])

    def mode_code(self):
        return {self.t("fixed"): "Fixed", self.t("balanced"): "Balanced Random", self.t("true_random"): "True Random"}[self.playback_mode.get()]

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

    def save_playback_settings(self, _event=None):
        settings = self.playback_settings()
        cfg = main.load_config()
        cfg.update(settings)
        main.save_config(cfg)
        if self.runtime_cfg is not None:
            self.runtime_cfg.update(settings)

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
                    self.toggle_pause()
                elif update == "__worker_finished__":
                    self.root.after(10, self._handle_worker_finished)
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
        membership_actions = ttk.Frame(frame)
        membership_actions.grid(row=5, column=2)
        self._localized(ttk.Button(membership_actions, command=lambda: self.set_membership(True)), "add").grid(row=0, column=0)
        self._localized(ttk.Button(membership_actions, command=lambda: self.set_membership(False)), "remove").grid(row=0, column=1)
        self._localized(ttk.Label(frame), "volume").grid(row=6, column=0, sticky="w")
        ttk.Scale(frame, variable=self.volume, from_=0.0, to=1.0, command=self.on_volume_change).grid(row=6, column=1, sticky="ew")
        self._localized(ttk.Label(frame), "fadeout").grid(row=7, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.fadeout, width=12).grid(row=7, column=1, sticky="w")
        self.start_button = self._localized(ttk.Button(frame, command=self.start), "start")
        self.start_button.grid(row=8, column=0, pady=(10, 0))
        self.stop_button = self._localized(ttk.Button(frame, command=self.stop), "stop")
        self.stop_button.grid(row=8, column=1, sticky="w", pady=(10, 0))
        self._localized(ttk.Label(frame), "runtime_status").grid(row=9, column=0, sticky="w", pady=(10, 0))
        ttk.Label(frame, textvariable=self.runtime_text).grid(row=9, column=1, sticky="w", pady=(10, 0))
        self._localized(ttk.Label(frame), "detection_state").grid(row=10, column=0, sticky="w")
        ttk.Label(frame, textvariable=self.detection_text).grid(row=10, column=1, sticky="w")
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
        if self.group_choice.get() not in groups:
            self.group_choice.set(groups[0] if groups else "")
        scope = self.scope_code()
        tracks = [track.name for track in self.library.tracks(self.group_choice.get() if scope == "Selected Group" else LIBRARY_SCOPE)]
        self.track_box["values"] = tracks
        if self.fixed_track.get() not in tracks:
            self.fixed_track.set(tracks[0] if tracks else "")

    def on_scope_change(self, _event=None):
        self.refresh_music()
        self.save_playback_settings()

    def on_group_change(self, _event=None):
        self.refresh_music()
        self.save_playback_settings()

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

    def set_membership(self, included):
        self.library.set_membership(self.group_choice.get(), self.fixed_track.get(), included)
        self.refresh_music()

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
        self.refresh_music()
        cfg.update(
            **self.playback_settings(),
            battle_bgm_volume=self.volume.get(),
            result_fadeout_ms=self.fadeout.get(),
        )
        self.runtime_cfg = cfg
        hwnd = self.windows.get(self.window_choice.get())
        if not hwnd: return messagebox.showerror(self.t("window_error"), self.t("choose_window"))
        try:
            templates = TemplateBank(main.ROOT / "templates")
            detector = ScreenDetector(cfg, templates)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Template warning: {exc}")
            return messagebox.showwarning(self.t("template_warning"), self.t("template_missing"))
        print(f"GUI selected window: {self.window_choice.get()}")
        self.stop_event = threading.Event()
        self.pause_requested = False
        audio = None
        state = None
        def on_event(timestamp, event):
            if audio is not None:
                audio.on_event(event)
            self.state_updates.put(state.state)
        state = BattleStateMachine(cfg, on_event)
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
            finally:
                if self.pause_requested:
                    audio.fadeout()
                self.state_updates.put("__worker_finished__")
        self.worker = threading.Thread(target=run_source, daemon=True)
        self.worker.start()

    def stop(self):
        self.pause_requested = False
        self.resume_pending = False
        if self.stop_event: self.stop_event.set()
        self.set_runtime_status("STOPPED")

    def toggle_pause(self):
        if self.runtime_code == "PAUSED":
            self.set_runtime_status("RUNNING")
            if self.worker and self.worker.is_alive():
                self.resume_pending = True
            else:
                self.start()
            return
        if self.worker and self.worker.is_alive():
            self.pause_requested = True
            self.stop_event.set()
            self.set_runtime_status("PAUSED")

    def close(self):
        self.stop()
        self.hotkey.stop()
        self.root.destroy()


def launch():
    root = tk.Tk()
    App(root)
    root.mainloop()
