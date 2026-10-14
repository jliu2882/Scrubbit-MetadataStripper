"""Build standalone executables with PyInstaller.

Usage:
    python scripts/build.py            # builds into dist/
    python scripts/build.py --zip NAME # also zips the result as dist/NAME.zip

Requires: pip install ".[gui,heic,dev]"
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def run_pyinstaller(name: str, entry: str, windowed: bool, extra: list[str]) -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        name,
        "--distpath",
        str(DIST),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT / "build"),
        "--paths",
        str(ROOT / "src"),
        *extra,
    ]
    if windowed:
        command.append("--windowed")
    command.append(str(ROOT / "packaging" / entry))
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip", metavar="NAME", help="zip the executables as dist/NAME.zip")
    parser.add_argument("--cli-only", action="store_true", help="skip the GUI build")
    args = parser.parse_args()

    run_pyinstaller("metastrip", "cli_entry.py", windowed=False, extra=["--collect-all", "pillow_heif"])
    if not args.cli_only:
        run_pyinstaller(
            "MetadataStripper",
            "gui_entry.py",
            windowed=True,
            extra=["--collect-all", "customtkinter", "--collect-all", "pillow_heif"],
        )

    if args.zip:
        archive = DIST / f"{args.zip}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for item in sorted(DIST.iterdir()):
                if item.is_file() and item.suffix != ".zip" and not item.name.startswith("."):
                    bundle.write(item, item.name)
        print(f"Created {archive}")


if __name__ == "__main__":
    main()
