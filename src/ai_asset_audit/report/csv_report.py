from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..pipeline.pipeline import AssetResult

CSV_FIELDS = [
    "file_id",
    "relative_path",
    "asset_type",
    "size_bytes",
    "dimensions",
    "final_label",
    "confidence",
    "review_required",
    "evidence",
]


def write_csv_report(results: list[AssetResult], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "report.csv"

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            row = asdict(r)
            row["evidence"] = " | ".join(r.evidence)
            writer.writerow(row)

    return path
