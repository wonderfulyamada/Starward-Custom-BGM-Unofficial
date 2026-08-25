import unittest

import cv2
import numpy as np

from detector import BurstGeometry, ScreenDetector


class AwakeningHudObservabilityTests(unittest.TestCase):
    def make_detector(self):
        detector = ScreenDetector.__new__(ScreenDetector)
        detector.cfg = {
            "burst_normal_tick_edge_min": 0.55,
            "burst_hud_inner_icon_edge_min": 0.2,
            "burst_normal_outer_edge_min": 0.8,
            "burst_gauge_value_min": 180,
            "burst_emblem_score_min": 0.8,
            "awakening_glow_present_score_min": 0.12,
            "awakening_glow_absent_score_max": 0.05,
        }
        detector.debug = False
        detector._burst_geometry = BurstGeometry((100, 100), 40.0)
        detector._awakening_emblems = []
        return detector

    def frame(self, glow=False):
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        # Stable local icon feature: inner tick ring, not the outer effect.
        cv2.circle(frame, (100, 100), 28, (255, 255, 255), 2)
        cv2.circle(frame, (100, 100), 15, (255, 255, 255), 2)
        cv2.circle(frame, (100, 100), 42, (150, 150, 150), 2)
        if glow:
            cv2.circle(frame, (100, 100), 45, (0, 255, 0), 6)
        return frame

    def test_visible_icon_without_glow_is_observable_and_absent(self):
        metrics = self.make_detector().burst_metrics(self.frame(), mode="awakening")
        self.assertTrue(metrics.hud_observable)
        self.assertEqual(metrics.glow_classification, "ABSENT")

    def test_visible_icon_with_glow_is_observable_and_present(self):
        metrics = self.make_detector().burst_metrics(self.frame(glow=True), mode="awakening")
        self.assertTrue(metrics.hud_observable)
        self.assertEqual(metrics.glow_classification, "PRESENT")

    def test_missing_icon_is_unknown(self):
        metrics = self.make_detector().burst_metrics(np.zeros((200, 200, 3), dtype=np.uint8), mode="awakening")
        self.assertFalse(metrics.hud_observable)
        self.assertEqual(metrics.glow_classification, "UNKNOWN")

    def test_scene_edge_resembling_only_the_tick_ring_is_unknown(self):
        frame = np.zeros((200, 200, 3), dtype=np.uint8)
        cv2.circle(frame, (100, 100), 28, (255, 255, 255), 2)
        metrics = self.make_detector().burst_metrics(frame, mode="awakening")
        self.assertFalse(metrics.hud_observable)
        self.assertIsNone(metrics.gauge_level)
        self.assertEqual(metrics.glow_classification, "UNKNOWN")
