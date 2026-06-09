from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..pipeline.pipeline import AssetResult


def write_markdown_report(results: list[AssetResult], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "report.md"

    lines = [
        "# AI 美术资源离线检测报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 扫描文件数：{len(results)}",
        "",
        "## 概览",
        "",
        "| 风险等级 | 数量 |",
        "|---------|------|",
    ]

    label_counts: dict[str, int] = {}
    for r in results:
        label_counts[r.final_label] = label_counts.get(r.final_label, 0) + 1
    for label in ["Confirmed AI", "Likely AI", "Suspicious", "Likely Human", "Low AI evidence", "Inconclusive"]:
        if label in label_counts:
            lines.append(f"| {label} | {label_counts[label]} |")

    lines.append("")
    lines.append("## 详细结果")
    lines.append("")

    for r in results:
        lines.append(f"### {r.relative_path}")
        lines.append("")
        lines.append(f"- **结论**：{r.final_label}")
        lines.append(f"- **置信度**：{r.confidence:.2f}")
        lines.append(f"- **SHA256**：`{r.file_id.replace('sha256:', '')}`")
        if r.dimensions:
            lines.append(f"- **尺寸**：{r.dimensions}")
        lines.append(f"- **大小**：{r.size_bytes:,} bytes")
        if r.evidence:
            lines.append("- **证据**：")
            for ev in r.evidence:
                lines.append(f"  - {ev}")
        if r.models:
            lines.append("- **模型分数**：")
            for name, score in r.models.items():
                lines.append(f"  - {name}: {score if score is not None else 'N/A'}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
