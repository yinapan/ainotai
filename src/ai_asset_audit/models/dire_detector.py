from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from .base import BaseDetector

logger = logging.getLogger(__name__)


class DireDetector(BaseDetector):
    """DIRE diffusion detector adapter for local offline checkpoints.

    Expected in model_path: a TorchScript file or pickled PyTorch model with a
    .pt/.pth/.ckpt extension. The model should accept a normalized RGB tensor
    and return a single logit/probability or a tensor whose last value is the AI
    probability/logit.
    """

    name = "dire"

    def __init__(self, model_path: str | Path, device: str = "cpu", weight: float = 0.20):
        super().__init__(model_path, device, weight)

    def load(self) -> bool:
        try:
            import torch

            weight_file = self._find_weight_file()
            if not weight_file:
                logger.error("DIRE weights not found in %s", self.model_path)
                return False

            try:
                self._model = torch.jit.load(str(weight_file), map_location=self.device)
            except Exception:
                self._model = torch.load(weight_file, map_location=self.device, weights_only=False)

            if hasattr(self._model, "to"):
                self._model.to(self.device)
            if hasattr(self._model, "eval"):
                self._model.eval()

            logger.info("Loaded DIRE detector from %s", weight_file)
            return True
        except ImportError:
            logger.error("PyTorch not installed, DIRE unavailable")
            return False
        except Exception as exc:
            logger.error("Failed to load DIRE detector: %s", exc)
            return False

    def _find_weight_file(self) -> Path | None:
        for suffix in ("*.pt", "*.pth", "*.ckpt"):
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
            output = self._model(tensor)
            if isinstance(output, (list, tuple)):
                output = output[0]
            if isinstance(output, dict):
                output = next(iter(output.values()))
            if hasattr(output, "flatten"):
                output = output.flatten()[-1]
            value = float(output.item() if hasattr(output, "item") else output)

        if 0.0 <= value <= 1.0:
            return value
        return float(torch.sigmoid(torch.tensor(value)).item())
