"""``metastrip`` command-line interface."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from metastrip import __version__
from metastrip.core import (
    FileMetadata,
    MetaStripError,
    Risk,
    StripOptions,
    StripResult,
    collect_files,
    inspect_file,
    strip_many,
)
from metastrip.core import report as report_mod

_VALUE_WIDTH = 60


def _truncate(text: str, width: int = _VALUE_WIDTH) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= width else text[: width - 3] + "..."


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("paths", nargs="+", type=Path, help="files and/or folders")
    parser.add_argument("-r", "--recursive", action="store_true", help="descend into subfolders")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="metastrip", description="See and remove hidden metadata from images."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_p = sub.add_parser("inspect", help="list the metadata in files")
    _add_common(inspect_p)
    inspect_p.add_argument(
        "--min-risk", default="low", choices=["low", "medium", "high"], help="hide anything below this risk"
    )

    clean_p = sub.add_parser("clean", help="remove metadata (originals are kept unless --in-place)")
    _add_common(clean_p)
    what = clean_p.add_mutually_exclusive_group()
    what.add_argument("--suggested", action="store_true", help="remove only High and Medium risk items")
    what.add_argument(
        "--remove", nargs="+", metavar="ID", help="remove only these ids (e.g. GPS.GPSLatitude)"
    )
    clean_p.add_argument(
        "--in-place", action="store_true", help="modify originals (a .bak backup is made first)"
    )
    clean_p.add_argument("-o", "--output-dir", type=Path, help="write cleaned copies here")
    clean_p.add_argument("--no-keep-orientation", action="store_true", help="also remove the rotation flag")
    clean_p.add_argument("--dry-run", action="store_true", help="show what would be removed, change nothing")

    report_p = sub.add_parser("report", help="export findings as JSON or CSV")
    _add_common(report_p)
    report_p.add_argument("--format", default="json", choices=["json", "csv"])
    report_p.add_argument("-o", "--output", type=Path, help="write to a file instead of stdout")

    sub.add_parser("gui", help="launch the desktop app")
    return parser


def _scan(paths: Sequence[Path], recursive: bool) -> tuple[list[FileMetadata], int]:
    """Inspect every file; returns (results, number of failures)."""
    failures = 0
    metas: list[FileMetadata] = []
    for path in collect_files(paths, recursive):
        try:
            metas.append(inspect_file(path))
        except MetaStripError as exc:
            print(f"error: {path}: {exc}", file=sys.stderr)
            failures += 1
    return metas, failures


def _cmd_inspect(args: argparse.Namespace) -> int:
    minimum = Risk.parse(args.min_risk)
    metas, failures = _scan(args.paths, args.recursive)
    for meta in metas:
        counts = meta.counts()
        summary = ", ".join(f"{counts[r]} {r.label.lower()}" for r in sorted(Risk, reverse=True))
        print(f"\n{meta.path}  [{meta.format}]  {len(meta.entries)} items ({summary})")
        shown = [e for e in meta.entries if e.risk >= minimum]
        if not shown:
            print("  (nothing to show)")
        for e in sorted(shown, key=lambda x: (-x.risk, x.id)):
            print(f"  {e.risk.label:<7} {e.id:<40} {_truncate(e.value)}")
    return 1 if failures else 0


def _print_result(result: StripResult) -> None:
    if not result.ok:
        print(f"error: {result.source}: {result.error}", file=sys.stderr)
    elif result.skipped:
        print(f"skip   {result.source} ({result.reason})")
    elif result.dry_run:
        print(f"would  {result.source} -> remove {len(result.removed)} items: {', '.join(result.removed)}")
    else:
        extra = f", backup {result.backup.name}" if result.backup else ""
        print(f"clean  {result.source} -> {result.output} (removed {len(result.removed)} items{extra})")


def _cmd_clean(args: argparse.Namespace) -> int:
    if args.remove:
        mode, ids = "selected", frozenset(args.remove)
    elif args.suggested:
        mode, ids = "suggested", frozenset()
    else:
        mode, ids = "all", frozenset()
    options = StripOptions(
        mode=mode,
        remove_ids=ids,
        keep_orientation=not args.no_keep_orientation,
        in_place=args.in_place,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )
    files = collect_files(args.paths, args.recursive)
    if not files:
        print("No supported images found.", file=sys.stderr)
        return 1
    results = strip_many(files, options, on_progress=lambda _i, _n, r: _print_result(r))
    cleaned = sum(1 for r in results if r.ok and not r.skipped)
    failed = sum(1 for r in results if not r.ok)
    print(f"\n{cleaned} cleaned, {len(results) - cleaned - failed} skipped, {failed} failed")
    return 1 if failed else 0


def _cmd_report(args: argparse.Namespace) -> int:
    metas, failures = _scan(args.paths, args.recursive)
    text = report_mod.to_json(metas) if args.format == "json" else report_mod.to_csv(metas)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(text)
    return 1 if failures else 0


def _cmd_gui(_args: argparse.Namespace) -> int:
    try:
        from metastrip.gui.app import main as gui_main
    except ImportError:
        print("The desktop app needs customtkinter: pip install 'metadata-stripper[gui]'", file=sys.stderr)
        return 1
    gui_main()
    return 0


_COMMANDS = {"inspect": _cmd_inspect, "clean": _cmd_clean, "report": _cmd_report, "gui": _cmd_gui}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s"
    )
    try:
        return _COMMANDS[args.command](args)
    except MetaStripError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
