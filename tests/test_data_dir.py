"""Databases are copied out of the git checkout once."""

import tempfile
import unittest
from pathlib import Path

from server.config import migrate_repo_data


class DataDirTests(unittest.TestCase):
    def test_copies_databases_without_overwriting(self):
        with tempfile.TemporaryDirectory() as src_name, tempfile.TemporaryDirectory() as dest_name:
            source = Path(src_name)
            (source / "calendar.db").write_bytes(b"sqlite-calendar")
            (source / "advisor").mkdir()
            (source / "advisor" / "info.md").write_text("hello", encoding="utf-8")
            target = migrate_repo_data(Path(dest_name) / "live", source)
            self.assertEqual((target / "calendar.db").read_bytes(), b"sqlite-calendar")
            self.assertEqual((target / "advisor" / "info.md").read_text(encoding="utf-8"), "hello")
            self.assertIn(str(target), (source / "DATA_LOCATION.txt").read_text(encoding="utf-8"))

            (source / "calendar.db").write_bytes(b"newer-copy")
            (source / "advisor" / "info.md").write_text("changed", encoding="utf-8")
            migrate_repo_data(target, source)
            self.assertEqual((target / "calendar.db").read_bytes(), b"sqlite-calendar")
            self.assertEqual((target / "advisor" / "info.md").read_text(encoding="utf-8"), "hello")
