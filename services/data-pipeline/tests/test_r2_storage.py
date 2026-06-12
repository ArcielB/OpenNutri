import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import r2_storage


FULL_ENV = {
    "R2_ACCOUNT_ID": "abc123",
    "R2_ACCESS_KEY_ID": "key",
    "R2_SECRET_ACCESS_KEY": "secret",
    "R2_PUBLIC_BASE_URL": "https://pub-test.r2.dev/",
}


class R2StorageTests(unittest.TestCase):
    def test_disabled_without_full_env(self) -> None:
        for missing in FULL_ENV:
            env = {k: v for k, v in FULL_ENV.items() if k != missing}
            with patch.dict("os.environ", env, clear=True):
                self.assertIsNone(r2_storage.r2_config())
                self.assertFalse(r2_storage.r2_enabled())

    def test_config_and_urls(self) -> None:
        with patch.dict("os.environ", FULL_ENV, clear=True):
            cfg = r2_storage.r2_config()
            self.assertEqual(cfg["bucket"], r2_storage.DEFAULT_BUCKET)
            self.assertEqual(cfg["endpoint"], "https://abc123.r2.cloudflarestorage.com")
            # Trailing slash on the public base is normalized away.
            self.assertEqual(
                r2_storage.public_url("p1.pdf"),
                "https://pub-test.r2.dev/papers/p1.pdf",
            )
            # Keys strip any directory component from the filename.
            self.assertEqual(r2_storage.object_key("/tmp/x/p1.pdf"), "papers/p1.pdf")
            self.assertTrue(r2_storage.is_r2_url("https://pub-test.r2.dev/papers/p1.pdf"))
            self.assertFalse(r2_storage.is_r2_url("https://europepmc.org/api/getPdf?pmcid=PMC1"))

    def test_upload_refuses_non_pdf(self) -> None:
        with patch.dict("os.environ", FULL_ENV, clear=True):
            with self.assertRaises(ValueError):
                r2_storage.upload_pdf_bytes(b"<html>not a pdf</html>", "p1.pdf")

    def test_upload_raises_when_unconfigured(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                r2_storage.upload_pdf_bytes(b"%PDF-1.4 ...", "p1.pdf")


if __name__ == "__main__":
    unittest.main()
