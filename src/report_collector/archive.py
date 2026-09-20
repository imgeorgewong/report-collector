"""Where a file goes, and under what name.

Archived by *publication* month, never by download date: anything reading this archive later
needs to know when a view was published, not when it was noticed.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from .models import Issue, Source

MONTH_FOLDERS = ["01_Jan", "02_Feb", "03_Mar", "04_Apr", "05_May", "06_Jun",
                 "07_Jul", "08_Aug", "09_Sep", "10_Oct", "11_Nov", "12_Dec"]


def month_dir(root: Path, issue: Issue) -> Path:
    return root / str(issue.year) / MONTH_FOLDERS[issue.month - 1]


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:60]


def filename_for(source: Source, issue: Issue, suffix: str) -> str:
    """`<key>__<period>__<name>.<ext>` - the prefix is what lets a hand-downloaded file be
    claimed by the right row later."""
    return f"{source.key}__{issue.label}__{slug(source.name)}{suffix}"


def write_atomic(path: Path, data: bytes) -> None:
    """Write via a temporary file in the same directory, then replace.

    A run interrupted halfway through a write leaves a truncated file that looks archived.
    Replace is atomic on the same filesystem; a partial temp file is obvious and harmless.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(handle, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def canonical_names(source: Source, issue: Issue) -> set[str]:
    """The names this engine writes for an issue - everything else in the folder is a human's."""
    return {filename_for(source, issue, suffix) for suffix in (".pdf", ".txt")}


def claimed_file(root: Path, source: Source, issue: Issue,
                 exclude: set[str] | None = None) -> Path | None:
    """A file a person dropped into the month folder for this source.

    Manual rows are claimed by the *file*, not by editing the manifest: the manifest is
    regenerated on every run, so a hand-edited status is wiped the next time the collector
    runs. A file on disk survives.

    `exclude` keeps the engine from claiming its own output. Without it, a file downloaded
    automatically last month is read back as a hand-download this month, and the run stops
    checking whether the source still publishes it.
    """
    folder = month_dir(root, issue)
    if not folder.is_dir():
        return None
    skip = {name.lower() for name in (exclude or set())}
    prefix = f"{source.key}__"
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        name = path.name.lower()
        if name in skip:
            continue
        if name.startswith(prefix.lower()):
            return path
        if source.key.lower() in re.split(r"[^a-z0-9]+", name):
            return path
    return None
