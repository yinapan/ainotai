from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath

_USERNAME = os.environ.get("USERNAME") or os.environ.get("USER") or ""
_SENSITIVE_PATTERNS = [
    (re.compile(r"[A-Za-z]:\\Users\\[^\\]+", re.IGNORECASE), "[REDACTED_PATH]"),
    (re.compile(r"/home/[^/]+", re.IGNORECASE), "[REDACTED_PATH]"),
    (re.compile(r"/Users/[^/]+", re.IGNORECASE), "[REDACTED_PATH]"),
    (re.compile(r"(?:password|passwd|secret|token|api_key|apikey)\s*[:=]\s*\S+", re.IGNORECASE), "[REDACTED_CREDENTIAL]"),
]

if _USERNAME:
    _SENSITIVE_PATTERNS.insert(0, (re.compile(re.escape(_USERNAME), re.IGNORECASE), "[REDACTED_USER]"))


def redact_path(path: str | Path) -> str:
    text = str(path)
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_log_line(line: str) -> str:
    for pattern, replacement in _SENSITIVE_PATTERNS:
        line = pattern.sub(replacement, line)
    return line
