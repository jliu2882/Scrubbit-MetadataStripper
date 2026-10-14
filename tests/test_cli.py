from __future__ import annotations

import json

import pytest

from metastrip.cli.main import main
from metastrip.core import inspect_file


def test_inspect(jpeg_file, capsys):
    assert main(["inspect", str(jpeg_file), "--min-risk", "high"]) == 0
    out = capsys.readouterr().out
    assert "GPS.GPSLatitude" in out and "High" in out
    assert "ISOSpeedRatings" not in out


def test_clean_default(jpeg_file, capsys):
    assert main(["clean", str(jpeg_file)]) == 0
    assert "removed" in capsys.readouterr().out
    assert (jpeg_file.parent / "photo_clean.jpg").exists()


def test_clean_folder_recursive_suggested(tmp_path, jpeg_file, png_file, capsys):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "inner.png").write_bytes(png_file.read_bytes())
    assert main(["clean", str(tmp_path), "-r", "--suggested", "-o", str(tmp_path / "out")]) == 0
    names = {p.name for p in (tmp_path / "out").iterdir()}
    assert names == {"photo_clean.jpg", "pic_clean.png", "inner_clean.png"}
    assert "3 cleaned" in capsys.readouterr().out


def test_clean_remove_ids(jpeg_file):
    assert main(["clean", str(jpeg_file), "--remove", "GPS.GPSLatitude", "GPS.GPSLongitude"]) == 0
    ids = {e.id for e in inspect_file(jpeg_file.parent / "photo_clean.jpg").entries}
    assert "GPS.GPSLatitude" not in ids and "Image.Make" in ids


def test_clean_in_place(jpeg_file):
    assert main(["clean", str(jpeg_file), "--in-place"]) == 0
    assert (jpeg_file.parent / "photo.jpg.bak").exists()


def test_clean_dry_run(jpeg_file, capsys):
    assert main(["clean", str(jpeg_file), "--dry-run"]) == 0
    assert "would" in capsys.readouterr().out
    assert not (jpeg_file.parent / "photo_clean.jpg").exists()


def test_clean_reports_failures(tmp_path, capsys):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"nope")
    assert main(["clean", str(bad)]) == 1
    assert "error" in capsys.readouterr().err


def test_clean_no_images(tmp_path, capsys):
    assert main(["clean", str(tmp_path)]) == 1


def test_missing_path(tmp_path, capsys):
    assert main(["inspect", str(tmp_path / "ghost.jpg")]) == 1
    assert "No such file" in capsys.readouterr().err


def test_report_to_file(jpeg_file, tmp_path):
    target = tmp_path / "report.json"
    assert main(["report", str(jpeg_file), "-o", str(target)]) == 0
    assert json.loads(target.read_text())[0]["format"] == "JPEG"


def test_report_csv_stdout(jpeg_file, capsys):
    assert main(["report", str(jpeg_file), "--format", "csv"]) == 0
    assert capsys.readouterr().out.startswith("file,format,group")


def test_version_and_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "metastrip" in capsys.readouterr().out
