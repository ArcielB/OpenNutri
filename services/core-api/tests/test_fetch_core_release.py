from __future__ import annotations

import gzip
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from scripts.fetch_core_release import ArtifactVerificationError, fetch_core_release


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class FetchCoreReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database_bytes = b"SQLite format 3\x00" + b"fixture database"
        self.archive_path = self.root / "fixture.sqlite.gz"
        with self.archive_path.open("wb") as raw_archive:
            with gzip.GzipFile(fileobj=raw_archive, mode="wb", mtime=0) as archive:
                archive.write(self.database_bytes)
        self.archive_bytes = self.archive_path.read_bytes()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def fetch(self, destination: Path) -> Path:
        return fetch_core_release(
            destination,
            url=self.archive_path.as_uri(),
            archive_size=len(self.archive_bytes),
            archive_sha256=sha256_bytes(self.archive_bytes),
            database_size=len(self.database_bytes),
            database_sha256=sha256_bytes(self.database_bytes),
        )

    def test_downloads_verifies_and_extracts_release(self) -> None:
        destination = self.root / "data" / "core.sqlite"

        result = self.fetch(destination)

        self.assertEqual(result, destination)
        self.assertEqual(destination.read_bytes(), self.database_bytes)

    def test_reuses_an_existing_verified_database_without_downloading(self) -> None:
        destination = self.root / "core.sqlite"
        destination.write_bytes(self.database_bytes)
        self.archive_path.unlink()

        result = self.fetch(destination)

        self.assertEqual(result, destination)
        self.assertEqual(destination.read_bytes(), self.database_bytes)

    def test_rejects_a_changed_archive_without_replacing_existing_database(self) -> None:
        destination = self.root / "core.sqlite"
        destination.write_bytes(b"existing database")

        with self.assertRaisesRegex(ArtifactVerificationError, "SHA-256"):
            fetch_core_release(
                destination,
                url=self.archive_path.as_uri(),
                archive_size=len(self.archive_bytes),
                archive_sha256="0" * 64,
                database_size=len(self.database_bytes),
                database_sha256=sha256_bytes(self.database_bytes),
            )

        self.assertEqual(destination.read_bytes(), b"existing database")


if __name__ == "__main__":
    unittest.main()
