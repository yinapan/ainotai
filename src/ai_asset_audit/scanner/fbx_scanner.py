from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FbxMeshInfo:
    name: str = ""
    vertex_count: int = 0
    face_count: int = 0
    has_normals: bool = False
    has_uvs: bool = False
    material_names: list[str] = field(default_factory=list)
    texture_paths: list[str] = field(default_factory=list)


@dataclass
class FbxAssetResult:
    success: bool = False
    meshes: list[FbxMeshInfo] = field(default_factory=list)
    total_vertices: int = 0
    total_faces: int = 0
    material_count: int = 0
    texture_count: int = 0
    mesh_count: int = 0
    topology_score: float = 0.0
    signals: list[str] = field(default_factory=list)
    error: str | None = None


def _compute_topology_score(meshes: list[FbxMeshInfo]) -> float:
    """Heuristic: AI-generated meshes often have unusual vertex/face ratios."""
    signals: list[float] = []

    for mesh in meshes:
        if mesh.vertex_count == 0 or mesh.face_count == 0:
            continue
        ratio = mesh.face_count / mesh.vertex_count
        if 0.3 <= ratio <= 3.0:
            signals.append(0.0)
        else:
            signals.append(min(abs(ratio - 1.5) / 5.0, 1.0))

    if not signals:
        return 0.0

    return round(sum(signals) / len(signals), 4)


def _collect_signals(meshes: list[FbxMeshInfo]) -> list[str]:
    signals: list[str] = []
    for mesh in meshes:
        if len(mesh.name) > 200:
            signals.append(f"Suspicious mesh name length: {len(mesh.name)}")
        if mesh.vertex_count > 10_000_000:
            signals.append(f"Very high vertex count: {mesh.vertex_count:,}")
        if mesh.face_count > 0 and mesh.vertex_count > 0:
            ratio = mesh.face_count / mesh.vertex_count
            if ratio > 5.0 or ratio < 0.1:
                signals.append(f"Unusual face/vertex ratio: {ratio:.2f}")
    return signals


def scan_fbx(path: Path) -> FbxAssetResult:
    try:
        import fbxloader
    except ImportError:
        return FbxAssetResult(error="fbxloader not installed")

    try:
        data = path.read_bytes()
        fbx = fbxloader.load(data)
    except Exception as exc:
        logger.warning("fbxloader failed for %s: %s", path.name, exc)
        return FbxAssetResult(error=str(exc))

    meshes: list[FbxMeshInfo] = []
    total_vertices = 0
    total_faces = 0
    all_materials: set[str] = set()
    all_textures: set[str] = set()

    try:
        geom = getattr(fbx, "geometry", None) or getattr(fbx, "geometries", None)
        if geom is None:
            geom_attr = getattr(fbx, "objects", None)
            if geom_attr is not None and callable(geom_attr):
                geom = [o for o in geom_attr() if hasattr(o, "vertices")]
            else:
                geom = []

        for geo in geom:
            verts = getattr(geo, "vertices", None)
            faces = getattr(geo, "faces", None) or getattr(geo, "polygons", None)
            normals = getattr(geo, "normals", None)
            uvs = getattr(geo, "uvs", None) or getattr(geo, "uv", None)
            materials = getattr(geo, "materials", None) or []
            textures = getattr(geo, "textures", None) or []

            v_count = len(verts) if verts else 0
            f_count = len(faces) if faces else 0

            if v_count == 0 and f_count == 0:
                continue

            mat_names = [getattr(m, "name", str(m)) for m in materials]
            tex_paths = [getattr(t, "path", str(t)) for t in textures]

            meshes.append(FbxMeshInfo(
                name=getattr(geo, "name", ""),
                vertex_count=v_count,
                face_count=f_count,
                has_normals=normals is not None,
                has_uvs=uvs is not None,
                material_names=mat_names,
                texture_paths=tex_paths,
            ))

            total_vertices += v_count
            total_faces += f_count
            all_materials.update(mat_names)
            all_textures.update(tex_paths)

    except Exception as exc:
        logger.warning("FBX geometry extraction failed: %s", exc)
        return FbxAssetResult(error=f"Geometry extraction error: {exc}")

    if not meshes:
        return FbxAssetResult(error="No meshes found in FBX file")

    topology_score = _compute_topology_score(meshes)
    signals = _collect_signals(meshes)

    return FbxAssetResult(
        success=True,
        meshes=meshes,
        total_vertices=total_vertices,
        total_faces=total_faces,
        material_count=len(all_materials),
        texture_count=len(all_textures),
        mesh_count=len(meshes),
        topology_score=topology_score,
        signals=signals,
    )
