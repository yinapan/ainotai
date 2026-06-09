"""Backward-compatibility shim. Import from subpackages directly."""
from src.ai_asset_audit.report.json_report import write_json_report
from src.ai_asset_audit.report.csv_report import write_csv_report
from src.ai_asset_audit.report.markdown_report import write_markdown_report
from src.ai_asset_audit.report.html_report import write_html_report
from src.ai_asset_audit.pipeline.pipeline import AssetResult
from src.ai_asset_audit.pipeline.scorer import label_from_score


def write_reports(results, output_dir):
    write_json_report(results, output_dir)
    write_csv_report(results, output_dir)
    write_markdown_report(results, output_dir)


__all__ = [
    "AssetResult",
    "label_from_score",
    "write_reports",
    "write_json_report",
    "write_csv_report",
    "write_markdown_report",
    "write_html_report",
]
