"""HEIC/HEIF handler (optional, needs ``pillow-heif``).

Cleaning re-encodes the image losslessly from its decoded pixels, which can
make the file larger. HDR/10-bit data and depth maps are not preserved.
"""

from __future__ import annotations

import io
from typing import Any

from PIL import Image

from metastrip.core import exif_codec
from metastrip.core.errors import CorruptFileError, UnsupportedFormatError, UnsupportedOperationError
from metastrip.core.handlers.base import FormatHandler
from metastrip.core.models import RawEntry


def _open(data: bytes) -> Image.Image:
    try:
        import pillow_heif
    except ImportError:
        raise UnsupportedFormatError(
            "HEIC support needs pillow-heif: pip install 'metadata-stripper[heic]'"
        ) from None
    pillow_heif.register_heif_opener()
    try:
        return Image.open(io.BytesIO(data))
    except Exception as exc:
        raise CorruptFileError(f"Unreadable HEIC: {exc}") from exc


class HeicHandler(FormatHandler):
    name = "HEIC"
    supports_selective = False

    def read(self, data: bytes) -> list[RawEntry]:
        img = _open(data)
        blob = img.info.get("exif")
        if not blob:
            return []
        try:
            return exif_codec.entries(exif_codec.load(blob))
        except CorruptFileError:
            return [RawEntry("Image", "Unreadable EXIF", f"<{len(blob)} bytes>")]

    def strip(self, data: bytes, remove_ids: frozenset[str] | None, keep_orientation: bool) -> bytes:
        if remove_ids is not None:
            raise UnsupportedOperationError("HEIC files support removing all metadata only")
        img = _open(data)
        img.load()
        # pillow-heif already applies the rotation flag to the decoded pixels,
        # so there is nothing to preserve for keep_orientation.
        clean = Image.frombytes(img.mode, img.size, img.tobytes())
        options: dict[str, Any] = {"quality": -1}
        for key in ("icc_profile", "nclx_profile"):
            if img.info.get(key):
                options[key] = img.info[key]
        out = io.BytesIO()
        clean.save(out, "HEIF", **options)
        return out.getvalue()
