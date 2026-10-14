"""High-level operations used by the CLI and GUI."""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path

from metastrip.core.backup import create_backup
from metastrip.core.errors import MetaStripError, UnsupportedOperationError
from metastrip.core.handlers import detect
from metastrip.core.handlers.base import FormatHandler
from metastrip.core.models import (
    FileMetadata,
    MetadataEntry,
    Risk,
    StripOptions,
    StripResult,
)
from metastrip.core.risk import score

log = logging.getLogger(__name__)


def _read_entries(handler: FormatHandler, data: bytes) -> list[MetadataEntry]:
    return [MetadataEntry(r.group, r.name, r.value, score(r.group, r.name)) for r in handler.read(data)]


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise MetaStripError(f"Cannot read {path}: {exc.strerror or exc}") from exc


def inspect_file(path: str | Path) -> FileMetadata:
    """List all metadata in a file with a privacy risk for each item."""
    path = Path(path)
    data = _read_bytes(path)
    handler = detect(data)
    return FileMetadata(path=path, format=handler.name, entries=_read_entries(handler, data))


def suggested_ids(meta: FileMetadata, min_risk: Risk = Risk.MEDIUM) -> frozenset[str]:
    """Ids of every entry at or above ``min_risk``."""
    return frozenset(e.id for e in meta.entries if e.risk >= min_risk)


def _resolve_ids(options: StripOptions, entries: list[MetadataEntry]) -> frozenset[str] | None:
    if options.mode == "all":
        return None
    if options.mode == "suggested":
        return frozenset(e.id for e in entries if e.risk >= options.min_risk)
    return options.remove_ids


def _output_path(path: Path, options: StripOptions) -> Path:
    if options.in_place:
        return path
    folder = options.output_dir or path.parent
    target = folder / f"{path.stem}{options.suffix}{path.suffix}"
    if target.resolve() == path.resolve():
        raise MetaStripError("Output would overwrite the original; use in-place mode instead")
    return target


def _atomic_write(target: Path, data: bytes) -> None:
    temp = target.with_name(target.name + ".tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(data)
        os.replace(temp, target)
    except OSError as exc:
        with contextlib.suppress(OSError):
            temp.unlink(missing_ok=True)
        raise MetaStripError(f"Cannot write {target}: {exc.strerror or exc}") from exc


def strip_file(path: str | Path, options: StripOptions | None = None) -> StripResult:
    """Remove metadata from one file according to ``options``.

    The original is never touched unless ``options.in_place`` is set, in which
    case a backup is made first. Output is verified by re-reading it before
    anything is written to disk.
    """
    options = options or StripOptions()
    path = Path(path)
    data = _read_bytes(path)
    handler = detect(data)
    before = _read_entries(handler, data)
    ids = _resolve_ids(options, before)

    present = {e.id for e in before}
    if not before or (ids is not None and not ids & present):
        return StripResult(path, skipped=True, reason="no matching metadata")
    if ids is not None and not handler.supports_selective:
        raise UnsupportedOperationError(f"{handler.name} files support removing all metadata only")

    new_data = handler.strip(data, ids, options.keep_orientation)
    after = {r.id for r in handler.read(new_data)}  # also proves the output parses
    removed = tuple(sorted(present - after))
    if not removed:
        return StripResult(path, skipped=True, reason="nothing to remove")

    target = _output_path(path, options)
    if options.dry_run:
        return StripResult(path, output=target, removed=removed, dry_run=True)

    backup = create_backup(path) if options.in_place else None
    _atomic_write(target, new_data)
    log.info("Cleaned %s -> %s (%d tags)", path, target, len(removed))
    return StripResult(path, output=target, removed=removed, backup=backup)
