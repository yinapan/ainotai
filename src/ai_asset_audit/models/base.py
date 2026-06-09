from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    model_name: str
    score: float
    available: bool = True
    error: str | None = None


class BaseDetector(ABC):
    name: str = "base"
    weight: float = 0.0

    def __init__(self, model_path: str | Path, device: str = "cpu", weight: float = 0.0):
        self.model_path = Path(model_path)
        self.device = device
        self.weight = weight
        self._model = None

    @abstractmethod
    def load(self) -> bool:
        ...

    @abstractmethod
    def predict(self, image: Image.Image) -> float:
        ...

    def detect(self, image: Image.Image) -> DetectionResult:
        if self._model is None:
            if not self.load():
                return DetectionResult(
                    model_name=self.name,
                    score=0.0,
                    available=False,
                    error="Model not loaded",
                )
        try:
            score = self.predict(image)
            return DetectionResult(model_name=self.name, score=score)
        except Exception as exc:
            logger.warning("Model %s prediction failed: %s", self.name, exc)
            return DetectionResult(
                model_name=self.name,
                score=0.0,
                available=False,
                error=str(exc),
            )

    def is_available(self) -> bool:
        return self.model_path.exists()
