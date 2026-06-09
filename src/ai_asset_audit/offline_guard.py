"""Backward-compatibility shim. Import from subpackages directly."""
from src.ai_asset_audit.pipeline.offline_guard import check_offline_status, OfflineStatus

__all__ = ["check_offline_status", "OfflineStatus"]
