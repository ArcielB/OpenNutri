"""Solver for NCBI PMC's "Preparing to download" proof-of-work challenge.

PMC fronts PDF downloads with a JS page that brute-forces a nonce such that
sha256(challenge + nonce) starts with `difficulty` zero hex digits, then
retries with a cookie `<name>=<challenge>,<nonce>`. Replicating that lets
server-side fetchers download PDFs directly.

NOTE: the hash is SHA-256. Earlier copies of this solver used MD5 — the page
accepted that historically, but current PMC verifies SHA-256, so the MD5
variant silently never unlocked anything.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

# Difficulty 4 needs ~65k attempts on average; the cap only guards against a
# pathological difficulty bump making us spin forever.
MAX_NONCE_ATTEMPTS = 20_000_000

_CHALLENGE = re.compile(r'POW_CHALLENGE = "([^"]+)"')
_DIFFICULTY = re.compile(r'POW_DIFFICULTY = "([^"]+)"')
_COOKIE_NAME = re.compile(r'POW_COOKIE_NAME = "([^"]+)"')


def solve_pmc_pow(html: str) -> Optional[str]:
    """Return the unlock cookie ("name=challenge,nonce") or None if the page
    is not a PMC POW challenge (or the nonce cap is exceeded)."""
    challenge_match = _CHALLENGE.search(html)
    difficulty_match = _DIFFICULTY.search(html)
    cookie_match = _COOKIE_NAME.search(html)
    if not challenge_match or not difficulty_match or not cookie_match:
        return None

    challenge = challenge_match.group(1)
    difficulty = int(difficulty_match.group(1))
    cookie_name = cookie_match.group(1)
    prefix = "0" * difficulty
    for nonce in range(MAX_NONCE_ATTEMPTS):
        digest = hashlib.sha256(f"{challenge}{nonce}".encode("utf-8")).hexdigest()
        if digest.startswith(prefix):
            return f"{cookie_name}={challenge},{nonce}"
    return None
