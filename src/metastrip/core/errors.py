"""Exceptions raised by the core library."""


class MetaStripError(Exception):
    """Base class for all expected errors."""


class UnsupportedFormatError(MetaStripError):
    """The file is not a supported image format."""


class UnsupportedOperationError(MetaStripError):
    """The format cannot perform the requested operation."""


class CorruptFileError(MetaStripError):
    """The file (or its metadata) could not be parsed."""
