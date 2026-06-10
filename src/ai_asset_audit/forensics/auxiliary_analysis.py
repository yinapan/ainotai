from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AuxAnalysisResult:
    role: str = ""
    valid: bool = True
    anomaly_score: float = 0.0
    details: list[str] = None

    def __post_init__(self):
        if self.details is None:
            self.details = []


def analyze_normal_map(image: np.ndarray, albedo: np.ndarray | None = None) -> AuxAnalysisResult:
    result = AuxAnalysisResult(role="normal")
    try:
        if len(image.shape) < 3 or image.shape[2] < 3:
            result.details.append("Not a 3-channel image")
            result.anomaly_score = 0.3
            return result

        b, g, r = cv2.split(image[:, :, :3])
        r_mean, g_mean, b_mean = float(r.mean()), float(g.mean()), float(b.mean())

        expected_b = 255 * 0.5
        expected_g = 255 * 0.5
        expected_r = 255 * 1.0

        b_dev = abs(b_mean - expected_b) / 255
        g_dev = abs(g_mean - expected_g) / 255
        r_dev = abs(r_mean - expected_r) / 255
        avg_dev = (b_dev + g_dev + r_dev) / 3

        if avg_dev > 0.25:
            result.details.append(f"Normal map channel means deviate: R={r_mean:.0f} G={g_mean:.0f} B={b_mean:.0f}")
            result.anomaly_score = min(avg_dev, 1.0)

        if albedo is not None:
            gray_n = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray_a = cv2.cvtColor(albedo, cv2.COLOR_BGR2GRAY)
            edges_n = cv2.Canny(gray_n, 50, 150)
            edges_a = cv2.Canny(gray_a, 50, 150)
            if edges_n.shape == edges_a.shape:
                overlap = np.logical_and(edges_n > 0, edges_a > 0).sum()
                total = max(edges_a.sum() // 255, 1)
                consistency = overlap / total
                if consistency < 0.1:
                    result.details.append(f"Low edge consistency with albedo: {consistency:.2f}")
                    result.anomaly_score = max(result.anomaly_score, 0.4)

    except Exception as exc:
        logger.warning("Normal map analysis failed: %s", exc)
        result.details.append(f"Analysis error: {exc}")
    return result


def analyze_packed_map(image: np.ndarray) -> AuxAnalysisResult:
    result = AuxAnalysisResult(role="packed")
    try:
        channels = cv2.split(image)
        for i, ch in enumerate(channels[:4]):
            ch_min, ch_max = float(ch.min()), float(ch.max())
            ch_std = float(ch.std())
            if ch_std < 1.0 and ch_max - ch_min < 5:
                result.details.append(f"Channel {i} appears constant (std={ch_std:.1f})")
            if ch_max - ch_min < 2:
                result.anomaly_score = max(result.anomaly_score, 0.2)

        if len(channels) >= 3:
            corr_rg = np.corrcoef(channels[0].flatten(), channels[1].flatten())[0, 1]
            if abs(corr_rg) > 0.95:
                result.details.append(f"R-G channels highly correlated ({corr_rg:.2f})")
                result.anomaly_score = max(result.anomaly_score, 0.3)

    except Exception as exc:
        logger.warning("Packed map analysis failed: %s", exc)
        result.details.append(f"Analysis error: {exc}")
    return result


def analyze_emissive_or_height(image: np.ndarray) -> AuxAnalysisResult:
    result = AuxAnalysisResult(role="emissive_height")
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        val_range = float(gray.max()) - float(gray.min())
        if val_range < 10:
            result.details.append(f"Very narrow value range: {val_range:.0f}")
            result.anomaly_score = 0.2

        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)
        grad_std = float(grad_mag.std())
        if grad_std > 50:
            result.details.append(f"High gradient variance: {grad_std:.1f}")
            result.anomaly_score = max(result.anomaly_score, 0.3)

    except Exception as exc:
        logger.warning("Emissive/height analysis failed: %s", exc)
        result.details.append(f"Analysis error: {exc}")
    return result
