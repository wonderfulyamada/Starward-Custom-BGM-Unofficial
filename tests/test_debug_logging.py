from types import SimpleNamespace
import unittest
from unittest.mock import patch

from state_machine import BattleStateMachine, DetectorScores


class ResultDebugLoggingTests(unittest.TestCase):
    def test_result_lifecycle_logs_only_when_debug_enabled(self):
        events = []
        cfg = {
            "_debug": True,
            "result_bgm_enabled": True,
            "result_blackout_confirm_frames": 2,
            "victory_threshold": 0.38,
            "defeat_threshold": 0.38,
            "result_confirm_frames": 1,
            "go_threshold": 0.42,
            "burst_hud_loss_confirm_frames": 2,
            "burst_gauge_delta_min": 0.04,
            "burst_gauge_decrease_confirm_frames": 3,
            "burst_gauge_recovery_confirm_frames": 3,
        }
        state = BattleStateMachine(cfg, lambda timestamp, event: events.append(event))
        state.state = state.BATTLE
        burst = SimpleNamespace(classification="normal", gauge_level=1.0)

        with patch("builtins.print") as printed:
            state.update(0.0, DetectorScores(victory=1.0), burst)
            state.update(0.1, DetectorScores(blackout=True, blackout_brightness=0.0), burst)
            state.update(0.2, DetectorScores(blackout=True, blackout_brightness=0.0), burst)

        messages = [call.args[0] for call in printed.call_args_list]
        self.assertEqual(events, ["VICTORY", "RESULT_END"])
        self.assertIn("RESULT enter event=VICTORY", messages)
        self.assertIn("RESULT_END transition=IDLE", messages)
        self.assertTrue(any("brightness=0.00" in message for message in messages))


class AwakeningDebugLoggingTests(unittest.TestCase):
    def test_ready_to_awakening_logs_baseline_samples_and_confirmation(self):
        events = []
        cfg = {
            "_debug": True,
            "result_bgm_enabled": False,
            "victory_threshold": 0.38,
            "defeat_threshold": 0.38,
            "result_confirm_frames": 1,
            "go_threshold": 0.42,
            "burst_hud_loss_confirm_frames": 2,
            "burst_gauge_delta_min": 0.04,
            "burst_gauge_decrease_confirm_frames": 2,
            "burst_gauge_recovery_confirm_frames": 3,
            "gamepad_input_assist_enabled": True,
        }
        state = BattleStateMachine(cfg, lambda timestamp, event: events.append(event))
        state.state = state.BATTLE
        visible = SimpleNamespace(classification="normal", gauge_level=1.0)
        missing = SimpleNamespace(classification="unknown", gauge_level=None)

        with patch("builtins.print") as printed:
            state.update(0.0, DetectorScores(), visible)
            state.update(0.1, DetectorScores(), missing)
            state.update(0.2, DetectorScores(), missing)
            state.update(0.3, DetectorScores(), SimpleNamespace(classification="normal", gauge_level=0.90))
            state.update(0.35, DetectorScores(), SimpleNamespace(classification="normal", gauge_level=0.80), True)
            state.update(0.4, DetectorScores(), SimpleNamespace(classification="unknown", gauge_level=None), True)

        messages = [call.args[0] for call in printed.call_args_list]
        self.assertEqual(events, ["AWAKENING_START"])
        self.assertTrue(any("BATTLE -> READY enter reason=hud_missing_confirmed" in message for message in messages))
        self.assertTrue(any("READY latched gauge=0.900" in message for message in messages))
        self.assertTrue(any(
            "AWAKENING_START confirmed" in message
            and "reason=ready_pending_input_normal_to_unknown" in message
            for message in messages
        ))

    def test_ready_rejection_logs_exact_reason(self):
        cfg = {
            "_debug": True,
            "result_bgm_enabled": False,
            "victory_threshold": 0.38,
            "defeat_threshold": 0.38,
            "result_confirm_frames": 1,
            "go_threshold": 0.42,
            "burst_hud_loss_confirm_frames": 1,
            "burst_gauge_delta_min": 0.04,
            "burst_gauge_decrease_confirm_frames": 2,
            "burst_gauge_recovery_confirm_frames": 3,
        }
        state = BattleStateMachine(cfg, lambda *_: None)
        state.state = state.BATTLE
        state.last_visible_gauge = 1.0
        missing = SimpleNamespace(classification="unknown", gauge_level=None)
        recovered = SimpleNamespace(classification="normal", gauge_level=0.98)

        with patch("builtins.print") as printed:
            state.update(0.0, DetectorScores(), missing)
            state.update(0.1, DetectorScores(), recovered)

        messages = [call.args[0] for call in printed.call_args_list]
        self.assertEqual(state.state, state.READY)
        self.assertTrue(any("READY latched gauge=0.980" in message for message in messages))
