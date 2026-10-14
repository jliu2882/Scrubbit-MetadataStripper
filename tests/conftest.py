"""Shared builders for sample images carrying realistic metadata."""

from __future__ import annotations

import io
import zlib
from pathlib import Path

import piexif
import pytest
from PIL import Image, PngImagePlugin

XMP_PACKET = b'<?xpacket begin=""?><x:xmpmeta xmlns:x="adobe:ns:meta/"><creator>Jane</creator></x:xmpmeta>'


def make_exif(orientation: int = 6, thumbnail: bool = False) -> bytes:
    thumb_bytes = None
    if thumbnail:
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), "blue").save(buf, "JPEG")
        thumb_bytes = buf.getvalue()
    exif = {
        "0th": {
            piexif.ImageIFD.Make: b"Canon",
            piexif.ImageIFD.Model: b"EOS R5",
            piexif.ImageIFD.Software: b"Photoshop 25",
            piexif.ImageIFD.Orientation: orientation,
            piexif.ImageIFD.Artist: b"Jane Doe",
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: b"2024:05:01 10:30:00",
            piexif.ExifIFD.ISOSpeedRatings: 200,
            piexif.ExifIFD.ExposureTime: (1, 250),
            piexif.ExifIFD.BodySerialNumber: b"SN123456",
        },
        "GPS": {
            piexif.GPSIFD.GPSLatitudeRef: b"N",
            piexif.GPSIFD.GPSLatitude: ((40, 1), (42, 1), (46, 1)),
            piexif.GPSIFD.GPSLongitudeRef: b"W",
            piexif.GPSIFD.GPSLongitude: ((74, 1), (0, 1), (21, 1)),
        },
        "1st": {},
        "thumbnail": thumb_bytes,
    }
    return piexif.dump(exif)


def insert_jpeg_segment(data: bytes, marker: int, payload: bytes) -> bytes:
    segment = b"\xff" + bytes([marker]) + (len(payload) + 2).to_bytes(2, "big") + payload
    return data[:2] + segment + data[2:]


def pixel_data(path_or_bytes) -> bytes:
    src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, bytes) else path_or_bytes
    with Image.open(src) as img:
        return img.convert("RGBA").tobytes()


def _picture() -> Image.Image:
    img = Image.new("RGB", (40, 30))
    img.putdata([(x * 6 % 256, y * 8 % 256, (x * y) % 256) for y in range(30) for x in range(40)])
    return img


@pytest.fixture
def jpeg_file(tmp_path: Path) -> Path:
    buf = io.BytesIO()
    _picture().save(buf, "JPEG", exif=make_exif(thumbnail=True), quality=90)
    data = insert_jpeg_segment(buf.getvalue(), 0xE1, b"http://ns.adobe.com/xap/1.0/\x00" + XMP_PACKET)
    data = insert_jpeg_segment(data, 0xED, b"Photoshop 3.0\x00" + b"8BIM" + b"\x00" * 10)
    data = insert_jpeg_segment(data, 0xFE, b"shot at my home")
    path = tmp_path / "photo.jpg"
    path.write_bytes(data)
    return path


@pytest.fixture
def png_file(tmp_path: Path) -> Path:
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "Jane Doe")
    info.add_text("Software", "GIMP")
    info.add_text("Description", "Family trip", zip=True)
    info.add_itxt("XML:com.adobe.xmp", XMP_PACKET.decode())
    buf = io.BytesIO()
    _picture().save(buf, "PNG", pnginfo=info, exif=make_exif())
    data = buf.getvalue()
    # inject a tIME chunk right after IHDR (offset 8 + 25)
    time_payload = (2024).to_bytes(2, "big") + bytes([5, 1, 10, 30, 0])
    body = b"tIME" + time_payload
    chunk = len(time_payload).to_bytes(4, "big") + body + zlib.crc32(body).to_bytes(4, "big")
    data = data[:33] + chunk + data[33:]
    path = tmp_path / "pic.png"
    path.write_bytes(data)
    return path


@pytest.fixture
def webp_file(tmp_path: Path) -> Path:
    path = tmp_path / "pic.webp"
    _picture().save(path, "WEBP", lossless=True, exif=make_exif(), xmp=XMP_PACKET)
    return path


@pytest.fixture
def tiff_file(tmp_path: Path) -> Path:
    path = tmp_path / "scan.tif"
    _picture().save(path, "TIFF", exif=make_exif())
    return path


@pytest.fixture
def plain_png(tmp_path: Path) -> Path:
    path = tmp_path / "plain.png"
    _picture().save(path, "PNG")
    return path
