from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from .format_detector import detect_format

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssetFile:
    path: Path
    relative_path: str
    extension: str
    size_bytes: int
    sha256: str
    asset_type: str
    detected_format: str | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _flatten_extensions(config: dict) -> dict[str, set[str]]:
    extensions = config.get("scan", {}).get("extensions", {})
    return {kind: {ext.lower() for ext in values} for kind, values in extensions.items()}


def _asset_type(extension: str, extension_map: dict[str, set[str]]) -> str:
    for kind, values in extension_map.items():
        if extension in values:
            return kind
    return "unknown"


def _is_excluded(relative_path: str, patterns: list[str]) -> bool:
    normalized = relative_path.replace("\\", "/")
    parts = set(normalized.split("/"))
    for pattern in patterns:
        if pattern in parts:
            return True
        if "*" in pattern or "?" in pattern:
            import fnmatch
            if fnmatch.fnmatch(normalized, pattern):
                return True
    return False


def scan_assets(root: str | Path, config: dict) -> list[AssetFile]:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise FileNotFoundError(f"Input directory not found: {root_path}")

    extension_map = _flatten_extensions(config)
    allowed = set().union(*extension_map.values()) if extension_map else set()
    max_bytes = int(config.get("scan", {}).get("max_file_size_mb", 500)) * 1024 * 1024
    excludes = list(config.get("scan", {}).get("exclude_patterns", []))
    assets: list[AssetFile] = []

    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink():
            logger.warning("Skipping symlink: %s", path)
            continue

        relative = path.relative_to(root_path).as_posix()
        if _is_excluded(relative, excludes):
            continue

        extension = path.suffix.lower()
        if extension not in allowed:
            continue

        size = path.stat().st_size
        if size > max_bytes:
            logger.warning("Skipping oversized file (%d bytes): %s", size, relative)
            continue
        if size == 0:
            logger.warning("Skipping empty file: %s", relative)
            continue

        detected = detect_format(path)
        assets.append(
            AssetFile(
                path=path,
                relative_path=relative,
                extension=extension,
                size_bytes=size,
                sha256=sha256_file(path),
                asset_type=_asset_type(extension, extension_map),
                detected_format=detected,
            )
        )

    logger.info("Scanned %d assets from %s", len(assets), root_path)
    return assets
