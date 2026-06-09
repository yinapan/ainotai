from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path

from PIL import Image

from .base import BaseDetector

logger = logging.getLogger(__name__)


def _build_npr_backbone():
    """Build the NPR model architecture matching the pre-trained weights.

    Architecture: modified ResNet bottleneck
    - conv1: 3x3, 3→64
    - layer1: 3× Bottleneck(64→256)
    - layer2: 4× Bottleneck(256→512)
    - avgpool → fc: 512→1
    """
    import torch.nn as nn

    class Bottleneck(nn.Module):
        expansion = 4

        def __init__(self, inplanes, planes, stride=1, downsample=None):
            super().__init__()
            self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
            self.bn1 = nn.BatchNorm2d(planes)
            self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
            self.bn2 = nn.BatchNorm2d(planes)
            self.conv3 = nn.Conv2d(planes, planes * self.expansion, kernel_size=1, bias=False)
            self.bn3 = nn.BatchNorm2d(planes * self.expansion)
            self.relu = nn.ReLU(inplace=True)
            self.downsample = downsample
            self.stride = stride

        def forward(self, x):
            residual = x
            out = self.relu(self.bn1(self.conv1(x)))
            out = self.relu(self.bn2(self.conv2(out)))
            out = self.bn3(self.conv3(out))
            if self.downsample is not None:
                residual = self.downsample(x)
            out += residual
            return self.relu(out)

    class NPRBackbone(nn.Module):
        def __init__(self):
            super().__init__()
            self.inplanes = 64
            self.conv1 = nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1, bias=False)
            self.bn1 = nn.BatchNorm2d(64)
            self.relu = nn.ReLU(inplace=True)
            self.layer1 = self._make_layer(64, 3)
            self.layer2 = self._make_layer(128, 4, stride=2)
            self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
            self.fc1 = nn.Linear(512, 1)

        def _make_layer(self, planes, blocks, stride=1):
            downsample = None
            if stride != 1 or self.inplanes != planes * 4:
                downsample = nn.Sequential(
                    nn.Conv2d(self.inplanes, planes * 4, kernel_size=1, stride=stride, bias=False),
                    nn.BatchNorm2d(planes * 4),
                )
            layers = [Bottleneck(self.inplanes, planes, stride, downsample)]
            self.inplanes = planes * 4
            for _ in range(1, blocks):
                layers.append(Bottleneck(self.inplanes, planes))
            return nn.Sequential(*layers)

        def forward(self, x):
            x = self.relu(self.bn1(self.conv1(x)))
            x = self.layer1(x)
            x = self.layer2(x)
            x = self.avgpool(x)
            x = x.view(x.size(0), -1)
            return self.fc1(x)

    return NPRBackbone()


class NprDetector(BaseDetector):
    """NPR (AI Art Style) detector — ResNet bottleneck backbone.

    Expected: NPR.pth (training checkpoint with model+optimizer state_dict).
    Input: 256x256 RGB, output: AI probability via sigmoid.
    """

    name = "npr"

    def __init__(self, model_path: str | Path, device: str = "cpu", weight: float = 0.15):
        super().__init__(model_path, device, weight)

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
                logger.error("NPR weights not found in %s", self.model_path)
                return False

            checkpoint = torch.load(weight_file, map_location=self.device, weights_only=True)

            if isinstance(checkpoint, dict) and "model" in checkpoint:
                state_dict = checkpoint["model"]
            elif isinstance(checkpoint, (dict, OrderedDict)):
                state_dict = checkpoint
            else:
                self._model = checkpoint
                if hasattr(self._model, "train"):
                    self._model.train(False)
                logger.info("Loaded NPR (full model) from %s", weight_file)
                return True

            if any(k.startswith("module.") for k in state_dict):
                state_dict = OrderedDict(
                    (k.removeprefix("module."), v) for k, v in state_dict.items()
                )

            self._model = _build_npr_backbone()
            self._model.load_state_dict(state_dict, strict=True)
            self._model.to(self.device)
            self._model.train(False)
            logger.info("Loaded NPR from %s", weight_file)
            return True

        except ImportError:
            logger.error("PyTorch not installed, NPR unavailable")
            return False
        except Exception as exc:
            logger.error("Failed to load NPR: %s", exc)
            return False

    def predict(self, image: Image.Image) -> float:
        import torch
        import torchvision.transforms as T

        transform = T.Compose([
            T.Resize((256, 256)),
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
