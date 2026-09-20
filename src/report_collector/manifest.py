"""The manifest: one row per expected issue, regenerated on every run.

It is a *generated* file. Statuses are never hand-edited - a hand mark is wiped by the next
run, and the file on disk is the evidence that survives (see archive.claimed_file).
"""
from __future__ import annotations

import csv
import os
import tempfile
from datetime import date
from pathlib import Path

from .models import MANIFEST_COLUMNS, Cadence, Issue, Record, Source

MANIFEST_NAME = "_manifest.csv"


def expected_issues(source: Source, year: int) -> list[Issue]:
    """The issues a source is expected to publish in a year.

    A WINDOW source deliberately produces no monthly rows. Publications that appear when the
    publisher feels like it would otherwise manufacture eleven false misses a year, and a
    manifest full of false misses is one nobody reads.
    """
    if source.cadence is Cadence.MONTHLY:
        months = range(1, 13)
    elif source.cadence in (Cadence.QUARTERLY, Cadence.ANNUAL):
        months = source.months
    else:
        return []
    return [Issue(source.key, year, month) for month in months]


def write_manifest(root: Path, records: list[Record]) -> Path:
    """Write the manifest atomically, so a locked or half-written file never loses a run."""
    path = root / MANIFEST_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".csv")
    try:
        with os.fdopen(handle, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
            writer.writeheader()
            for record in sorted(records, key=lambda r: (r.source.key, r.issue.label)):
                writer.writerow(record.as_row())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


def read_manifest(root: Path) -> list[dict[str, str]]:
    path = root / MANIFEST_NAME
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def today_iso() -> str:
    return date.today().isoformat()
