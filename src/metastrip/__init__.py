"""Metadata Stripper: see and remove hidden metadata before you share files."""

from metastrip.core import (
    FileMetadata,
    MetadataEntry,
    Risk,
    StripOptions,
    StripResult,
    collect_files,
    inspect_file,
    strip_file,
    strip_many,
    suggested_ids,
)

__version__ = "1.0.0"

__all__ = [
    "FileMetadata",
    "MetadataEntry",
    "Risk",
    "StripOptions",
    "StripResult",
    "__version__",
    "collect_files",
    "inspect_file",
    "strip_file",
    "strip_many",
    "suggested_ids",
]
