"""Audit: check the manifest against the files on disk, row by row.

A run summary counts what the engine *believed*. This reads what is actually there. The two
disagreeing is the interesting case, and it is invisible in a green summary - the first real
run of a collector wrote 39 files, reported no errors, and six of them were the wrong
document.
"""
from __future__ import annotations

from pathlib import Path

from .archive import MONTH_FOLDERS
from .manifest import read_manifest
from .models import Status

HOLDING_STATUSES = {Status.DOWNLOADED.value, Status.UNCHANGED.value, Status.MANUAL_DONE.value}


def audit(root: Path) -> list[str]:
    """Return a list of problems. An empty list is the only good result."""
    root = Path(root)
    rows = read_manifest(root)
    problems: list[str] = []
    if not rows:
        return [f"no manifest in {root}"]

    on_disk: set[str] = set()
    for year_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for month_dir in sorted(p for p in year_dir.iterdir() if p.is_dir()):
            for file in month_dir.iterdir():
                if file.is_file() and not file.name.startswith("."):
                    on_disk.add(f"{year_dir.name}/{month_dir.name}/{file.name}")

    claimed: set[str] = set()
    for row in rows:
        status, name, period = row["status"], row["filename"], row["period"]
        year, month = period.split("-")
        expected_dir = f"{year}/{MONTH_FOLDERS[int(month) - 1]}"

        if status in HOLDING_STATUSES:
            if not name:
                problems.append(f"{row['source_key']} {period}: status {status} with no filename")
                continue
            path = f"{expected_dir}/{name}"
            if path not in on_disk:
                problems.append(f"{row['source_key']} {period}: {status}, but {path} is not on disk")
            else:
                claimed.add(path)
        elif name:
            problems.append(f"{row['source_key']} {period}: status {status} but a filename is set")

    for path in sorted(on_disk - claimed):
        problems.append(f"file not claimed by any manifest row: {path}")

    # Duplicate content across rows: the same document filed twice under different periods.
    digests: dict[str, str] = {}
    for row in rows:
        digest = row.get("sha256") or ""
        if not digest:
            continue
        first = digests.get(digest)
        if first:
            problems.append(
                f"{row['source_key']} {row['period']}: identical content to {first} "
                "- one of the two is the wrong edition")
        else:
            digests[digest] = f"{row['source_key']} {row['period']}"

    return problems
