from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ElaResult:
    uniformity: float = 0.0
    mean_error: float = 0.0
    max_error: float = 0.0
    suspicious: bool = False
    error: str | None = None


def compute_ela(
    image: np.ndarray,
    quality: int = 90,
    threshold: float = 0.75,
) -> ElaResult:
    try:
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        _, buf = cv2.imencode(".jpg", image, encode_params)
        recompressed = cv2.imdecode(buf, cv2.IMREAD_COLOR)

        diff = np.abs(image.astype(np.float32) - recompressed.astype(np.float32))
        mean_error = float(np.mean(diff))
        max_error = float(np.max(diff))

        block_size = 8
        h, w = diff.shape[:2]
        blocks_h, blocks_w = h // block_size, w // block_size
        if blocks_h == 0 or blocks_w == 0:
            return ElaResult(uniformity=0.5, mean_error=mean_error, max_error=max_error)

        cropped = diff[: blocks_h * block_size, : blocks_w * block_size]
        blocks = cropped.reshape(blocks_h, block_size, blocks_w, block_size, -1)
        block_means = blocks.mean(axis=(1, 3))
        overall_mean = block_means.mean()
        if overall_mean < 1e-6:
            uniformity = 1.0
        else:
            std = float(block_means.std())
            uniformity = 1.0 - min(std / (overall_mean + 1e-6), 1.0)

        suspicious = uniformity > threshold

        return ElaResult(
            uniformity=round(uniformity, 4),
            mean_error=round(mean_error, 4),
            max_error=round(max_error, 4),
            suspicious=suspicious,
        )
    except Exception as exc:
        logger.warning("ELA failed: %s", exc)
        return ElaResult(error=str(exc))
