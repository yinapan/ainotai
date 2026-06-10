from pathlib import Path
import tempfile
import unittest

from src.ai_asset_audit.pipeline.pipeline import AssetResult
from src.ai_asset_audit.report.html_report import write_html_report


class ReportTests(unittest.TestCase):
    def test_html_report_uses_readable_chinese_and_model_scores(self):
        result = AssetResult(
            file_id="sha256:abc",
            relative_path="Road_01_D.png",
            asset_type="image",
            size_bytes=123,
            dimensions="64x64",
            models={"cnn_detection": 0.7, "dire": None},
            final_label="Suspicious",
            confidence=0.55,
            review_required=True,
            evidence=["Model ensemble high confidence"],
        )

        with tempfile.TemporaryDirectory() as directory:
            path = write_html_report([result], Path(directory))
            html = path.read_text(encoding="utf-8-sig")

        self.assertIn("AI 美术资源离线检测报告", html)
        self.assertIn("置信度", html)
        self.assertIn("模型分数", html)
        self.assertIn("cnn_detection: 0.7000", html)
        self.assertIn("dire: unavailable", html)


if __name__ == "__main__":
    unittest.main()
