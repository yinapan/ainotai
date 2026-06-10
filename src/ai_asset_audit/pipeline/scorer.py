from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


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


def texture_model_weight_factor(relative_path: str) -> float:
    """Reduce natural-image model influence for packed or derived texture maps."""
    stem = Path(relative_path).stem.lower()
    suffix = stem.rsplit("_", 1)[-1] if "_" in stem else ""

    if suffix in {"d", "diff", "diffuse", "albedo", "basecolor", "base_color"}:
        return 1.0
    if suffix in {"n", "normal", "mads", "orm", "rma", "mask"}:
        return 0.65
    if suffix in {"e", "emissive", "h", "height", "ao", "roughness", "metallic"}:
        return 0.75
    return 0.9


def texture_model_weight_overrides(relative_path: str) -> dict[str, float] | None:
    """For game texture assets, return per-model weight overrides.

    CLIP and NPR produce near-1.0 on all game textures regardless of origin.
    sdxl_detector is the strongest discriminator for this asset class.
    """
    stem = Path(relative_path).stem.lower()
    suffix = stem.rsplit("_", 1)[-1] if "_" in stem else ""

    texture_suffixes = {
        "d", "diff", "diffuse", "albedo", "basecolor", "base_color",
        "n", "normal", "mads", "orm", "rma", "mask",
        "e", "emissive", "h", "height", "ao", "roughness", "metallic",
    }
    if suffix not in texture_suffixes:
        return None

    return {
        "community_forensics": 0.25,
        "cnn_detection": 0.20,
        "clip_detector": 0.05,
        "npr": 0.05,
        "universal_fake_detect": 0.25,
        "sdxl_detector": 0.50,
        "freq_detect": 0.15,
        "dire_detector": 0.20,
    }


@dataclass
class ModelConsensus:
    """Model agreement analysis for more robust scoring."""
    available_count: int = 0
    high_score_count: int = 0  # models scoring > 0.7
    low_score_count: int = 0   # models scoring < 0.3
    divergence: float = 0.0    # std of model scores
    max_score: float = 0.0
    min_score: float = 0.0
    agreement: str = "unknown"  # "unanimous_high", "majority_high", "split", "majority_low", "unanimous_low"


def compute_model_consensus(model_scores: dict[str, float | None]) -> ModelConsensus:
    scores = [s for s in model_scores.values() if s is not None and isinstance(s, float)]
    if not scores:
        return ModelConsensus()

    import numpy as np
    arr = np.array(scores)
    high = int(np.sum(arr > 0.7))
    low = int(np.sum(arr < 0.3))
    n = len(scores)

    if n >= 2 and high == n:
        agreement = "unanimous_high"
    elif n >= 2 and high >= n * 0.6:
        agreement = "majority_high"
    elif n >= 2 and low == n:
        agreement = "unanimous_low"
    elif n >= 2 and low >= n * 0.6:
        agreement = "majority_low"
    else:
        agreement = "split"

    return ModelConsensus(
        available_count=n,
        high_score_count=high,
        low_score_count=low,
        divergence=round(float(arr.std()), 4),
        max_score=round(float(arr.max()), 4),
        min_score=round(float(arr.min()), 4),
        agreement=agreement,
    )


@dataclass
class ScoreComponents:
    metadata_score: float = 0.0
    forensics_score: float = 0.0
    model_score: float = 0.0
    metadata_confirmed: bool = False
    consensus: ModelConsensus | None = None


def compute_final_score(components: ScoreComponents, scoring_config: dict | None = None) -> float:
    if components.metadata_confirmed:
        return 1.0

    sc = scoring_config or {}
    weights = sc.get("weights", {})
    penalties = sc.get("penalties", {})
    w_meta = weights.get("metadata", 0.35)
    w_model = weights.get("model_consensus", 0.40)
    w_forensics = weights.get("forensics", 0.15)
    p_low_count = penalties.get("low_model_count", 0.8)
    p_single_high = penalties.get("single_model_high", 0.7)

    if components.model_score > 0:
        base = (
            components.metadata_score * w_meta
            + components.forensics_score * w_forensics
            + components.model_score * w_model
        )
        remainder = 1.0 - w_meta - w_model - w_forensics
        if remainder > 0:
            base += components.forensics_score * remainder

        if components.consensus:
            c = components.consensus
            if c.agreement == "split" and c.available_count >= 2:
                base *= 0.7
            elif c.agreement == "unanimous_high":
                base = min(base * 1.1, 1.0)
            elif c.agreement == "majority_low":
                base *= 0.5
            if c.available_count < 3:
                base *= p_low_count
            if c.high_score_count == 1 and c.available_count >= 2:
                base *= p_single_high

        score = base
    elif components.forensics_score > 0:
        score = (
            components.metadata_score * 0.5
            + components.forensics_score * 0.5
        )
    else:
        score = components.metadata_score

    return round(min(max(score, 0.0), 1.0), 4)
