import unittest

import cv2
import numpy as np

from src.ai_asset_audit.forensics.ela import compute_ela
from src.ai_asset_audit.forensics.frequency import compute_frequency_analysis
from src.ai_asset_audit.forensics.color_stats import compute_color_stats
from src.ai_asset_audit.forensics.noise import compute_noise_consistency


def _make_image(w=64, h=64, color=(255, 255, 255)):
    """Create a BGR numpy image matching cv2.imread output."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = color[::-1]  # RGB to BGR
    return img


class ElaTests(unittest.TestCase):
    def test_ela_returns_valid_result(self):
        img = _make_image(64, 64)
        result = compute_ela(img)
        self.assertIsNone(result.error)
        self.assertGreaterEqual(result.uniformity, 0.0)
        self.assertLessEqual(result.uniformity, 1.0)

    def test_ela_small_image(self):
        img = _make_image(4, 4, (255, 0, 0))
        result = compute_ela(img)
        self.assertIsNone(result.error)

    def test_ela_grayscale(self):
        img = np.ones((64, 64), dtype=np.uint8) * 128
        result = compute_ela(img)
        self.assertIsNone(result.error)


class FrequencyTests(unittest.TestCase):
    def test_frequency_returns_valid_result(self):
        img = _make_image(64, 64, (0, 0, 255))
        result = compute_frequency_analysis(img)
        self.assertIsNone(result.error)
        self.assertGreaterEqual(result.anomaly_score, 0.0)
        self.assertLessEqual(result.anomaly_score, 1.0)

    def test_frequency_too_small(self):
        img = _make_image(4, 4)
        result = compute_frequency_analysis(img)
        self.assertIsNotNone(result.error)

    def test_frequency_grayscale(self):
        img = np.ones((64, 64), dtype=np.uint8) * 128
        result = compute_frequency_analysis(img)
        self.assertIsNone(result.error)


class ColorStatsTests(unittest.TestCase):
    def test_color_stats_solid_image(self):
        img = _make_image(64, 64, (128, 128, 128))
        result = compute_color_stats(img)
        self.assertIsNone(result.error)
        self.assertGreater(result.smoothness, 0.9)

    def test_color_stats_grayscale(self):
        img = np.ones((64, 64), dtype=np.uint8) * 128
        result = compute_color_stats(img)
        self.assertIsNone(result.error)


class NoiseTests(unittest.TestCase):
    def test_noise_returns_valid_result(self):
        img = _make_image(128, 128)
        result = compute_noise_consistency(img)
        self.assertIsNone(result.error)
        self.assertGreaterEqual(result.consistency, 0.0)
        self.assertLessEqual(result.consistency, 1.0)

    def test_noise_too_small(self):
        img = _make_image(16, 16)
        result = compute_noise_consistency(img, block_size=64)
        self.assertIsNotNone(result.error)


if __name__ == "__main__":
    unittest.main()
