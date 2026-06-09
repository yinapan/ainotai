"""Backward-compatibility shim. Import from subpackages directly."""
from src.ai_asset_audit.pipeline.pipeline import run_pipeline

run_scan = run_pipeline

__all__ = ["run_pipeline", "run_scan"]
