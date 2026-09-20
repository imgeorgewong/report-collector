import tempfile
import unittest
from pathlib import Path

from _support import PDF_BYTES, FakeFetcher
from report_collector.archive import month_dir
from report_collector.engine import run
from report_collector.models import Cadence, Issue, Source, Status, Tier

LANDING = "https://acme.example/reports"


def template_source(**kwargs):
    base = dict(key="acme", name="Monthly Outlook", publisher="Acme", tier=Tier.TEMPLATE,
                cadence=Cadence.QUARTERLY, months=(1,),
                url_template="https://acme.example/{year}/outlook-{month:02d}.pdf",
                allowed_hosts=("acme.example",))
    base.update(kwargs)
    return Source(**base)


def statuses(summary):
    return {r.issue.label: r.status for r in summary.records}


class TemplateSource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.url = "https://acme.example/2026/outlook-01.pdf"
        self.fetcher = FakeFetcher({self.url: (PDF_BYTES, "application/pdf", None)})

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_run_downloads_and_files_by_publication_month(self):
        summary = run([template_source()], self.root, 2026, fetcher=self.fetcher)
        self.assertEqual(statuses(summary)["2026-01"], Status.DOWNLOADED)
        folder = month_dir(self.root, Issue("acme", 2026, 1))
        self.assertEqual([p.name for p in folder.iterdir()],
                         ["acme__2026-01__Monthly-Outlook.pdf"])

    def test_second_run_downloads_nothing(self):
        # The acceptance test for any registry: a second run must report downloaded = 0.
        run([template_source()], self.root, 2026, fetcher=self.fetcher)
        summary = run([template_source()], self.root, 2026, fetcher=self.fetcher)
        self.assertEqual(summary.counts().get("downloaded", 0), 0)
        self.assertEqual(statuses(summary)["2026-01"], Status.UNCHANGED)


class Failures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_redirect_to_a_hub_page_is_not_archived(self):
        url = "https://acme.example/2026/outlook-01.pdf"
        fetcher = FakeFetcher({url: (PDF_BYTES, "application/pdf", "https://acme.example/latest")})
        summary = run([template_source()], self.root, 2026, fetcher=fetcher)
        record = summary.records[0]
        self.assertIn(record.status, {Status.MISSED, Status.ABSENT})
        self.assertIn("redirected", record.note)
        self.assertFalse(any(month_dir(self.root, Issue("acme", 2026, 1)).glob("*")))

    def test_html_where_a_pdf_was_expected_is_not_archived(self):
        url = "https://acme.example/2026/outlook-01.pdf"
        fetcher = FakeFetcher({url: (b"<html>Sorry, page not found</html>", "text/html", None)})
        summary = run([template_source()], self.root, 2026, fetcher=fetcher)
        self.assertIn("not the expected document type", summary.records[0].note)

    def test_identical_content_for_two_periods_is_flagged_not_filed_twice(self):
        source = template_source(cadence=Cadence.QUARTERLY, months=(1, 4))
        fetcher = FakeFetcher({
            "https://acme.example/2026/outlook-01.pdf": (PDF_BYTES, "application/pdf", None),
            "https://acme.example/2026/outlook-04.pdf": (PDF_BYTES, "application/pdf", None),
        })
        summary = run([source], self.root, 2026, fetcher=fetcher)
        result = statuses(summary)
        self.assertEqual(result["2026-01"], Status.DOWNLOADED)
        self.assertEqual(result["2026-04"], Status.ABSENT)
        note = [r.note for r in summary.records if r.issue.label == "2026-04"][0]
        self.assertIn("same content as 2026-01", note)

    def test_a_missing_file_is_missed_not_silently_skipped(self):
        fetcher = FakeFetcher({})   # every request 404s
        summary = run([template_source()], self.root, 2026, fetcher=fetcher)
        self.assertEqual(summary.records[0].status, Status.MISSED)


class ScrapeAndManual(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_link_is_discovered_on_the_landing_page(self):
        html = ('<a href="/files/outlook-january-2026.pdf">Outlook January 2026</a>'
                '<a href="https://elsewhere.example/other-january-2026.pdf">Partner report</a>')
        source = Source(key="acme", name="Outlook", publisher="Acme", tier=Tier.SCRAPE,
                        cadence=Cadence.QUARTERLY, months=(1,), landing_url=LANDING,
                        allowed_hosts=("acme.example",))
        fetcher = FakeFetcher({
            LANDING: (html.encode(), "text/html", None),
            "https://acme.example/files/outlook-january-2026.pdf":
                (PDF_BYTES, "application/pdf", None),
        })
        summary = run([source], self.root, 2026, fetcher=fetcher)
        self.assertEqual(summary.records[0].status, Status.DOWNLOADED)
        self.assertNotIn("https://elsewhere.example/other-january-2026.pdf", fetcher.calls)

    def test_manual_source_becomes_manual_done_when_the_file_appears(self):
        source = Source(key="mem", name="Member Survey", publisher="Body", tier=Tier.MANUAL,
                        cadence=Cadence.QUARTERLY, months=(1,),
                        manual_reason="member login required")
        summary = run([source], self.root, 2026, fetcher=FakeFetcher({}))
        self.assertEqual(summary.records[0].status, Status.MANUAL)
        self.assertEqual(summary.records[0].note, "member login required")

        folder = month_dir(self.root, Issue("mem", 2026, 1))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "mem__2026-01__hand-download.pdf").write_bytes(PDF_BYTES)
        summary = run([source], self.root, 2026, fetcher=FakeFetcher({}))
        self.assertEqual(summary.records[0].status, Status.MANUAL_DONE)


class Validation(unittest.TestCase):
    def test_a_scrape_source_without_allowed_hosts_is_rejected_before_any_request(self):
        source = Source(key="x", name="X", publisher="P", tier=Tier.SCRAPE,
                        cadence=Cadence.MONTHLY, landing_url=LANDING)
        fetcher = FakeFetcher({})
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as caught:
                run([source], Path(tmp), 2026, fetcher=fetcher)
        self.assertIn("allowed_hosts", str(caught.exception))
        self.assertEqual(fetcher.calls, [])


if __name__ == "__main__":
    unittest.main()
