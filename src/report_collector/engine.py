"""The run: for each source, for each expected issue, decide a status and archive a file.

The whole engine is one pass with no hidden state beyond `seen_hashes`, which exists to
catch one issue's content being saved twice in a single run.

The acceptance test for any registry is not in this file: run it twice. On the second run
every row must be `unchanged`, `manual`, `manual-done`, `no-issue`, `future` or `absent` -
never `downloaded`. A `downloaded` on an unchanged source means the de-duplication key is
matching something volatile, and the collector would re-download for ever.
"""
from __future__ import annotations

import re
from pathlib import Path

from .archive import (canonical_names, claimed_file, filename_for, month_dir,
                      write_atomic)
from .discover import candidates_for_issue, find_links, window_candidates
from .extract import decode, fingerprint_text, html_to_text
from .guards import (duplicate_of, edition_matches, host_allowed,
                     looks_like_document, redirected_away, sha256)
from .http import Fetcher
from .manifest import expected_issues, today_iso, write_manifest
from .models import Cadence, FetchResult, Issue, Record, RunSummary, Source, Status, Tier


def _template_url(source: Source, issue: Issue) -> str:
    return source.url_template.format(year=issue.year, month=issue.month,
                                      month_name=f"{issue.month:02d}",
                                      quarter=(issue.month - 1) // 3 + 1)


def _landing_links(source: Source, fetcher: Fetcher,
                   cache: dict[str, tuple[list, str]]) -> tuple[list, str]:
    """Links on the source's landing page, plus any hand-supplied extra_urls.

    Returns (links, problem). A landing page that fails to load is the single most damaging
    silent failure available here: every issue of the source then matches nothing, and the
    run reports an archive with a source quietly missing from it. So the reason travels with
    the result instead of being swallowed.
    """
    if source.key in cache:
        return cache[source.key]
    links: list = []
    problem = ""
    if source.landing_url:
        result = fetcher.get(source.landing_url, accept="text/html")
        if result.ok:
            html = decode(result.body, result.content_type)
            links = find_links(html, result.final_url)
            if not links:
                problem = f"landing page {source.landing_url} has no links (JavaScript shell?)"
        else:
            problem = (f"landing page {source.landing_url} failed: "
                       f"{result.error or 'HTTP ' + str(result.status)}")
    links.extend((url, "") for url in source.extra_urls)
    cache[source.key] = (links, problem)
    return links, problem


def _store(root: Path, source: Source, issue: Issue, result: FetchResult,
           seen: dict[str, str]) -> Record:
    """Write the body (or its extracted text) and return the resulting record."""
    if result.is_pdf:
        payload, suffix = result.body, ".pdf"
    else:
        text = html_to_text(decode(result.body, result.content_type))
        if not source.save_text:
            return Record(issue, source, Status.ABSENT, url=result.final_url,
                          note="not a PDF and save_text is off", checked_at=today_iso())
        payload, suffix = text.encode("utf-8"), ".txt"
        # Hash the normalised text, never the raw page: an HTML page differs on every fetch.
        digest = sha256(fingerprint_text(text).encode("utf-8"))
        return _write(root, source, issue, result, payload, suffix, digest, seen)

    return _write(root, source, issue, result, payload, suffix, sha256(payload), seen)


def _write(root: Path, source: Source, issue: Issue, result: FetchResult,
           payload: bytes, suffix: str, digest: str, seen: dict[str, str]) -> Record:
    duplicate = duplicate_of(digest, seen)
    if duplicate and duplicate != issue.label:
        return Record(issue, source, Status.ABSENT, url=result.final_url, sha256=digest,
                      note=f"same content as {duplicate} in this run - pattern matches a "
                           "series, not an edition",
                      checked_at=today_iso())
    seen[digest] = issue.label

    target = month_dir(root, issue) / filename_for(source, issue, suffix)
    if target.is_file() and sha256(target.read_bytes()) == sha256(payload):
        status = Status.UNCHANGED
    else:
        write_atomic(target, payload)
        status = Status.DOWNLOADED
    return Record(issue, source, status, url=result.final_url, filename=target.name,
                  sha256=digest, checked_at=today_iso())


def _rewritten(source: Source, url: str) -> str:
    """Apply the source's url_rewrite, if it changes anything."""
    if not source.url_rewrite:
        return ""
    pattern, replacement = source.url_rewrite
    out = re.sub(pattern, replacement, url)
    return out if out != url else ""


def _detail_page_documents(source: Source, url: str, fetcher: Fetcher) -> list[str]:
    """Open an article page and return the document links on it, best first.

    The commonest shape in the wild: the listing links to a page about the report, and the
    PDF is a button on that page. One extra request per issue buys a registry that does not
    have to encode the publisher's file-naming scheme.
    """
    result = fetcher.get(url, accept="text/html")
    if not result.ok:
        return []
    html = decode(result.body, result.content_type)
    found = []
    for href, text in find_links(html, result.final_url):
        if not host_allowed(href, source):
            continue
        if any(href.lower().split("?")[0].endswith(ext.lower()) for ext in source.extensions):
            found.append(href)
    return found


def _collect_issue(source: Source, issue: Issue, root: Path, fetcher: Fetcher,
                   cache: dict[str, tuple[list, str]], seen: dict[str, str]) -> Record:
    now = today_iso()

    if issue.is_future:
        return Record(issue, source, Status.FUTURE, checked_at=now)

    if source.tier is Tier.MANUAL:
        found = claimed_file(root, source, issue)
        if found:
            return Record(issue, source, Status.MANUAL_DONE, filename=found.name, checked_at=now)
        return Record(issue, source, Status.MANUAL, note=source.manual_reason, checked_at=now)

    # A hand-downloaded file counts for automated sources too - a person who fetched it while
    # the pattern was broken should not be asked to do it again. The engine's own output is
    # excluded, or last run's download is read back as a hand-download and the source is
    # never checked again.
    own = canonical_names(source, issue)
    found = claimed_file(root, source, issue, exclude=own)
    if found:
        return Record(issue, source, Status.MANUAL_DONE, filename=found.name, checked_at=now)

    if source.tier is Tier.TEMPLATE:
        urls = [_template_url(source, issue)]
    else:
        links, problem = _landing_links(source, fetcher, cache)
        found = candidates_for_issue(source, links, issue.year, issue.month)
        if not found:
            return Record(issue, source, Status.ABSENT, checked_at=now,
                          note=problem or "no link on the landing page matched - not "
                               "published, rolled off the list, or the pattern is wrong")
        # For each candidate: the rewritten address first (no extra request), then the link
        # itself, then - if declared - whatever the article page points at.
        urls = []
        for candidate in found[:3]:
            rewritten = _rewritten(source, candidate)
            if rewritten:
                urls.append(rewritten)
            urls.append(candidate)
            if source.detail_page:
                urls.extend(_detail_page_documents(source, candidate, fetcher)[:2])

    last_note = ""
    for url in urls[:6]:
        result = fetcher.get(url, accept="application/pdf,text/html")
        if not result.ok:
            last_note = result.error or f"HTTP {result.status}"
            if "robots" in last_note:
                return Record(issue, source, Status.MANUAL, url=url, note=last_note, checked_at=now)
            continue
        if redirected_away(result):
            last_note = f"redirected to {result.final_url} - not this issue"
            continue
        if not looks_like_document(result, source):
            last_note = "response is not the expected document type (soft 404?)"
            continue
        text = "" if result.is_pdf else html_to_text(decode(result.body, result.content_type))
        if not edition_matches(source, issue.year, text, result.final_url):
            last_note = "edition check failed - the link serves a different year"
            continue
        return _store(root, source, issue, result, seen)

    # Nothing was obtained this run. If a copy from an earlier run is on disk, say so rather
    # than dropping the row: the archive still holds the issue, but the source did not serve
    # it today, and that is worth reading in the manifest.
    existing = [month_dir(root, issue) / name for name in sorted(own)
                if (month_dir(root, issue) / name).is_file()]
    if existing:
        return Record(issue, source, Status.UNCHANGED, filename=existing[0].name,
                      note=f"not re-checked this run: {last_note}" if last_note else "",
                      checked_at=now)

    status = Status.MISSED if last_note else Status.ABSENT
    return Record(issue, source, status, note=last_note, checked_at=now)


def run(sources: list[Source], root: Path, year: int,
        fetcher: Fetcher | None = None) -> RunSummary:
    """Collect one year for a list of sources. Returns the summary; writes the manifest."""
    problems = [p for source in sources for p in source.validate()]
    if problems:
        raise ValueError("Registry problems:\n  " + "\n  ".join(problems))

    fetcher = fetcher or Fetcher()
    root = Path(root)
    cache: dict[str, list] = {}
    seen: dict[str, str] = {}
    summary = RunSummary()

    for source in sources:
        issues = expected_issues(source, year)
        before = len(summary.records)

        if source.cadence is Cadence.WINDOW:
            # No expected months. Sweep what the landing page offers and file each link under
            # the month it names; a month with nothing simply has no row.
            links, problem = _landing_links(source, fetcher, cache)
            months = sorted({month for _, month in window_candidates(source, links, year)})
            for month in months:
                issue = Issue(source.key, year, month)
                if issue.is_future:
                    continue
                summary.records.append(_collect_issue(source, issue, root, fetcher, cache, seen))
            if len(summary.records) == before:
                # A source that produces no rows at all would otherwise vanish from the run
                # silently - the counts still add up, and nobody notices it stopped.
                summary.records.append(Record(
                    Issue(source.key, year, 1), source, Status.ABSENT,
                    note=problem or (f"no issue link on {source.landing_url} named a month in "
                                     f"{year} - check link_patterns and the page itself"),
                    checked_at=today_iso()))
            continue

        for issue in issues:
            summary.records.append(_collect_issue(source, issue, root, fetcher, cache, seen))

    write_manifest(root, summary.records)
    return summary
