"""Format handlers and detection by file signature."""

from __future__ import annotations

from metastrip.core.errors import UnsupportedFormatError
from metastrip.core.handlers.base import FormatHandler
from metastrip.core.handlers.heic import HeicHandler
from metastrip.core.handlers.jpeg import JpegHandler
from metastrip.core.handlers.png import PngHandler
from metastrip.core.handlers.tiff import TiffHandler
from metastrip.core.handlers.webp import WebpHandler

SUPPORTED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic", ".heif"})

_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}


def detect(data: bytes) -> FormatHandler:
    """Pick a handler from the file's contents (not its extension)."""
    if data[:3] == b"\xff\xd8\xff":
        return JpegHandler()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return PngHandler()
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return WebpHandler()
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return TiffHandler()
    if data[4:8] == b"ftyp" and data[8:12] in _HEIF_BRANDS:
        return HeicHandler()
    raise UnsupportedFormatError("Unsupported or unrecognized file format")


__all__ = ["SUPPORTED_EXTENSIONS", "FormatHandler", "detect"]
