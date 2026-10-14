"""Backups taken before a file is modified in place."""

from __future__ import annotations

import shutil
from pathlib import Path


def create_backup(path: Path) -> Path:
    """Copy ``path`` to ``<name>.bak`` (or ``.bak1``, ``.bak2``... if taken)."""
    candidate = path.with_name(path.name + ".bak")
    counter = 0
    while candidate.exists():
        counter += 1
        candidate = path.with_name(f"{path.name}.bak{counter}")
    shutil.copy2(path, candidate)
    return candidate
