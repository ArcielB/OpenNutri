#!/usr/bin/env python3
"""Probe which cascade models accept native file input (PDF / image).

Read-only capability check: for each model it sends (a) a tiny one-page PDF
part and (b) a tiny PNG part with a trivial prompt and records whether the API
accepts the part or rejects it. Use this before flipping a stage to PDF input.

Usage:
    GEMINI_API_KEY=... python3 scripts/probe_model_file_input.py [model ...]

With no model args it probes the four cascade models.
"""
import base64
import os
import sys

try:
    import google.generativeai as genai
except ImportError:
    sys.exit("google-generativeai not installed (pip install google-generativeai)")

DEFAULT_MODELS = [
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
]

# 1x1 transparent PNG.
PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+M8AAAMBAQDJ/1eMAAAAAElFTkSuQmCC"
)


def make_test_pdf(text: str = "PROBE PAGE ONE ZX9") -> bytes:
    """Build a tiny, well-formed single-page PDF with correct xref offsets."""
    stream = b"BT /F1 18 Tf 20 100 Td (" + text.encode("ascii") + b") Tj ET"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(pdf))
        pdf += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(pdf)
    count = len(objs) + 1
    pdf += b"xref\n0 " + str(count).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        pdf += ("%010d 00000 n \n" % off).encode()
    pdf += (
        b"trailer\n<< /Size " + str(count).encode() + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    )
    return bytes(pdf)


def probe(model_name: str, part: dict, prompt: str) -> tuple[str, str]:
    try:
        model = genai.GenerativeModel(model_name)
        resp = model.generate_content([part, prompt], request_options={"timeout": 120})
        text = (getattr(resp, "text", "") or "").strip().replace("\n", " ")
        return "OK", text[:90]
    except Exception as exc:  # noqa: BLE001 - we want every failure mode
        return "ERR", f"{type(exc).__name__}: {str(exc)[:160]}"


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY not set")
    genai.configure(api_key=api_key)

    pdf_part = {"mime_type": "application/pdf", "data": make_test_pdf()}
    png_part = {"mime_type": "image/png", "data": base64.b64decode(PNG_B64)}
    models = sys.argv[1:] or DEFAULT_MODELS

    print(f"{'model':30} {'PDF':5} {'IMG':5}  detail")
    print("-" * 90)
    for name in models:
        pdf_status, pdf_detail = probe(name, pdf_part, "What exact text is on page 1?")
        img_status, img_detail = probe(name, png_part, "Describe this image in three words.")
        print(f"{name:30} {pdf_status:5} {img_status:5}  PDF[{pdf_detail}] IMG[{img_detail}]")


if __name__ == "__main__":
    main()
