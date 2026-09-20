import tempfile
import unittest
from pathlib import Path

from _support import *  # noqa: F401,F403
from report_collector.manifest import expected_issues, read_manifest, write_manifest
from report_collector.models import Cadence, Issue, Record, Source, Status, Tier


def source(cadence, months=()):
    return Source(key="k", name="Report", publisher="Pub", tier=Tier.MANUAL,
                  cadence=cadence, months=months, manual_reason="member login required")


class ExpectedIssues(unittest.TestCase):
    def test_monthly_expects_twelve(self):
        self.assertEqual(len(expected_issues(source(Cadence.MONTHLY), 2026)), 12)

    def test_quarterly_expects_its_declared_months(self):
        issues = expected_issues(source(Cadence.QUARTERLY, (1, 4, 7, 10)), 2026)
        self.assertEqual([i.month for i in issues], [1, 4, 7, 10])

    def test_window_sources_expect_nothing(self):
        # An irregular publication would otherwise manufacture eleven false misses a year.
        self.assertEqual(expected_issues(source(Cadence.WINDOW), 2026), [])


class ManifestRoundTrip(unittest.TestCase):
    def test_written_rows_read_back_identically(self):
        src = source(Cadence.MONTHLY)
        records = [Record(Issue("k", 2026, 2), src, Status.MANUAL, note="member login required"),
                   Record(Issue("k", 2026, 1), src, Status.DOWNLOADED,
                          filename="k__2026-01__Report.pdf", sha256="abc")]
        with tempfile.TemporaryDirectory() as tmp:
            write_manifest(Path(tmp), records)
            rows = read_manifest(Path(tmp))
        self.assertEqual([r["period"] for r in rows], ["2026-01", "2026-02"])  # sorted
        self.assertEqual(rows[0]["status"], "downloaded")
        self.assertEqual(rows[1]["note"], "member login required")

    def test_rewriting_replaces_rather_than_appends(self):
        src = source(Cadence.MONTHLY)
        with tempfile.TemporaryDirectory() as tmp:
            write_manifest(Path(tmp), [Record(Issue("k", 2026, 1), src, Status.MANUAL)])
            write_manifest(Path(tmp), [Record(Issue("k", 2026, 1), src, Status.MANUAL_DONE,
                                              filename="f.pdf")])
            rows = read_manifest(Path(tmp))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "manual-done")


if __name__ == "__main__":
    unittest.main()
