from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .pipeline import run_pipeline

logger = logging.getLogger(__name__)

GROUND_TRUTH_LABELS = {
    "human": 0.0,
    "ai_generated": 1.0,
    "ai_assisted": 0.7,
    "false_positive": 0.0,
}


@dataclass
class CalibrationResult:
    total_samples: int = 0
    per_category: dict = field(default_factory=dict)
    recommended_thresholds: dict = field(default_factory=dict)
    current_thresholds: dict = field(default_factory=dict)
    confusion: dict = field(default_factory=dict)


def _category_stats(category_dir: Path, category: str, gt: float, config: dict) -> tuple[str, dict | None, list[tuple[float, float]]]:
    results = run_pipeline(str(category_dir), config)
    scores = [r.confidence for r in results]

    if not scores:
        return category, None, []

    arr = np.array(scores)
    stats = {
        "count": len(scores),
        "ground_truth": gt,
        "min": round(float(arr.min()), 4),
        "max": round(float(arr.max()), 4),
        "median": round(float(np.median(arr)), 4),
        "p25": round(float(np.percentile(arr, 25)), 4),
        "p75": round(float(np.percentile(arr, 75)), 4),
        "mean": round(float(arr.mean()), 4),
    }

    return category, stats, [(s, gt) for s in scores]


def run_calibration(benchmark_dir: str | Path, config: dict) -> CalibrationResult:
    benchmark = Path(benchmark_dir)
    if not benchmark.is_dir():
        raise FileNotFoundError(f"Benchmark directory not found: {benchmark}")

    all_scores: list[tuple[float, float]] = []
    per_category: dict[str, dict] = {}
    jobs: list[tuple[Path, str, float]] = []

    for category_dir in sorted(benchmark.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        if category not in GROUND_TRUTH_LABELS:
            logger.warning("Unknown category %s, skipping", category)
            continue

        gt = GROUND_TRUTH_LABELS[category]
        jobs.append((category_dir, category, gt))

    workers = int(config.get("calibration", {}).get("parallel_workers", 1) or 1)
    if workers > 1 and len(jobs) > 1:
        with ThreadPoolExecutor(max_workers=min(workers, len(jobs))) as executor:
            futures = [
                executor.submit(_category_stats, category_dir, category, gt, config)
                for category_dir, category, gt in jobs
            ]
            category_results = [future.result() for future in as_completed(futures)]
    else:
        category_results = [
            _category_stats(category_dir, category, gt, config)
            for category_dir, category, gt in jobs
        ]

    for category, stats, scores in sorted(category_results, key=lambda item: item[0]):
        if stats:
            per_category[category] = stats
        all_scores.extend(scores)

    if not all_scores:
        return CalibrationResult(per_category=per_category)

    recommended = _find_optimal_thresholds(all_scores)
    current = config.get("thresholds", {})

    confusion = _compute_confusion(all_scores, current)

    return CalibrationResult(
        total_samples=len(all_scores),
        per_category=per_category,
        recommended_thresholds=recommended,
        current_thresholds=current,
        confusion=confusion,
    )


def _find_optimal_thresholds(scores: list[tuple[float, float]]) -> dict:
    positives = [s for s, gt in scores if gt >= 0.5]
    negatives = [s for s, gt in scores if gt < 0.5]

    if not positives or not negatives:
        return {}

    pos_arr = np.array(positives)
    neg_arr = np.array(negatives)

    best_f1 = 0.0
    best_thresh = 0.5
    for t in np.arange(0.1, 0.95, 0.05):
        tp = int(np.sum(pos_arr >= t))
        fp = int(np.sum(neg_arr >= t))
        fn = int(np.sum(pos_arr < t))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = float(t)

    return {
        "suspicious": round(best_thresh * 0.6, 2),
        "likely_ai": round(best_thresh * 0.85, 2),
        "confirmed_ai": round(best_thresh, 2),
        "likely_human": round(best_thresh * 0.35, 2),
        "best_f1": round(best_f1, 4),
    }


def _compute_confusion(scores: list[tuple[float, float]], thresholds: dict) -> dict:
    suspicious_t = thresholds.get("suspicious", 0.45)
    tp = fp = tn = fn = 0
    for score, gt in scores:
        predicted_positive = score >= suspicious_t
        actual_positive = gt >= 0.5
        if predicted_positive and actual_positive:
            tp += 1
        elif predicted_positive and not actual_positive:
            fp += 1
        elif not predicted_positive and actual_positive:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}
