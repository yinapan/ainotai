from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from .base import BaseDetector

logger = logging.getLogger(__name__)


class UniversalFakeDetector(BaseDetector):
    name = "universal_fake_detect"

    def __init__(self, model_path: str | Path, device: str = "cpu", weight: float = 0.25):
        super().__init__(model_path, device, weight)
        self._processor = None

    def load(self) -> bool:
        try:
            import torch

            weight_file = None
            for suffix in ("*.pth", "*.pt"):
                for candidate in self.model_path.glob(suffix):
                    weight_file = candidate
                    break
                if weight_file:
                    break

            if not weight_file or not weight_file.exists():
                logger.error("UniversalFakeDetect weights not found in %s", self.model_path)
                return False

            self._model = torch.load(weight_file, map_location=self.device, weights_only=False)
            if hasattr(self._model, "train"):
                self._model.train(False)
            logger.info("Loaded UniversalFakeDetect from %s", weight_file)
            return True
        except ImportError:
            logger.error("PyTorch not installed, UniversalFakeDetect unavailable")
            return False
        except Exception as exc:
            logger.error("Failed to load UniversalFakeDetect: %s", exc)
            return False

    def predict(self, image: Image.Image) -> float:
        import torch
        import torchvision.transforms as T

        transform = T.Compose([
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        if image.mode != "RGB":
            image = image.convert("RGB")

        tensor = transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            output = self._model(tensor)
            if isinstance(output, (list, tuple)):
                output = output[0]
            if isinstance(output, dict):
                output = list(output.values())[0]
            prob = torch.sigmoid(output).item()

        return float(prob)
