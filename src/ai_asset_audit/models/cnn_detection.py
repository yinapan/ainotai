from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

from .base import BaseDetector

logger = logging.getLogger(__name__)


class CNNDetectionDetector(BaseDetector):
    """Wang et al. CNNdetection — ResNet-50 baseline for AI-generated image detection.

    Downloads weights from: https://github.com/PeterWang512/CNNDetection
    Expected in model_path: model.pth or *.pth (full pickled model).
    Input: 224x224 RGB, output: single AI probability via sigmoid.
    """

    name = "cnn_detection"

    def __init__(self, model_path: str | Path, device: str = "cpu", weight: float = 0.20):
        super().__init__(model_path, device, weight)

    def load(self) -> bool:
        try:
            import torch
            import torchvision.models as tv_models

            weight_file = self._find_weight_file()
            if not weight_file:
                logger.error("CNNDetection weights not found in %s", self.model_path)
                return False

            state_dict = torch.load(weight_file, map_location=self.device, weights_only=True)

            self._model = tv_models.resnet50(num_classes=1)
            self._model.fc = torch.nn.Linear(2048, 1)

            if any(k.startswith("module.") for k in state_dict):
                state_dict = {k.removeprefix("module."): v for k, v in state_dict.items()}

            self._model.load_state_dict(state_dict, strict=False)
            self._model.to(self.device)
            self._model.eval()
            logger.info("Loaded CNNDetection from %s", weight_file)
            return True
        except ImportError:
            logger.error("PyTorch not installed, CNNDetection unavailable")
            return False
        except Exception as exc:
            logger.error("Failed to load CNNDetection: %s", exc)
            return False

    def _find_weight_file(self) -> Path | None:
        for suffix in ("*.pth", "*.pt", "*.ckpt"):
            for candidate in sorted(self.model_path.glob(suffix)):
                return candidate
        return None

    def predict(self, image: Image.Image) -> float:
        import torch
        import torchvision.transforms as T

        transform = T.Compose([
            T.Resize((256, 256)),
            T.CenterCrop((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        if image.mode != "RGB":
            image = image.convert("RGB")

        tensor = transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self._model(tensor)
            prob = torch.sigmoid(logits).item()

        return float(prob)
