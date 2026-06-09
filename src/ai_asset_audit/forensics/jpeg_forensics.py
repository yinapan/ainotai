from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

STANDARD_LUMINANCE_TABLE = [
    16, 11, 10, 16, 24, 40, 51, 61,
    12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56,
    14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77,
    24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101,
    72, 92, 95, 98, 112, 100, 103, 99,
]


@dataclass
class JpegForensicsResult:
    is_jpeg: bool = False
    quantization_tables: list[list[int]] = field(default_factory=list)
    estimated_quality: int | None = None
    camera_likely: bool = False
    error: str | None = None


def _extract_quantization_tables(data: bytes) -> list[list[int]]:
    tables: list[list[int]] = []
    pos = 0
    while pos < len(data) - 1:
        if data[pos] != 0xFF:
            pos += 1
            continue
        marker = data[pos + 1]
        if marker == 0xDB:
            if pos + 4 >= len(data):
                break
            length = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
            segment = data[pos + 4 : pos + 2 + length]
            offset = 0
            while offset < len(segment):
                precision_id = segment[offset]
                offset += 1
                if (precision_id >> 4) & 0x0F == 0:
                    table_size = 64
                    if offset + table_size > len(segment):
                        break
                    table = list(segment[offset : offset + table_size])
                else:
                    table_size = 128
                    if offset + table_size > len(segment):
                        break
                    table = [
                        struct.unpack(">H", segment[offset + i : offset + i + 2])[0]
                        for i in range(0, table_size, 2)
                    ]
                tables.append(table)
                offset += table_size
            pos += 2 + length
        elif marker == 0xDA:
            break
        elif marker in (0x00, 0xFF):
            pos += 1
        else:
            if pos + 4 < len(data):
                try:
                    length = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
                    pos += 2 + length
                except struct.error:
                    pos += 2
            else:
                pos += 2
    return tables


def _estimate_quality(table: list[int]) -> int:
    if len(table) != 64:
        return -1
    ratio = sum(table) / sum(STANDARD_LUMINANCE_TABLE)
    if ratio <= 0:
        return 100
    if ratio < 1:
        quality = int(50 / ratio)
    else:
        quality = int(50 * (2 - ratio))
    return max(1, min(100, quality))


def analyze_jpeg_quantization(path: Path) -> JpegForensicsResult:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return JpegForensicsResult(error=str(exc))

    if not data.startswith(b"\xff\xd8\xff"):
        return JpegForensicsResult(is_jpeg=False)

    tables = _extract_quantization_tables(data)
    if not tables:
        return JpegForensicsResult(is_jpeg=True)

    quality = _estimate_quality(tables[0])
    camera_likely = 75 <= quality <= 98

    return JpegForensicsResult(
        is_jpeg=True,
        quantization_tables=tables,
        estimated_quality=quality if quality > 0 else None,
        camera_likely=camera_likely,
    )
