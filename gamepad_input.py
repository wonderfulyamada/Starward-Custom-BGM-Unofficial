"""Optional gamepad combination evidence for awakening confirmation."""
from __future__ import annotations

import os
import time
import threading
import weakref
import ctypes
from pathlib import Path

# SDL reads this setting while it initializes its joystick/event subsystem.
# This module is imported before the optional pygame audio backend, so set it
# before pygame can be imported or initialized by this application.
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"


class _GamepadMonitor:
    """The only owner of pygame's joystick and event APIs in production."""
    def __init__(self, logger=None, pygame_module=None, poll_interval=0.01,
                 retry_delay=0.1, autostart=True):
        self.logger = logger
        self.pygame_module = pygame_module
        self.poll_interval = poll_interval
        self.retry_delay = retry_delay
        self.lock = threading.RLock()
        self.snapshot = (frozenset(), {}, [])
        self.captures = weakref.WeakSet()
        self.started = threading.Event()
        self.thread = threading.Thread(target=self._run, name="GamepadInputMonitor", daemon=True)
        if autostart:
            self.thread.start()
            self.started.wait(2)

    def _log(self, message, *args):
        if self.logger:
            self.logger.info(message, *args)

    @staticmethod
    def _value(joystick, method, default=None):
        try:
            return getattr(joystick, method)()
        except Exception:
            return default

    def _devices(self, pygame):
        """Return fresh device probes and a signature that survives index reuse."""
        joysticks = [pygame.joystick.Joystick(index)
                     for index in range(pygame.joystick.get_count())]
        signature = tuple(
            (index,
             self._value(joystick, "get_instance_id"),
             self._value(joystick, "get_guid"),
             self._value(joystick, "get_name", "unknown"))
            for index, joystick in enumerate(joysticks)
        )
        return joysticks, signature

    @staticmethod
    def _device_event_types(pygame):
        return {
            event_type for event_type in (
                getattr(pygame, "JOYDEVICEADDED", None),
                getattr(pygame, "JOYDEVICEREMOVED", None),
            ) if event_type is not None
        }

    def _publish(self, pygame, joysticks, events):
        pressed = set()
        sources = {}
        for index, joystick in enumerate(joysticks):
            source = {
                "index": index,
                "name": self._value(joystick, "get_name", "unknown"),
                "instance_id": self._value(joystick, "get_instance_id", "n/a"),
            }
            for button in range(joystick.get_numbuttons()):
                if joystick.get_button(button):
                    pressed.add(button)
                    sources.setdefault(button, []).append(source)
        with self.lock:
            self.snapshot = (frozenset(pressed), sources, events)
            captures = tuple(self.captures)
        for assist in captures:
            for event in events:
                if event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                    assist._capture_event(event, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP)

    def _run(self):
        # Importing and initializing pygame, pumping events, and reading joystick
        # state intentionally all happen on this one thread.
        pygame = self.pygame_module
        joysticks = []
        signature = None
        initialized = False
        reported_hint = False
        while True:
            try:
                if pygame is None:
                    import pygame as pygame_module
                    pygame = pygame_module
                if not initialized:
                    pygame.joystick.init()
                    initialized = True
                if not reported_hint:
                    reported_hint = True
                    hint = None
                    try:
                        sdl = ctypes.WinDLL(str(Path(pygame.__file__).with_name("SDL2.dll")))
                        sdl.SDL_GetHint.argtypes = [ctypes.c_char_p]
                        sdl.SDL_GetHint.restype = ctypes.c_char_p
                        value = sdl.SDL_GetHint(b"SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS")
                        hint = value.decode("ascii") if value else None
                    except Exception:
                        pass
                    self._log("gamepad monitor_thread=%s sdl_background_events=%s",
                              threading.current_thread().name, hint)

                pygame.event.pump()
                # This monitor owns the queue, so drain every event.  Leaving device
                # events behind can eventually fill SDL's queue on a long-running app.
                events = pygame.event.get()
                candidates, candidate_signature = self._devices(pygame)
                device_changed = any(
                    getattr(event, "type", None) in self._device_event_types(pygame)
                    for event in events
                )
                if device_changed or candidate_signature != signature:
                    for joystick in candidates:
                        joystick.init()
                    joysticks = candidates
                    signature = candidate_signature
                    self._log("gamepad controller_count=%s signature=%s",
                              len(joysticks), signature)

                self._publish(pygame, joysticks, events)
                self.started.set()
                time.sleep(self.poll_interval)
            except Exception as exc:
                # SDL devices can disappear between enumeration and polling.  Reset
                # published state, log the fault, then retry rather than killing the
                # sole event consumer permanently.
                self._log("gamepad monitor_recovering error=%r retry_seconds=%s",
                          exc, self.retry_delay)
                with self.lock:
                    self.snapshot = (frozenset(), {}, [])
                joysticks = []
                signature = None
                initialized = False
                self.started.set()
                time.sleep(self.retry_delay)

    def read(self):
        with self.lock:
            pressed, sources, _events = self.snapshot
            return pressed, {button: list(items) for button, items in sources.items()}


_monitor = None
_monitor_lock = threading.Lock()


def _get_monitor(logger):
    global _monitor
    with _monitor_lock:
        if _monitor is None:
            _monitor = _GamepadMonitor(logger)
        return _monitor


class GamepadInputAssist:
    _capture_assists = weakref.WeakSet()

    def __init__(self, cfg, pygame_module=None, clock=time.monotonic, logger=None):
        self.cfg = cfg
        self.pygame = pygame_module
        self.clock = clock
        self.logger = logger
        self.buttons_down = set()
        self.button_down_at = {}
        self.combo_latched = False
        self.capture_buttons = None
        self.capture_complete = False
        self._capture_held_at_start = set()
        self._joystick = None  # Compatibility alias for the first controller.
        self._joysticks = []
        self._controller_info = {}
        self._event_ready = False
        self._event_init_failed = False
        self._last_controller_count = None
        self._last_held_buttons = None
        self._last_combo_active = None
        self.last_combo_activation = None
        self._state_lock = threading.RLock()
        # Injected pygame is retained only for deterministic unit tests. Real
        # application instances consume the shared monitor snapshot instead.
        self._monitor = None if pygame_module is not None else _get_monitor(logger)

    def _debug(self, message):
        if self.logger and (message.startswith("controller_") or message.startswith("joystick_init")):
            self.logger.info("gamepad %s", message)
        if self.cfg.get("_debug", False):
            print(f"GAMEPAD {message}")

    @property
    def buttons(self):
        return tuple(sorted({int(button) for button in self.cfg.get("gamepad_awakening_buttons", [])}))

    @property
    def enabled(self):
        return bool(self.cfg.get("gamepad_input_assist_enabled", False))

    @property
    def active(self):
        with self._state_lock:
            return self.enabled and bool(self.buttons) and self.combo_latched

    @property
    def recent(self):
        with self._state_lock:
            if self.last_combo_activation is None:
                return False
            window = max(0.0, float(self.cfg.get("gamepad_awakening_recent_ms", 500))) / 1000.0
            return self.clock() - self.last_combo_activation <= window

    def consume_recent(self):
        with self._state_lock:
            self.last_combo_activation = None

    def _ensure_controller(self):
        if self.pygame is None:
            try:
                import pygame
                self.pygame = pygame
            except ImportError:
                self._debug("pygame_unavailable")
                return False
        try:
            if not self.pygame.joystick.get_init():
                self._debug("joystick_init")
                self.pygame.joystick.init()
            count = self.pygame.joystick.get_count()
            if count != self._last_controller_count:
                self._debug(f"controller_count={count}")
                self._last_controller_count = count
            if count < 1:
                self._disconnect()
                return False
            if len(self._joysticks) != count:
                self._joysticks = []
                for index in range(count):
                    joystick = self.pygame.joystick.Joystick(index)
                    joystick.init()
                    self._joysticks.append(joystick)
                    name = getattr(joystick, "get_name", lambda: "unknown")()
                    instance_id = getattr(joystick, "get_instance_id", lambda: "n/a")()
                    self._controller_info[id(joystick)] = {
                        "index": index, "name": name, "instance_id": instance_id,
                    }
                    self._debug(f"controller_connected index={index} name={name!r} instance_id={instance_id}")
                self._joystick = self._joysticks[0]
            return True
        except Exception as exc:
            self._debug(f"controller_init_failed error={exc}")
            self._disconnect()
            return False

    def _disconnect(self):
        if self._joystick is not None:
            self._debug("controller_disconnected")
        self._joystick = None
        self._joysticks = []
        self._controller_info = {}
        self.buttons_down.clear()
        self.button_down_at.clear()
        self.combo_latched = False

    def _ensure_event_system(self):
        if self._event_ready:
            return True
        if self._event_init_failed:
            return False
        display = getattr(self.pygame, "display", None)
        if display is None:  # Lightweight test adapters may expose events only.
            self._event_ready = True
            return True
        try:
            if not display.get_init():
                self._debug("event_system_display_init headless=true")
                display.init()
            self._event_ready = True
            return True
        except Exception as exc:
            self._event_init_failed = True
            self._debug(f"event_system_init_failed error={exc}")
            return False

    def begin_capture(self):
        with self._state_lock:
            self.capture_buttons = set()
            self.capture_complete = False
            if self._monitor is not None:
                self._capture_held_at_start = set(self._monitor.read()[0])
                with self._monitor.lock:
                    self._monitor.captures.add(self)
            else:
                self._capture_held_at_start = self._current_pressed_buttons()
                self._capture_assists.add(self)
        self._debug("registration_start mode=single_button")

    def finish_capture(self):
        with self._state_lock:
            captured = sorted(self.capture_buttons or [])
            self._capture_assists.discard(self)
            if self._monitor is not None:
                with self._monitor.lock:
                    self._monitor.captures.discard(self)
            self.capture_buttons = None
            self.capture_complete = False
            self._capture_held_at_start.clear()
        self._debug(f"registration_end captured={captured}")
        return captured

    def is_capture_complete(self):
        with self._state_lock:
            return self.capture_complete

    def _current_pressed_buttons(self):
        if not self._ensure_controller():
            return set()
        return {
            button
            for joystick in self._joysticks
            for button in range(joystick.get_numbuttons())
            if joystick.get_button(button)
        }

    def _capture_event(self, event, joy_down=None, joy_up=None):
        with self._state_lock:
            if self.capture_buttons is None or self.capture_complete:
                return
            button = getattr(event, "button", None)
            if button is None:
                return
            joy_up = joy_up if joy_up is not None else getattr(self.pygame, "JOYBUTTONUP", 2)
            joy_down = joy_down if joy_down is not None else getattr(self.pygame, "JOYBUTTONDOWN", 1)
            if event.type == joy_up:
                self._capture_held_at_start.discard(button)
            elif event.type == joy_down and button not in self._capture_held_at_start:
                self.capture_buttons = {button}
                self.capture_complete = True
                self._debug(f"registration_button_captured button={button}")

    def poll(self):
        if self._monitor is not None:
            return self._poll_snapshot()
        if not self._ensure_controller():
            return False
        if not self._ensure_event_system():
            return False
        try:
            self.pygame.event.pump()
            now = self.clock()
            event_types = [
                getattr(self.pygame, "JOYBUTTONDOWN", None),
                getattr(self.pygame, "JOYBUTTONUP", None),
            ]
            events = getattr(self.pygame.event, "get", lambda *_: [])([kind for kind in event_types if kind is not None])
            for event in events:
                if getattr(event, "type", None) in event_types:
                    action = "JOYBUTTONDOWN" if event.type == getattr(self.pygame, "JOYBUTTONDOWN", None) else "JOYBUTTONUP"
                    self._debug(f"{action} button={getattr(event, 'button', 'n/a')}")
                    for assist in tuple(self._capture_assists):
                        if assist.pygame is self.pygame:
                            assist._capture_event(event)
            # A registered button may be held on any connected controller.
            # Keep button numbers global to preserve the existing combo format.
            pressed_sources = {}
            for joystick in self._joysticks:
                source = self._controller_info.get(id(joystick), {})
                for button in range(joystick.get_numbuttons()):
                    if joystick.get_button(button):
                        pressed_sources.setdefault(button, []).append(source)
            pressed_buttons = set(pressed_sources)
            for button in set(self.buttons_down) | pressed_buttons:
                pressed = button in pressed_buttons
                if pressed and button not in self.buttons_down:
                    self.buttons_down.add(button)
                    self.button_down_at[button] = now
                elif not pressed and button in self.buttons_down:
                    self.buttons_down.remove(button)
                    self.button_down_at.pop(button, None)
                    self._capture_held_at_start.discard(button)
                    self.combo_latched = False
            held = tuple(sorted(self.buttons_down))
            if held != self._last_held_buttons:
                self._debug(f"held_buttons={list(held)}")
                self._last_held_buttons = held
            required = set(self.buttons)
            if required and required <= self.buttons_down and not self.combo_latched:
                timings = [self.button_down_at[button] for button in required]
                grace = max(0.0, float(self.cfg.get("gamepad_awakening_grace_ms", 250))) / 1000.0
                self.combo_latched = max(timings) - min(timings) <= grace
                if self.combo_latched and self.logger:
                    sources = {
                        (source.get("index"), source.get("name"), source.get("instance_id"))
                        for button in required for source in pressed_sources.get(button, [])
                    }
                    self.logger.info(
                        "gamepad_awakening_combo buttons=%s controllers=%s",
                        sorted(required),
                        [
                            {"index": index, "name": name, "instance_id": instance_id}
                            for index, name, instance_id in sorted(sources, key=lambda item: item[0])
                        ],
                    )
            active = self.active
            if active and self._last_combo_active is not True:
                self.last_combo_activation = now
            if active != self._last_combo_active:
                self._debug(f"combo_active={active}")
                self._last_combo_active = active
            return active
        except Exception as exc:
            self._debug(f"poll_failed error={exc}")
            self._disconnect()
            return False

    def _poll_snapshot(self):
        """Apply the monitor's latest state without touching pygame/SDL."""
        pressed_buttons, pressed_sources = self._monitor.read()
        now = self.clock()
        with self._state_lock:
            for button in set(self.buttons_down) | set(pressed_buttons):
                pressed = button in pressed_buttons
                if pressed and button not in self.buttons_down:
                    self.buttons_down.add(button)
                    self.button_down_at[button] = now
                elif not pressed and button in self.buttons_down:
                    self.buttons_down.remove(button)
                    self.button_down_at.pop(button, None)
                    self._capture_held_at_start.discard(button)
                    self.combo_latched = False
            required = set(self.buttons)
            if required and required <= self.buttons_down and not self.combo_latched:
                timings = [self.button_down_at[button] for button in required]
                grace = max(0.0, float(self.cfg.get("gamepad_awakening_grace_ms", 250))) / 1000.0
                self.combo_latched = max(timings) - min(timings) <= grace
                if self.combo_latched and self.logger:
                    sources = {
                        (source.get("index"), source.get("name"), source.get("instance_id"))
                        for button in required for source in pressed_sources.get(button, [])
                    }
                    self.logger.info("gamepad_awakening_combo buttons=%s controllers=%s", sorted(required), [
                        {"index": index, "name": name, "instance_id": instance_id}
                        for index, name, instance_id in sorted(sources, key=lambda item: item[0])
                    ])
            active = self.enabled and bool(required) and self.combo_latched
            if active and self._last_combo_active is not True:
                self.last_combo_activation = now
            self._last_combo_active = active
            return active
