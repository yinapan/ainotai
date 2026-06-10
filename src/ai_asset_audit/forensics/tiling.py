from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TilingResult:
    tiling_score: float = 0.0
    peak_strength: float = 0.0
    period_x: int = 0
    period_y: int = 0
    suspicious: bool = False
    error: str | None = None


def compute_tiling_analysis(
    image: np.ndarray,
    threshold: float = 0.3,
    min_period_frac: float = 0.05,
    max_period_frac: float = 0.45,
) -> TilingResult:
    try:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        gray = gray.astype(np.float32)
        h, w = gray.shape
        if h < 64 or w < 64:
            return TilingResult(error="Image too small for tiling analysis")

        gray -= gray.mean()

        f = np.fft.fft2(gray)
        power = np.abs(f) ** 2
        autocorr = np.fft.ifft2(power).real

        autocorr = np.fft.fftshift(autocorr)
        center_val = autocorr[h // 2, w // 2]
        if center_val < 1e-6:
            return TilingResult(tiling_score=0.0, peak_strength=0.0)

        autocorr_norm = autocorr / center_val

        min_dy = int(h * min_period_frac)
        max_dy = int(h * max_period_frac)
        min_dx = int(w * min_period_frac)
        max_dx = int(w * max_period_frac)

        mask = np.zeros_like(autocorr_norm, dtype=bool)
        cy, cx = h // 2, w // 2
        mask[cy - max_dy : cy - min_dy, cx - max_dx : cx + max_dx + 1] = True
        mask[cy + min_dy : cy + max_dy + 1, cx - max_dx : cx + max_dx + 1] = True
        mask[cy - max_dy : cy + max_dy + 1, cx - max_dx : cx - min_dx] = True
        mask[cy - max_dy : cy + max_dy + 1, cx + min_dx : cx + max_dx + 1] = True

        masked = autocorr_norm.copy()
        masked[~mask] = 0.0

        peak_val = float(masked.max())
        peak_pos = np.unravel_index(masked.argmax(), masked.shape)
        period_y = abs(peak_pos[0] - cy)
        period_x = abs(peak_pos[1] - cx)

        tiling_score = min(max(peak_val, 0.0), 1.0)
        suspicious = tiling_score > threshold

        return TilingResult(
            tiling_score=round(tiling_score, 4),
            peak_strength=round(peak_val, 4),
            period_x=int(period_x),
            period_y=int(period_y),
            suspicious=suspicious,
        )
    except Exception as exc:
        logger.warning("Tiling analysis failed: %s", exc)
        return TilingResult(error=str(exc))
