from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DependencyFinding:
    tool: str
    package: str
    severity: str
    description: str


@dataclass
class DependencyAuditResult:
    findings: list[DependencyFinding] = field(default_factory=list)
    tools_run: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _run_pip_audit(venv_path: str | None = None) -> list[DependencyFinding]:
    findings: list[DependencyFinding] = []
    cmd = ["pip-audit", "--format", "json"]
    if venv_path:
        cmd.extend(["--path", venv_path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.stdout:
            import json
            data = json.loads(result.stdout)
            for dep in data.get("dependencies", []):
                for vuln in dep.get("vulns", []):
                    findings.append(DependencyFinding(
                        tool="pip-audit",
                        package=dep.get("name", "unknown"),
                        severity=vuln.get("fix_versions", ["unknown"])[0] if vuln.get("fix_versions") else "unknown",
                        description=vuln.get("id", ""),
                    ))
    except FileNotFoundError:
        logger.debug("pip-audit not available")
    except Exception as exc:
        logger.warning("pip-audit failed: %s", exc)
    return findings


def _run_bandit(root: Path) -> list[DependencyFinding]:
    findings: list[DependencyFinding] = []
    try:
        result = subprocess.run(
            ["bandit", "-r", str(root), "-f", "json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.stdout:
            import json
            data = json.loads(result.stdout)
            for issue in data.get("results", []):
                findings.append(DependencyFinding(
                    tool="bandit",
                    package=issue.get("filename", ""),
                    severity=issue.get("issue_severity", "unknown"),
                    description=f"{issue.get('issue_text', '')} [{issue.get('test_id', '')}]",
                ))
    except FileNotFoundError:
        logger.debug("bandit not available")
    except Exception as exc:
        logger.warning("bandit failed: %s", exc)
    return findings


def audit_dependencies(root: str | Path, venv_path: str | None = None) -> DependencyAuditResult:
    root_path = Path(root)
    result = DependencyAuditResult()

    pip_findings = _run_pip_audit(venv_path)
    if pip_findings:
        result.findings.extend(pip_findings)
        result.tools_run.append("pip-audit")

    bandit_findings = _run_bandit(root_path)
    if bandit_findings:
        result.findings.extend(bandit_findings)
        result.tools_run.append("bandit")

    return result
