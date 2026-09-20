import socket
import unittest
import urllib.error
from unittest import mock

from _support import *  # noqa: F401,F403
from report_collector.http import Fetcher


class RetryPolicy(unittest.TestCase):
    """What gets retried is a decision, not an accident: retry what time can fix."""

    def _count_attempts(self, raises):
        calls = []

        def fake_urlopen(request, timeout=None):
            calls.append(request.full_url)
            raise raises

        fetcher = Fetcher(pace_seconds=0, backoff=(0.0, 0.0), obey_robots=False)
        with mock.patch("urllib.request.urlopen", fake_urlopen):
            result = fetcher.get("https://nowhere.example/x.pdf")
        return len(calls), result

    def test_a_name_that_does_not_resolve_is_not_retried(self):
        attempts, result = self._count_attempts(
            urllib.error.URLError(socket.gaierror(-2, "Name or service not known")))
        self.assertEqual(attempts, 1)
        self.assertFalse(result.ok)

    def test_a_timeout_is_retried(self):
        attempts, _ = self._count_attempts(TimeoutError("timed out"))
        self.assertEqual(attempts, 3)

    def test_a_404_is_not_retried(self):
        attempts, result = self._count_attempts(
            urllib.error.HTTPError("https://nowhere.example/x.pdf", 404, "Not Found", {}, None))
        self.assertEqual(attempts, 1)
        self.assertEqual(result.status, 404)

    def test_a_429_is_retried(self):
        attempts, _ = self._count_attempts(
            urllib.error.HTTPError("https://nowhere.example/x.pdf", 429, "Too Many", {}, None))
        self.assertEqual(attempts, 3)


if __name__ == "__main__":
    unittest.main()
