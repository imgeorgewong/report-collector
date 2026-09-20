import unittest

from _support import PDF_BYTES
from report_collector.guards import (duplicate_of, edition_matches, host_allowed,
                                     looks_like_document, redirected_away, stable_identity,
                                     within_year_window)
from report_collector.models import Cadence, FetchResult, Source, Tier


def make_source(**kwargs):
    base = dict(key="acme", name="Outlook", publisher="Acme", tier=Tier.SCRAPE,
                cadence=Cadence.MONTHLY, landing_url="https://acme.example/reports",
                allowed_hosts=("acme.example",))
    base.update(kwargs)
    return Source(**base)


class StableIdentity(unittest.TestCase):
    def test_query_string_is_not_identity(self):
        # Per-request tokens change on every fetch; keying on them re-downloads for ever.
        a = stable_identity("https://a.example/x/report.pdf?ver=123&apikey=abc")
        b = stable_identity("https://a.example/x/report.pdf?ver=999")
        self.assertEqual(a, b)

    def test_alternate_spelling_of_the_same_file(self):
        self.assertEqual(
            stable_identity("https://a.example/r.pdf"),
            stable_identity("https://a.example/r.coredownload.inline.pdf"))

    def test_different_documents_stay_different(self):
        self.assertNotEqual(stable_identity("https://a.example/1.pdf"),
                            stable_identity("https://a.example/2.pdf"))


class HostAllowList(unittest.TestCase):
    def test_default_deny_when_no_hosts_declared(self):
        source = Source(key="k", name="n", publisher="p", tier=Tier.TEMPLATE,
                        cadence=Cadence.MONTHLY, url_template="https://x.example/{year}.pdf")
        self.assertFalse(host_allowed("https://x.example/a.pdf", source))

    def test_subdomains_allowed_but_lookalikes_not(self):
        source = make_source()
        self.assertTrue(host_allowed("https://cdn.acme.example/a.pdf", source))
        self.assertFalse(host_allowed("https://acme.example.evil.test/a.pdf", source))
        self.assertFalse(host_allowed("https://other.example/a.pdf", source))


class RedirectGuard(unittest.TestCase):
    def test_landing_somewhere_else_is_not_this_issue(self):
        result = FetchResult(url="https://a.example/2026/june.pdf",
                             final_url="https://a.example/latest", status=200, body=PDF_BYTES)
        self.assertTrue(redirected_away(result))

    def test_same_document_with_a_tracking_parameter_is_fine(self):
        result = FetchResult(url="https://a.example/r.pdf",
                             final_url="https://a.example/r.pdf?icid=nav", status=200,
                             body=PDF_BYTES)
        self.assertFalse(redirected_away(result))


class DuplicateGuard(unittest.TestCase):
    def test_reports_the_period_the_content_was_first_seen_as(self):
        seen = {"deadbeef": "2026-03"}
        self.assertEqual(duplicate_of("deadbeef", seen), "2026-03")
        self.assertIsNone(duplicate_of("other", seen))


class EditionGuard(unittest.TestCase):
    def test_year_token_must_appear(self):
        source = make_source(edition_tokens=("{year}",))
        self.assertTrue(edition_matches(source, 2026, "Outlook 2026 edition", "https://a/x.pdf"))
        self.assertFalse(edition_matches(source, 2026, "Outlook 2025 edition", "https://a/x.pdf"))

    def test_no_tokens_means_no_opinion(self):
        self.assertTrue(edition_matches(make_source(), 2026, "anything", "https://a/x.pdf"))


class YearWindow(unittest.TestCase):
    def test_old_archive_links_are_out_of_scope(self):
        source = make_source(year_window=1)
        self.assertTrue(within_year_window(source, 2026, 2026))
        self.assertTrue(within_year_window(source, 2026, 2025))
        self.assertFalse(within_year_window(source, 2026, 2019))

    def test_undated_link_is_not_excluded(self):
        self.assertTrue(within_year_window(make_source(), 2026, None))


class ShapeCheck(unittest.TestCase):
    def test_pdf_is_recognised_by_magic_bytes_not_status(self):
        source = make_source(extensions=(".pdf",))
        good = FetchResult(url="u", final_url="u", status=200, body=PDF_BYTES)
        soft404 = FetchResult(url="u", final_url="u", status=200,
                              body=b"<html>Page not found</html>", content_type="text/html")
        self.assertTrue(looks_like_document(good, source))
        self.assertFalse(looks_like_document(soft404, source))


if __name__ == "__main__":
    unittest.main()
