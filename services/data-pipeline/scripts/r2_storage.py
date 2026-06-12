"""Cloudflare R2 (S3-compatible) helpers for hosting paper PDFs.

R2 is the durable PDF origin: 10 GB storage and zero egress fees on the free
tier, so repeat reads cost nothing (unlike Supabase Storage, whose egress
overage froze the original project, and unlike publisher hosts such as
EuropePMC, which send no-store and re-serve slowly).

Configuration comes from the environment; the integration is dormant until all
required values are present (so the pipeline keeps working unchanged without
credentials):

- R2_ACCOUNT_ID         Cloudflare account id (32-hex, dashboard sidebar)
- R2_ACCESS_KEY_ID      R2 API token access key (S3-compatible)
- R2_SECRET_ACCESS_KEY  R2 API token secret
- R2_PUBLIC_BASE_URL    public base for reads, e.g. https://pub-xxxx.r2.dev
- R2_BUCKET             bucket name (optional, default "open-nutri")

Objects are keyed "papers/<filename>" — papers.filename is the crawler's
unique, stable name for each PDF, so the key works both for new uploads and
for backfilling existing rows.
"""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_BUCKET = "open-nutri"
KEY_PREFIX = "papers"


def r2_config() -> dict | None:
    account_id = os.environ.get("R2_ACCOUNT_ID", "").strip()
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    public_base = os.environ.get("R2_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not (account_id and access_key and secret_key and public_base):
        return None
    return {
        "account_id": account_id,
        "access_key": access_key,
        "secret_key": secret_key,
        "public_base": public_base,
        "bucket": os.environ.get("R2_BUCKET", "").strip() or DEFAULT_BUCKET,
        "endpoint": f"https://{account_id}.r2.cloudflarestorage.com",
    }


def r2_enabled() -> bool:
    return r2_config() is not None


def object_key(filename: str) -> str:
    return f"{KEY_PREFIX}/{Path(str(filename)).name}"


def public_url(filename: str, config: dict | None = None) -> str:
    cfg = config or r2_config()
    if cfg is None:
        raise RuntimeError("R2 is not configured (missing R2_* environment variables).")
    return f"{cfg['public_base']}/{object_key(filename)}"


def is_r2_url(url: object, config: dict | None = None) -> bool:
    cfg = config or r2_config()
    if cfg is None:
        return False
    return str(url or "").startswith(cfg["public_base"] + "/")


def _client(cfg: dict):
    # Imported lazily so workers without boto3 can import this module freely.
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint"],
        aws_access_key_id=cfg["access_key"],
        aws_secret_access_key=cfg["secret_key"],
        region_name="auto",
        config=Config(retries={"max_attempts": 3, "mode": "standard"}),
    )


def upload_pdf_bytes(data: bytes, filename: str, config: dict | None = None) -> str:
    """Upload PDF bytes and return the public URL. Raises on failure."""
    cfg = config or r2_config()
    if cfg is None:
        raise RuntimeError("R2 is not configured (missing R2_* environment variables).")
    if not data.startswith(b"%PDF"):
        raise ValueError(f"refusing to upload non-PDF payload for {filename!r}")
    _client(cfg).put_object(
        Bucket=cfg["bucket"],
        Key=object_key(filename),
        Body=data,
        ContentType="application/pdf",
        CacheControl="public, max-age=31536000, immutable",
    )
    return public_url(filename, cfg)


def upload_pdf_file(file_path: Path | str, filename: str | None = None, config: dict | None = None) -> str:
    path = Path(file_path)
    return upload_pdf_bytes(path.read_bytes(), filename or path.name, config=config)
