"""Backward-compatibility shim. Import from subpackages directly."""
from src.ai_asset_audit.audit.code_audit import audit_code, AuditFinding

__all__ = ["audit_code", "AuditFinding"]
