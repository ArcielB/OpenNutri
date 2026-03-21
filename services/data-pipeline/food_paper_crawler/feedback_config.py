from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

DEFAULT_FEEDBACK_PATH = Path(__file__).resolve().parent / "feedback" / "latest.json"
SUPPORTED_LANGUAGES = ("en", "tr")


def load_feedback_config(path: Optional[str] = None) -> Dict[str, object]:
    configured = os.environ.get("L2_FEEDBACK_CONFIG")
    target = Path(configured) if configured else Path(path) if path else DEFAULT_FEEDBACK_PATH
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_term(term: str) -> str:
    return " ".join((term or "").lower().strip().split())


def merge_terms(base: Iterable[str], extra: Iterable[str]) -> List[str]:
    merged: List[str] = []
    seen = set()
    for term in list(base) + list(extra):
        normalized = _normalize_term(term)
        if not normalized or normalized in seen:
            continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


def _extract_list(payload: object) -> List[str]:
    if not isinstance(payload, list):
        return []
    return [str(term).strip() for term in payload if str(term).strip()]


def _language_payload(config: Dict[str, object], language: str) -> Dict[str, object]:
    languages = config.get("languages")
    if isinstance(languages, dict):
        payload = languages.get(language)
        if isinstance(payload, dict):
            return payload
    return {}


def extract_terms(config: Dict[str, object], key: str, language: Optional[str] = None) -> List[str]:
    if language in SUPPORTED_LANGUAGES:
        payload = _language_payload(config, language)
        scoped = _extract_list(payload.get(key))
        if scoped:
            return scoped

        keyed = config.get(f"{key}_by_language")
        if isinstance(keyed, dict):
            scoped = _extract_list(keyed.get(language))
            if scoped:
                return scoped

        if language == "tr":
            return []

    raw = config.get(key)
    if not isinstance(raw, list):
        return []
    return [str(term).strip() for term in raw if str(term).strip()]
