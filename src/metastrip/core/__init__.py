"""Core library: no GUI or CLI dependencies."""

from metastrip.core.batch import collect_files, strip_many
from metastrip.core.errors import (
    CorruptFileError,
    MetaStripError,
    UnsupportedFormatError,
    UnsupportedOperationError,
)
from metastrip.core.models import (
    FileMetadata,
    MetadataEntry,
    Risk,
    StripOptions,
    StripResult,
)
from metastrip.core.service import inspect_file, strip_file, suggested_ids

__all__ = [
    "CorruptFileError",
    "FileMetadata",
    "MetaStripError",
    "MetadataEntry",
    "Risk",
    "StripOptions",
    "StripResult",
    "UnsupportedFormatError",
    "UnsupportedOperationError",
    "collect_files",
    "inspect_file",
    "strip_file",
    "strip_many",
    "suggested_ids",
]
