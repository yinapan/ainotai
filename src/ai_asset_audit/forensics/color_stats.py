from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ColorStatsResult:
    smoothness: float = 0.0
    unique_ratio: float = 0.0
    channel_correlation: float = 0.0
    suspicious: bool = False
    error: str | None = None


def compute_color_stats(
    image: np.ndarray,
    threshold: float = 0.7,
) -> ColorStatsResult:
    try:
        h, w = image.shape[:2]
        total_pixels = h * w

        if len(image.shape) == 2:
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            bgr = image

        arr = bgr.astype(np.float32)

        flat = bgr.reshape(-1, 3)
        _, indices = np.unique(flat, axis=0, return_index=True)
        unique_ratio = len(indices) / total_pixels if total_pixels > 0 else 0.0

        diffs_h = np.abs(np.diff(arr, axis=0)).mean()
        diffs_w = np.abs(np.diff(arr, axis=1)).mean()
        mean_diff = (diffs_h + diffs_w) / 2.0
        smoothness = 1.0 - min(mean_diff / 128.0, 1.0)

        b, g, r = arr[:, :, 0].flatten(), arr[:, :, 1].flatten(), arr[:, :, 2].flatten()
        if np.std(b) > 0 and np.std(g) > 0 and np.std(r) > 0:
            corr_bg = float(np.corrcoef(b, g)[0, 1])
            corr_br = float(np.corrcoef(b, r)[0, 1])
            corr_gr = float(np.corrcoef(g, r)[0, 1])
            channel_correlation = (abs(corr_bg) + abs(corr_br) + abs(corr_gr)) / 3.0
        else:
            channel_correlation = 0.0

        suspicious = smoothness > threshold

        return ColorStatsResult(
            smoothness=round(smoothness, 4),
            unique_ratio=round(unique_ratio, 6),
            channel_correlation=round(channel_correlation, 4),
            suspicious=suspicious,
        )
    except Exception as exc:
        logger.warning("Color stats failed: %s", exc)
        return ColorStatsResult(error=str(exc))
