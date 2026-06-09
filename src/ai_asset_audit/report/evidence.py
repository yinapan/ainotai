from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..pipeline.pipeline import AssetResult


@dataclass
class EvidenceChain:
    file_id: str
    relative_path: str
    layers: list[str] = field(default_factory=list)
    conclusion: str = "Inconclusive"
    strength: str = "none"


def build_evidence_chain(result: AssetResult) -> EvidenceChain:
    layers: list[str] = []

    if result.metadata.get("signals"):
        for signal in result.metadata["signals"]:
            layers.append(f"[Metadata] {signal}")

    if result.forensics:
        combined = result.forensics.get("combined_score", 0)
        if combined > 0.7:
            layers.append(f"[Forensics] Combined anomaly score: {combined:.2f}")
        elif combined > 0.45:
            layers.append(f"[Forensics] Moderate anomaly: {combined:.2f}")

    if result.models:
        for name, score in result.models.items():
            if score is not None and score > 0.5:
                layers.append(f"[Model:{name}] Score: {score:.2f}")

    if not layers:
        strength = "none"
    elif len(layers) >= 3:
        strength = "strong"
    elif len(layers) >= 2:
        strength = "moderate"
    else:
        strength = "weak"

    return EvidenceChain(
        file_id=result.file_id,
        relative_path=result.relative_path,
        layers=layers,
        conclusion=result.final_label,
        strength=strength,
    )
