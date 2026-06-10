from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AicheckResult:
    success: bool = False
    ai_marker: bool = False
    signals: list[str] = field(default_factory=list)
    raw_output: str | None = None
    error: str | None = None


def _find_aicheck(config_path: str | None = None) -> str | None:
    if config_path and Path(config_path).is_file():
        return config_path
    return shutil.which("aicheck")


def run_aicheck(
    path: Path,
    aicheck_path: str | None = None,
    timeout: float = 30.0,
) -> AicheckResult:
    tool = _find_aicheck(aicheck_path)
    if not tool:
        return AicheckResult(error="aicheck not found")

    try:
        result = subprocess.run(
            [tool, str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return AicheckResult(error="aicheck timeout")
    except (FileNotFoundError, OSError):
        return AicheckResult(error="aicheck binary not executable")

    output = result.stdout.strip()
    signals: list[str] = []
    ai_marker = False

    try:
        data = json.loads(output)
        if isinstance(data, dict):
            if data.get("ai_generated") or data.get("ai_marker"):
                ai_marker = True
                signals.append("aicheck: AI marker detected")
            if data.get("watermark"):
                signals.append(f"aicheck: watermark found ({data.get('watermark_type', 'unknown')})")
    except json.JSONDecodeError:
        lower_output = output.lower()
        if "ai" in lower_output and ("detected" in lower_output or "found" in lower_output or "true" in lower_output):
            ai_marker = True
            signals.append("aicheck: AI indicator in text output")

    return AicheckResult(
        success=result.returncode == 0,
        ai_marker=ai_marker,
        signals=signals,
        raw_output=output[:2000] if output else None,
    )
