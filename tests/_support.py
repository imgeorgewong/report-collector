"""Shared test helpers: path setup and a Fetcher that never touches the network."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from report_collector.models import FetchResult  # noqa: E402

PDF_BYTES = b"%PDF-1.7\nfake pdf body\n%%EOF"


@dataclass
class FakeFetcher:
    """Serves canned responses. The engine only ever calls `get`, so this is the whole seam.

    Tests that need network behaviour (timeouts, robots, pacing) belong against the real
    Fetcher; everything else is faster and more honest offline.
    """

    responses: dict = field(default_factory=dict)
    calls: list = field(default_factory=list)

    def get(self, url: str, accept: str = "*/*") -> FetchResult:
        self.calls.append(url)
        response = self.responses.get(url)
        if response is None:
            return FetchResult(url=url, final_url=url, status=404, error="HTTP 404")
        if isinstance(response, FetchResult):
            return response
        body, content_type, final = response
        return FetchResult(url=url, final_url=final or url, status=200,
                           body=body, content_type=content_type)
