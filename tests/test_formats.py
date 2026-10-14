"""Read/strip behavior for every supported format."""

from __future__ import annotations

import pytest
from conftest import pixel_data
from PIL import Image

from metastrip.core import (
    Risk,
    StripOptions,
    UnsupportedOperationError,
    inspect_file,
    strip_file,
    suggested_ids,
)

SENSITIVE = {"GPS.GPSLatitude", "GPS.GPSLongitude", "Exif.BodySerialNumber", "Image.Artist"}


def _ids(path):
    return {e.id for e in inspect_file(path).entries}


# ----------------------------------------------------------------- JPEG ----
def test_jpeg_inspect(jpeg_file):
    meta = inspect_file(jpeg_file)
    ids = {e.id for e in meta.entries}
    assert meta.format == "JPEG"
    assert SENSITIVE <= ids
    assert {"XMP.Packet", "IPTC.Photoshop Block", "Comment.JPEG Comment", "Thumbnail.Embedded Image"} <= ids
    by_id = {e.id: e for e in meta.entries}
    assert by_id["Image.Make"].value == "Canon"
    assert by_id["Exif.ExposureTime"].value == "0.004"
    assert by_id["GPS.GPSLatitude"].risk is Risk.HIGH
    assert meta.highest_risk is Risk.HIGH


def test_jpeg_strip_all_keeps_pixels_and_orientation(jpeg_file):
    before = jpeg_file.read_bytes()
    result = strip_file(jpeg_file)
    assert result.ok and result.output.name == "photo_clean.jpg"
    assert jpeg_file.read_bytes() == before  # original untouched
    assert _ids(result.output) == {"Image.Orientation"}
    # lossless: the compressed image data is byte-identical
    after = result.output.read_bytes()
    assert before[before.rindex(b"\xff\xda") :] == after[after.rindex(b"\xff\xda") :]
    assert pixel_data(result.output) == pixel_data(jpeg_file)


def test_jpeg_strip_all_without_orientation(jpeg_file):
    result = strip_file(jpeg_file, StripOptions(keep_orientation=False))
    assert _ids(result.output) == set()


def test_jpeg_selective(jpeg_file):
    result = strip_file(
        jpeg_file,
        StripOptions(mode="selected", remove_ids=frozenset({"GPS.GPSLatitude", "GPS.GPSLongitude"})),
    )
    remaining = _ids(result.output)
    assert "GPS.GPSLatitude" not in remaining and "GPS.GPSLongitude" not in remaining
    assert "GPS.GPSLatitudeRef" in remaining
    assert {"Image.Make", "XMP.Packet", "Thumbnail.Embedded Image"} <= remaining
    assert set(result.removed) == {"GPS.GPSLatitude", "GPS.GPSLongitude"}


def test_jpeg_selective_blocks_and_thumbnail(jpeg_file):
    ids = frozenset(
        {"XMP.Packet", "IPTC.Photoshop Block", "Comment.JPEG Comment", "Thumbnail.Embedded Image"}
    )
    result = strip_file(jpeg_file, StripOptions(mode="selected", remove_ids=ids))
    remaining = _ids(result.output)
    assert not ids & remaining
    assert "GPS.GPSLatitude" in remaining


def test_jpeg_suggested_removes_high_and_medium_only(jpeg_file):
    meta = inspect_file(jpeg_file)
    wanted = suggested_ids(meta)
    result = strip_file(jpeg_file, StripOptions(mode="suggested"))
    remaining = _ids(result.output)
    assert not wanted & remaining
    assert "Exif.ISOSpeedRatings" in remaining  # low risk survives
    assert all(inspect_file(result.output).entries[i].risk is Risk.LOW for i in range(len(remaining)))


def test_jpeg_output_still_opens(jpeg_file):
    out = strip_file(jpeg_file).output
    with Image.open(out) as img:
        img.load()
        assert img.size == (40, 30)


# ------------------------------------------------------------------ PNG ----
def test_png_inspect(png_file):
    ids = _ids(png_file)
    assert {"PNG Text.Author", "PNG Text.Software", "PNG Text.Description", "XMP.Packet"} <= ids
    assert {"Time.Modification Time", "GPS.GPSLatitude", "Image.Make"} <= ids
    by_id = {e.id: e for e in inspect_file(png_file).entries}
    assert by_id["Time.Modification Time"].value == "2024-05-01 10:30:00"
    assert by_id["PNG Text.Description"].value == "Family trip"


def test_png_strip_all(png_file):
    result = strip_file(png_file)
    assert _ids(result.output) == {"Image.Orientation"}
    assert pixel_data(result.output) == pixel_data(png_file)


def test_png_selective(png_file):
    ids = frozenset({"PNG Text.Author", "Time.Modification Time", "GPS.GPSLatitude"})
    result = strip_file(png_file, StripOptions(mode="selected", remove_ids=ids))
    remaining = _ids(result.output)
    assert not ids & remaining
    assert {"PNG Text.Software", "XMP.Packet", "Image.Make"} <= remaining


def test_png_without_metadata_is_skipped(plain_png):
    result = strip_file(plain_png)
    assert result.skipped and result.output is None
    assert not (plain_png.parent / "plain_clean.png").exists()


# ----------------------------------------------------------------- WebP ----
def test_webp_inspect_and_strip(webp_file):
    ids = _ids(webp_file)
    assert {"Image.Make", "GPS.GPSLatitude", "XMP.Packet"} <= ids
    result = strip_file(webp_file)
    assert _ids(result.output) == {"Image.Orientation"}
    assert pixel_data(result.output) == pixel_data(webp_file)


def test_webp_selective(webp_file):
    result = strip_file(webp_file, StripOptions(mode="selected", remove_ids=frozenset({"XMP.Packet"})))
    remaining = _ids(result.output)
    assert "XMP.Packet" not in remaining and "Image.Make" in remaining
    with Image.open(result.output) as img:
        img.load()


def test_webp_strip_all_clears_feature_flags(webp_file):
    out = strip_file(webp_file, StripOptions(keep_orientation=False)).output.read_bytes()
    assert out[12:16] == b"VP8X"
    assert out[20] & 0x0C == 0
    assert int.from_bytes(out[4:8], "little") == len(out) - 8


# ----------------------------------------------------------------- TIFF ----
def test_tiff_inspect(tiff_file):
    ids = _ids(tiff_file)
    assert {"Image.Make", "Image.Artist", "GPS.GPSLatitudeRef"} <= ids


def test_tiff_strip_all(tiff_file):
    result = strip_file(tiff_file)
    # Pillow >= 12 bakes the rotation into the pixels; older versions keep the tag.
    assert _ids(result.output) <= {"Image.Orientation"}
    assert pixel_data(result.output) == pixel_data(tiff_file)


def test_tiff_strip_keeps_compression(tmp_path):
    path = tmp_path / "lzw.tif"
    exif = Image.Exif()
    exif[271] = "Canon"
    exif[274] = 3
    Image.new("RGB", (30, 20), "green").save(path, "TIFF", exif=exif, compression="tiff_lzw")
    out = strip_file(path).output
    with Image.open(out) as img:
        assert img.info["compression"] == "tiff_lzw"
        assert 271 not in img.tag_v2
    assert pixel_data(out) == pixel_data(path)


def test_tiff_selective_unsupported(tiff_file):
    with pytest.raises(UnsupportedOperationError):
        strip_file(tiff_file, StripOptions(mode="selected", remove_ids=frozenset({"Image.Make"})))


# ----------------------------------------------------------------- HEIC ----
def test_heic_roundtrip(tmp_path):
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    from conftest import make_exif

    path = tmp_path / "shot.heic"
    Image.new("RGB", (64, 48), "red").save(path, exif=make_exif(), quality=90)
    ids = _ids(path)
    assert {"Image.Make", "GPS.GPSLatitude"} <= ids
    result = strip_file(path)
    assert _ids(result.output) == set()
    with Image.open(result.output) as img:
        img.load()
