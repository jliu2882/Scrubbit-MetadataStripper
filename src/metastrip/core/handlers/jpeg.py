"""JPEG handler. Works on file segments, so pixel data is never re-encoded."""

from __future__ import annotations

from typing import NamedTuple

from metastrip.core import exif_codec
from metastrip.core.errors import CorruptFileError
from metastrip.core.handlers.base import FormatHandler
from metastrip.core.models import RawEntry

_EXIF_SIG = b"Exif\x00\x00"
_XMP_SIGS = (b"http://ns.adobe.com/xap/1.0/\x00", b"http://ns.adobe.com/xmp/extension/\x00")
_PHOTOSHOP_SIG = b"Photoshop 3.0\x00"
_SOS = 0xDA

XMP_ID = "XMP.Packet"
IPTC_ID = "IPTC.Photoshop Block"
COMMENT_ID = "Comment.JPEG Comment"


class _Segment(NamedTuple):
    marker: int
    start: int  # offset of the 0xFF byte
    end: int  # exclusive
    kind: str | None


def _classify(marker: int, payload: bytes) -> str | None:
    if marker == 0xE1:
        if payload.startswith(_EXIF_SIG):
            return "exif"
        if payload.startswith(_XMP_SIGS):
            return "xmp"
    elif marker == 0xED and payload.startswith(_PHOTOSHOP_SIG):
        return "iptc"
    elif marker == 0xFE:
        return "comment"
    return None


def _parse(data: bytes) -> tuple[list[_Segment], int]:
    """Split a JPEG into header segments; returns (segments, offset of SOS)."""
    if data[:2] != b"\xff\xd8":
        raise CorruptFileError("Not a valid JPEG (missing SOI marker)")
    segments: list[_Segment] = []
    pos, size = 2, len(data)
    while pos + 2 <= size:
        if data[pos] != 0xFF:
            raise CorruptFileError("Corrupt JPEG: expected a marker")
        marker = data[pos + 1]
        if marker == 0xFF:  # fill byte
            pos += 1
            continue
        if marker == _SOS:
            return segments, pos
        if marker == 0xD9 or marker == 0x01 or 0xD0 <= marker <= 0xD7:
            segments.append(_Segment(marker, pos, pos + 2, None))
            pos += 2
            continue
        if pos + 4 > size:
            raise CorruptFileError("Corrupt JPEG: truncated segment")
        length = int.from_bytes(data[pos + 2 : pos + 4], "big")
        end = pos + 2 + length
        if length < 2 or end > size:
            raise CorruptFileError("Corrupt JPEG: bad segment length")
        kind = _classify(marker, data[pos + 4 : min(end, pos + 4 + 32)])
        segments.append(_Segment(marker, pos, end, kind))
        pos = end
    raise CorruptFileError("Corrupt JPEG: no image data found")


def _app1(blob: bytes) -> bytes:
    if len(blob) + 2 > 0xFFFF:
        raise CorruptFileError("EXIF data too large to store in a JPEG")
    return b"\xff\xe1" + (len(blob) + 2).to_bytes(2, "big") + blob


class JpegHandler(FormatHandler):
    name = "JPEG"

    def read(self, data: bytes) -> list[RawEntry]:
        segments, _ = _parse(data)
        result: list[RawEntry] = []
        xmp_bytes = iptc_bytes = 0
        comments: list[str] = []
        exif_done = False
        for seg in segments:
            payload = data[seg.start + 4 : seg.end]
            if seg.kind == "exif" and not exif_done:
                exif_done = True
                try:
                    result.extend(exif_codec.entries(exif_codec.load(payload)))
                except CorruptFileError:
                    result.append(RawEntry("Image", "Unreadable EXIF", f"<{len(payload)} bytes>"))
            elif seg.kind == "xmp":
                xmp_bytes += len(payload)
            elif seg.kind == "iptc":
                iptc_bytes += len(payload)
            elif seg.kind == "comment":
                comments.append(payload.decode("utf-8", errors="replace").strip("\x00"))
        if xmp_bytes:
            result.append(RawEntry("XMP", "Packet", f"<{xmp_bytes} bytes>"))
        if iptc_bytes:
            result.append(RawEntry("IPTC", "Photoshop Block", f"<{iptc_bytes} bytes>"))
        if comments:
            result.append(RawEntry("Comment", "JPEG Comment", " | ".join(comments)))
        return result

    def strip(self, data: bytes, remove_ids: frozenset[str] | None, keep_orientation: bool) -> bytes:
        segments, sos = _parse(data)
        everything = remove_ids is None
        parts = [data[:2]]
        exif_done = False
        for seg in segments:
            raw = data[seg.start : seg.end]
            if seg.kind == "exif":
                if exif_done:
                    continue  # duplicate EXIF blocks are dropped
                exif_done = True
                try:
                    parsed = exif_codec.load(raw[4:])
                except CorruptFileError:
                    if not everything:
                        parts.append(raw)  # cannot edit it safely, leave untouched
                        continue
                    parsed = {}
                new = exif_codec.filter_exif(parsed, remove_ids, keep_orientation)
                if new:
                    parts.append(_app1(new))
                continue
            if seg.kind == "xmp" and (everything or XMP_ID in remove_ids):  # type: ignore[operator]
                continue
            if seg.kind == "iptc" and (everything or IPTC_ID in remove_ids):  # type: ignore[operator]
                continue
            if seg.kind == "comment" and (everything or COMMENT_ID in remove_ids):  # type: ignore[operator]
                continue
            parts.append(raw)
        parts.append(data[sos:])
        return b"".join(parts)
