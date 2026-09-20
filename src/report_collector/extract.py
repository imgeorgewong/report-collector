"""Turn an HTML page into the text of the report, and nothing else.

Some publications have no PDF at all: the press release *is* the publication. Saving the raw
HTML keeps the navigation, the cookie banner and the "related links" column, all of which
change between fetches - so a page saved twice is never byte-identical, and de-duplication
by hash can never say "unchanged". Extracting the main text fixes both problems at once.

Standard library only: html.parser, no BeautifulSoup.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

# Containers whose contents are never the report.
DROP_TAGS = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form",
             "svg", "button", "select", "iframe"}
BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
              "section", "article", "table", "blockquote"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._drop_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_TAGS:
            self._drop_depth += 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in DROP_TAGS and self._drop_depth:
            self._drop_depth -= 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._drop_depth == 0 and data.strip():
            self.parts.append(data.strip())
            self.parts.append(" ")


def html_to_text(html: str) -> str:
    """Main text of a page, normalised so that two fetches of the same page compare equal."""
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def decode(body: bytes, content_type: str = "") -> str:
    """Decode a response body, preferring the declared charset and never throwing."""
    match = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    for encoding in [match.group(1) if match else None, "utf-8", "cp1252"]:
        if not encoding:
            continue
        try:
            return body.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", errors="replace")


def fingerprint_text(text: str) -> str:
    """Whitespace- and case-normalised text, for comparing two fetches of the same page.

    Compare *this*, not the raw bytes: a page can differ on every request (a build id, a
    timestamp, a rotating advert) while the report itself has not changed at all.
    """
    return re.sub(r"\s+", " ", text).strip().lower()


def looks_like_shell(text: str, anchor_count: int) -> bool:
    """A page rendered entirely by JavaScript: many links, almost no prose.

    Distinguishing this from a broken extractor matters. Few links *and* little text means
    the page is a shell; many links and little text means the extraction is wrong - and only
    one of those is fixed by changing this file.
    """
    return len(text) < 400 and anchor_count > 10
