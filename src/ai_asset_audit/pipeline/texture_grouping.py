from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pipeline import AssetResult, LayerVerdict


@dataclass(frozen=True)
class TextureRole:
    group_key: str
    role: str
    suffix: str


_ROLE_BY_SUFFIX = {
    "d": "albedo",
    "diff": "albedo",
    "diffuse": "albedo",
    "albedo": "albedo",
    "basecolor": "albedo",
    "base_color": "albedo",
    "n": "normal",
    "normal": "normal",
    "mads": "packed",
    "orm": "packed",
    "rma": "packed",
    "mask": "packed",
    "e": "emissive",
    "emissive": "emissive",
    "h": "height",
    "height": "height",
    "ao": "packed",
    "roughness": "packed",
    "metallic": "packed",
}

_AUXILIARY_ROLES = {"normal", "packed", "emissive", "height"}
_RISK_LABELS = {"Confirmed AI", "Likely AI", "Suspicious"}


def parse_texture_role(relative_path: str) -> TextureRole:
    stem = Path(relative_path).stem
    if "_" not in stem:
        return TextureRole(group_key=stem, role="unknown", suffix="")

    group_key, suffix = stem.rsplit("_", 1)
    role = _ROLE_BY_SUFFIX.get(suffix.lower(), "unknown")
    if role == "unknown":
        group_key = stem
    return TextureRole(group_key=group_key, role=role, suffix=suffix)


def apply_material_group_review(results: list[AssetResult]) -> None:
    groups: dict[str, list[AssetResult]] = {}
    roles: dict[str, TextureRole] = {}

    for result in results:
        if result.asset_type != "image":
            continue
        role = parse_texture_role(result.relative_path)
        roles[result.relative_path] = role
        result.metadata.setdefault("material_group", role.group_key)
        result.metadata.setdefault("texture_role", role.role)
        groups.setdefault(role.group_key, []).append(result)

    for group_results in groups.values():
        if len(group_results) < 2:
            _annotate_group_consensus(group_results, 0)
            continue

        albedos = [
            r for r in group_results
            if roles.get(r.relative_path, TextureRole("", "", "")).role == "albedo"
        ]
        auxiliaries = [
            r for r in group_results
            if roles.get(r.relative_path, TextureRole("", "", "")).role in _AUXILIARY_ROLES
        ]

        albedo_risky = [r for r in albedos if r.final_label in _RISK_LABELS]
        aux_risky = [r for r in auxiliaries if r.final_label in _RISK_LABELS]

        if albedo_risky:
            for aux in auxiliaries:
                if aux.final_label not in _RISK_LABELS:
                    aux.review_required = True
                    aux.asset_attributes.append(
                        "Albedo in same material group flagged — review recommended"
                    )
            group_conclusion = "flagged"
            group_detail = f"{len(albedo_risky)} albedo(s) flagged, auxiliary textures marked for review"
        elif aux_risky and not albedo_risky:
            for suspect in aux_risky:
                suspect.final_label = "Likely Human"
                suspect.review_required = True
                suspect.confidence = min(suspect.confidence, 0.44)
                suspect.asset_attributes.append(
                    "Isolated auxiliary texture suspicion downgraded by material group review"
                )
            group_conclusion = "downgraded"
            group_detail = f"{len(aux_risky)} isolated auxiliary suspicion(s) downgraded"
        else:
            group_conclusion = "clean"
            group_detail = "No group-level risk signals"

        risky_count = len(albedo_risky) + len(aux_risky)
        _annotate_group_consensus(group_results, risky_count)

        from .pipeline import LayerVerdict
        for r in group_results:
            r.layer_verdicts.append(LayerVerdict(
                "group", group_conclusion, group_detail, float(risky_count),
            ))


def _annotate_group_consensus(results: list[AssetResult], risky_count: int) -> None:
    group_size = len(results)
    for result in results:
        result.metadata.setdefault("material_group_size", group_size)
        result.metadata.setdefault("material_group_risky_count", risky_count)
