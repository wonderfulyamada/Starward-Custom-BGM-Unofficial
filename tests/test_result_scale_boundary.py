import unittest

import numpy as np

from detector import DetectionResult, MaskedTemplate, ScreenDetector


class ResultScaleBoundaryTests(unittest.TestCase):
    def setUp(self):
        detector = ScreenDetector.__new__(ScreenDetector)
        detector.cfg = {
            "reference_width": 1280,
            "reference_height": 720,
            "template_alpha_threshold": 16,
            "result_color_saturation_min": 70,
            "result_color_min_pixels": 500,
            "victory_hue_ranges": [[5, 35]],
            "victory_color_ratio_min": 0.45,
            "result_position": [435, 142],
            "result_position_tolerance_x": 35,
            "result_position_tolerance_y": 30,
            "result_scale_min": 0.7,
            "result_scale_max": 0.8,
            "result_template_score_min": 0.85,
        }
        self.detector = detector
        self.template = MaskedTemplate(
            image=np.zeros((100, 100), dtype=np.uint8),
            mask=np.full((100, 100), 255, dtype=np.uint8),
        )

    def test_1920x1080_reference_scale_at_minimum_is_accepted(self):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frame[213:318, 652:757] = (0, 170, 255)

        frame_scale = self.detector._frame_scale(frame)
        raw_scale = 0.7 * frame_scale
        result = DetectionResult(1.0, (652, 213), raw_scale)
        checked = self.detector._with_color_check(frame, result, self.template, "victory", 0.38)

        self.assertAlmostEqual(frame_scale, 1.5)
        self.assertAlmostEqual(raw_scale, 1.05)
        self.assertLess(raw_scale / frame_scale, 0.7)
        self.assertTrue(checked.candidate)

    def test_reference_scale_at_maximum_is_accepted(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[142:222, 435:515] = (0, 170, 255)
        result = DetectionResult(1.0, (435, 142), 0.8)

        checked = self.detector._with_color_check(frame, result, self.template, "victory", 0.38)

        self.assertTrue(checked.candidate)

    def test_result_score_081_is_accepted_at_the_080_threshold(self):
        self.detector.cfg["result_template_score_min"] = 0.8
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame[142:222, 435:515] = (0, 170, 255)
        result = DetectionResult(0.81, (435, 142), 0.8)

        checked = self.detector._with_color_check(frame, result, self.template, "victory", 0.38)

        self.assertTrue(checked.candidate)


if __name__ == "__main__":
    unittest.main()
