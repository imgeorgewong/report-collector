"""Find the document link for one issue on a publisher's page.

The rules here are all consequences of the same fact: link text is written for humans. A
pattern loose enough to match every month's wording also matches the compliance disclosure,
the template file and someone else's report hosted on the same page. So: match on the href
*and* the anchor text, pin the host, and prefer a miss over a wrong file.
"""
from __future__ import annotations

import re
import urllib.parse
from html.parser import HTMLParser

from .guards import host_allowed, within_year_window
from .models import Source

MONTH_NAMES = ["january", "february", "march", "april", "may", "june",
               "july", "august", "september", "october", "november", "december"]


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []   # (href, anchor text)
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attributes = dict(attrs)
            # data-* attributes carry the real target on sites that attach downloads via JS.
            href = (attributes.get("href") or attributes.get("data-href")
                    or attributes.get("data-url") or attributes.get("data-file"))
            self._href = href
            self._text = []

    def handle_data(self, data):
        if self._href is not None and data.strip():
            self._text.append(data.strip())

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text)))
            self._href, self._text = None, []


def find_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """All links on a page as (absolute href, anchor text)."""
    parser = _LinkParser()
    parser.feed(html)
    return [(urllib.parse.urljoin(base_url, href), text) for href, text in parser.links if href]


def year_in(text: str) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return int(match.group(0)) if match else None


def candidates_for_issue(
    source: Source, links: list[tuple[str, str]], year: int, month: int
) -> list[str]:
    """Links that could be this issue, best first.

    A candidate has to pass all of:
      * the host is on the source's allow list (default deny);
      * the extension matches, or a declared link pattern matches the href or the text;
      * the year, where the link carries one, is inside the source's year window.
    Candidates that name the issue's month or year rank above ones that do not, so an
    "evergreen" link is only taken when nothing dated matches.
    """
    month_name = MONTH_NAMES[month - 1]
    patterns = [re.compile(p, re.I) for p in source.link_patterns]
    scored: list[tuple[int, str]] = []

    for href, text in links:
        if not host_allowed(href, source):
            continue
        haystack = f"{href} {text}".lower()
        ext_ok = any(href.lower().split("?")[0].endswith(e.lower()) for e in source.extensions)
        pattern_ok = any(p.search(href) or p.search(text) for p in patterns) if patterns else False
        if not (ext_ok or pattern_ok):
            continue
        link_year = year_in(href) or year_in(text)
        if not within_year_window(source, year, link_year):
            continue

        score = 0
        if link_year == year:
            score += 4
        if month_name in haystack or f"-{month:02d}" in haystack or f"_{month:02d}" in haystack:
            score += 3
        if ext_ok:
            score += 1
        scored.append((score, href))

    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    seen: set[str] = set()
    ordered: list[str] = []
    for _, href in scored:
        if href not in seen:
            seen.add(href)
            ordered.append(href)
    return ordered


def month_in(text: str) -> int | None:
    """The month a link names, from its text or its href, or None."""
    lowered = text.lower()
    for index, name in enumerate(MONTH_NAMES, start=1):
        if name in lowered or f"-{name[:3]}-" in lowered:
            return index
    match = re.search(r"\b(19|20)\d{2}[-_/](0[1-9]|1[0-2])\b", lowered)
    return int(match.group(2)) if match else None


def window_candidates(source: Source, links: list[tuple[str, str]],
                      year: int) -> list[tuple[str, int]]:
    """For irregular publications: every link that qualifies, with the month it names.

    A publication that appears when the publisher decides gets no expected months - asking
    "where is the March issue?" of something that publishes eight times a year manufactures
    misses that are not misses. Instead the links themselves say which month they belong to,
    and a link that names no month is left alone rather than guessed at.
    """
    out: list[tuple[str, int]] = []
    patterns = [re.compile(p, re.I) for p in source.link_patterns]
    for href, text in links:
        if not host_allowed(href, source):
            continue
        ext_ok = any(href.lower().split("?")[0].endswith(e.lower()) for e in source.extensions)
        pattern_ok = any(p.search(href) or p.search(text) for p in patterns) if patterns else False
        if not (ext_ok or pattern_ok):
            continue
        link_year = year_in(href) or year_in(text)
        if link_year is not None and link_year != year:
            continue
        month = month_in(text) or month_in(href)
        if month:
            out.append((href, month))
    return out
