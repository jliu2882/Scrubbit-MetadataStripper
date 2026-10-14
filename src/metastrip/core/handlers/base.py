"""Interface every file-format handler implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from metastrip.core.models import RawEntry


class FormatHandler(ABC):
    """Reads and strips metadata for one file format."""

    #: Human readable format name.
    name: str = ""
    #: Whether individual tags can be removed (otherwise strip-all only).
    supports_selective: bool = True

    @abstractmethod
    def read(self, data: bytes) -> list[RawEntry]:
        """List every metadata item in ``data``."""

    @abstractmethod
    def strip(self, data: bytes, remove_ids: frozenset[str] | None, keep_orientation: bool) -> bytes:
        """Return new file bytes without the given metadata ids.

        ``remove_ids=None`` means remove everything. ``keep_orientation``
        preserves the EXIF rotation flag so images still display upright.
        """
