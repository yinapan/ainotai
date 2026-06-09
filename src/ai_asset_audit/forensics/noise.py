from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class NoiseResult:
    consistency: float = 0.0
    noise_std: float = 0.0
    block_uniformity: float = 0.0
    suspicious: bool = False
    error: str | None = None


def compute_noise_consistency(
    image: np.ndarray,
    block_size: int = 64,
    threshold: float = 0.75,
) -> NoiseResult:
    try:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        gray = gray.astype(np.float32)
        h, w = gray.shape
        if h < block_size or w < block_size:
            return NoiseResult(error="Image too small for noise analysis")

        noise = cv2.Laplacian(gray, cv2.CV_32F)
        noise = np.abs(noise)

        overall_std = float(np.std(noise))

        blocks_h = (h - 2) // block_size
        blocks_w = (w - 2) // block_size
        if blocks_h == 0 or blocks_w == 0:
            return NoiseResult(noise_std=overall_std, consistency=0.5)

        block_stds: list[float] = []
        for by in range(blocks_h):
            for bx in range(blocks_w):
                block = noise[
                    by * block_size : (by + 1) * block_size,
                    bx * block_size : (bx + 1) * block_size,
                ]
                block_stds.append(float(np.std(block)))

        if not block_stds:
            return NoiseResult(noise_std=overall_std, consistency=0.5)

        std_of_stds = float(np.std(block_stds))
        mean_of_stds = float(np.mean(block_stds))
        if mean_of_stds < 1e-6:
            uniformity = 1.0
        else:
            uniformity = 1.0 - min(std_of_stds / mean_of_stds, 1.0)

        consistency = uniformity
        suspicious = consistency > threshold

        return NoiseResult(
            consistency=round(consistency, 4),
            noise_std=round(overall_std, 4),
            block_uniformity=round(uniformity, 4),
            suspicious=suspicious,
        )
    except Exception as exc:
        logger.warning("Noise analysis failed: %s", exc)
        return NoiseResult(error=str(exc))
