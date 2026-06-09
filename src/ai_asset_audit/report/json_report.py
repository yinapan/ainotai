from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ..pipeline.pipeline import AssetResult


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy scalars and arrays."""

    def default(self, o):
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


def _sanitize(obj):
    """Recursively convert numpy types in nested dicts/lists."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def write_json_report(results: list[AssetResult], output_dir: str | Path) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "report.json"

    data = []
    for r in results:
        entry = _sanitize(asdict(r))
        data.append(entry)

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
