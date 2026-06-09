from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

from .base import BaseDetector

logger = logging.getLogger(__name__)


class FreqDetector(BaseDetector):
    """Frequency-domain AI image detector.

    Uses DCT-based frequency features concatenated with RGB input.
    Expected in model_path: *.pth or *.pt (full pickled model or state_dict).
    Input: 224x224, output: AI probability via sigmoid.
    """

    name = "freq_detect"

    def __init__(self, model_path: str | Path, device: str = "cpu", weight: float = 0.15):
        super().__init__(model_path, device, weight)

    def load(self) -> bool:
        try:
            import torch
            import torch.nn as nn
            import torchvision.models as tv_models

            weight_file = self._find_weight_file()
            if not weight_file:
                logger.error("FreqDetector weights not found in %s", self.model_path)
                return False

            state_dict = torch.load(weight_file, map_location=self.device, weights_only=True)

            backbone = tv_models.resnet34(weights=None)
            backbone.conv1 = nn.Conv2d(4, 64, kernel_size=7, stride=2, padding=3, bias=False)
            backbone.fc = nn.Linear(512, 1)
            self._model = backbone

            if any(k.startswith("module.") for k in state_dict):
                state_dict = {k.removeprefix("module."): v for k, v in state_dict.items()}

            self._model.load_state_dict(state_dict, strict=False)
            self._model.to(self.device)
            self._model.eval()
            logger.info("Loaded FreqDetector from %s", weight_file)
            return True
        except ImportError:
            logger.error("PyTorch not installed, FreqDetector unavailable")
            return False
        except Exception as exc:
            logger.error("Failed to load FreqDetector: %s", exc)
            return False

    def _find_weight_file(self) -> Path | None:
        for suffix in ("*.pth", "*.pt"):
            for candidate in sorted(self.model_path.glob(suffix)):
                return candidate
        return None

    def _compute_dct_channel(self, gray: np.ndarray) -> np.ndarray:
        """Compute single-channel DCT energy map at 8x8 block level."""
        import torch

        h, w = gray.shape
        h_pad = (h + 7) // 8 * 8
        w_pad = (w + 7) // 8 * 8
        padded = np.zeros((h_pad, w_pad), dtype=np.float32)
        padded[:h, :w] = gray

        blocks = padded.reshape(h_pad // 8, 8, w_pad // 8, 8)
        blocks = blocks.transpose(0, 2, 1, 3).reshape(-1, 8, 8).astype(np.float32)

        dct_blocks = np.zeros_like(blocks)
        for i in range(blocks.shape[0]):
            dct_blocks[i] = self._dct_2d(blocks[i])

        energy = np.abs(dct_blocks).mean(axis=(1, 2))
        energy_map = energy.reshape(h_pad // 8, w_pad // 8)
        energy_map = np.repeat(np.repeat(energy_map, 8, axis=0), 8, axis=1)
        return energy_map[:h, :w]

    @staticmethod
    def _dct_2d(block: np.ndarray) -> np.ndarray:
        from scipy.fft import dct

        return dct(dct(block.T, norm="ortho").T, norm="ortho")

    def predict(self, image: Image.Image) -> float:
        import torch
        import torchvision.transforms as T

        if image.mode != "RGB":
            image = image.convert("RGB")

        gray = np.array(image.convert("L"), dtype=np.float32)
        dct_map = self._compute_dct_channel(gray)
        dct_map = (dct_map - dct_map.mean()) / (dct_map.std() + 1e-6)
        dct_map = np.clip(dct_map * 0.1 + 0.5, 0, 1) * 255

        rgb_tensor = T.ToTensor()(image.resize((224, 224)))
        dct_tensor = torch.from_numpy(dct_map).unsqueeze(0).float()
        dct_tensor = T.Resize((224, 224))(dct_tensor)
        dct_tensor = dct_tensor / 255.0

        combined = torch.cat([
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])(rgb_tensor),
            dct_tensor,
        ], dim=0).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self._model(combined)
            prob = torch.sigmoid(logits).item()

        return float(prob)
