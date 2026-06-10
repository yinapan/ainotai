from __future__ import annotations

import logging
from dataclasses import dataclass, field

from PIL import Image

from .base import BaseDetector, DetectionResult

logger = logging.getLogger(__name__)


@dataclass
class EnsembleResult:
    weighted_score: float = 0.0
    model_results: dict[str, DetectionResult] = field(default_factory=dict)
    active_models: int = 0
    total_weight: float = 0.0


class EnsembleDetector:
    def __init__(self, detectors: list[BaseDetector] | None = None):
        self.detectors: list[BaseDetector] = detectors or []

    def add(self, detector: BaseDetector) -> None:
        self.detectors.append(detector)

    def predict(self, image: Image.Image, weight_overrides: dict[str, float] | None = None) -> EnsembleResult:
        results: dict[str, DetectionResult] = {}
        weighted_sum = 0.0
        total_weight = 0.0
        active = 0

        for detector in self.detectors:
            result = detector.detect(image)
            results[detector.name] = result
            if result.available and result.error is None:
                w = weight_overrides.get(detector.name, detector.weight) if weight_overrides else detector.weight
                weighted_sum += result.score * w
                total_weight += w
                active += 1

        weighted_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        return EnsembleResult(
            weighted_score=round(weighted_score, 4),
            model_results=results,
            active_models=active,
            total_weight=round(total_weight, 4),
        )

    def available_models(self) -> list[str]:
        return [d.name for d in self.detectors if d.is_available()]
