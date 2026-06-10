from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from ..scanner.file_scanner import AssetFile, scan_assets
from ..scanner.fbx_scanner import scan_fbx, FbxAssetResult
from ..metadata.signatures import MetadataFinding, load_signatures, scan_text_for_ai_signals
from ..metadata.exif_analyzer import extract_exif
from ..metadata.png_chunks import parse_png_text_chunks
from ..metadata.c2pa_checker import check_c2pa
from ..metadata.xmp_parser import extract_xmp
from ..metadata.aicheck_runner import run_aicheck
from ..forensics.ela import compute_ela
from ..forensics.frequency import compute_frequency_analysis
from ..forensics.noise import compute_noise_consistency
from ..forensics.color_stats import compute_color_stats
from ..forensics.jpeg_forensics import analyze_jpeg_quantization
from ..forensics.tiling import compute_tiling_analysis
from ..models.base import BaseDetector
from ..models.ensemble import EnsembleDetector, EnsembleResult
from ..models import MODEL_REGISTRY
from .scorer import (
    ScoreComponents,
    ModelConsensus,
    compute_final_score,
    compute_model_consensus,
    label_from_score,
    texture_model_weight_factor,
    texture_model_weight_overrides,
)
from .texture_grouping import apply_material_group_review, parse_texture_role

logger = logging.getLogger(__name__)


@dataclass
class AssetResult:
    file_id: str
    relative_path: str
    asset_type: str
    size_bytes: int
    dimensions: str | None = None
    metadata: dict = field(default_factory=dict)
    forensics: dict = field(default_factory=dict)
    mesh_info: dict | None = None
    models: dict = field(default_factory=dict)
    final_label: str = "Inconclusive"
    confidence: float = 0.0
    review_required: bool = False
    evidence: list[str] = field(default_factory=list)


def _build_ensemble(config: dict) -> EnsembleDetector | None:
    models_config = config.get("models", {})
    if not models_config.get("enabled", False):
        return None

    device = models_config.get("device", "cpu")
    ensemble = EnsembleDetector()

    for model_key, detector_cls in MODEL_REGISTRY.items():
        model_cfg = models_config.get(model_key, {})
        if not isinstance(model_cfg, dict):
            continue
        if not model_cfg.get("enabled", False):
            continue

        path = model_cfg.get("path", f"./models/{model_key}")
        weight = model_cfg.get("weight", 0.1)
        detector = detector_cls(path, device=device, weight=weight)
        if detector.is_available():
            ensemble.add(detector)
            logger.info("Registered %s (weight=%.2f)", model_key, weight)

    return ensemble if ensemble.detectors else None


def _scan_metadata(asset: AssetFile, signatures: dict, config: dict) -> tuple[float, list[str], dict]:
    signals: list[str] = []
    metadata_info: dict = {}
    tool_detected = False

    meta_config = config.get("metadata", {})
    exiftool_path = meta_config.get("exiftool_path")
    c2patool_path = meta_config.get("c2patool_path")
    aicheck_path = meta_config.get("aicheck_path")

    raw_bytes = asset.path.read_bytes()[:1024 * 1024]
    text = raw_bytes.decode("utf-8", errors="ignore")
    text_finding = scan_text_for_ai_signals(text, signatures)
    if text_finding.signals:
        signals.extend(text_finding.signals)
    if text_finding.tool_detected:
        tool_detected = True
        metadata_info["tool_detected"] = text_finding.tool_detected

    if asset.extension == ".png":
        png_result = parse_png_text_chunks(asset.path)
        if png_result.is_png and png_result.chunks:
            all_text = " ".join(c.text for c in png_result.chunks)
            chunk_finding = scan_text_for_ai_signals(all_text, signatures)
            if chunk_finding.signals:
                signals.extend(chunk_finding.signals)
            if chunk_finding.tool_detected:
                tool_detected = True

    xmp_result = extract_xmp(asset.path)
    if xmp_result.found:
        metadata_info["xmp_found"] = True
        if xmp_result.creator_tool:
            metadata_info["creator_tool"] = xmp_result.creator_tool
            xmp_finding = scan_text_for_ai_signals(xmp_result.creator_tool, signatures)
            if xmp_finding.signals:
                signals.extend(xmp_finding.signals)
                tool_detected = True

    exif_result = extract_exif(asset.path, exiftool_path=exiftool_path)
    if exif_result.success:
        metadata_info["exif_detected"] = True
        if exif_result.software:
            metadata_info["software"] = exif_result.software
            exif_finding = scan_text_for_ai_signals(exif_result.software, signatures)
            if exif_finding.signals:
                signals.extend(exif_finding.signals)
                tool_detected = True

    c2pa_result = check_c2pa(asset.path, c2patool_path=c2patool_path)
    metadata_info["c2pa_detected"] = c2pa_result.detected
    if c2pa_result.ai_related:
        signals.extend(c2pa_result.signals)
        tool_detected = True

    aicheck_result = run_aicheck(asset.path, aicheck_path=aicheck_path)
    metadata_info["aicheck_ai_marker"] = aicheck_result.ai_marker
    if aicheck_result.ai_marker:
        signals.extend(aicheck_result.signals)
        tool_detected = True

    if tool_detected and signals:
        score = 1.0
    elif len(signals) >= 2:
        score = 0.8
    elif signals:
        score = 0.6
    else:
        score = 0.0

    metadata_info["signals"] = signals
    return score, signals, metadata_info


def _run_forensics(image: np.ndarray, config: dict) -> tuple[float, dict]:
    forensics_config = config.get("forensics", {})
    if not forensics_config.get("enabled", True):
        return 0.0, {}

    results: dict = {}
    scores: list[float] = []

    if forensics_config.get("ela", {}).get("enabled", True):
        quality = forensics_config.get("ela", {}).get("quality", 90)
        ela_result = compute_ela(image, quality=quality)
        results["ela_uniformity"] = ela_result.uniformity
        if not ela_result.error:
            scores.append(ela_result.uniformity)

    if forensics_config.get("frequency", {}).get("enabled", True):
        freq_result = compute_frequency_analysis(image)
        results["frequency_anomaly"] = freq_result.anomaly_score
        if not freq_result.error:
            scores.append(freq_result.anomaly_score)

    if forensics_config.get("noise", {}).get("enabled", True):
        noise_result = compute_noise_consistency(image)
        results["noise_consistency"] = noise_result.consistency
        if not noise_result.error:
            scores.append(noise_result.consistency)

    if forensics_config.get("color_stats", {}).get("enabled", True):
        color_result = compute_color_stats(image)
        results["color_smoothness"] = color_result.smoothness
        if not color_result.error:
            scores.append(color_result.smoothness)

    if forensics_config.get("tiling", {}).get("enabled", True):
        tiling_thresh = forensics_config.get("tiling", {}).get("threshold", 0.3)
        tiling_result = compute_tiling_analysis(image, threshold=tiling_thresh)
        results["tiling_score"] = tiling_result.tiling_score
        results["tiling_period"] = f"{tiling_result.period_x}x{tiling_result.period_y}"
        results["tiling_suspicious"] = tiling_result.suspicious

    combined = sum(scores) / len(scores) if scores else 0.0
    results["combined_score"] = round(combined, 4)
    return combined, results


def _ndarray_to_pil(image: np.ndarray):
    """Convert cv2 BGR numpy array to PIL RGB Image for model inference."""
    from PIL import Image
    if len(image.shape) == 2:
        return Image.fromarray(image)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def _extract_crops(image: np.ndarray, crop_size: int = 512, max_crops: int = 5) -> list[np.ndarray]:
    """Extract center + corner crops from large images for multi-crop TTA."""
    h, w = image.shape[:2]
    if h <= crop_size or w <= crop_size:
        return [image]

    crops = []
    cy, cx = h // 2, w // 2
    half = crop_size // 2

    # Center crop
    crops.append(image[cy - half:cy + half, cx - half:cx + half])
    # Top-left
    crops.append(image[:crop_size, :crop_size])
    # Top-right
    crops.append(image[:crop_size, w - crop_size:])
    # Bottom-left
    crops.append(image[h - crop_size:, :crop_size])
    # Bottom-right
    crops.append(image[h - crop_size:, w - crop_size:])

    return crops[:max_crops]


def _run_model_inference(image: np.ndarray, ensemble: EnsembleDetector, weight_overrides: dict[str, float] | None = None) -> tuple[float, dict]:
    h, w = image.shape[:2]
    use_multicrop = h >= 1024 and w >= 1024

    if not use_multicrop:
        pil_image = _ndarray_to_pil(image)
        ensemble_result = ensemble.predict(pil_image, weight_overrides=weight_overrides)
        model_info: dict = {}
        for name, det_result in ensemble_result.model_results.items():
            model_info[name] = det_result.score if det_result.available else None
        return ensemble_result.weighted_score, model_info

    crops = _extract_crops(image)
    all_scores: list[float] = []
    all_model_scores: dict[str, list[float]] = {}

    for crop in crops:
        pil_crop = _ndarray_to_pil(crop)
        result = ensemble.predict(pil_crop, weight_overrides=weight_overrides)
        all_scores.append(result.weighted_score)
        for name, det_result in result.model_results.items():
            if det_result.available and det_result.error is None:
                all_model_scores.setdefault(name, []).append(det_result.score)

    model_info = {}
    for name, scores in all_model_scores.items():
        model_info[name] = max(scores)

    # Use max of crop scores as final (conservative — catches AI patches)
    weighted_score = max(all_scores) if all_scores else 0.0
    return weighted_score, model_info


def _adjust_model_score_for_asset(score: float, relative_path: str, config: dict) -> tuple[float, float]:
    texture_cfg = config.get("models", {}).get("texture_weighting", {})
    if not texture_cfg.get("enabled", True):
        return score, 1.0

    factor = texture_model_weight_factor(relative_path)
    return round(score * factor, 4), factor


def _process_image_asset(
    asset: AssetFile,
    signatures: dict,
    config: dict,
    meta_score: float,
    meta_signals: list[str],
    metadata_info: dict,
    ensemble: EnsembleDetector | None,
    thresholds: dict,
) -> AssetResult:
    evidence: list[str] = list(meta_signals)
    texture_role = parse_texture_role(asset.relative_path)
    is_auxiliary = texture_role.role in ("normal", "packed", "emissive", "height")

    image = cv2.imread(str(asset.path))
    if image is None:
        try:
            from PIL import Image
            pil_img = Image.open(asset.path).convert("RGB")
            image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception:
            pass
    if image is None:
        return AssetResult(
            file_id=f"sha256:{asset.sha256}",
            relative_path=asset.relative_path,
            asset_type=asset.asset_type,
            size_bytes=asset.size_bytes,
            metadata=metadata_info,
            final_label="Inconclusive",
            evidence=["Cannot open image with OpenCV"],
        )

    h, w = image.shape[:2]
    dims = f"{w}x{h}"

    forensics_score, forensics_info = _run_forensics(image, config)
    if forensics_score > 0.7:
        evidence.append("Pixel forensics abnormal")

    model_score = 0.0
    model_info: dict = {}
    consensus = None
    if ensemble:
        weight_ov = texture_model_weight_overrides(asset.relative_path)
        raw_model_score, model_info = _run_model_inference(image, ensemble, weight_overrides=weight_ov)
        raw_model_score, model_factor = _adjust_model_score_for_asset(
            raw_model_score,
            asset.relative_path,
            config,
        )
        model_info["_weighted_score"] = raw_model_score
        model_info["_texture_weight_factor"] = model_factor

        consensus = compute_model_consensus(model_info)
        model_info["_consensus"] = consensus.agreement
        model_info["_high_count"] = consensus.high_score_count
        model_info["_available_count"] = consensus.available_count
        model_info["_divergence"] = consensus.divergence

        if is_auxiliary:
            model_score = 0.0
            evidence.append("Auxiliary texture: AI scoring deferred to group review")
        else:
            model_score = raw_model_score
            if consensus.agreement in ("unanimous_high", "majority_high"):
                evidence.append("Model ensemble high confidence")
            elif consensus.agreement == "split" and model_score > 0.5:
                evidence.append("Model scores split (needs review)")

    if forensics_info.get("tiling_suspicious", False) and model_score > 0.5 and forensics_score > 0.5:
        if texture_role.role in ("albedo", "unknown"):
            evidence.append("Tiling pattern detected (auxiliary)")

    consensus_obj = consensus if ensemble and model_score > 0 else None
    components = ScoreComponents(
        metadata_score=meta_score,
        forensics_score=forensics_score,
        model_score=model_score,
        metadata_confirmed=meta_score >= 1.0,
        consensus=consensus_obj,
    )
    final_score = compute_final_score(components)
    label = label_from_score(final_score, thresholds or None)
    review = label in {"Confirmed AI", "Likely AI", "Suspicious"}

    if not evidence:
        evidence.append("No significant AI evidence found")

    return AssetResult(
        file_id=f"sha256:{asset.sha256}",
        relative_path=asset.relative_path,
        asset_type=asset.asset_type,
        size_bytes=asset.size_bytes,
        dimensions=dims,
        metadata=metadata_info,
        forensics=forensics_info,
        models=model_info,
        final_label=label,
        confidence=final_score,
        review_required=review,
        evidence=evidence,
    )


def _process_mesh_asset(
    asset: AssetFile,
    signatures: dict,
    config: dict,
    meta_score: float,
    meta_signals: list[str],
    metadata_info: dict,
) -> AssetResult:
    evidence: list[str] = list(meta_signals)

    fbx_result = scan_fbx(asset.path)

    if fbx_result.error:
        return AssetResult(
            file_id=f"sha256:{asset.sha256}",
            relative_path=asset.relative_path,
            asset_type=asset.asset_type,
            size_bytes=asset.size_bytes,
            metadata=metadata_info,
            final_label="Inconclusive",
            evidence=[f"FBX scan failed: {fbx_result.error}"],
        )

    evidence.extend(fbx_result.signals)

    mesh_score = fbx_result.topology_score
    mesh_info = {
        "mesh_count": fbx_result.mesh_count,
        "total_vertices": fbx_result.total_vertices,
        "total_faces": fbx_result.total_faces,
        "material_count": fbx_result.material_count,
        "texture_count": fbx_result.texture_count,
        "topology_score": fbx_result.topology_score,
        "signals": fbx_result.signals,
    }

    components = ScoreComponents(
        metadata_score=meta_score,
        forensics_score=0.0,
        model_score=mesh_score,
        metadata_confirmed=meta_score >= 1.0,
    )
    final_score = compute_final_score(components)
    label = label_from_score(final_score, config.get("thresholds", None))
    review = label in {"Confirmed AI", "Likely AI", "Suspicious"} or bool(fbx_result.signals)

    if not evidence:
        evidence.append("No significant AI evidence found in mesh")

    return AssetResult(
        file_id=f"sha256:{asset.sha256}",
        relative_path=asset.relative_path,
        asset_type=asset.asset_type,
        size_bytes=asset.size_bytes,
        metadata=metadata_info,
        mesh_info=mesh_info,
        final_label=label,
        confidence=final_score,
        review_required=review,
        evidence=evidence,
    )


def run_pipeline(input_path: str | Path, config: dict) -> list[AssetResult]:
    signatures_file = config.get("metadata", {}).get("signatures_file", "./config/signatures.yaml")
    signatures = load_signatures(signatures_file)
    thresholds = config.get("thresholds", {})

    ensemble = _build_ensemble(config)
    results: list[AssetResult] = []

    meta_enabled = config.get("metadata", {}).get("enabled", True)

    for asset in scan_assets(input_path, config):
        if meta_enabled:
            meta_score, meta_signals, metadata_info = _scan_metadata(asset, signatures, config)
        else:
            meta_score, meta_signals, metadata_info = 0.0, [], {}

        if meta_score >= 1.0:
            results.append(AssetResult(
                file_id=f"sha256:{asset.sha256}",
                relative_path=asset.relative_path,
                asset_type=asset.asset_type,
                size_bytes=asset.size_bytes,
                metadata=metadata_info,
                final_label="Confirmed AI",
                confidence=1.0,
                review_required=True,
                evidence=meta_signals + ["Metadata confirms AI generation"],
            ))
            continue

        if asset.asset_type in ("threed",):
            result = _process_mesh_asset(
                asset, signatures, config,
                meta_score, meta_signals, metadata_info,
            )
        elif asset.asset_type == "image":
            result = _process_image_asset(
                asset, signatures, config,
                meta_score, meta_signals, metadata_info,
                ensemble, thresholds,
            )
        else:
            result = AssetResult(
                file_id=f"sha256:{asset.sha256}",
                relative_path=asset.relative_path,
                asset_type=asset.asset_type,
                size_bytes=asset.size_bytes,
                final_label="Inconclusive",
                evidence=["Unsupported asset type, no processing path available"],
            )

        results.append(result)

    if config.get("models", {}).get("material_group_review", {}).get("enabled", True):
        apply_material_group_review(results)

    logger.info("Pipeline complete: %d assets processed", len(results))
    return results
