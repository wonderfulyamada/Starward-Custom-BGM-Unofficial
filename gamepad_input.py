"""Optional gamepad combination evidence for awakening confirmation."""
from __future__ import annotations

import time


class GamepadInputAssist:
    def __init__(self, cfg, pygame_module=None, clock=time.monotonic):
        self.cfg = cfg
        self.pygame = pygame_module
        self.clock = clock
        self.buttons_down = set()
        self.button_down_at = {}
        self.combo_latched = False
        self.capture_buttons = None
        self.capture_complete = False
        self._joystick = None
        self._event_ready = False
        self._event_init_failed = False
        self._last_controller_count = None
        self._last_held_buttons = None
        self._last_combo_active = None
        self.last_combo_activation = None

    def _debug(self, message):
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
        return self.enabled and bool(self.buttons) and self.combo_latched

    @property
    def recent(self):
        if self.last_combo_activation is None:
            return False
        window = max(0.0, float(self.cfg.get("gamepad_awakening_recent_ms", 500))) / 1000.0
        return self.clock() - self.last_combo_activation <= window

    def consume_recent(self):
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
            if self._joystick is None:
                self._joystick = self.pygame.joystick.Joystick(0)
                self._joystick.init()
                name = getattr(self._joystick, "get_name", lambda: "unknown")()
                instance_id = getattr(self._joystick, "get_instance_id", lambda: "n/a")()
                self._debug(f"controller_connected name={name!r} instance_id={instance_id}")
            return True
        except Exception as exc:
            self._debug(f"controller_init_failed error={exc}")
            self._disconnect()
            return False

    def _disconnect(self):
        if self._joystick is not None:
            self._debug("controller_disconnected")
        self._joystick = None
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
        self.capture_buttons = set()
        self.capture_complete = False
        self._debug("registration_start mode=single_button")

    def finish_capture(self):
        captured = sorted(self.capture_buttons or [])
        self.capture_buttons = None
        self.capture_complete = False
        self._debug(f"registration_end captured={captured}")
        return captured

    def poll(self):
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
            for button in range(self._joystick.get_numbuttons()):
                pressed = bool(self._joystick.get_button(button))
                if pressed and button not in self.buttons_down:
                    self.buttons_down.add(button)
                    self.button_down_at[button] = now
                    if self.capture_buttons is not None:
                        self.capture_buttons.add(button)
                        self.capture_complete = True
                        self._debug(f"registration_button_captured button={button}")
                elif not pressed and button in self.buttons_down:
                    self.buttons_down.remove(button)
                    self.button_down_at.pop(button, None)
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
