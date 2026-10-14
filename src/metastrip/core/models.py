"""Plain data types shared by the core, CLI and GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Literal


class Risk(IntEnum):
    """How sensitive a piece of metadata is."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @property
    def label(self) -> str:
        return self.name.capitalize()

    @classmethod
    def parse(cls, text: str) -> Risk:
        try:
            return cls[text.strip().upper()]
        except KeyError:
            raise ValueError(f"Unknown risk level: {text!r}") from None


@dataclass(frozen=True)
class RawEntry:
    """A metadata item as read from a file, before risk scoring."""

    group: str
    name: str
    value: str

    @property
    def id(self) -> str:
        return f"{self.group}.{self.name}"


@dataclass(frozen=True)
class MetadataEntry:
    """A scored metadata item."""

    group: str
    name: str
    value: str
    risk: Risk

    @property
    def id(self) -> str:
        return f"{self.group}.{self.name}"


@dataclass
class FileMetadata:
    """Everything found in one file."""

    path: Path
    format: str
    entries: list[MetadataEntry] = field(default_factory=list)

    def counts(self) -> dict[Risk, int]:
        result = {risk: 0 for risk in Risk}
        for entry in self.entries:
            result[entry.risk] += 1
        return result

    @property
    def highest_risk(self) -> Risk | None:
        return max((e.risk for e in self.entries), default=None)


@dataclass(frozen=True)
class StripOptions:
    """How to clean a file.

    mode:
        ``all``       remove every piece of metadata
        ``suggested`` remove everything at or above ``min_risk``
        ``selected``  remove only the ids in ``remove_ids``
    """

    mode: Literal["all", "suggested", "selected"] = "all"
    remove_ids: frozenset[str] = frozenset()
    min_risk: Risk = Risk.MEDIUM
    keep_orientation: bool = True
    in_place: bool = False
    output_dir: Path | None = None
    suffix: str = "_clean"
    dry_run: bool = False


@dataclass(frozen=True)
class StripResult:
    """Outcome of cleaning one file."""

    source: Path
    output: Path | None = None
    removed: tuple[str, ...] = ()
    backup: Path | None = None
    skipped: bool = False
    reason: str = ""
    dry_run: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None
