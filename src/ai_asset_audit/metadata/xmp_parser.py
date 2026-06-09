from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

XMP_START = b"<x:xmpmeta"
XMP_END = b"</x:xmpmeta>"

CREATOR_TOOL_PATTERN = re.compile(r"<xmp:CreatorTool>(.*?)</xmp:CreatorTool>", re.DOTALL)
SOFTWARE_PATTERN = re.compile(r"<tiff:Software>(.*?)</tiff:Software>", re.DOTALL)
DESCRIPTION_PATTERN = re.compile(r"<dc:description>.*?<rdf:li[^>]*>(.*?)</rdf:li>", re.DOTALL)
HISTORY_ACTION_PATTERN = re.compile(r"stEvt:action=\"(.*?)\"", re.DOTALL)
HISTORY_SOFTWARE_PATTERN = re.compile(r"stEvt:softwareAgent=\"(.*?)\"", re.DOTALL)


@dataclass
class XmpResult:
    found: bool = False
    creator_tool: str | None = None
    software: str | None = None
    description: str | None = None
    history_actions: list[str] = field(default_factory=list)
    history_software: list[str] = field(default_factory=list)
    raw_xmp: str | None = None
    error: str | None = None


def extract_xmp(path: Path) -> XmpResult:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return XmpResult(error=str(exc))

    start = data.find(XMP_START)
    if start == -1:
        return XmpResult(found=False)

    end = data.find(XMP_END, start)
    if end == -1:
        return XmpResult(found=False)

    xmp_bytes = data[start : end + len(XMP_END)]
    xmp_text = xmp_bytes.decode("utf-8", errors="replace")

    creator_tool = None
    m = CREATOR_TOOL_PATTERN.search(xmp_text)
    if m:
        creator_tool = m.group(1).strip()

    software = None
    m = SOFTWARE_PATTERN.search(xmp_text)
    if m:
        software = m.group(1).strip()

    description = None
    m = DESCRIPTION_PATTERN.search(xmp_text)
    if m:
        description = m.group(1).strip()

    history_actions = HISTORY_ACTION_PATTERN.findall(xmp_text)
    history_software = HISTORY_SOFTWARE_PATTERN.findall(xmp_text)

    return XmpResult(
        found=True,
        creator_tool=creator_tool,
        software=software,
        description=description,
        history_actions=history_actions,
        history_software=history_software,
        raw_xmp=xmp_text,
    )
