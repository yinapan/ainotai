import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.ai_asset_audit.metadata.signatures import load_signatures, scan_text_for_ai_signals
from src.ai_asset_audit.metadata.png_chunks import parse_png_text_chunks
from src.ai_asset_audit.metadata.xmp_parser import extract_xmp


class SignaturesTests(unittest.TestCase):
    def test_scan_detects_stable_diffusion(self):
        sigs = {"ai_software": ["stable diffusion"], "ai_parameter_patterns": ["steps:\\s*\\d+"]}
        finding = scan_text_for_ai_signals("Made with Stable Diffusion, Steps: 20", sigs)
        self.assertTrue(finding.tool_detected)
        self.assertEqual(finding.score, 1.0)
        self.assertTrue(len(finding.signals) >= 2)

    def test_scan_no_signals_for_clean_text(self):
        sigs = {"ai_software": ["stable diffusion"], "ai_parameter_patterns": []}
        finding = scan_text_for_ai_signals("Photoshop CC 2023", sigs)
        self.assertEqual(finding.score, 0.0)
        self.assertEqual(len(finding.signals), 0)

    def test_load_signatures_from_file(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "sigs.yaml"
            p.write_text("ai_software:\n  - midjourney\nai_parameter_patterns: []\n", encoding="utf-8")
            sigs = load_signatures(p)
            self.assertIn("midjourney", sigs.get("ai_software", []))


class PngChunksTests(unittest.TestCase):
    def test_parse_non_png(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "test.txt"
            p.write_bytes(b"not a png")
            result = parse_png_text_chunks(p)
            self.assertFalse(result.is_png)

    def test_parse_png_with_text_chunk(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "test.png"
            img = np.zeros((4, 4, 3), dtype=np.uint8)
            img[:] = (255, 0, 0)[::-1]
            cv2.imwrite(str(p), img)
            result = parse_png_text_chunks(p)
            self.assertTrue(result.is_png)


class XmpTests(unittest.TestCase):
    def test_extract_xmp_not_found(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "test.png"
            p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            result = extract_xmp(p)
            self.assertFalse(result.found)


if __name__ == "__main__":
    unittest.main()
