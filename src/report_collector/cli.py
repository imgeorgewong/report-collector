"""Command line: `python -m report_collector <command>`.

Everything here is a thin wrapper over the library functions, so the same behaviour is
available to a script, a notebook, or an editor that can only press Run.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from .audit import audit
from .engine import run
from .http import Fetcher
from .models import Source


def load_registry(path: str) -> list[Source]:
    """Import a .py registry file and return its SOURCES list."""
    spec = importlib.util.spec_from_file_location("registry", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import registry: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sources = getattr(module, "SOURCES", None)
    if not sources:
        raise SystemExit(f"{path} defines no SOURCES list")
    return list(sources)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="report-collector")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="collect one year into an archive folder")
    run_cmd.add_argument("--registry", required=True, help="path to a .py file defining SOURCES")
    run_cmd.add_argument("--archive", required=True, help="archive root folder")
    run_cmd.add_argument("--year", type=int, required=True)
    run_cmd.add_argument("--pace", type=float, default=1.0, help="seconds between requests per host")
    run_cmd.add_argument("--ignore-robots", action="store_true",
                         help="not recommended; provided so the choice is explicit rather than silent")

    audit_cmd = sub.add_parser("audit", help="check the manifest against the files on disk")
    audit_cmd.add_argument("--archive", required=True)

    check_cmd = sub.add_parser("check", help="validate a registry without fetching anything")
    check_cmd.add_argument("--registry", required=True)

    args = parser.parse_args(argv)

    if args.command == "check":
        sources = load_registry(args.registry)
        problems = [p for s in sources for p in s.validate()]
        print("\n".join(problems) if problems else f"{len(sources)} sources, no problems.")
        return 1 if problems else 0

    if args.command == "audit":
        problems = audit(Path(args.archive))
        print("\n".join(problems) if problems else "Audit passed: manifest and files agree.")
        return 1 if problems else 0

    sources = load_registry(args.registry)
    fetcher = Fetcher(pace_seconds=args.pace, obey_robots=not args.ignore_robots)
    summary = run(sources, Path(args.archive), args.year, fetcher=fetcher)
    print(summary)
    print("\nRun it a second time: every row should then be unchanged/manual/future - "
          "a downloaded on the second run means de-duplication is not matching.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
