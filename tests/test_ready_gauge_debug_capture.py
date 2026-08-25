import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import detector
from detector import ScreenDetector


class ReadyGaugeDebugCaptureTests(unittest.TestCase):
    def test_ready_capture_logs_roi_measurement_and_respects_limit(self):
        instance = ScreenDetector.__new__(ScreenDetector)
        instance.debug = True
        instance.cfg = {"burst_gauge_value_min": 180}
        instance._debug_ready_episode = 3
        instance._debug_ready_missing_samples = 0
        instance._debug_ready_missing_limit = 2
        instance._debug_ready_gauge_samples = 0
        instance._debug_ready_gauge_limit = 1

        with tempfile.TemporaryDirectory() as temp, \
                patch.object(detector, "ROOT", Path(temp)), \
                patch("builtins.print") as printed, \
                patch("detector.cv2.imwrite", return_value=True) as saved:
            instance._debug_ready_gauge(
                np.zeros((8, 8, 3), dtype=np.uint8), (10, 20, 18, 28),
                False, None, 0, 0, "geometry_unavailable",
            )
            instance._debug_ready_gauge(
                np.zeros((8, 8, 3), dtype=np.uint8), (10, 20, 18, 28),
                True, 0.708, 51, 118, "normal",
            )
            instance._debug_ready_gauge(
                np.zeros((8, 8, 3), dtype=np.uint8), (10, 20, 18, 28),
                True, 0.722, 52, 120, "normal",
            )

        messages = [call.args[0] for call in printed.call_args_list]
        self.assertTrue(any("episode=3 kind=missing sample=1/2" in message for message in messages))
        self.assertTrue(any("episode=3 kind=gauge sample=1/1" in message for message in messages))
        self.assertTrue(any("hud_visible=True gauge=0.708 lit_sectors=51/72 lit_pixels=118" in message for message in messages))
        self.assertEqual(instance._debug_ready_missing_samples, 1)
        self.assertEqual(instance._debug_ready_gauge_samples, 1)
        self.assertEqual(saved.call_count, 2)
