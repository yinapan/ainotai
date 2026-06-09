import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.ai_asset_audit.pipeline.pipeline import run_pipeline


def _create_test_png(path: Path, size=64, color=(255, 255, 255), extra_bytes: bytes = b""):
    """Create a PNG file using OpenCV, optionally appending raw metadata bytes."""
    img = np.zeros((size, size, 3), dtype=np.uint8)
    img[:] = color[::-1]  # BGR
    cv2.imwrite(str(path), img)
    if extra_bytes:
        with path.open("ab") as handle:
            handle.write(extra_bytes)


class PipelineTests(unittest.TestCase):
    def test_run_pipeline_detects_ai_metadata_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "sd.png"
            _create_test_png(
                image, 64, (255, 255, 255),
                extra_bytes=b"Stable Diffusion Steps: 20, Sampler: Euler, CFG scale: 7, Seed: 123",
            )

            signatures = root / "signatures.yaml"
            signatures.write_text(
                """
ai_software:
  - stable diffusion
ai_parameter_patterns:
  - "steps:\\\\s*\\\\d+"
  - "seed:\\\\s*\\\\d+"
""",
                encoding="utf-8",
            )
            config = {
                "scan": {
                    "extensions": {"image": [".png"]},
                    "max_file_size_mb": 10,
                    "exclude_patterns": [],
                },
                "metadata": {"signatures_file": str(signatures)},
                "forensics": {"enabled": False},
                "models": {"enabled": False},
            }

            results = run_pipeline(root, config)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].final_label, "Confirmed AI")
            self.assertTrue(results[0].review_required)

    def test_run_pipeline_clean_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "clean.png"
            _create_test_png(image, 64, (0, 0, 255))

            signatures = root / "signatures.yaml"
            signatures.write_text(
                """
ai_software:
  - stable diffusion
ai_parameter_patterns:
  - "steps:\\\\s*\\\\d+"
""",
                encoding="utf-8",
            )
            config = {
                "scan": {
                    "extensions": {"image": [".png"]},
                    "max_file_size_mb": 10,
                    "exclude_patterns": [],
                },
                "metadata": {"signatures_file": str(signatures)},
                "forensics": {"enabled": False},
                "models": {"enabled": False},
            }

            results = run_pipeline(root, config)

            self.assertEqual(len(results), 1)
            self.assertIn(results[0].final_label, {"Low AI evidence", "Likely Human"})
            self.assertFalse(results[0].review_required)

    def test_run_pipeline_with_forensics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "test.png"
            _create_test_png(image, 128, (100, 150, 200))

            signatures = root / "signatures.yaml"
            signatures.write_text("ai_software: []\nai_parameter_patterns: []\n", encoding="utf-8")
            config = {
                "scan": {
                    "extensions": {"image": [".png"]},
                    "max_file_size_mb": 10,
                    "exclude_patterns": [],
                },
                "metadata": {"signatures_file": str(signatures)},
                "forensics": {"enabled": True},
                "models": {"enabled": False},
            }

            results = run_pipeline(root, config)
            self.assertEqual(len(results), 1)
            self.assertIsNotNone(results[0].forensics)
            self.assertIn("combined_score", results[0].forensics)


if __name__ == "__main__":
    unittest.main()
