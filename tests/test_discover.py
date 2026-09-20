import unittest

from _support import *  # noqa: F401,F403
from report_collector.discover import candidates_for_issue, find_links, year_in
from report_collector.models import Cadence, Source, Tier

HTML = """
<ul>
  <li><a href="/files/outlook-june-2026.pdf">Outlook June 2026</a></li>
  <li><a href="/files/outlook-may-2026.pdf">Outlook May 2026</a></li>
  <li><a href="/files/outlook-june-2019.pdf">Outlook June 2019 (archive)</a></li>
  <li><a href="https://elsewhere.example/partner-outlook-june-2026.pdf">Partner Outlook June 2026</a></li>
  <li><a href="/files/template.docx">Response template</a></li>
</ul>
"""

SOURCE = Source(key="acme", name="Outlook", publisher="Acme", tier=Tier.SCRAPE,
                cadence=Cadence.MONTHLY, landing_url="https://acme.example/reports",
                allowed_hosts=("acme.example",), extensions=(".pdf",), year_window=1)


class FindLinks(unittest.TestCase):
    def test_relative_links_are_made_absolute(self):
        links = find_links(HTML, "https://acme.example/reports")
        self.assertIn("https://acme.example/files/outlook-june-2026.pdf",
                      [href for href, _ in links])


class Candidates(unittest.TestCase):
    def setUp(self):
        self.links = find_links(HTML, "https://acme.example/reports")
        self.found = candidates_for_issue(SOURCE, self.links, 2026, 6)

    def test_the_issues_own_file_ranks_first(self):
        self.assertEqual(self.found[0], "https://acme.example/files/outlook-june-2026.pdf")

    def test_another_publisher_on_the_same_page_is_never_taken(self):
        self.assertTrue(all("elsewhere.example" not in url for url in self.found))

    def test_old_archive_links_are_outside_the_year_window(self):
        self.assertTrue(all("2019" not in url for url in self.found))

    def test_non_matching_extensions_are_ignored(self):
        self.assertTrue(all(not url.endswith(".docx") for url in self.found))


class YearIn(unittest.TestCase):
    def test_finds_a_four_digit_year(self):
        self.assertEqual(year_in("outlook-june-2026.pdf"), 2026)
        self.assertIsNone(year_in("outlook-latest.pdf"))


if __name__ == "__main__":
    unittest.main()


WINDOW_HTML = """
<a href="/pub/eb202605.en.pdf">6 August 2026 Economic Bulletin Issue 5, 2026</a>
<a href="/pub/eb202604.en.pdf">25 June 2026 Economic Bulletin Issue 4, 2026</a>
<a href="/pub/eb202501.en.pdf">12 February 2025 Economic Bulletin Issue 1, 2025</a>
<a href="/pub/undated-overview.pdf">Overview</a>
"""

WINDOW_SOURCE = Source(key="eb", name="Bulletin", publisher="Bank", tier=Tier.SCRAPE,
                       cadence=Cadence.WINDOW, landing_url="https://bank.example/eb",
                       allowed_hosts=("bank.example",), extensions=(".pdf",))


class WindowCandidates(unittest.TestCase):
    def setUp(self):
        from report_collector.discover import window_candidates
        links = find_links(WINDOW_HTML, "https://bank.example/eb")
        self.found = dict(window_candidates(WINDOW_SOURCE, links, 2026))

    def test_month_comes_from_the_link_text(self):
        self.assertEqual(self.found["https://bank.example/pub/eb202605.en.pdf"], 8)
        self.assertEqual(self.found["https://bank.example/pub/eb202604.en.pdf"], 6)

    def test_other_years_are_not_collected_into_this_year(self):
        self.assertNotIn("https://bank.example/pub/eb202501.en.pdf", self.found)

    def test_a_link_naming_no_month_is_left_alone_rather_than_guessed(self):
        self.assertNotIn("https://bank.example/pub/undated-overview.pdf", self.found)


class MonthIn(unittest.TestCase):
    def test_reads_month_names_and_numeric_dates(self):
        from report_collector.discover import month_in
        self.assertEqual(month_in("Published 6 August 2026"), 8)
        self.assertEqual(month_in("/files/2026-03/report.pdf"), 3)
        self.assertIsNone(month_in("Annual overview"))
