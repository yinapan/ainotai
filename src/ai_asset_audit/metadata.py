"""Backward-compatibility shim. Import from subpackages directly."""
from src.ai_asset_audit.metadata.signatures import (
    MetadataFinding,
    load_signatures,
    scan_text_for_ai_signals,
)

scan_file_metadata = None  # removed, use pipeline.pipeline

__all__ = ["MetadataFinding", "load_signatures", "scan_text_for_ai_signals"]
