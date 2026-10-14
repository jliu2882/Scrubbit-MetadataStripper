"""TIFF handler (single-page). Cleaning re-writes the file losslessly."""

from __future__ import annotations

import io
from typing import Any

from PIL import ExifTags, Image, TiffTags

from metastrip.core import exif_codec
from metastrip.core.errors import CorruptFileError, UnsupportedOperationError
from metastrip.core.handlers.base import FormatHandler
from metastrip.core.models import RawEntry

_TAG_ORIENTATION = 274
_TAG_EXIF_IFD = 0x8769
_TAG_GPS_IFD = 0x8825
_TAG_XMP = 700
_TAG_IPTC = 33723
_TAG_PHOTOSHOP = 34377

#: Base-IFD tags that carry personal information (everything else is structural).
_BASE_TAGS = {269, 270, 271, 272, _TAG_ORIENTATION, 285, 305, 306, 315, 316, 33432}
_LOSSY = {"jpeg", "tiff_jpeg"}


def _open(data: bytes) -> Image.Image:
    try:
        return Image.open(io.BytesIO(data))
    except Exception as exc:
        raise CorruptFileError(f"Unreadable TIFF: {exc}") from exc


def _fmt(value: Any) -> str:
    if isinstance(value, (bytes, tuple)):
        return exif_codec.format_value(value)
    return str(float(value)) if hasattr(value, "numerator") and not isinstance(value, int) else str(value)


class TiffHandler(FormatHandler):
    name = "TIFF"
    supports_selective = False

    def read(self, data: bytes) -> list[RawEntry]:
        img = _open(data)
        result: list[RawEntry] = []
        tags = getattr(img, "tag_v2", {})
        for tag in sorted(tags.keys()):
            if tag in _BASE_TAGS:
                name = TiffTags.lookup(tag).name
                result.append(RawEntry("Image", name, _fmt(tags[tag])))
        if _TAG_XMP in tags:
            result.append(RawEntry("XMP", "Packet", f"<{len(tags[_TAG_XMP])} bytes>"))
        for tag in (_TAG_IPTC, _TAG_PHOTOSHOP):
            if tag in tags:
                result.append(RawEntry("IPTC", "Photoshop Block", "<embedded>"))
                break
        try:
            exif = img.getexif()
            for ifd_tag, group, table in (
                (_TAG_EXIF_IFD, "Exif", ExifTags.TAGS),
                (_TAG_GPS_IFD, "GPS", ExifTags.GPSTAGS),
            ):
                ifd = exif.get_ifd(ifd_tag)
                for tag in sorted(ifd):
                    result.append(RawEntry(group, table.get(tag, f"Tag0x{tag:04X}"), _fmt(ifd[tag])))
        except Exception as exc:
            raise CorruptFileError(f"Unreadable TIFF metadata: {exc}") from exc
        return result

    def strip(self, data: bytes, remove_ids: frozenset[str] | None, keep_orientation: bool) -> bytes:
        if remove_ids is not None:
            raise UnsupportedOperationError("TIFF files support removing all metadata only")
        img = _open(data)
        if getattr(img, "n_frames", 1) > 1:
            raise UnsupportedOperationError("Multi-page TIFF files are not supported")
        img.load()
        # Newer Pillow applies the rotation while loading and deletes the tag, so
        # the pixels are already upright. Only write the tag back if it survived.
        orientation = int(img.tag_v2.get(_TAG_ORIENTATION, 1))

        clean = Image.frombytes(img.mode, img.size, img.tobytes())
        if img.mode == "P" and img.getpalette():
            clean.putpalette(img.getpalette())

        options: dict[str, Any] = {}
        compression = img.info.get("compression")
        if compression and compression != "raw":
            options["compression"] = "tiff_adobe_deflate" if compression in _LOSSY else compression
        if img.info.get("icc_profile"):
            options["icc_profile"] = img.info["icc_profile"]
        if img.info.get("dpi"):
            options["dpi"] = img.info["dpi"]
        if keep_orientation and orientation not in (0, 1):
            options["tiffinfo"] = {_TAG_ORIENTATION: orientation}

        out = io.BytesIO()
        try:
            clean.save(out, "TIFF", **options)
        except (OSError, ValueError, KeyError):
            options.pop("compression", None)
            out = io.BytesIO()
            clean.save(out, "TIFF", **options)
        return out.getvalue()
