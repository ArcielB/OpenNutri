from __future__ import annotations

import gzip
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen


RELEASE_TAG = "core-usda-v0.3.0"
ARCHIVE_NAME = "opennutri-core.sqlite.gz"
ARCHIVE_URL = (
    "https://github.com/ArcielB/OpenNutri/releases/download/"
    f"{RELEASE_TAG}/{ARCHIVE_NAME}"
)
ARCHIVE_SHA256 = "335184e30c91cb5204d74aeb91f9ea8eec8da3dabba403e6db328316e3a8623c"
ARCHIVE_SIZE = 29_376_064
DATABASE_SHA256 = "3e23c64063e7b6d72132fbe374a587ae0b9e6ad6d4cf3922358c20c7c78b0a50"
DATABASE_SIZE = 169_099_264
SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = SERVICE_ROOT / "data" / "opennutri-core.sqlite"
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
            f"Unexpected SHA-256 for {path.name}: expected {expected_sha256}, "
            f"got {actual_sha256}"
        )


def fetch_core_release(
    destination: Path = DEFAULT_DATABASE_PATH,
    *,
    url: str = ARCHIVE_URL,
) -> Path:
    destination = destination.resolve()
    if destination.is_file():
        try:
            verify_file(
                destination,
                expected_size=DATABASE_SIZE,
                expected_sha256=DATABASE_SHA256,
            )
            print(f"Using verified OpenNutri Core database at {destination}")
            return destination
        except ArtifactVerificationError:
            pass

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".core-release-",
        dir=destination.parent,
    ) as temp_dir:
        temp_root = Path(temp_dir)
        archive_path = temp_root / ARCHIVE_NAME
        extracted_path = temp_root / destination.name
        request = Request(url, headers={"User-Agent": "OpenNutri-Voice-Build/0.1"})
        with urlopen(request, timeout=120) as response, archive_path.open("wb") as output:
            shutil.copyfileobj(response, output, length=CHUNK_SIZE)
        verify_file(
            archive_path,
            expected_size=ARCHIVE_SIZE,
            expected_sha256=ARCHIVE_SHA256,
        )
        with gzip.open(archive_path, "rb") as source, extracted_path.open("wb") as output:
            shutil.copyfileobj(source, output, length=CHUNK_SIZE)
        verify_file(
            extracted_path,
            expected_size=DATABASE_SIZE,
            expected_sha256=DATABASE_SHA256,
        )
        with extracted_path.open("rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                raise ArtifactVerificationError("Artifact is not a SQLite database")
        os.replace(extracted_path, destination)
    print(f"Installed verified OpenNutri Core database at {destination}")
    return destination


if __name__ == "__main__":
    fetch_core_release()
