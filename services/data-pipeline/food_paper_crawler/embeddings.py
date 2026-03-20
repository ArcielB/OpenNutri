from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None


EN_ANCHOR_PHRASES = [
    "food composition",
    "food composition table",
    "composition table",
    "nutrient composition",
    "nutritional composition",
    "chemical composition",
    "proximate composition",
    "proximate analysis",
    "nutrient content",
    "nutrient profile",
    "mineral content",
    "vitamin content",
    "fatty acid composition",
    "amino acid composition",
    "nutrient data",
    "composition data",
]

MULTI_ANCHOR_PHRASES = EN_ANCHOR_PHRASES + [
    "gida bilesimi",
    "besin bilesimi",
    "gida kompozisyonu",
    "besin kompozisyonu",
    "composicion de alimentos",
    "composicion nutricional",
    "composicao de alimentos",
    "composicao nutricional",
    "composition des aliments",
]


@dataclass
class DualEmbeddingConfig:
    en_model: str
    multi_model: str
    en_threshold: float
    multi_threshold: float
    max_chars: int
    version: str = "dual-embeddings-v1"


class DualEmbeddingScorer:
    def __init__(self, config: Optional[DualEmbeddingConfig] = None) -> None:
        if config is None:
            config = DualEmbeddingConfig(
                en_model=os.environ.get("L2_EMBED_EN_MODEL", "all-MiniLM-L6-v2"),
                multi_model=os.environ.get("L2_EMBED_MULTI_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
                en_threshold=float(os.environ.get("L2_EMBED_EN_THRESHOLD", "0.45")),
                multi_threshold=float(os.environ.get("L2_EMBED_MULTI_THRESHOLD", "0.42")),
                max_chars=int(os.environ.get("L2_EMBED_MAX_CHARS", "1800")),
            )
        self.config = config
        self.available = SentenceTransformer is not None
        self.error: Optional[str] = None
        self._en_model = None
        self._multi_model = None
        self._en_anchors = EN_ANCHOR_PHRASES
        self._multi_anchors = MULTI_ANCHOR_PHRASES
        self._en_anchor_emb = None
        self._multi_anchor_emb = None
        if not self.available:
            self.error = "sentence-transformers not installed"
            return
        try:
            self._en_model = SentenceTransformer(self.config.en_model)
            self._multi_model = SentenceTransformer(self.config.multi_model)
            self._en_anchor_emb = self._encode(self._en_model, self._en_anchors)
            self._multi_anchor_emb = self._encode(self._multi_model, self._multi_anchors)
        except Exception as exc:  # pragma: no cover
            self.available = False
            self.error = str(exc)

    def info(self) -> Dict[str, object]:
        return {
            "version": self.config.version,
            "available": self.available,
            "error": self.error,
            "en_model": self.config.en_model,
            "multi_model": self.config.multi_model,
            "en_threshold": self.config.en_threshold,
            "multi_threshold": self.config.multi_threshold,
            "en_anchor_count": len(self._en_anchors),
            "multi_anchor_count": len(self._multi_anchors),
        }

    def score(self, text: str) -> Dict[str, object]:
        if not self.available:
            return {"available": False, "error": self.error}

        trimmed = " ".join((text or "").split())
        if self.config.max_chars > 0:
            trimmed = trimmed[: self.config.max_chars]
        if not trimmed:
            return {"available": False, "error": "empty_text"}

        en_score, en_anchor = self._max_similarity(self._en_model, self._en_anchor_emb, trimmed, self._en_anchors)
        multi_score, multi_anchor = self._max_similarity(
            self._multi_model, self._multi_anchor_emb, trimmed, self._multi_anchors
        )

        return {
            "available": True,
            "en": {
                "model": self.config.en_model,
                "threshold": self.config.en_threshold,
                "max_similarity": en_score,
                "anchor": en_anchor,
            },
            "multi": {
                "model": self.config.multi_model,
                "threshold": self.config.multi_threshold,
                "max_similarity": multi_score,
                "anchor": multi_anchor,
            },
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
