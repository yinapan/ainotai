"""Backward-compatibility shim."""
from src.ai_asset_audit.pipeline.scorer import label_from_score  # noqa: F401

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data
