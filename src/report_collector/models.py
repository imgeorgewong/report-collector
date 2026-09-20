"""Data model: what a source declares, and what a run records about it.

Everything here is a plain dataclass. A source is a *declaration* - what to fetch and how to
recognise it - never code, so that adding a publisher is a data change and the engine stays
the only place where behaviour lives.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Tier(str, Enum):
    """How an issue is obtained."""

    TEMPLATE = "template"   # the URL can be built from the period alone
    SCRAPE = "scrape"       # the URL has to be found on a landing page
    MANUAL = "manual"       # a person downloads it; the engine only tracks whether they did


class Cadence(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    WINDOW = "window"       # published irregularly: collect whatever is there, never expect a month


class Status(str, Enum):
    """The status of one expected issue after a run.

    Keep `missed` and `manual` apart: `missed` means the engine looked and the issue is gone
    from the source, `manual` means it is the operator's turn. Collapsing the two hides work
    that a person could still do.
    """

    DOWNLOADED = "downloaded"     # new file written this run
    UNCHANGED = "unchanged"       # already archived, content identical
    MANUAL = "manual"             # tier 3, or blocked: a person must fetch it
    MANUAL_DONE = "manual-done"   # a hand-downloaded file was found in the month folder
    MISSED = "missed"             # due, looked for, not obtainable any more
    NO_ISSUE = "no-issue"         # the publisher did not publish for this period
    FUTURE = "future"             # not due yet
    ABSENT = "absent"             # due, nothing matched - not published, rolled off, or pattern wrong


@dataclass(frozen=True)
class Source:
    """One publication series from one publisher."""

    key: str                       # short identifier, also used as a filename prefix
    name: str                      # human name of the publication
    publisher: str
    tier: Tier
    cadence: Cadence
    landing_url: str = ""          # SCRAPE: the page that links to the issues
    url_template: str = ""         # TEMPLATE: e.g. ".../{year}/report-{month:02d}.pdf"
    months: tuple[int, ...] = ()   # QUARTERLY/ANNUAL: months an issue is expected in
    link_patterns: tuple[str, ...] = ()   # regexes matched against href and anchor text
    allowed_hosts: tuple[str, ...] = ()   # default deny: a link off these hosts is never taken
    extensions: tuple[str, ...] = (".pdf",)
    extra_urls: tuple[str, ...] = ()      # URLs a person pasted in, for sources whose links
                                          # cannot be discovered (e.g. revealed after a form)
    url_rewrite: tuple[str, str] = ()     # (regex, replacement): the link found is not the
                                          # file, but the file's address can be derived from
                                          # it, e.g. an article page -> its PDF
    detail_page: bool = False             # the link found is an article page: open it and
                                          # look for the document on that page
    edition_tokens: tuple[str, ...] = ()  # text that must appear for the issue to be the right
                                          # edition; "{year}" is substituted per issue
    year_window: int = 1           # how many years back a landing page's links may go
    save_text: bool = True         # HTML issues: save the extracted main text
    manual_reason: str = ""        # why this is MANUAL - a reason, never "it didn't work"
    notes: str = ""

    def validate(self) -> list[str]:
        """Return a list of problems. A declaration that cannot work should say so before a run."""
        problems: list[str] = []
        if not self.key or " " in self.key:
            problems.append(f"{self.key!r}: key must be non-empty and contain no spaces")
        if self.tier is Tier.TEMPLATE and not self.url_template:
            problems.append(f"{self.key}: tier TEMPLATE needs url_template")
        if self.tier is Tier.SCRAPE and not self.landing_url:
            problems.append(f"{self.key}: tier SCRAPE needs landing_url")
        if self.tier is Tier.SCRAPE and not self.allowed_hosts:
            problems.append(
                f"{self.key}: tier SCRAPE needs allowed_hosts. Matching a link by its text alone "
                "picks up other publishers' documents hosted on the same page.")
        if self.tier is Tier.MANUAL and not self.manual_reason:
            problems.append(f"{self.key}: tier MANUAL needs manual_reason")
        if self.cadence in (Cadence.QUARTERLY, Cadence.ANNUAL) and not self.months:
            problems.append(f"{self.key}: cadence {self.cadence.value} needs months")
        if any(not (1 <= m <= 12) for m in self.months):
            problems.append(f"{self.key}: months out of range: {self.months}")
        if self.url_rewrite and len(self.url_rewrite) != 2:
            problems.append(f"{self.key}: url_rewrite must be (regex, replacement)")
        if (self.url_rewrite or self.detail_page) and self.tier is not Tier.SCRAPE:
            problems.append(
                f"{self.key}: url_rewrite / detail_page only apply to tier SCRAPE")
        return problems


@dataclass(frozen=True)
class Issue:
    """One expected issue of one source: the unit the manifest has a row for."""

    source_key: str
    year: int
    month: int

    @property
    def label(self) -> str:
        return f"{self.year}-{self.month:02d}"

    @property
    def is_future(self) -> bool:
        today = date.today()
        return (self.year, self.month) > (today.year, today.month)


@dataclass
class Record:
    """One manifest row: an issue plus what happened to it."""

    issue: Issue
    source: Source
    status: Status
    url: str = ""
    filename: str = ""
    sha256: str = ""
    note: str = ""
    checked_at: str = ""

    def as_row(self) -> dict[str, str]:
        return {
            "source_key": self.source.key,
            "source_name": self.source.name,
            "publisher": self.source.publisher,
            "period": self.issue.label,
            "status": self.status.value,
            "url": self.url,
            "filename": self.filename,
            "sha256": self.sha256,
            "note": self.note,
            "checked_at": self.checked_at,
        }


MANIFEST_COLUMNS = [
    "source_key", "source_name", "publisher", "period", "status",
    "url", "filename", "sha256", "note", "checked_at",
]


@dataclass
class FetchResult:
    """What came back from one HTTP request."""

    url: str                  # the URL asked for
    final_url: str            # where the response actually came from
    status: int
    body: bytes = b""
    content_type: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == 200 and not self.error

    @property
    def is_pdf(self) -> bool:
        return self.body[:5] == b"%PDF-"


@dataclass
class RunSummary:
    """Counts per status, plus the records themselves."""

    records: list[Record] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for record in self.records:
            out[record.status.value] = out.get(record.status.value, 0) + 1
        return dict(sorted(out.items()))

    def __str__(self) -> str:
        return "  ".join(f"{k}={v}" for k, v in self.counts().items())
