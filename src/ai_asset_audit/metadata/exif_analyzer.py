from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ExifResult:
    success: bool = False
    software: str | None = None
    creator_tool: str | None = None
    fields: dict[str, str] = field(default_factory=dict)
    error: str | None = None


def _find_exiftool(config_path: str | None = None) -> str | None:
    if config_path and Path(config_path).is_file():
        return config_path
    return shutil.which("exiftool")


def extract_exif(
    path: Path,
    exiftool_path: str | None = None,
    timeout: float = 30.0,
) -> ExifResult:
    exiftool = _find_exiftool(exiftool_path)
    if not exiftool:
        return ExifResult(error="exiftool not found")

    try:
        result = subprocess.run(
            [exiftool, "-json", "-n", "-G", str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ExifResult(error="exiftool timeout")
    except (FileNotFoundError, OSError):
        return ExifResult(error="exiftool binary not executable")

    if result.returncode != 0:
        return ExifResult(error=f"exiftool exit code {result.returncode}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return ExifResult(error="exiftool output is not valid JSON")

    if not data:
        return ExifResult(success=True)

    entry = data[0] if isinstance(data, list) else data
    flat: dict[str, str] = {}
    for key, value in entry.items():
        flat[key] = str(value)

    software = flat.get("EXIF:Software") or flat.get("XMP:CreatorTool")
    creator_tool = flat.get("XMP:CreatorTool")

    return ExifResult(
        success=True,
        software=software,
        creator_tool=creator_tool,
        fields=flat,
    )
