"""Export what was found in files as JSON or CSV."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable

from metastrip.core.models import FileMetadata, Risk


def to_dicts(metas: Iterable[FileMetadata]) -> list[dict]:
    """Plain-data form of the scan results."""
    rows = []
    for meta in metas:
        counts = meta.counts()
        rows.append(
            {
                "file": str(meta.path),
                "format": meta.format,
                "risk_summary": {risk.label: counts[risk] for risk in sorted(Risk, reverse=True)},
                "entries": [
                    {"id": e.id, "group": e.group, "name": e.name, "value": e.value, "risk": e.risk.label}
                    for e in meta.entries
                ],
            }
        )
    return rows


def to_json(metas: Iterable[FileMetadata]) -> str:
    return json.dumps(to_dicts(metas), indent=2, ensure_ascii=False)


def to_csv(metas: Iterable[FileMetadata]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["file", "format", "group", "name", "value", "risk"])
    for meta in metas:
        for e in meta.entries:
            writer.writerow([str(meta.path), meta.format, e.group, e.name, e.value, e.risk.label])
    return buffer.getvalue()
