"""HTTP with the manners a publisher's site deserves, on the standard library only.

No third-party dependencies anywhere in this package: it has to run on locked-down machines
where installing packages is a negotiation, and a collector that cannot be installed is a
collector that does not run.

What this layer does and why:
  * honours robots.txt - and records the refusal as a reason, rather than pretending the
    issue does not exist;
  * paces requests per host, and retries 429/5xx with a backoff;
  * never disables TLS verification. A certificate error is a real signal, and the fix for a
    server that omits an intermediate certificate is a trust store, not `verify=False`;
  * reports the URL the response actually came from, because a 200 from somewhere else is
    the most common way to archive a file that is not the report.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field

from .models import FetchResult

DEFAULT_UA = (
    "report-collector/0.1 (+https://github.com/imgeorgewong/report-collector) "
    "python-urllib"
)
RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}


@dataclass
class Fetcher:
    """A small HTTP client. Swap it for a fake in tests: the engine only calls `get`."""

    user_agent: str = DEFAULT_UA
    timeout: int = 60
    pace_seconds: float = 1.0
    attempts: int = 3
    backoff: tuple[float, ...] = (2.0, 5.0)
    obey_robots: bool = True
    _last_request: dict[str, float] = field(default_factory=dict, repr=False)
    _robots: dict[str, urllib.robotparser.RobotFileParser] = field(default_factory=dict, repr=False)

    # -- robots -----------------------------------------------------------------
    def allowed(self, url: str) -> bool:
        if not self.obey_robots:
            return True
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        parser = self._robots.get(origin)
        if parser is None:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(f"{origin}/robots.txt")
            try:
                parser.read()
            except Exception:
                # An unreadable robots.txt is not permission to ignore it, but it is also not
                # a reason to stop: treat it as "no rules stated".
                parser.parse([])
            self._robots[origin] = parser
        return parser.can_fetch(self.user_agent, url)

    # -- pacing -----------------------------------------------------------------
    def _wait_turn(self, url: str) -> None:
        host = urllib.parse.urlsplit(url).netloc
        last = self._last_request.get(host)
        if last is not None:
            gap = time.monotonic() - last
            if gap < self.pace_seconds:
                time.sleep(self.pace_seconds - gap)
        self._last_request[host] = time.monotonic()

    # -- the one method the engine uses -----------------------------------------
    def get(self, url: str, accept: str = "*/*") -> FetchResult:
        if not self.allowed(url):
            return FetchResult(url=url, final_url=url, status=0,
                               error="blocked by robots.txt")
        request = urllib.request.Request(
            url, headers={"User-Agent": self.user_agent, "Accept": accept})
        status, error = 0, ""
        for attempt in range(1, self.attempts + 1):
            self._wait_turn(url)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return FetchResult(
                        url=url,
                        final_url=response.geturl(),
                        status=response.status,
                        body=response.read(),
                        content_type=response.headers.get("Content-Type", ""),
                    )
            except urllib.error.HTTPError as exc:
                status, error = exc.code, f"HTTP {exc.code}"
                if exc.code not in RETRY_STATUSES:
                    break
            except Exception as exc:  # timeout, DNS, TLS
                status, error = 0, f"{type(exc).__name__}: {exc}"
            if attempt < self.attempts:
                time.sleep(self.backoff[min(attempt, len(self.backoff)) - 1])
        return FetchResult(url=url, final_url=url, status=status, error=error)
