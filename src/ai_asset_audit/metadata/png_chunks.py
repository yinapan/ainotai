from __future__ import annotations

import logging
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
TEXT_CHUNK_TYPES = {b"tEXt", b"iTXt", b"zTXt"}


@dataclass
class PngTextChunk:
    chunk_type: str
    keyword: str
    text: str


@dataclass
class PngChunkResult:
    is_png: bool = False
    chunks: list[PngTextChunk] = field(default_factory=list)
    error: str | None = None


def _read_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    if not data.startswith(PNG_SIGNATURE):
        return []

    pos = 8
    chunks: list[tuple[bytes, bytes]] = []
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        chunks.append((chunk_type, chunk_data))
        pos += 12 + length
        if chunk_type == b"IEND":
            break
    return chunks


def _decode_text(chunk_type: bytes, chunk_data: bytes) -> PngTextChunk | None:
    ct = chunk_type.decode("ascii", errors="replace")
    try:
        if chunk_type == b"tEXt":
            sep = chunk_data.index(0)
            keyword = chunk_data[:sep].decode("latin-1")
            text = chunk_data[sep + 1 :].decode("latin-1")
            return PngTextChunk(chunk_type=ct, keyword=keyword, text=text)

        if chunk_type == b"zTXt":
            sep = chunk_data.index(0)
            keyword = chunk_data[:sep].decode("latin-1")
            compressed = chunk_data[sep + 2 :]
            text = zlib.decompress(compressed).decode("latin-1")
            return PngTextChunk(chunk_type=ct, keyword=keyword, text=text)

        if chunk_type == b"iTXt":
            sep = chunk_data.index(0)
            keyword = chunk_data[:sep].decode("utf-8")
            rest = chunk_data[sep + 1 :]
            compression_flag = rest[0] if rest else 0
            text_start = 0
            null_count = 0
            for i, b in enumerate(rest):
                if b == 0:
                    null_count += 1
                    if null_count >= 3:
                        text_start = i + 1
                        break
            raw = rest[text_start:]
            if compression_flag:
                text = zlib.decompress(raw).decode("utf-8", errors="replace")
            else:
                text = raw.decode("utf-8", errors="replace")
            return PngTextChunk(chunk_type=ct, keyword=keyword, text=text)
    except Exception as exc:
        logger.debug("Failed to decode %s chunk: %s", ct, exc)
        return None
    return None


def parse_png_text_chunks(path: Path) -> PngChunkResult:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return PngChunkResult(error=str(exc))

    if not data.startswith(PNG_SIGNATURE):
        return PngChunkResult(is_png=False)

    chunks: list[PngTextChunk] = []
    for chunk_type, chunk_data in _read_chunks(data):
        if chunk_type in TEXT_CHUNK_TYPES:
            decoded = _decode_text(chunk_type, chunk_data)
            if decoded:
                chunks.append(decoded)

    return PngChunkResult(is_png=True, chunks=chunks)
