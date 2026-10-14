"""Service-level behavior: output handling, backups, batch, reports."""

from __future__ import annotations

import csv
import io
import json

import pytest
from conftest import pixel_data

from metastrip.core import (
    MetaStripError,
    Risk,
    StripOptions,
    UnsupportedFormatError,
    collect_files,
    inspect_file,
    strip_file,
    strip_many,
    suggested_ids,
)
from metastrip.core import report as report_mod
from metastrip.core.backup import create_backup


def test_unrecognized_file_rejected(tmp_path):
    path = tmp_path / "notes.jpg"
    path.write_text("not an image")
    with pytest.raises(UnsupportedFormatError):
        inspect_file(path)


def test_detection_ignores_extension(jpeg_file, tmp_path):
    disguised = tmp_path / "actually_jpeg.png"
    disguised.write_bytes(jpeg_file.read_bytes())
    assert inspect_file(disguised).format == "JPEG"


def test_missing_file(tmp_path):
    with pytest.raises(MetaStripError):
        inspect_file(tmp_path / "nope.jpg")


def test_corrupt_jpeg(tmp_path):
    path = tmp_path / "bad.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe1\x00\x50Exif")
    with pytest.raises(MetaStripError):
        inspect_file(path)


def test_corrupt_png(tmp_path, png_file):
    path = tmp_path / "bad.png"
    path.write_bytes(png_file.read_bytes()[:60])
    with pytest.raises(MetaStripError):
        inspect_file(path)


def test_in_place_makes_backup_and_replaces(jpeg_file):
    original = jpeg_file.read_bytes()
    result = strip_file(jpeg_file, StripOptions(in_place=True))
    assert result.output == jpeg_file
    assert result.backup.read_bytes() == original
    assert jpeg_file.read_bytes() != original
    assert {e.group for e in inspect_file(jpeg_file).entries} <= {"Image"}


def test_in_place_backups_do_not_overwrite(jpeg_file):
    first = create_backup(jpeg_file)
    second = create_backup(jpeg_file)
    assert first != second and first.exists() and second.exists()


def test_output_dir(jpeg_file, tmp_path):
    out_dir = tmp_path / "cleaned" / "deep"
    result = strip_file(jpeg_file, StripOptions(output_dir=out_dir))
    assert result.output == out_dir / "photo_clean.jpg"
    assert result.output.exists()


def test_refuses_to_overwrite_original(jpeg_file):
    with pytest.raises(MetaStripError):
        strip_file(jpeg_file, StripOptions(suffix=""))


def test_dry_run_writes_nothing(jpeg_file):
    result = strip_file(jpeg_file, StripOptions(dry_run=True))
    assert result.dry_run and result.removed
    assert not (jpeg_file.parent / "photo_clean.jpg").exists()


def test_selected_ids_not_present_is_skipped(jpeg_file):
    result = strip_file(jpeg_file, StripOptions(mode="selected", remove_ids=frozenset({"GPS.Nope"})))
    assert result.skipped


def test_cleaning_twice_skips(jpeg_file):
    first = strip_file(jpeg_file).output
    again = strip_file(first, StripOptions(output_dir=jpeg_file.parent / "second"))
    assert again.skipped and again.reason == "nothing to remove"


def test_suggested_ids_respects_min_risk(jpeg_file):
    meta = inspect_file(jpeg_file)
    high = suggested_ids(meta, Risk.HIGH)
    medium = suggested_ids(meta, Risk.MEDIUM)
    assert high < medium
    assert "GPS.GPSLatitude" in high and "Image.Make" in medium and "Image.Make" not in high


# ---------------------------------------------------------------- batch ----
def test_collect_files(tmp_path, jpeg_file, png_file):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.png").write_bytes(png_file.read_bytes())
    (tmp_path / "readme.txt").write_text("hi")
    (tmp_path / "old_clean.jpg").write_bytes(jpeg_file.read_bytes())

    flat = collect_files([tmp_path])
    assert {p.name for p in flat} == {"photo.jpg", "pic.png"}
    deep = collect_files([tmp_path], recursive=True)
    assert "deep.png" in {p.name for p in deep}
    assert collect_files([tmp_path / "old_clean.jpg"]) == [tmp_path / "old_clean.jpg"]
    with pytest.raises(MetaStripError):
        collect_files([tmp_path / "missing"])


def test_strip_many_continues_after_failure(tmp_path, jpeg_file, png_file):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"garbage")
    seen = []
    results = strip_many([bad, jpeg_file, png_file], on_progress=lambda i, n, r: seen.append((i, n)))
    assert [r.ok for r in results] == [False, True, True]
    assert seen == [(1, 3), (2, 3), (3, 3)]
    assert pixel_data(results[1].output) == pixel_data(jpeg_file)


# --------------------------------------------------------------- report ----
def test_report_json_and_csv(jpeg_file, png_file):
    metas = [inspect_file(jpeg_file), inspect_file(png_file)]
    data = json.loads(report_mod.to_json(metas))
    assert [d["format"] for d in data] == ["JPEG", "PNG"]
    assert data[0]["risk_summary"]["High"] >= 4
    assert any(e["id"] == "GPS.GPSLatitude" and e["risk"] == "High" for e in data[0]["entries"])

    rows = list(csv.DictReader(io.StringIO(report_mod.to_csv(metas))))
    assert rows and set(rows[0]) == {"file", "format", "group", "name", "value", "risk"}
    assert {r["format"] for r in rows} == {"JPEG", "PNG"}


# ------------------------------------------------------ malformed input ----
def test_corrupt_exif_is_reported_and_removable(jpeg_file, tmp_path):
    from conftest import insert_jpeg_segment

    path = tmp_path / "broken_exif.jpg"
    path.write_bytes(insert_jpeg_segment(_without_exif(jpeg_file.read_bytes()), 0xE1, b"Exif\x00\x00garbage"))
    assert any(e.name == "Unreadable EXIF" for e in inspect_file(path).entries)
    result = strip_file(path, StripOptions(keep_orientation=False))
    assert not any(e.group == "Image" for e in inspect_file(result.output).entries)


def _without_exif(data: bytes) -> bytes:
    """Rebuild a JPEG with its real EXIF segment removed."""
    from metastrip.core.handlers.jpeg import _parse

    segments, sos = _parse(data)
    parts = [data[:2]]
    parts += [data[s.start : s.end] for s in segments if s.kind != "exif"]
    parts.append(data[sos:])
    return b"".join(parts)


def test_truncated_webp(tmp_path, webp_file):
    path = tmp_path / "cut.webp"
    path.write_bytes(webp_file.read_bytes()[:40])
    with pytest.raises(MetaStripError):
        inspect_file(path)


def test_multipage_tiff_rejected(tmp_path):
    from PIL import Image

    from metastrip.core import UnsupportedOperationError

    a = Image.new("RGB", (8, 8), "red")
    b = Image.new("RGB", (8, 8), "blue")
    path = tmp_path / "multi.tif"
    exif = Image.Exif()
    exif[271] = "Canon"
    a.save(path, "TIFF", save_all=True, append_images=[b], exif=exif)
    with pytest.raises(UnsupportedOperationError):
        strip_file(path)


def test_heic_without_library(monkeypatch, tmp_path):
    import sys

    monkeypatch.setitem(sys.modules, "pillow_heif", None)
    path = tmp_path / "x.heic"
    path.write_bytes(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32)
    with pytest.raises(UnsupportedFormatError, match="pillow-heif"):
        inspect_file(path)


def test_write_failure_is_reported(jpeg_file, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a folder")
    with pytest.raises(MetaStripError):
        strip_file(jpeg_file, StripOptions(output_dir=blocker / "sub"))
