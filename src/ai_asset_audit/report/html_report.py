from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..pipeline.pipeline import AssetResult


_LABEL_COLORS = {
    "Confirmed AI": "#dc3545",
    "Likely AI": "#fd7e14",
    "Suspicious": "#ffc107",
    "Likely Human": "#28a745",
    "Low AI evidence": "#6c757d",
    "Inconclusive": "#adb5bd",
}


def write_html_report(results: list[AssetResult], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "report.html"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(results)

    label_counts: dict[str, int] = {}
    for result in results:
        label_counts[result.final_label] = label_counts.get(result.final_label, 0) + 1

    rows = "".join(_result_row(result) for result in results)
    summary_items = "".join(
        f'<li><span style="color:{_LABEL_COLORS.get(label, "#000")}">'
        f"{escape(label)}</span>: {count}</li>"
        for label, count in sorted(label_counts.items(), key=lambda item: -item[1])
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>AI 美术资源离线检测报告</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Microsoft YaHei", sans-serif; margin: 2rem; background: #f8f9fa; }}
h1 {{ color: #212529; }}
.meta {{ color: #6c757d; margin-bottom: 1.5rem; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th, td {{ padding: 0.75rem; border: 1px solid #dee2e6; text-align: left; font-size: 0.9rem; vertical-align: top; }}
th {{ background: #343a40; color: #fff; }}
tr:nth-child(even) {{ background: #f8f9fa; }}
.evidence {{ font-size: 0.8rem; color: #495057; max-width: 400px; }}
.models {{ font-size: 0.8rem; color: #495057; max-width: 320px; }}
ul {{ list-style: none; padding: 0; }}
li {{ margin: 0.3rem 0; }}
</style>
</head>
<body>
<h1>AI 美术资源离线检测报告</h1>
<div class="meta">
<p>生成时间：{timestamp} | 扫描文件数：{total}</p>
</div>
<h2>概览</h2>
<ul>{summary_items}</ul>
<h2>详细结果</h2>
<table>
<thead><tr><th>文件路径</th><th>类型</th><th>结论</th><th>置信度</th><th>尺寸</th><th>模型分数</th><th>证据</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<footer style="margin-top:2rem;color:#6c757d;font-size:0.8rem;">
<p>本报告由离线检测流水线自动生成，仅限内网查看。</p>
</footer>
</body>
</html>"""

    path.write_text(html, encoding="utf-8-sig")
    return path


def _result_row(result: AssetResult) -> str:
    color = _LABEL_COLORS.get(result.final_label, "#000")
    evidence_html = "<br>".join(escape(evidence) for evidence in result.evidence)
    model_html = _format_models(result.models)
    return f"""<tr>
<td>{escape(result.relative_path)}</td>
<td>{escape(result.asset_type)}</td>
<td style="color:{color};font-weight:bold">{escape(result.final_label)}</td>
<td>{result.confidence:.2f}</td>
<td>{result.dimensions or '-'}</td>
<td class="models">{model_html}</td>
<td class="evidence">{evidence_html}</td>
</tr>"""


def _format_models(models: dict) -> str:
    if not models:
        return "-"

    rows: list[str] = []
    for name, value in models.items():
        if value is None:
            display = "unavailable"
        elif isinstance(value, float):
            display = f"{value:.4f}"
        else:
            display = escape(str(value))
        rows.append(f"{escape(name)}: {display}")
    return "<br>".join(rows)
