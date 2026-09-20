import unittest

from _support import *  # noqa: F401,F403  (path setup)
from report_collector.extract import (decode, fingerprint_text, html_to_text,
                                      looks_like_shell)

PAGE = """
<html><head><style>.a{color:red}</style><script>var build='17231';</script></head>
<body>
<nav><a href="/">Home</a><a href="/about">About</a></nav>
<main><h1>Quarterly Outlook</h1><p>Prices rose 2.1% in the quarter.</p>
<p>Demand was flat.</p></main>
<footer>Cookie notice</footer>
</body></html>
"""


class HtmlToText(unittest.TestCase):
    def test_drops_chrome_and_keeps_prose(self):
        text = html_to_text(PAGE)
        self.assertIn("Quarterly Outlook", text)
        self.assertIn("Prices rose 2.1%", text)
        for noise in ("Cookie notice", "About", "var build", "color:red"):
            self.assertNotIn(noise, text)

    def test_two_fetches_of_a_changing_page_compare_equal(self):
        # The page differs on every request (a build id, whitespace), the report does not.
        other = PAGE.replace("17231", "99999").replace("\n<p>Demand", "\n\n   <p>Demand")
        self.assertEqual(fingerprint_text(html_to_text(PAGE)),
                         fingerprint_text(html_to_text(other)))


class Decode(unittest.TestCase):
    def test_uses_declared_charset_then_falls_back(self):
        self.assertEqual(decode("café".encode("cp1252"), "text/html; charset=windows-1252"),
                         "café")
        self.assertEqual(decode("café".encode("utf-8")), "café")

    def test_never_raises_on_broken_bytes(self):
        self.assertIsInstance(decode(b"\xff\xfe\x00bad"), str)


class Shell(unittest.TestCase):
    def test_many_links_little_text_is_a_js_shell(self):
        self.assertTrue(looks_like_shell("short", anchor_count=40))

    def test_little_of_both_is_not_called_a_shell(self):
        self.assertFalse(looks_like_shell("short", anchor_count=2))


if __name__ == "__main__":
    unittest.main()
