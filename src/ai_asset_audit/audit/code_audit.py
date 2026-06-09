from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


NETWORK_PATTERNS = [
    r"requests\.",  # audit: allow
    r"httpx\.",  # audit: allow
    r"aiohttp",  # audit: allow
    r"urllib",  # audit: allow
    r"socket",  # audit: allow
    r"websocket",  # audit: allow
    r"grpc",  # audit: allow
    r"boto3",  # audit: allow
    r"openai",  # audit: allow
    r"huggingface_hub",  # audit: allow
    r"snapshot_download",  # audit: allow
    r"curl",  # audit: allow
    r"wget",  # audit: allow
    r"Invoke-WebRequest",  # audit: allow
    r"Invoke-RestMethod",  # audit: allow
]

EXFIL_PATTERNS = [
    r"upload",  # audit: allow
    r"multipart",  # audit: allow
    r"form-data",  # audit: allow
    r"\.post\(",  # audit: allow
    r"\.put\(",  # audit: allow
    r"\bs3\b",  # audit: allow
    r"\boss\b",  # audit: allow
    r"\bcos\b",  # audit: allow
    r"\bftp\b",  # audit: allow
    r"\bsftp\b",  # audit: allow
    r"\bsmtp\b",  # audit: allow
    r"sendmail",  # audit: allow
]

LOG_LEAK_PATTERNS = [
    r"base64",  # audit: allow
    r"password",  # audit: allow
    r"secret",  # audit: allow
    r"token",  # audit: allow
    r"credential",  # audit: allow
]

ALLOWED_EXTENSIONS = {".py", ".ps1", ".sh", ".yaml", ".yml", ".toml", ".json", ".js", ".ts"}
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".tox"}


@dataclass(frozen=True)
class AuditFinding:
    path: str
    line: int
    category: str
    pattern: str
    text: str


def _build_patterns() -> list[tuple[str, str]]:
    patterns: list[tuple[str, str]] = []
    patterns.extend(("network", p) for p in NETWORK_PATTERNS)
    patterns.extend(("exfiltration", p) for p in EXFIL_PATTERNS)
    patterns.extend(("log_leak", p) for p in LOG_LEAK_PATTERNS)
    return patterns


def audit_code(root: str | Path) -> list[AuditFinding]:
    root_path = Path(root)
    findings: list[AuditFinding] = []
    patterns = _build_patterns()

    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "audit: allow" in line:
                continue
            for category, pattern in patterns:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    findings.append(
                        AuditFinding(
                            path=path.as_posix(),
                            line=line_number,
                            category=category,
                            pattern=pattern,
                            text=line.strip()[:240],
                        )
                    )
    return findings
