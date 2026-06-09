"""Backward-compatibility shim. Import from subpackages directly."""
from src.ai_asset_audit.scanner.file_scanner import AssetFile, scan_assets, sha256_file
from src.ai_asset_audit.scanner.format_detector import detect_format
from src.ai_asset_audit.scanner.fbx_scanner import scan_fbx, FbxAssetResult, FbxMeshInfo
from src.ai_asset_audit.metadata.signatures import load_signatures, scan_text_for_ai_signals, MetadataFinding

__all__ = [
    "AssetFile", "scan_assets", "sha256_file", "detect_format",
    "scan_fbx", "FbxAssetResult", "FbxMeshInfo",
    "load_signatures", "scan_text_for_ai_signals", "MetadataFinding",
]
