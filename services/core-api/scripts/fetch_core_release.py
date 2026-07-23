from __future__ import annotations

import gzip
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen


RELEASE_TAG = "core-usda-v0.2.0"
ARCHIVE_NAME = "opennutri-core.sqlite.gz"
ARCHIVE_URL = (
    "https://github.com/ArcielB/OpenNutri/releases/download/"
    f"{RELEASE_TAG}/{ARCHIVE_NAME}"
)
ARCHIVE_SHA256 = "fd006d4d67f924ef927892ec3cb36636a15dcaf213a9324a33e2fb91ebabe4a7"
ARCHIVE_SIZE = 26_912_444
DATABASE_SHA256 = "edc6e28de6a73ac11bb9bb041a4ba638d9d1b6e79b89ff46873652efc461789b"
DATABASE_SIZE = 160_272_384
API_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = API_ROOT / "data" / "opennutri-core.sqlite"
CHUNK_SIZE = 1024 * 1024


class ArtifactVerificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, *, expected_size: int, expected_sha256: str) -> None:
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        raise ArtifactVerificationError(
            f"Unexpected size for {path.name}: expected {expected_size}, got {actual_size}"
        )

    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise ArtifactVerificationError(
            f"Unexpected SHA-256 for {path.name}: expected {expected_sha256}, got {actual_sha256}"
        )


def download(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "OpenNutri-Vercel-Build/0.2"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output, length=CHUNK_SIZE)


def fetch_core_release(
    destination: Path = DEFAULT_DATABASE_PATH,
    *,
    url: str = ARCHIVE_URL,
    archive_size: int = ARCHIVE_SIZE,
    archive_sha256: str = ARCHIVE_SHA256,
    database_size: int = DATABASE_SIZE,
    database_sha256: str = DATABASE_SHA256,
) -> Path:
    destination = destination.resolve()
    if destination.is_file():
        try:
            verify_file(
                destination,
                expected_size=database_size,
                expected_sha256=database_sha256,
            )
            print(f"Using verified OpenNutri Core database at {destination}")
            return destination
        except ArtifactVerificationError:
            pass

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".core-release-", dir=destination.parent) as temp_dir:
        temp_root = Path(temp_dir)
        archive_path = temp_root / ARCHIVE_NAME
        extracted_path = temp_root / destination.name

        print(f"Downloading OpenNutri Core {RELEASE_TAG} from {url}")
        download(url, archive_path)
        verify_file(
            archive_path,
            expected_size=archive_size,
            expected_sha256=archive_sha256,
        )

        with gzip.open(archive_path, "rb") as source, extracted_path.open("wb") as output:
            shutil.copyfileobj(source, output, length=CHUNK_SIZE)

        verify_file(
            extracted_path,
            expected_size=database_size,
            expected_sha256=database_sha256,
        )
        with extracted_path.open("rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                raise ArtifactVerificationError("Extracted artifact is not a SQLite 3 database")

        os.replace(extracted_path, destination)

    print(f"Installed verified OpenNutri Core database at {destination}")
    return destination


if __name__ == "__main__":
    fetch_core_release()
