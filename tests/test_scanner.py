import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.ai_asset_audit.scanner.file_scanner import scan_assets, sha256_file
from src.ai_asset_audit.scanner.format_detector import detect_format


def _create_test_png(path: Path, size=4, color=(255, 0, 0)):
    img = np.zeros((size, size, 3), dtype=np.uint8)
    img[:] = color[::-1]  # BGR
    cv2.imwrite(str(path), img)


class ScannerTests(unittest.TestCase):
    def test_scan_assets_finds_png(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            img = root / "test.png"
            _create_test_png(img)

            config = {
                "scan": {
                    "extensions": {"image": [".png"]},
                    "max_file_size_mb": 10,
                    "exclude_patterns": [],
                },
            }
            assets = scan_assets(root, config)
            self.assertEqual(len(assets), 1)
            self.assertEqual(assets[0].extension, ".png")
            self.assertEqual(assets[0].asset_type, "image")

    def test_scan_assets_skips_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            img = root / "real.png"
            _create_test_png(img)
            link = root / "link.png"
            try:
                link.symlink_to(img)
            except OSError:
                self.skipTest("Symlinks not supported")

            config = {
                "scan": {
                    "extensions": {"image": [".png"]},
                    "max_file_size_mb": 10,
                    "exclude_patterns": [],
                },
            }
            assets = scan_assets(root, config)
            paths = [a.relative_path for a in assets]
            self.assertIn("real.png", paths)
            self.assertNotIn("link.png", paths)

    def test_detect_format_png(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            img = root / "test.png"
            _create_test_png(img)
            detected = detect_format(img)
            self.assertEqual(detected, "png")

    def test_detect_format_jpeg(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            img_path = root / "test.jpg"
            img = np.zeros((4, 4, 3), dtype=np.uint8)
            img[:] = (0, 0, 255)[::-1]
            cv2.imwrite(str(img_path), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            detected = detect_format(img_path)
            self.assertEqual(detected, "jpeg")

    def test_sha256_consistent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            img = root / "hash.png"
            _create_test_png(img)
            h1 = sha256_file(img)
            h2 = sha256_file(img)
            self.assertEqual(h1, h2)
            self.assertEqual(len(h1), 64)

    def test_detect_format_fbx_ascii(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fbx = root / "test.fbx"
            fbx.write_text(
                """; FBX 7.5.0 project file
; Created by SomeTool

FBXHeaderExtension:  {
    FBXHeaderVersion: 1003
    FBXVersion: 7500
}

Objects:  {
    Model: 1, "Model::cube", "Mesh" {
        Version: 232
    }
}

Connections:  {
}

Takes:  {
    Current: ""
}
""",
                encoding="ascii",
            )
            detected = detect_format(fbx)
            self.assertEqual(detected, "fbx_ascii")

    def test_detect_format_obj(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            obj = root / "test.obj"
            obj.write_text(
                """# Test OBJ
v 0.0 0.0 0.0
v 1.0 0.0 0.0
v 0.0 1.0 0.0
f 1 2 3
""",
                encoding="ascii",
            )
            detected = detect_format(obj)
            self.assertEqual(detected, "obj")


if __name__ == "__main__":
    unittest.main()
