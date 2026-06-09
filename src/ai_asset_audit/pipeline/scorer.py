from __future__ import annotations

from dataclasses import dataclass, field


THRESHOLDS = {
    "confirmed_ai": 0.85,
    "likely_ai": 0.65,
    "suspicious": 0.45,
    "likely_human": 0.25,
}


def label_from_score(score: float, thresholds: dict[str, float] | None = None) -> str:
    t = thresholds or THRESHOLDS
    if score >= t.get("confirmed_ai", 0.85):
        return "Confirmed AI"
    if score >= t.get("likely_ai", 0.65):
        return "Likely AI"
    if score >= t.get("suspicious", 0.45):
        return "Suspicious"
    if score >= t.get("likely_human", 0.25):
        return "Likely Human"
    return "Low AI evidence"


@dataclass
class ScoreComponents:
    metadata_score: float = 0.0
    forensics_score: float = 0.0
    model_score: float = 0.0
    metadata_confirmed: bool = False


def compute_final_score(components: ScoreComponents) -> float:
    if components.metadata_confirmed:
        return 1.0

    if components.model_score > 0:
        score = (
            components.metadata_score * 0.3
            + components.forensics_score * 0.2
            + components.model_score * 0.5
        )
    elif components.forensics_score > 0:
        score = (
            components.metadata_score * 0.5
            + components.forensics_score * 0.5
        )
    else:
        score = components.metadata_score

    return round(min(max(score, 0.0), 1.0), 4)
