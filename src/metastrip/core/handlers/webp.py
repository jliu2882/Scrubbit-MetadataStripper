"""WebP handler. Works on RIFF chunks, so pixel data is never re-encoded."""

from __future__ import annotations

from typing import NamedTuple

from metastrip.core import exif_codec
from metastrip.core.errors import CorruptFileError
from metastrip.core.handlers.base import FormatHandler
from metastrip.core.models import RawEntry

XMP_ID = "XMP.Packet"
_FLAG_EXIF = 0x08
_FLAG_XMP = 0x04


class _Chunk(NamedTuple):
    fourcc: bytes
    start: int
    end: int  # exclusive, includes header and padding
    size: int

    def payload(self, data: bytes) -> bytes:
        return data[self.start + 8 : self.start + 8 + self.size]


def _chunks(data: bytes) -> list[_Chunk]:
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise CorruptFileError("Not a valid WebP file")
    chunks: list[_Chunk] = []
    pos = 12
    while pos + 8 <= len(data):
        size = int.from_bytes(data[pos + 4 : pos + 8], "little")
        end = pos + 8 + size + (size & 1)
        if pos + 8 + size > len(data):
            raise CorruptFileError("Corrupt WebP: chunk extends past end of file")
        chunks.append(_Chunk(data[pos : pos + 4], pos, min(end, len(data)), size))
        pos = end
    if not chunks:
        raise CorruptFileError("Corrupt WebP: no chunks")
    return chunks


def _make_chunk(fourcc: bytes, payload: bytes) -> bytes:
    pad = b"\x00" if len(payload) & 1 else b""
    return fourcc + len(payload).to_bytes(4, "little") + payload + pad


class WebpHandler(FormatHandler):
    name = "WebP"

    def read(self, data: bytes) -> list[RawEntry]:
        result: list[RawEntry] = []
        for chunk in _chunks(data):
            payload = chunk.payload(data)
            if chunk.fourcc == b"EXIF":
                try:
                    result.extend(exif_codec.entries(exif_codec.load(payload)))
                except CorruptFileError:
                    result.append(RawEntry("Image", "Unreadable EXIF", f"<{len(payload)} bytes>"))
            elif chunk.fourcc == b"XMP ":
                result.append(RawEntry("XMP", "Packet", f"<{len(payload)} bytes>"))
        return result

    def strip(self, data: bytes, remove_ids: frozenset[str] | None, keep_orientation: bool) -> bytes:
        everything = remove_ids is None
        body: list[bytes] = []
        has_exif = has_xmp = False
        for chunk in _chunks(data):
            raw = data[chunk.start : chunk.end]
            if chunk.fourcc == b"EXIF":
                try:
                    parsed = exif_codec.load(chunk.payload(data))
                except CorruptFileError:
                    if not everything:
                        body.append(raw)
                        has_exif = True
                        continue
                    parsed = {}
                new = exif_codec.filter_exif(parsed, remove_ids, keep_orientation)
                if new:
                    body.append(_make_chunk(b"EXIF", new[6:]))
                    has_exif = True
                continue
            if chunk.fourcc == b"XMP ":
                if everything or XMP_ID in remove_ids:  # type: ignore[operator]
                    continue
                has_xmp = True
            body.append(raw)

        # Keep the VP8X feature flags in sync with the chunks that remain.
        if body and body[0][:4] == b"VP8X":
            head = bytearray(body[0])
            flags = head[8]
            flags = (flags | _FLAG_EXIF) if has_exif else (flags & ~_FLAG_EXIF)
            flags = (flags | _FLAG_XMP) if has_xmp else (flags & ~_FLAG_XMP)
            head[8] = flags & 0xFF
            body[0] = bytes(head)

        payload = b"WEBP" + b"".join(body)
        return b"RIFF" + len(payload).to_bytes(4, "little") + payload
