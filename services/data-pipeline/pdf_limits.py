from __future__ import annotations

import os


DEFAULT_MAX_PAPER_PDF_BYTES = 50 * 1024 * 1024
PAPER_PDF_LIMIT_ENV_VARS = (
    "OPENNUTRI_MAX_PAPER_PDF_BYTES",
    "SUPABASE_PAPER_MAX_UPLOAD_BYTES",
)


def max_paper_pdf_bytes() -> int:
    for name in PAPER_PDF_LIMIT_ENV_VARS:
        raw_value = os.environ.get(name)
        if raw_value in {None, ""}:
            continue
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{name} must be an integer byte limit.") from exc
        if parsed <= 0:
            raise RuntimeError(f"{name} must be greater than zero.")
        return parsed
    return DEFAULT_MAX_PAPER_PDF_BYTES


def format_byte_size(size_bytes: int) -> str:
    size = float(max(0, int(size_bytes)))
    for unit in ("bytes", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            if unit == "bytes":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"


def pdf_size_exceeds_limit(size_bytes: int, *, limit_bytes: int | None = None) -> bool:
    limit = max_paper_pdf_bytes() if limit_bytes is None else int(limit_bytes)
    return int(size_bytes) > limit


def pdf_size_limit_message(size_bytes: int, *, limit_bytes: int | None = None) -> str:
    limit = max_paper_pdf_bytes() if limit_bytes is None else int(limit_bytes)
    return (
        f"PDF size {format_byte_size(size_bytes)} exceeds Supabase upload limit "
        f"{format_byte_size(limit)}"
    )
