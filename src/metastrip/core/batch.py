"""Working on many files at once."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from metastrip.core.errors import MetaStripError
from metastrip.core.handlers import SUPPORTED_EXTENSIONS
from metastrip.core.models import StripOptions, StripResult
from metastrip.core.service import strip_file

ProgressCallback = Callable[[int, int, StripResult], None]


def collect_files(
    paths: Iterable[str | Path],
    recursive: bool = False,
    skip_suffix: str = "_clean",
) -> list[Path]:
    """Expand files and folders into a sorted list of supported images.

    Files named explicitly are always included. Inside folders, files whose
    name ends with ``skip_suffix`` (previous output) are skipped so repeated
    runs do not clean the cleaned copies again.
    """
    found: dict[Path, None] = {}
    for item in paths:
        path = Path(item)
        if path.is_file():
            found[path] = None
        elif path.is_dir():
            pattern = path.rglob("*") if recursive else path.glob("*")
            for child in pattern:
                if (
                    child.is_file()
                    and child.suffix.lower() in SUPPORTED_EXTENSIONS
                    and not (skip_suffix and child.stem.endswith(skip_suffix))
                ):
                    found[child] = None
        else:
            raise MetaStripError(f"No such file or folder: {path}")
    return sorted(found)


def strip_many(
    files: Iterable[Path],
    options: StripOptions | None = None,
    on_progress: ProgressCallback | None = None,
) -> list[StripResult]:
    """Clean many files. One failure never stops the rest."""
    options = options or StripOptions()
    items = list(files)
    results: list[StripResult] = []
    for index, path in enumerate(items, start=1):
        try:
            result = strip_file(path, options)
        except (MetaStripError, OSError) as exc:
            result = StripResult(path, error=str(exc))
        results.append(result)
        if on_progress:
            on_progress(index, len(items), result)
    return results
