from types import SimpleNamespace
import unittest

from state_machine import BattleStateMachine, DetectorScores


class AwakeningEndDetectionTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.cfg = {
            "_debug": False,
            "result_bgm_enabled": False,
            "victory_threshold": 0.38,
            "defeat_threshold": 0.38,
            "result_confirm_frames": 1,
            "go_threshold": 0.42,
            "burst_hud_loss_confirm_frames": 2,
            "burst_gauge_delta_min": 0.04,
            "burst_gauge_decrease_confirm_frames": 3,
            "awakening_end_gauge_max": 0.25,
            "burst_end_confirm_frames": 4,
        }
        self.state = BattleStateMachine(
            self.cfg, lambda _timestamp, event: self.events.append(event)
        )
        self.state.state = self.state.AWAKENING
        self.state.awakening_started_at = 0.0

    def update(self, timestamp, gauge, glow="PRESENT", observable=True, scores=None):
        self.state.update(
            timestamp,
            scores or DetectorScores(),
            SimpleNamespace(
                classification="normal" if observable else "unknown",
                gauge_level=gauge if observable else None,
                glow_score=0.2 if glow == "PRESENT" else 0.01,
                glow_classification=glow,
                hud_observable=observable,
            ),
        )

    def test_near_zero_gauge_with_glow_present_does_not_end(self):
        for timestamp in (0.1, 0.2, 0.3, 0.4):
            self.update(timestamp, 0.05, "PRESENT")

        self.assertEqual(self.state.state, self.state.AWAKENING)
        self.assertEqual(self.events, [])

    def test_glow_absent_at_high_gauge_ends(self):
        for timestamp in (0.1, 0.2, 0.3, 0.4):
            self.update(timestamp, 0.40, "ABSENT")

        self.assertEqual(self.state.state, self.state.BATTLE)
        self.assertEqual(self.events, ["AWAKENING_END"])

    def test_sustained_near_zero_gauge_and_absent_glow_ends(self):
        for timestamp in (0.1, 0.2, 0.3, 0.4):
            self.update(timestamp, 0.05, "ABSENT")

        self.assertEqual(self.state.state, self.state.BATTLE)
        self.assertEqual(self.events, ["AWAKENING_END"])

    def test_unrelated_sample_resets_combined_confirmation(self):
        self.update(0.1, 0.05, "ABSENT")
        self.update(0.2, 0.05, "ABSENT")
        self.update(0.3, 0.40, "PRESENT")
        self.update(0.4, 0.05, "ABSENT")
        self.update(0.5, 0.05, "ABSENT")

        self.assertEqual(self.state.state, self.state.AWAKENING)
        self.assertEqual(self.events, [])

    def test_result_still_interrupts_awakening(self):
        self.update(0.1, 0.90, scores=DetectorScores(victory=1.0))

        self.assertEqual(self.state.state, self.state.RESULT)
        self.assertEqual(self.events, ["VICTORY"])

    def test_active_glow_of_any_colour_keeps_awakening(self):
        for timestamp in (0.1, 0.2, 0.3):
            self.update(timestamp, 0.05, "PRESENT")
        self.assertEqual(self.state.state, self.state.AWAKENING)

    def test_unknown_cut_in_or_occlusion_never_counts_as_absent(self):
        self.update(0.1, 0.8, "PRESENT")
        self.update(0.2, 0.8, "UNKNOWN", observable=False)
        self.update(0.3, 0.8, "UNKNOWN", observable=False)
        self.assertEqual(self.state.awakening_end_streak, 0)
        self.assertEqual(self.state.state, self.state.AWAKENING)

    def test_single_absent_sample_does_not_end_awakening(self):
        self.update(0.1, 0.05, "ABSENT")
        self.assertEqual(self.state.awakening_end_streak, 1)
        self.assertEqual(self.state.state, self.state.AWAKENING)

    def test_near_zero_jitter_does_not_reset_confirmation(self):
        self.state.cfg["burst_end_confirm_frames"] = 4
        for timestamp, gauge in zip((0.1, 0.2, 0.3, 0.4), (0.111, 0.125, 0.111, 0.111)):
            self.update(timestamp, gauge, "ABSENT")
        self.assertEqual(self.state.state, self.state.BATTLE)
        self.assertEqual(self.events, ["AWAKENING_END"])

    def test_gauge_recovery_is_not_required(self):
        self.update(0.1, 0.05, "ABSENT")
        for timestamp in (0.2, 0.3, 0.4, 0.5):
            self.update(timestamp, 0.05, "ABSENT")
        self.assertEqual(self.state.state, self.state.BATTLE)
        self.assertEqual(self.events, ["AWAKENING_END"])

    def test_glow_absence_alone_cannot_end(self):
        for timestamp in (0.1, 0.2, 0.3, 0.4, 0.5):
            self.update(timestamp, 0.8, "ABSENT")
        self.assertEqual(self.state.state, self.state.BATTLE)
        self.assertEqual(self.events, ["AWAKENING_END"])

    def test_present_resets_combined_history(self):
        self.update(0.1, 0.05, "ABSENT")
        self.update(0.2, 0.05, "PRESENT")
        self.assertEqual(self.state.awakening_end_streak, 0)

    def test_gauge_recovery_with_glow_present_does_not_end(self):
        for timestamp, gauge in ((1.0, 0.05), (1.1, 0.06), (1.2, 0.05), (1.3, 0.06), (1.4, 0.05)):
            self.update(timestamp, gauge, "PRESENT")
        self.assertEqual(self.state.state, self.state.AWAKENING)

    def test_unavailable_hud_blocks_a_gauge_end(self):
        self.update(1.0, 0.05, "ABSENT")
        self.update(1.1, 0.05, "ABSENT")
        self.update(1.2, 0.05, "UNKNOWN", observable=False)
        self.assertEqual(self.state.state, self.state.AWAKENING)
        self.assertEqual(self.state.awakening_end_streak, 0)

    def test_attack_hiding_hud_resets_end_confirmation(self):
        self.update(0.1, 0.05, "ABSENT")
        self.update(0.2, 0.05, "ABSENT")
        # An attack occludes the gauge: it is UNKNOWN, not an end sample.
        self.update(0.3, None, "UNKNOWN", observable=False)
        self.update(0.4, 0.05, "ABSENT")
        self.update(0.5, 0.05, "ABSENT")
        self.assertEqual(self.state.state, self.state.AWAKENING)
        self.assertEqual(self.state.awakening_end_streak, 2)

        self.update(0.6, 0.05, "ABSENT")
        self.update(0.7, 0.05, "ABSENT")
        self.assertEqual(self.state.state, self.state.BATTLE)
        self.assertEqual(self.events, ["AWAKENING_END"])
