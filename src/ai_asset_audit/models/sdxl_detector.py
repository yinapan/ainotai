from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from .base import BaseDetector

logger = logging.getLogger(__name__)


class SdxlDetector(BaseDetector):
    name = "sdxl_detector"

    def __init__(self, model_path: str | Path, device: str = "cpu", weight: float = 0.15):
        super().__init__(model_path, device, weight)
        self._processor = None

    def load(self) -> bool:
        try:
            from transformers import AutoModelForImageClassification, AutoImageProcessor

            config_file = self.model_path / "config.json"
            if not config_file.exists():
                logger.error("SDXL detector config not found in %s", self.model_path)
                return False

            self._model = AutoModelForImageClassification.from_pretrained(
                str(self.model_path),
                local_files_only=True,
            ).to(self.device)
            self._model.train(False)

            self._processor = AutoImageProcessor.from_pretrained(
                str(self.model_path),
                local_files_only=True,
            )
            logger.info("Loaded SDXL detector from %s", self.model_path)
            return True
        except ImportError:
            logger.error("transformers not installed, SDXL detector unavailable")
            return False
        except Exception as exc:
            logger.error("Failed to load SDXL detector: %s", exc)
            return False

    def predict(self, image: Image.Image) -> float:
        import torch

        if image.mode != "RGB":
            image = image.convert("RGB")

        inputs = self._processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            output = self._model(**inputs)
            logits = output.logits
            probs = torch.softmax(logits, dim=-1)

            ai_index = None
            if hasattr(self._model.config, "label2id"):
                for label, idx in self._model.config.label2id.items():
                    if "ai" in label.lower() or "artificial" in label.lower() or "fake" in label.lower():
                        ai_index = idx
                        break

            if ai_index is not None:
                prob = probs[0, ai_index].item()
            else:
                prob = probs[0, -1].item()

        return float(prob)
