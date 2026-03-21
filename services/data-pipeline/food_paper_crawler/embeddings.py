from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from .feedback_seed_terms import SEED_ANCHOR_PHRASES_BY_LANGUAGE

_sentence_transformers_import_error = None
try:
    from sentence_transformers import SentenceTransformer
except Exception as exc:  # pragma: no cover - optional dependency
    SentenceTransformer = None
    _sentence_transformers_import_error = exc


@dataclass
class DualEmbeddingConfig:
    en_model: str
    tr_model: str
    en_threshold: float
    tr_threshold: float
    max_chars: int
    version: str = "language-scoped-embeddings-v2"


class DualEmbeddingScorer:
    def __init__(self, config: Optional[DualEmbeddingConfig] = None) -> None:
        if config is None:
            config = DualEmbeddingConfig(
                en_model=os.environ.get("L2_EMBED_EN_MODEL", "all-MiniLM-L6-v2"),
                tr_model=(
                    os.environ.get("L2_EMBED_TR_MODEL")
                    or os.environ.get("L2_EMBED_MULTI_MODEL")
                    or "paraphrase-multilingual-MiniLM-L12-v2"
                ),
                en_threshold=float(os.environ.get("L2_EMBED_EN_THRESHOLD", "0.45")),
                tr_threshold=float(
                    os.environ.get("L2_EMBED_TR_THRESHOLD")
                    or os.environ.get("L2_EMBED_MULTI_THRESHOLD")
                    or "0.42"
                ),
                max_chars=int(os.environ.get("L2_EMBED_MAX_CHARS", "1800")),
            )
        self.config = config
        if SentenceTransformer is None:
            raise ModuleNotFoundError(
                "sentence-transformers is required for L2 embedding scoring. "
                "Install with `python3 -m pip install sentence-transformers`."
            ) from _sentence_transformers_import_error
        self.available = True
        self.error: Optional[str] = None
        self._models: Dict[str, SentenceTransformer] = {}
        self._anchors: Dict[str, List[str]] = {}
        self._anchor_embeddings: Dict[str, object] = {}
        from .feedback_config import extract_terms, load_feedback_config

        feedback_config = load_feedback_config()
        self._anchors["en"] = extract_terms(feedback_config, "anchor_phrases", language="en") or list(
            SEED_ANCHOR_PHRASES_BY_LANGUAGE["en"]
        )
        self._anchors["tr"] = extract_terms(feedback_config, "anchor_phrases", language="tr") or list(
            SEED_ANCHOR_PHRASES_BY_LANGUAGE["tr"]
        )
        try:
            self._models["en"] = SentenceTransformer(self.config.en_model)
            self._models["tr"] = SentenceTransformer(self.config.tr_model)
            for language, model in self._models.items():
                self._anchor_embeddings[language] = self._encode(model, self._anchors[language])
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Failed to initialize embedding models "
                f"'{self.config.en_model}' and '{self.config.tr_model}'. "
                "Ensure the models can be downloaded and loaded."
            ) from exc

    def info(self) -> Dict[str, object]:
        return {
            "version": self.config.version,
            "available": self.available,
            "error": self.error,
            "languages": {
                "en": {
                    "model": self.config.en_model,
                    "threshold": self.config.en_threshold,
                    "anchor_count": len(self._anchors["en"]),
                },
                "tr": {
                    "model": self.config.tr_model,
                    "threshold": self.config.tr_threshold,
                    "anchor_count": len(self._anchors["tr"]),
                },
            },
        }

    def score(self, text: str, language: str) -> Dict[str, object]:
        if language not in {"en", "tr"}:
            raise ValueError(f"Unsupported embedding language '{language}'.")
        trimmed = " ".join((text or "").split())
        if self.config.max_chars > 0:
            trimmed = trimmed[: self.config.max_chars]
        if not trimmed:
            raise ValueError("Embedding input is empty (missing title/abstract).")

        score, anchor = self._max_similarity(
            self._models[language],
            self._anchor_embeddings[language],
            trimmed,
            self._anchors[language],
        )

        return {
            "available": True,
            "language": language,
            "model": self.config.en_model if language == "en" else self.config.tr_model,
            "threshold": self.config.en_threshold if language == "en" else self.config.tr_threshold,
            "max_similarity": score,
            "anchor": anchor,
        }

    def _encode(self, model: SentenceTransformer, phrases: List[str]):
        return model.encode(
            phrases,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

    def _max_similarity(self, model: SentenceTransformer, anchor_emb, text: str, anchors: List[str]) -> tuple:
        vector = model.encode(
            [text],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        scores = anchor_emb @ vector
        best_idx = int(scores.argmax())
        return float(scores[best_idx]), anchors[best_idx]
