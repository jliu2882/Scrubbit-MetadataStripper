"""PNG handler. Works on chunks, so pixel data is never re-encoded."""

from __future__ import annotations

import zlib
from typing import NamedTuple

from metastrip.core import exif_codec
from metastrip.core.errors import CorruptFileError
from metastrip.core.handlers.base import FormatHandler
from metastrip.core.models import RawEntry

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_TEXT_TYPES = {b"tEXt", b"zTXt", b"iTXt"}
_XMP_KEYWORD = "XML:com.adobe.xmp"
TIME_ID = "Time.Modification Time"
XMP_ID = "XMP.Packet"


class _Chunk(NamedTuple):
    ctype: bytes
    start: int
    end: int  # exclusive, includes length/type/crc

    def payload(self, data: bytes) -> bytes:
        return data[self.start + 8 : self.end - 4]


def _chunks(data: bytes) -> list[_Chunk]:
    if data[:8] != _SIGNATURE:
        raise CorruptFileError("Not a valid PNG (bad signature)")
    chunks: list[_Chunk] = []
    pos = 8
    while pos + 12 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        ctype = data[pos + 4 : pos + 8]
        end = pos + 12 + length
        if end > len(data):
            raise CorruptFileError("Corrupt PNG: chunk extends past end of file")
        chunks.append(_Chunk(ctype, pos, end))
        pos = end
        if ctype == b"IEND":
            break
    if not chunks or chunks[0].ctype != b"IHDR":
        raise CorruptFileError("Corrupt PNG: missing IHDR")
    if chunks[-1].ctype != b"IEND":
        raise CorruptFileError("Corrupt PNG: file is truncated (no IEND chunk)")
    return chunks


def _make_chunk(ctype: bytes, payload: bytes) -> bytes:
    body = ctype + payload
    return len(payload).to_bytes(4, "big") + body + zlib.crc32(body).to_bytes(4, "big")


def _decompress(blob: bytes) -> bytes | None:
    try:
        return zlib.decompress(blob)
    except zlib.error:
        return None


def _parse_text(ctype: bytes, payload: bytes) -> tuple[str, str, int]:
    """Return (keyword, text, text_size) for a tEXt/zTXt/iTXt payload."""
    keyword, _, rest = payload.partition(b"\x00")
    key = keyword.decode("latin-1")
    if ctype == b"tEXt":
        return key, rest.decode("latin-1"), len(rest)
    if ctype == b"zTXt":
        raw = _decompress(rest[1:])
        return key, ("<compressed>" if raw is None else raw.decode("latin-1")), len(rest)
    flag = rest[:1]
    rest = rest[2:]
    _, _, rest = rest.partition(b"\x00")  # language tag
    _, _, rest = rest.partition(b"\x00")  # translated keyword
    raw = _decompress(rest) if flag == b"\x01" else rest
    if raw is None:
        return key, "<compressed>", len(rest)
    return key, raw.decode("utf-8", errors="replace"), len(raw)


def _describe(data: bytes, chunks: list[_Chunk]) -> dict[int, list[RawEntry]]:
    """Map chunk start offset -> entries it contributes (stable, unique names)."""
    seen: dict[str, int] = {}
    described: dict[int, list[RawEntry]] = {}
    for chunk in chunks:
        payload = chunk.payload(data)
        if chunk.ctype in _TEXT_TYPES:
            key, text, size = _parse_text(chunk.ctype, payload)
            if key == _XMP_KEYWORD:
                entry = RawEntry("XMP", "Packet", f"<{size} bytes>")
            else:
                count = seen.get(key, 0)
                seen[key] = count + 1
                name = key if count == 0 else f"{key} ({count + 1})"
                entry = RawEntry("PNG Text", name, text)
            described[chunk.start] = [entry]
        elif chunk.ctype == b"tIME" and len(payload) == 7:
            year = int.from_bytes(payload[:2], "big")
            month, day, hour, minute, second = payload[2:]
            stamp = f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
            described[chunk.start] = [RawEntry("Time", "Modification Time", stamp)]
        elif chunk.ctype == b"eXIf":
            try:
                described[chunk.start] = exif_codec.entries(exif_codec.load(payload))
            except CorruptFileError:
                described[chunk.start] = [RawEntry("Image", "Unreadable EXIF", f"<{len(payload)} bytes>")]
    return described


class PngHandler(FormatHandler):
    name = "PNG"

    def read(self, data: bytes) -> list[RawEntry]:
        chunks = _chunks(data)
        result: list[RawEntry] = []
        for entries in _describe(data, chunks).values():
            result.extend(entries)
        return result

    def strip(self, data: bytes, remove_ids: frozenset[str] | None, keep_orientation: bool) -> bytes:
        chunks = _chunks(data)
        described = _describe(data, chunks)
        everything = remove_ids is None
        parts = [data[:8]]
        for chunk in chunks:
            raw = data[chunk.start : chunk.end]
            if chunk.ctype in _TEXT_TYPES or chunk.ctype == b"tIME":
                ids = {e.id for e in described.get(chunk.start, [])}
                if everything or ids & remove_ids:  # type: ignore[operator]
                    continue
            elif chunk.ctype == b"eXIf":
                try:
                    parsed = exif_codec.load(chunk.payload(data))
                except CorruptFileError:
                    if not everything:
                        parts.append(raw)
                        continue
                    parsed = {}
                new = exif_codec.filter_exif(parsed, remove_ids, keep_orientation)
                if new:
                    parts.append(_make_chunk(b"eXIf", new[6:]))
                continue
            parts.append(raw)
        return b"".join(parts)
