"""Guards: the checks that turn "the run threw no errors" into "the files are right".

Every guard here exists because of a failure that produced *plausible* output. A collector
without them still finishes, still writes files, and still reports success.
"""
from __future__ import annotations

import hashlib
import re
import urllib.parse

from .models import FetchResult, Source


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_identity(url: str) -> str:
    """The part of a URL that identifies a document.

    Query strings carry per-request tokens (`?ver=`, `?apikey=`, `?rev=`, tracking ids) that
    change on every fetch, so keying a manifest on the full URL re-downloads the same file
    for ever. The path is the identity; the query is not.
    """
    parts = urllib.parse.urlsplit(url)
    path = re.sub(r"\.(coredownload\.inline)?\.pdf$", ".pdf", parts.path, flags=re.I)
    return f"{parts.netloc}{path}".lower()


def host_allowed(url: str, source: Source) -> bool:
    """Default deny. A link that matches on text alone can belong to another publisher."""
    if not source.allowed_hosts:
        return False
    host = urllib.parse.urlsplit(url).netloc.lower()
    return any(host == h.lower() or host.endswith("." + h.lower()) for h in source.allowed_hosts)


def redirected_away(result: FetchResult) -> bool:
    """True when the response came from a different document than the one requested.

    A request for a future or withdrawn issue is often answered 200 by a hub page, a search
    page or a "latest" page. The bytes are real, the content is not the issue asked for, and
    saving it puts a wrong file in the archive under the right name.
    """
    if not result.ok:
        return False
    asked = stable_identity(result.url)
    got = stable_identity(result.final_url)
    return asked != got


def duplicate_of(digest: str, seen: dict[str, str]) -> str | None:
    """Return the label this content was already saved under in this run, if any.

    Two issues with identical content in one run means the pattern matched a series rather
    than an edition - typically an annual publication whose URL has no year in it.
    """
    return seen.get(digest)


def edition_matches(source: Source, issue_year: int, text: str, url: str) -> bool:
    """Check that the thing fetched is the edition expected, not last year's.

    Evergreen URLs (".../latest-report.pdf") keep answering 200 long after the publisher has
    stopped updating them, and the bytes stay stable, so nothing looks wrong.
    """
    if not source.edition_tokens:
        return True
    haystack = f"{url}\n{text[:20000]}".lower()
    tokens = [t.replace("{year}", str(issue_year)).lower() for t in source.edition_tokens]
    return any(t in haystack for t in tokens)


def within_year_window(source: Source, current_year: int, candidate_year: int | None) -> bool:
    """Keep a first run from hoovering up a decade of back issues from an archive page."""
    if candidate_year is None:
        return True
    return 0 <= current_year - candidate_year <= max(0, source.year_window)


def looks_like_document(result: FetchResult, source: Source) -> bool:
    """Shape check, not a status check.

    A soft 404 returns HTML with a 200. Asserting on the magic bytes of a PDF - or on there
    being real content in an HTML page - is what separates "the server answered" from "we
    have the document".

    A source that declares only `.pdf` gets no HTML fallback: if HTML comes back where a PDF
    was asked for, that is an error page, a consent wall or a landing page, and archiving it
    would put a plausible-looking wrong file under the right name. Sources whose publication
    really is a web page declare an HTML extension as well, and are held to "has content".
    """
    if not result.ok:
        return False
    if result.is_pdf:
        return True
    pdf_only = bool(source.extensions) and all(
        ext.lower() in (".pdf",) for ext in source.extensions)
    if pdf_only:
        return False
    if "pdf" in result.content_type.lower():
        # It claims to be a PDF and does not start with %PDF-: believe the bytes.
        return False
    return len(result.body.strip()) > 0
