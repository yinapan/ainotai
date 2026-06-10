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

    rows_parts = []
    for i, result in enumerate(results):
        result._row_idx = i
        rows_parts.append(_result_row(result))
    rows = "".join(rows_parts)
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
.filters {{ background: #fff; border: 1px solid #dee2e6; border-radius: 8px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; }}
.filters label {{ font-size: 0.85rem; font-weight: 600; color: #495057; }}
.filters select, .filters input {{ padding: 0.4rem 0.8rem; border: 1px solid #ced4da; border-radius: 4px; font-size: 0.85rem; }}
.filters input[type="text"] {{ width: 200px; }}
.filter-group {{ display: flex; align-items: center; gap: 0.4rem; }}
.count-badge {{ background: #e9ecef; padding: 0.25rem 0.6rem; border-radius: 12px; font-size: 0.8rem; color: #495057; margin-left: 0.5rem; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
th, td {{ padding: 0.75rem; border: 1px solid #dee2e6; text-align: left; font-size: 0.9rem; vertical-align: top; }}
th {{ background: #343a40; color: #fff; cursor: pointer; user-select: none; position: relative; white-space: nowrap; }}
th:hover {{ background: #495057; }}
th .sort-arrow {{ margin-left: 4px; font-size: 0.7rem; opacity: 0.5; }}
th.sort-asc .sort-arrow {{ opacity: 1; }}
th.sort-desc .sort-arrow {{ opacity: 1; }}
tr:nth-child(even) {{ background: #f8f9fa; }}
tr.hidden {{ display: none; }}
.evidence {{ font-size: 0.8rem; color: #495057; max-width: 400px; }}
.models {{ font-size: 0.8rem; color: #495057; max-width: 320px; }}
ul {{ list-style: none; padding: 0; }}
li {{ margin: 0.3rem 0; }}
.tag {{ display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 0.75rem; margin: 1px; }}
.tag-tiling {{ background: #fff3cd; color: #856404; }}
.tag-pixel {{ background: #f8d7da; color: #721c24; }}
.tag-model {{ background: #d4edda; color: #155724; }}
.tag-none {{ background: #e2e3e5; color: #383d41; }}
.tag-strong {{ background: #f8d7da; color: #721c24; }}
.tag-weak {{ background: #fff3cd; color: #856404; }}
.tag-attr {{ background: #e2e3e5; color: #495057; }}
.ev-tier {{ margin-bottom: 3px; }}
</style>
</head>
<body>
<h1>AI 美术资源离线检测报告</h1>
<div class="meta">
<p>生成时间：{timestamp} | 扫描文件数：{total}</p>
</div>
<h2>概览</h2>
<ul>{summary_items}</ul>

<details class="legend" style="margin-bottom:1.5rem;">
<summary style="cursor:pointer;font-weight:600;font-size:0.95rem;color:#343a40;">图例说明 (点击展开)</summary>
<div style="display:flex;gap:2rem;flex-wrap:wrap;margin-top:0.8rem;">
<div>
<h4 style="margin:0 0 0.4rem;font-size:0.85rem;color:#495057;">结论标签</h4>
<table style="font-size:0.8rem;border-collapse:collapse;box-shadow:none;">
<tr><td style="padding:2px 8px;color:#dc3545;font-weight:bold;">Confirmed AI</td><td style="padding:2px 8px;">确认 AI 生成 — 元数据直接命中或多模型一致高分</td></tr>
<tr><td style="padding:2px 8px;color:#fd7e14;font-weight:bold;">Likely AI</td><td style="padding:2px 8px;">很可能 AI — 多个信号指向 AI，缺少元数据铁证</td></tr>
<tr><td style="padding:2px 8px;color:#ffc107;font-weight:bold;">Suspicious</td><td style="padding:2px 8px;">可疑 — 部分信号异常，建议人工复核</td></tr>
<tr><td style="padding:2px 8px;color:#28a745;font-weight:bold;">Likely Human</td><td style="padding:2px 8px;">很可能人工 — 少量弱信号，不构成威胁</td></tr>
<tr><td style="padding:2px 8px;color:#6c757d;font-weight:bold;">Low AI evidence</td><td style="padding:2px 8px;">AI 证据极少 — 基本无 AI 痕迹</td></tr>
<tr><td style="padding:2px 8px;color:#adb5bd;font-weight:bold;">Inconclusive</td><td style="padding:2px 8px;">无法判定 — 文件无法打开或格式不支持</td></tr>
</table>
</div>
<div>
<h4 style="margin:0 0 0.4rem;font-size:0.85rem;color:#495057;">证据分级</h4>
<table style="font-size:0.8rem;border-collapse:collapse;box-shadow:none;">
<tr><td style="padding:2px 8px;"><span class="tag tag-strong">强证据</span></td><td style="padding:2px 8px;">可定论的决定性证据 (AI 元数据、C2PA 标记、模型集成高置信)</td></tr>
<tr><td style="padding:2px 8px;"><span class="tag tag-weak">弱证据</span></td><td style="padding:2px 8px;">辅助参考信号 (像素取证异常、模型意见分歧)</td></tr>
<tr><td style="padding:2px 8px;"><span class="tag tag-attr">属性</span></td><td style="padding:2px 8px;">资产上下文信息，不参与评分</td></tr>
</table>
<h4 style="margin:0.6rem 0 0.4rem;font-size:0.85rem;color:#495057;">常见属性标签</h4>
<table style="font-size:0.8rem;border-collapse:collapse;box-shadow:none;">
<tr><td style="padding:2px 8px;font-family:monospace;">Texture role: albedo</td><td style="padding:2px 8px;">漫反射/基础色贴图，材质中最重要的通道</td></tr>
<tr><td style="padding:2px 8px;font-family:monospace;">Texture role: normal</td><td style="padding:2px 8px;">法线贴图，用专属分析替代通用模型</td></tr>
<tr><td style="padding:2px 8px;font-family:monospace;">Texture role: packed</td><td style="padding:2px 8px;">通道打包图 (MADS/ORM/RMA 等)</td></tr>
<tr><td style="padding:2px 8px;font-family:monospace;">Tiling pattern detected</td><td style="padding:2px 8px;">检测到平铺重复纹理，游戏贴图常见特征，仅作参考</td></tr>
<tr><td style="padding:2px 8px;font-family:monospace;">Auxiliary texture: AI scoring deferred</td><td style="padding:2px 8px;">辅助贴图不直接用模型评分，延迟到材质组复核</td></tr>
<tr><td style="padding:2px 8px;font-family:monospace;">Albedo in same material group flagged</td><td style="padding:2px 8px;">同材质组的 albedo 已标记风险，该辅助贴图需复核</td></tr>
</table>
</div>
</div>
</details>

<div class="filters">
  <div class="filter-group">
    <label>结论:</label>
    <select id="filter-label">
      <option value="">全部</option>
      <option value="Confirmed AI">Confirmed AI</option>
      <option value="Likely AI">Likely AI</option>
      <option value="Suspicious">Suspicious</option>
      <option value="Likely Human">Likely Human</option>
      <option value="Low AI evidence">Low AI evidence</option>
      <option value="Inconclusive">Inconclusive</option>
    </select>
  </div>
  <div class="filter-group">
    <label>证据:</label>
    <select id="filter-evidence">
      <option value="">全部</option>
      <option value="Tiling pattern detected">Tiling pattern</option>
      <option value="Pixel forensics abnormal">Pixel forensics</option>
      <option value="Model ensemble high confidence">Model high confidence</option>
    </select>
  </div>
  <div class="filter-group">
    <label>搜索:</label>
    <input type="text" id="filter-search" placeholder="文件名...">
  </div>
  <div class="filter-group">
    <label>置信度 &ge;:</label>
    <input type="number" id="filter-confidence" min="0" max="1" step="0.05" value="0" style="width:80px;">
  </div>
  <span class="count-badge" id="visible-count">{total} / {total}</span>
</div>

<table id="report-table">
<thead><tr>
<th data-col="0">文件路径 <span class="sort-arrow">&#9650;&#9660;</span></th>
<th data-col="1">类型 <span class="sort-arrow">&#9650;&#9660;</span></th>
<th data-col="2">结论 <span class="sort-arrow">&#9650;&#9660;</span></th>
<th data-col="3" data-type="number">置信度 <span class="sort-arrow">&#9650;&#9660;</span></th>
<th data-col="4">尺寸 <span class="sort-arrow">&#9650;&#9660;</span></th>
<th data-col="5" data-type="number">Tiling <span class="sort-arrow">&#9650;&#9660;</span></th>
<th data-col="6">模型分数 <span class="sort-arrow">&#9650;&#9660;</span></th>
<th data-col="7">证据 <span class="sort-arrow">&#9650;&#9660;</span></th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>

<footer style="margin-top:2rem;color:#6c757d;font-size:0.8rem;">
<p>本报告由离线检测流水线自动生成，仅限内网查看。</p>
</footer>

<script>
(function() {{
  const table = document.getElementById('report-table');
  const tbody = table.querySelector('tbody');
  const headers = table.querySelectorAll('th');
  const filterLabel = document.getElementById('filter-label');
  const filterEvidence = document.getElementById('filter-evidence');
  const filterSearch = document.getElementById('filter-search');
  const filterConfidence = document.getElementById('filter-confidence');
  const countBadge = document.getElementById('visible-count');
  const totalCount = {total};

  let sortCol = -1;
  let sortDir = 0; // 0=none, 1=asc, -1=desc

  function getCellValue(row, col) {{
    const cell = row.cells[col];
    if (!cell) return '';
    return cell.getAttribute('data-value') || cell.textContent.trim();
  }}

  function sortTable(col) {{
    const header = headers[col];
    const isNumber = header.getAttribute('data-type') === 'number';

    if (sortCol === col) {{
      sortDir = sortDir === 1 ? -1 : sortDir === -1 ? 0 : 1;
    }} else {{
      sortDir = 1;
      sortCol = col;
    }}

    headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
    if (sortDir === 1) header.classList.add('sort-asc');
    if (sortDir === -1) header.classList.add('sort-desc');

    const rows = Array.from(tbody.querySelectorAll('tr'));

    if (sortDir === 0) {{
      rows.sort((a, b) => parseInt(a.dataset.idx) - parseInt(b.dataset.idx));
    }} else {{
      rows.sort((a, b) => {{
        let va = getCellValue(a, col);
        let vb = getCellValue(b, col);
        if (isNumber) {{
          va = parseFloat(va) || 0;
          vb = parseFloat(vb) || 0;
          return sortDir * (va - vb);
        }}
        return sortDir * va.localeCompare(vb, 'zh');
      }});
    }}

    rows.forEach(r => tbody.appendChild(r));
  }}

  headers.forEach((h, i) => {{
    h.addEventListener('click', () => sortTable(i));
  }});

  function applyFilters() {{
    const labelVal = filterLabel.value;
    const evidenceVal = filterEvidence.value;
    const searchVal = filterSearch.value.toLowerCase();
    const confVal = parseFloat(filterConfidence.value) || 0;

    const rows = tbody.querySelectorAll('tr');
    let visible = 0;

    rows.forEach(row => {{
      const label = getCellValue(row, 2);
      const evidence = getCellValue(row, 7);
      const filename = getCellValue(row, 0).toLowerCase();
      const conf = parseFloat(getCellValue(row, 3)) || 0;

      let show = true;
      if (labelVal && label !== labelVal) show = false;
      if (evidenceVal && !evidence.includes(evidenceVal)) show = false;
      if (searchVal && !filename.includes(searchVal)) show = false;
      if (conf < confVal) show = false;

      row.classList.toggle('hidden', !show);
      if (show) visible++;
    }});

    countBadge.textContent = visible + ' / ' + totalCount;
  }}

  filterLabel.addEventListener('change', applyFilters);
  filterEvidence.addEventListener('change', applyFilters);
  filterSearch.addEventListener('input', applyFilters);
  filterConfidence.addEventListener('input', applyFilters);
}})();
</script>
</body>
</html>"""

    path.write_text(html, encoding="utf-8-sig")
    return path


def _result_row(result: AssetResult) -> str:
    color = _LABEL_COLORS.get(result.final_label, "#000")
    tiered_html = _format_tiered_evidence(result)
    evidence_raw = "; ".join(result.evidence)
    model_html = _format_models(result.models)
    tiling_score = result.forensics.get("tiling_score", 0) if result.forensics else 0
    idx = getattr(result, '_row_idx', 0)
    return f"""<tr data-idx="{idx}">
<td>{escape(result.relative_path)}</td>
<td>{escape(result.asset_type)}</td>
<td style="color:{color};font-weight:bold" data-value="{escape(result.final_label)}">{escape(result.final_label)}</td>
<td data-value="{result.confidence:.4f}">{result.confidence:.2f}</td>
<td>{result.dimensions or '-'}</td>
<td data-value="{tiling_score:.4f}">{tiling_score:.4f}</td>
<td class="models">{model_html}</td>
<td class="evidence" data-value="{escape(evidence_raw)}">{tiered_html}</td>
</tr>"""


def _format_evidence_tags(evidence: list[str]) -> str:
    tags = []
    for e in evidence:
        if "Tiling" in e:
            cls = "tag-tiling"
        elif "Pixel" in e:
            cls = "tag-pixel"
        elif "Model" in e:
            cls = "tag-model"
        else:
            cls = "tag-none"
        tags.append(f'<span class="tag {cls}">{escape(e)}</span>')
    return " ".join(tags)


def _format_tiered_evidence(result: AssetResult) -> str:
    parts = []
    if result.strong_evidence:
        items = " ".join(f'<span class="tag tag-strong">{escape(e)}</span>' for e in result.strong_evidence)
        parts.append(f'<div class="ev-tier"><b>强证据:</b> {items}</div>')
    if result.weak_evidence:
        items = " ".join(f'<span class="tag tag-weak">{escape(e)}</span>' for e in result.weak_evidence)
        parts.append(f'<div class="ev-tier"><b>弱证据:</b> {items}</div>')
    if result.asset_attributes:
        items = " ".join(f'<span class="tag tag-attr">{escape(e)}</span>' for e in result.asset_attributes)
        parts.append(f'<div class="ev-tier"><b>属性:</b> {items}</div>')
    if not parts:
        parts.append('<span class="tag tag-none">No evidence</span>')
    return "".join(parts)


def _format_models(models: dict) -> str:
    if not models:
        return "-"

    participated = models.get("_participated", [])
    unavailable = models.get("_unavailable", [])
    consensus = models.get("_consensus", "")
    weighted = models.get("_weighted_score", 0)
    divergence = models.get("_divergence", 0)

    parts: list[str] = []
    if participated:
        parts.append("<b>参与:</b>")
        for name in participated:
            score = models.get(name)
            if isinstance(score, float):
                parts.append(f"&nbsp;&nbsp;{escape(name)}: {score:.4f}")
            else:
                parts.append(f"&nbsp;&nbsp;{escape(name)}")
    if unavailable:
        parts.append("<b>未参与:</b>")
        for name in unavailable:
            parts.append(f"&nbsp;&nbsp;{escape(name)}: 缺失")
    if consensus:
        parts.append(f"<b>综合:</b> 加权={weighted:.4f} | 共识={consensus} | 分歧={divergence:.4f}")

    return "<br>".join(parts) if parts else "-"
