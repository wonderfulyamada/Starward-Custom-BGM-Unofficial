import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gamepad_input import GamepadInputAssist
from gui import App
from state_machine import BattleStateMachine, DetectorScores


class FakeJoystick:
    def __init__(self, buttons=4):
        self.state = [False] * buttons

    def init(self):
        pass

    def get_numbuttons(self):
        return len(self.state)

    def get_button(self, button):
        return self.state[button]


class FakePygame:
    def __init__(self, joystick):
        self._joystick = joystick
        self.joystick = SimpleNamespace(
            get_init=lambda: True, init=lambda: None, get_count=lambda: 1,
            Joystick=lambda _index: joystick,
        )
        self.event = SimpleNamespace(pump=lambda: None)
        self.display = SimpleNamespace(get_init=self._display_get_init, init=self._display_init)
        self.display_initialized = False
        self.display_init_calls = 0

    def _display_get_init(self):
        return self.display_initialized

    def _display_init(self):
        self.display_initialized = True
        self.display_init_calls += 1


class MultiPygame(FakePygame):
    def __init__(self, joysticks):
        super().__init__(joysticks[0])
        self._joysticks = joysticks
        self.joystick.get_count = lambda: len(joysticks)
        self.joystick.Joystick = lambda index: joysticks[index]


class GamepadInputAssistTests(unittest.TestCase):
    def make_state(self, enabled):
        events = []
        cfg = {
            "gamepad_input_assist_enabled": enabled,
            "victory_threshold": 1.0, "defeat_threshold": 1.0,
            "result_confirm_frames": 1, "go_threshold": 1.0,
            "burst_hud_loss_confirm_frames": 2, "burst_gauge_delta_min": 0.04,
            "burst_gauge_decrease_confirm_frames": 2, "burst_gauge_recovery_confirm_frames": 2,
        }
        state = BattleStateMachine(cfg, lambda _timestamp, event: events.append(event))
        return state, events

    def make_assist(self, buttons, enabled=True, grace=250):
        self.clock = [0.0]
        self.joystick = FakeJoystick()
        cfg = {
            "gamepad_input_assist_enabled": enabled,
            "gamepad_awakening_buttons": buttons,
            "gamepad_awakening_grace_ms": grace,
        }
        return GamepadInputAssist(cfg, FakePygame(self.joystick), lambda: self.clock[0])

    def press(self, assist, button, elapsed=0.0):
        self.clock[0] += elapsed
        self.joystick.state[button] = True
        return assist.poll()

    def test_single_button(self):
        assist = self.make_assist([0])
        self.assertTrue(self.press(assist, 0))

    def test_background_joystick_events_are_enabled_before_pygame_use(self):
        self.assertEqual(os.environ.get("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"), "1")

    def test_two_and_three_button_combinations(self):
        assist = self.make_assist([0, 1])
        self.assertFalse(self.press(assist, 0))
        self.assertTrue(self.press(assist, 1, 0.05))
        assist = self.make_assist([0, 1, 2])
        self.press(assist, 0)
        self.press(assist, 1, 0.02)
        self.assertTrue(self.press(assist, 2, 0.02))

    def test_registered_button_is_found_on_any_connected_controller(self):
        first, second = FakeJoystick(), FakeJoystick()
        assist = GamepadInputAssist(
            {"gamepad_input_assist_enabled": True, "gamepad_awakening_buttons": [1], "gamepad_awakening_grace_ms": 250},
            MultiPygame([first, second]), lambda: 0.0,
        )
        second.state[1] = True
        self.assertTrue(assist.poll())
        self.assertEqual(len(assist._joysticks), 2)

    def test_combo_log_names_the_controller_without_per_poll_entries(self):
        class Logger:
            def __init__(self): self.entries = []
            def info(self, message, *args): self.entries.append(message % args)

        joystick = FakeJoystick()
        joystick.get_name = lambda: "Controller A"
        joystick.get_instance_id = lambda: 42
        logger = Logger()
        assist = GamepadInputAssist(
            {"gamepad_input_assist_enabled": True, "gamepad_awakening_buttons": [1], "gamepad_awakening_grace_ms": 250},
            FakePygame(joystick), lambda: 0.0, logger,
        )
        joystick.state[1] = True
        self.assertTrue(assist.poll())
        assist.poll()
        combos = [entry for entry in logger.entries if entry.startswith("gamepad_awakening_combo")]
        self.assertEqual(len(combos), 1)
        self.assertIn("Controller A", combos[0])
        self.assertIn("42", combos[0])

    def test_staggered_incomplete_and_release_states(self):
        assist = self.make_assist([0, 1])
        self.press(assist, 0)
        self.assertTrue(self.press(assist, 1, 0.2))
        self.joystick.state[1] = False
        assist.poll()
        self.joystick.state[0] = False
        assist.poll()
        self.assertFalse(self.press(assist, 0))
        self.assertTrue(self.press(assist, 1, 0.05))
        self.joystick.state[0] = False
        self.assertFalse(assist.poll())

    def test_disconnect_and_disabled_are_safe(self):
        assist = self.make_assist([0], enabled=False)
        self.assertFalse(self.press(assist, 0))
        assist = self.make_assist([0])
        assist.pygame.joystick.get_count = lambda: 0
        self.assertFalse(assist.poll())

    def test_event_system_initializes_headlessly_and_controller_stays_connected(self):
        assist = self.make_assist([0])
        pygame = assist.pygame
        self.assertFalse(assist.poll())
        first_controller = assist._joystick
        self.assertTrue(pygame.display_initialized)
        self.assertEqual(pygame.display_init_calls, 1)
        self.assertFalse(assist.poll())
        self.assertIs(assist._joystick, first_controller)
        self.assertEqual(pygame.display_init_calls, 1)

    def test_debug_registration_logs_controller_and_capture_lifecycle(self):
        assist = self.make_assist([0])
        assist.cfg["_debug"] = True
        with patch("builtins.print") as printed:
            assist.begin_capture()
            self.press(assist, 0)
            self.assertEqual(assist.finish_capture(), [0])
        messages = [call.args[0] for call in printed.call_args_list]
        self.assertTrue(any("registration_start" in message for message in messages))
        self.assertTrue(any("controller_count=1" in message for message in messages))
        self.assertTrue(any("held_buttons=[0]" in message for message in messages))
        self.assertTrue(any("registration_end captured=[0]" in message for message in messages))

    def test_debug_poll_logs_only_state_changes(self):
        assist = self.make_assist([0])
        assist.cfg["_debug"] = True
        with patch("builtins.print") as printed:
            assist.poll()
            assist.poll()
            self.joystick.state[0] = True
            assist.poll()
            assist.poll()
            assist.pygame.joystick.get_count = lambda: 0
            assist.poll()
        messages = [call.args[0] for call in printed.call_args_list]
        self.assertEqual(sum("controller_count=1" in message for message in messages), 1)
        self.assertEqual(sum("held_buttons=[0]" in message for message in messages), 1)
        self.assertEqual(sum("combo_active=True" in message for message in messages), 1)
        self.assertTrue(any("controller_count=0" in message for message in messages))
        self.assertTrue(any("controller_disconnected" in message for message in messages))

    def test_gui_registration_polls_without_blocking_and_handles_timeout(self):
        scheduled = []

        class Root:
            def after(self, delay, callback):
                scheduled.append((delay, callback))

        class Assist:
            def __init__(self, captured):
                self.captured = captured
                self.poll_calls = 0
                self.capture_complete = False
                self.cfg = {"gamepad_awakening_buttons": []}

            def begin_capture(self): pass
            def poll(self):
                self.poll_calls += 1
                self.capture_complete = bool(self.captured)
            def finish_capture(self): return self.captured
            @property
            def buttons(self): return tuple(self.cfg["gamepad_awakening_buttons"])

        app = App.__new__(App)
        app.root = Root()
        app.debug = False
        app.gamepad_registration_active = False
        app.gamepad_assist = Assist([0, 2])
        app.gamepad_binding_text = SimpleNamespace(set=lambda _value: None)
        app.t = lambda key: key
        app.update_gamepad_binding_text = lambda: None
        app.save_playback_settings = lambda: None
        app.register_gamepad_buttons()
        self.assertEqual([delay for delay, _ in scheduled], [25, 1000])
        scheduled[0][1]()
        self.assertEqual(app.gamepad_assist.poll_calls, 1)
        self.assertEqual(app.gamepad_assist.cfg["gamepad_awakening_buttons"], [0])
        self.assertFalse(app.gamepad_registration_active)

        app.gamepad_assist = Assist([])
        app.gamepad_registration_active = True
        app.finish_gamepad_registration()
        self.assertFalse(app.gamepad_registration_active)

    def test_first_press_completes_capture_and_duplicate_add_is_ignored(self):
        assist = self.make_assist([])
        assist.begin_capture()
        self.press(assist, 1)
        self.assertTrue(assist.capture_complete)
        self.assertEqual(assist.finish_capture(), [1])
        assist.cfg["gamepad_awakening_buttons"] = [1]
        self.assertEqual(sorted(set(assist.buttons + (1,))), [1])

    def test_gui_can_remove_one_registered_button(self):
        app = App.__new__(App)
        app.gamepad_remove_choice = SimpleNamespace(get=lambda: "1")
        app.gamepad_assist = SimpleNamespace(buttons=(0, 1, 2), cfg={"gamepad_awakening_buttons": [0, 1, 2]})
        app.update_gamepad_binding_text = lambda: None
        app.save_playback_settings = lambda: None
        app.remove_gamepad_button()
        self.assertEqual(app.gamepad_assist.cfg["gamepad_awakening_buttons"], [0, 2])

    def test_ready_input_then_unknown_starts_awakening(self):
        state, events = self.make_state(True)
        state.state = state.READY
        state.update(0.0, DetectorScores(), SimpleNamespace(classification="normal", gauge_level=1.0), True)
        self.assertEqual(state.state, state.READY)
        state.update(0.1, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), True)
        self.assertEqual(state.state, state.AWAKENING)
        self.assertEqual(events, ["AWAKENING_START"])

    def test_ready_after_combo_release_uses_recent_input_once(self):
        assist = self.make_assist([0])
        self.assertTrue(self.press(assist, 0))
        self.clock[0] += 0.1
        self.joystick.state[0] = False
        self.assertFalse(assist.poll())
        self.assertTrue(assist.recent)
        state, events = self.make_state(True)
        state.state = state.READY
        state.update(0.0, DetectorScores(), SimpleNamespace(classification="normal", gauge_level=1.0), False, assist.recent, assist.consume_recent)
        state.update(0.1, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), False, assist.recent, assist.consume_recent)
        self.assertEqual(state.state, state.AWAKENING)
        self.assertEqual(events, ["AWAKENING_START"])
        self.assertFalse(assist.recent)

    def test_input_outside_ready_and_disabled_assist_do_not_start(self):
        state, events = self.make_state(True)
        state.state = state.BATTLE
        state.update(0.0, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), True)
        self.assertEqual(state.state, state.BATTLE)
        self.assertEqual(events, [])
        state.state = state.READY
        state.update(0.1, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), True)
        self.assertEqual(state.state, state.READY)
        self.assertEqual(events, [])
        state, events = self.make_state(False)
        state.state = state.READY
        state.update(0.0, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None, cut_in_detected=True), True)
        self.assertEqual(state.state, state.READY)
        self.assertEqual(events, [])

    def test_ready_remains_latched_after_hud_recovery_without_combo(self):
        state, events = self.make_state(True)
        state.state = state.READY
        state.ready_gauge = 1.0
        state.last_visible_gauge = 1.0
        for timestamp, gauge in ((0.0, 0.90), (0.1, 1.00)):
            state.update(timestamp, DetectorScores(), SimpleNamespace(classification="normal", gauge_level=gauge), False)
        self.assertEqual(state.state, state.READY)
        self.assertEqual(events, [])

    def test_staggered_combo_outside_250ms_does_not_activate(self):
        assist = self.make_assist([0, 1])
        self.press(assist, 0)
        self.assertFalse(self.press(assist, 1, 0.251))

    def test_ready_resets_on_awakening_result_and_battle_reset(self):
        state, _events = self.make_state(True)
        state.state = state.READY
        state.update(0.0, DetectorScores(), SimpleNamespace(classification="normal", gauge_level=1.0), True)
        state.update(0.1, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), True)
        self.assertEqual(state.state, state.AWAKENING)

        state.state = state.READY
        state.update(0.1, DetectorScores(victory=1.0), SimpleNamespace(classification="unknown", gauge_level=None))
        self.assertEqual(state.state, state.RESULT)

        state.state = state.IDLE
        state.update(0.2, DetectorScores(go=1.0), SimpleNamespace(classification="unknown", gauge_level=None))
        self.assertEqual(state.state, state.BATTLE)

    def test_ready_known_hud_with_input_does_not_start(self):
        state, events = self.make_state(True)
        state.state = state.READY
        state.update(0.0, DetectorScores(), SimpleNamespace(classification="normal", gauge_level=1.0), True)
        state.update(0.1, DetectorScores(), SimpleNamespace(classification="normal", gauge_level=1.0), True)
        self.assertEqual(state.state, state.READY)
        self.assertEqual(events, [])

    def test_ready_cut_in_without_input_does_not_start(self):
        state, events = self.make_state(True)
        state.state = state.READY
        state.update(0.0, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None, cut_in_detected=True), False)
        self.assertEqual(state.state, state.READY)
        self.assertEqual(events, [])

    def test_unknown_before_input_requires_normal_then_later_unknown(self):
        state, events = self.make_state(True)
        state.state = state.READY
        state.update(0.0, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), False)
        state.update(0.1, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), True)
        self.assertEqual(state.state, state.READY)
        state.update(0.2, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), True)
        self.assertEqual(state.state, state.READY)
        state.update(0.3, DetectorScores(), SimpleNamespace(classification="normal", gauge_level=1.0), True)
        state.update(0.4, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), True)
        self.assertEqual(state.state, state.AWAKENING)
        self.assertEqual(events, ["AWAKENING_START"])

    def test_pending_input_expires_without_unknown(self):
        state, events = self.make_state(True)
        state.cfg["gamepad_awakening_recent_ms"] = 100
        state.state = state.READY
        state.update(0.0, DetectorScores(), SimpleNamespace(classification="normal", gauge_level=1.0), True)
        state.update(0.2, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), True)
        self.assertEqual(state.state, state.READY)
        self.assertEqual(events, [])

    def test_expired_recent_input_does_not_bypass_ready_gauge_fallback(self):
        assist = self.make_assist([0])
        self.press(assist, 0)
        self.joystick.state[0] = False
        self.clock[0] += 0.6
        assist.poll()
        self.assertFalse(assist.recent)
        state, events = self.make_state(True)
        state.state = state.READY
        state.update(0.0, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), False, assist.recent)
        self.assertEqual(state.state, state.READY)
        self.assertEqual(events, [])
