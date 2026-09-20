import tempfile
import unittest
from pathlib import Path

from _support import PDF_BYTES
from report_collector.archive import month_dir
from report_collector.audit import audit
from report_collector.manifest import write_manifest
from report_collector.models import Cadence, Issue, Record, Source, Status, Tier

SOURCE = Source(key="acme", name="Outlook", publisher="Acme", tier=Tier.TEMPLATE,
                cadence=Cadence.QUARTERLY, months=(1,),
                url_template="https://acme.example/{year}-{month:02d}.pdf")


class Audit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = month_dir(self.root, Issue("acme", 2026, 1))
        self.folder.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_archive_passes(self):
        name = "acme__2026-01__Outlook.pdf"
        (self.folder / name).write_bytes(PDF_BYTES)
        write_manifest(self.root, [Record(Issue("acme", 2026, 1), SOURCE, Status.DOWNLOADED,
                                          filename=name, sha256="a1")])
        self.assertEqual(audit(self.root), [])

    def test_a_row_claiming_a_file_that_is_not_there_is_reported(self):
        write_manifest(self.root, [Record(Issue("acme", 2026, 1), SOURCE, Status.DOWNLOADED,
                                          filename="missing.pdf", sha256="a1")])
        problems = audit(self.root)
        self.assertTrue(any("is not on disk" in p for p in problems))

    def test_a_file_no_row_claims_is_reported(self):
        (self.folder / "stray.pdf").write_bytes(PDF_BYTES)
        write_manifest(self.root, [Record(Issue("acme", 2026, 1), SOURCE, Status.ABSENT)])
        problems = audit(self.root)
        self.assertTrue(any("not claimed by any manifest row" in p for p in problems))

    def test_two_rows_with_identical_content_are_reported(self):
        for month, name in ((1, "a.pdf"), (4, "b.pdf")):
            folder = month_dir(self.root, Issue("acme", 2026, month))
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(PDF_BYTES)
        write_manifest(self.root, [
            Record(Issue("acme", 2026, 1), SOURCE, Status.DOWNLOADED, filename="a.pdf", sha256="same"),
            Record(Issue("acme", 2026, 4), SOURCE, Status.DOWNLOADED, filename="b.pdf", sha256="same"),
        ])
        problems = audit(self.root)
        self.assertTrue(any("identical content" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
