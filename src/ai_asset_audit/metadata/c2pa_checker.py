from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class C2paResult:
    detected: bool = False
    manifests: list[dict] = field(default_factory=list)
    ai_related: bool = False
    signals: list[str] = field(default_factory=list)
    error: str | None = None


def _find_c2patool(config_path: str | None = None) -> str | None:
    if config_path and Path(config_path).is_file():
        return config_path
    return shutil.which("c2patool")


AI_ACTION_KEYWORDS = {
    "c2pa.ai_generated",
    "c2pa.ai_trained",
    "ai_generated",
    "ai_trained",
    "generativeAI",
}


def check_c2pa(
    path: Path,
    c2patool_path: str | None = None,
    timeout: float = 30.0,
) -> C2paResult:
    tool = _find_c2patool(c2patool_path)
    if not tool:
        return C2paResult(error="c2patool not found")

    try:
        result = subprocess.run(
            [tool, str(path), "--output", "-"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return C2paResult(error="c2patool timeout")
    except (FileNotFoundError, OSError):
        return C2paResult(error="c2patool binary not executable")

    if result.returncode != 0:
        if "no manifest" in result.stderr.lower() or "not found" in result.stderr.lower():
            return C2paResult(detected=False)
        return C2paResult(error=f"c2patool exit code {result.returncode}: {result.stderr[:200]}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return C2paResult(error="c2patool output is not valid JSON")

    manifests = data.get("manifests", {})
    manifest_list = list(manifests.values()) if isinstance(manifests, dict) else manifests
    signals: list[str] = []
    ai_related = False

    for manifest in manifest_list:
        assertions = manifest.get("assertions", [])
        for assertion in assertions:
            label = assertion.get("label", "")
            for keyword in AI_ACTION_KEYWORDS:
                if keyword in label:
                    ai_related = True
                    signals.append(f"C2PA AI assertion: {label}")

    return C2paResult(
        detected=True,
        manifests=manifest_list,
        ai_related=ai_related,
        signals=signals,
    )
