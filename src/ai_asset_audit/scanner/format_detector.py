from __future__ import annotations

from pathlib import Path

FORMAT_SIGNATURES: dict[str, list[tuple[int, bytes]]] = {
    "png": [(0, b"\x89PNG\r\n\x1a\n")],
    "jpeg": [(0, b"\xff\xd8\xff")],
    "webp": [(0, b"RIFF"), (8, b"WEBP")],
    "bmp": [(0, b"BM")],
    "gif": [(0, b"GIF8")],
    "tiff_le": [(0, b"II\x2a\x00")],
    "tiff_be": [(0, b"MM\x00\x2a")],
    "pdf": [(0, b"%PDF")],
    "glb": [(0, b"glTF")],
    "fbx_binary": [(0, b"Kaydara FBX Binary")],
    "blend": [(0, b"BLENDER")],
    "psd": [(0, b"8BPS")],
    "svg_xml": [(0, b"<?xml")],
    "svg_tag": [(0, b"<svg")],
    "onnx": [(0, b"\x08")],
}

ASCII_FBX_MARKERS = [
    b"FBXHeaderExtension",
    b"Objects",
    b"Connections",
    b"Takes",
    b"Version5",
]


def detect_format(path: Path) -> str | None:
    try:
        with path.open("rb") as f:
            header = f.read(4096)
    except OSError:
        return None

    if len(header) == 0:
        return None

    for fmt, checks in FORMAT_SIGNATURES.items():
        matched = True
        for offset, magic in checks:
            if offset + len(magic) > len(header):
                matched = False
                break
            if header[offset : offset + len(magic)] != magic:
                matched = False
                break
        if matched:
            return fmt

    if _is_ascii_fbx(header):
        return "fbx_ascii"

    if _is_obj(header):
        return "obj"

    return None


def _is_ascii_fbx(data: bytes) -> bool:
    try:
        text = data.decode("ascii", errors="ignore")
    except UnicodeDecodeError:
        return False

    markers_found = sum(
        1 for m in ASCII_FBX_MARKERS if m.decode("ascii") in text
    )
    return markers_found >= 3


def _is_obj(data: bytes) -> bool:
    try:
        text = data.decode("ascii", errors="ignore")
    except UnicodeDecodeError:
        return False

    for line in text.splitlines()[:50]:
        stripped = line.strip()
        if stripped.startswith("v ") or stripped.startswith("f ") or stripped.startswith("vn "):
            return True
    return False
