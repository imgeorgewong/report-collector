#!/usr/bin/env python3
"""Block commits that contain employer-internal or credential-like content.

Usage:
    python tools/check_sensitive.py            # scan files staged for commit (pre-commit hook)
    python tools/check_sensitive.py --all      # scan every tracked + untracked file (pre-release review)

A line can opt out of one match by ending with the marker  `sensitive-scan: allow`
(use sparingly, and only after reading the line).
"""
import re
import subprocess
import sys
from pathlib import Path

# File types that must never be committed. Excel files hide connection strings,
# cached data and author metadata even when the visible cells are empty.
BLOCKED_EXTENSIONS = {".xlsx", ".xlsm", ".xlsb", ".xls", ".pbix", ".pdf", ".csv", ".ods"}

# (label, pattern). Case-insensitive.
PATTERNS = [
    ("employer name", r"\bsisk\b"),
    ("SharePoint / OneDrive URL", r"sharepoint\.com|/sites/[A-Za-z0-9_-]+|onedrive\s*-\s*\w"),
    ("Power Platform / Dataverse", r"powerplatform|dynamics\.com|crm\d*\.dynamics|dataflow"),
    ("tenant / environment id", r"\btenant\s*id\b|\benvironment\s*id\b"),
    ("GUID", r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
    ("Windows user path", r"[a-z]:\\users\\[^\\\s<>]+"),
    ("secret-looking assignment",
     r"(api[_-]?key|securitytoken|token|password|passwd|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
    ("key in URL query", r"[?&](api[_-]?key|token|securityToken|sig|signature)=[A-Za-z0-9_\-%]{8,}"),
]
ALLOW_MARKER = "sensitive-scan: allow"
SELF = Path(__file__).resolve()


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False).stdout


def files_to_scan(scan_all):
    if scan_all:
        out = git("ls-files", "--cached", "--others", "--exclude-standard")
    else:
        out = git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return [Path(p) for p in out.splitlines() if p.strip()]


def scan(paths):
    problems = []
    compiled = [(label, re.compile(rx, re.IGNORECASE)) for label, rx in PATTERNS]
    for path in paths:
        if path.suffix.lower() in BLOCKED_EXTENSIONS:
            problems.append(f"{path}: blocked file type {path.suffix}")
            continue
        if not path.is_file() or path.resolve() == SELF or path.name == SELF.name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append(f"{path}: binary file - review by hand before committing")
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if ALLOW_MARKER in line:
                continue
            for label, rx in compiled:
                if rx.search(line):
                    problems.append(f"{path}:{lineno}: {label}: {line.strip()[:120]}")
    return problems


def main():
    scan_all = "--all" in sys.argv
    problems = scan(files_to_scan(scan_all))
    if problems:
        print("Sensitive-content check FAILED:\n")
        print("\n".join(problems))
        print(f"\n{len(problems)} problem(s). Fix them, or mark a reviewed line with '{ALLOW_MARKER}'.")
        return 1
    print("Sensitive-content check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
