from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class MetadataFinding:
    score: float = 0.0
    signals: list[str] = field(default_factory=list)
    tool_detected: str | None = None
    raw_fields: dict[str, str] = field(default_factory=dict)


def load_signatures(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def scan_text_for_ai_signals(text: str, signatures: dict) -> MetadataFinding:
    haystack = text.lower()
    signals: list[str] = []
    tool_detected: str | None = None

    for signature in signatures.get("ai_software", []):
        if str(signature).lower() in haystack:
            tool_detected = str(signature)
            signals.append(f"AI software signature: {signature}")

    for pattern in signatures.get("ai_parameter_patterns", []):
        if re.search(pattern, text, flags=re.IGNORECASE):
            signals.append(f"AI parameter pattern: {pattern}")

    if tool_detected and signals:
        score = 1.0
    elif len(signals) >= 2:
        score = 0.8
    elif signals:
        score = 0.6
    else:
        score = 0.0

    return MetadataFinding(score=score, signals=signals, tool_detected=tool_detected)
