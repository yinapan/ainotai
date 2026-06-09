from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from .base import BaseDetector

logger = logging.getLogger(__name__)


class ClipDetector(BaseDetector):
    """CLIP-based zero-shot AI image detector.

    Uses OpenAI CLIP ViT-B/32 to compute cosine similarity between the image
    and text prompts ("a real photo" vs "an AI-generated image").
    No task-specific fine-tuning weights needed — uses pretrained CLIP.

    Expected in model_path: OpenCLIP or HuggingFace CLIP model directory
    with config.json + pytorch_model.bin, or leave empty to use auto-download
    on the download machine (offline-safe after initial download).

    Input: 224x224 RGB, output: AI probability via softmax over text prompts.
    """

    name = "clip_detector"

    def __init__(self, model_path: str | Path, device: str = "cpu", weight: float = 0.15):
        super().__init__(model_path, device, weight)
        self._clip_model = None
        self._processor = None

    def load(self) -> bool:
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor

            model_dir = self.model_path if self.model_path.exists() else "openai/clip-vit-base-patch32"

            if isinstance(model_dir, Path):
                model_dir = str(model_dir)

            self._clip_model = CLIPModel.from_pretrained(
                model_dir,
                local_files_only=True,
            ).to(self.device)
            self._clip_model.eval()

            self._processor = CLIPProcessor.from_pretrained(
                model_dir,
                local_files_only=True,
            )

            self._real_text = "a real photograph taken by a camera"
            self._ai_text = "an AI-generated synthetic image"

            logger.info("Loaded CLIP detector from %s", model_dir)
            return True
        except ImportError:
            logger.error("transformers not installed, CLIP detector unavailable")
            return False
        except Exception as exc:
            logger.error("Failed to load CLIP detector: %s", exc)
            return False

    def predict(self, image: Image.Image) -> float:
        import torch

        if image.mode != "RGB":
            image = image.convert("RGB")

        inputs = self._processor(
            text=[self._real_text, self._ai_text],
            images=image,
            return_tensors="pt",
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._clip_model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = torch.softmax(logits_per_image, dim=-1)
            ai_prob = probs[0, 1].item()

        return float(ai_prob)
