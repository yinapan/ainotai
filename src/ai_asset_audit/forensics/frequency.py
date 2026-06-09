from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FrequencyResult:
    anomaly_score: float = 0.0
    high_freq_ratio: float = 0.0
    suspicious: bool = False
    error: str | None = None


def compute_frequency_analysis(
    image: np.ndarray,
    threshold: float = 0.7,
) -> FrequencyResult:
    try:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        gray = gray.astype(np.float32)
        h, w = gray.shape
        if h < 16 or w < 16:
            return FrequencyResult(error="Image too small for frequency analysis")

        dft = cv2.dft(gray, flags=cv2.DFT_COMPLEX_OUTPUT)
        dft_shift = np.fft.fftshift(dft)
        magnitude = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1])
        magnitude = np.log1p(magnitude)

        cy, cx = h // 2, w // 2
        radius = min(cy, cx) // 4

        y, x = np.ogrid[:h, :w]
        dist = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)

        low_mask = dist <= radius
        high_mask = dist > radius

        total_energy = magnitude.sum()
        if total_energy < 1e-6:
            return FrequencyResult(anomaly_score=0.0, high_freq_ratio=0.0)

        high_energy = magnitude[high_mask].sum()
        high_freq_ratio = float(high_energy / total_energy)

        anomaly_score = 1.0 - high_freq_ratio if high_freq_ratio < 0.5 else high_freq_ratio
        anomaly_score = min(max(anomaly_score, 0.0), 1.0)

        return FrequencyResult(
            anomaly_score=round(anomaly_score, 4),
            high_freq_ratio=round(high_freq_ratio, 4),
            suspicious=anomaly_score > threshold,
        )
    except Exception as exc:
        logger.warning("Frequency analysis failed: %s", exc)
        return FrequencyResult(error=str(exc))
