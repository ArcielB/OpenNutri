from __future__ import annotations

import json
import re
import shutil
import hashlib
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .embeddings import DualEmbeddingScorer
from .europe_pmc import EuropePMCClient
from .feedback_config import extract_terms, load_feedback_config
from .feedback_seed_terms import SEED_ANCHOR_PHRASES_BY_LANGUAGE, SEED_QUERY_PHRASES_BY_LANGUAGE
from .feedback_terms import extract_scored_terms, extract_terms as extract_feedback_terms
from .language_utils import SUPPORTED_LANGUAGES, normalize_language_text
from .models import CandidatePaper, DownloadRecord
from .ranking import validate_pdf_text
from .supabase_terms import fetch_food_terms_by_language, fetch_nutrient_terms_by_language


HEALTH_OUTCOME_TERMS_BY_LANGUAGE = {
    "en": [
        "diet",
        "dietary",
        "intake",
        "intervention",
        "clinical",
        "patients",
        "dietary intake",
        "dietary assessment",
        "diet quality",
        "diet pattern",
        "dietary intervention",
        "randomized",
        "trial",
        "cohort",
        "case-control",
        "odds ratio",
        "hazard ratio",
        "mortality",
        "disease",
        "diabetes",
        "obesity",
        "cardiovascular",
        "hypertension",
        "cancer",
        "cholesterol",
        "insulin",
    ],
    "tr": [
        "diyet",
        "diyetle",
        "alım",
        "alim",
        "müdahale",
        "müdahalesi",
        "mudahale",
        "klinik",
        "hasta",
        "hastalar",
        "randomize",
        "deneme",
        "kohort",
        "mortalite",
        "hastalık",
        "hastalik",
        "diyabet",
        "obezite",
        "kardiyovasküler",
        "kardiyovaskuler",
        "hipertansiyon",
        "kanser",
        "kolesterol",
        "insülin",
        "insulin",
    ],
}

UNIT_PATTERN = re.compile(r"\b(?:mg|g|µg|ug)\s*/?\s*100\s*g\b", re.IGNORECASE)

PMC_OA_API = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
AUDIT_EVERY_N = 100
METADATA_ACCEPT_THRESHOLD = 1.75
MAX_FEEDBACK_TERM_ABS = 2.5
MAX_FEEDBACK_SCORE_ABS = 6.0
MAX_HEALTH_PENALTY = 2.0
FILTER_TITLE_WEIGHT = 1.5
FILTER_TA_WEIGHT = 1.0
QUERY_BASE_FLOOR = 2
QUERY_PHRASE_EXPLORATION_RATE = 0.02
COMPOSITION_FRAMES = {
    "en": (
        '("food composition" OR "nutrient composition" OR "chemical composition" OR '
        '"proximate analysis" OR "nutrient content")'
    ),
    "tr": (
        '("gıda bileşimi" OR "besin bileşimi" OR "gıda kompozisyonu" OR '
        '"besin kompozisyonu" OR "yaklaşık analiz" OR "besin içeriği")'
    ),
}


@dataclass(frozen=True)
class QuerySpec:
    query: str
    template_id: str
    source_term: Optional[str]
    term_type: str
    language: str


class FoodCompositionCrawlerV2:
    def __init__(
        self,
        data_dir: str,
        supabase_url: str,
        supabase_key: str,
        target_pdfs: int = 12,
        query_limit: int = 50,
        food_term_limit: int = 0,
        nutrient_term_limit: int = 0,
        max_queries: int = 80,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.raw_pdf_dir = self.data_dir / "raw_pdfs"
        self.state_path = self.data_dir / "crawl_state.json"
        self.manifest_path = self.raw_pdf_dir / "_harvest_metadata.json"
        self.client = EuropePMCClient(page_size=query_limit)
        self.target_pdfs = target_pdfs
        self.query_limit = query_limit
        food_limit = food_term_limit if food_term_limit > 0 else 5000
        nutrient_limit = nutrient_term_limit if nutrient_term_limit > 0 else 500
        self.food_terms_by_language = fetch_food_terms_by_language(supabase_url, supabase_key, limit=food_limit)
        self.nutrient_terms_by_language = fetch_nutrient_terms_by_language(supabase_url, supabase_key, limit=nutrient_limit)
        self.feedback_config = load_feedback_config()
        self.query_phrases_by_language = {
            language: (
                extract_terms(self.feedback_config, "query_phrases", language=language)
                or list(SEED_QUERY_PHRASES_BY_LANGUAGE[language])
            )
            for language in SUPPORTED_LANGUAGES
        }
        self.anchor_phrases_by_language = {
            language: (
                extract_terms(self.feedback_config, "anchor_phrases", language=language)
                or list(SEED_ANCHOR_PHRASES_BY_LANGUAGE[language])
            )
            for language in SUPPORTED_LANGUAGES
        }
        self.feedback_weighted_terms_by_language = {
            language: extract_scored_terms(self.feedback_config, language=language)
            for language in SUPPORTED_LANGUAGES
        }
        self.feedback_rules = self.feedback_config.get("rules", {}) if isinstance(self.feedback_config.get("rules"), dict) else {}
        self.feedback_max_ngram = max(1, int(self.feedback_rules.get("max_ngram", 3) or 3))
        self.feedback_min_token_len = max(1, int(self.feedback_rules.get("min_token_len", 3) or 3))
        self.feedback_max_phrase_len = max(1, int(self.feedback_rules.get("max_phrase_len", 40) or 40))
        self.filter_title_weight = float(self.feedback_rules.get("filter_title_weight", FILTER_TITLE_WEIGHT) or FILTER_TITLE_WEIGHT)
        self.filter_ta_weight = float(self.feedback_rules.get("filter_ta_weight", FILTER_TA_WEIGHT) or FILTER_TA_WEIGHT)
        self.embedding_scorer = DualEmbeddingScorer()
        self.max_queries = max_queries
        self.state = self._load_state()

    def run(self, replace_existing: bool = False) -> Dict[str, object]:
        self.audit_reject_counter = int(self.state.get("audit_reject_counter", 0))
        if replace_existing and self.raw_pdf_dir.exists():
            shutil.rmtree(self.raw_pdf_dir)
        if replace_existing:
            self.state = self._default_state()
        self.raw_pdf_dir.mkdir(parents=True, exist_ok=True)

        accepted_records: List[DownloadRecord] = []
        rejected_records: List[DownloadRecord] = []
        seen_ids: Set[str] = set(self.state.get("seen_ids", []))
        query_stats: Dict[str, Dict[str, int]] = {}
        query_log: List[Dict[str, object]] = []

        queries = self._build_queries()

        for spec in queries:
            if len(accepted_records) >= self.target_pdfs:
                break
            candidates = self.client.search(spec.query, limit=self.query_limit)
            stats = {
                "query": spec.query,
                "language": spec.language,
                "template_id": spec.template_id,
                "source_term": spec.source_term,
                "term_type": spec.term_type,
                "results": len(candidates),
                "accepted": 0,
                "rejected": 0,
                "skipped_seen": 0,
            }
            query_log.append(stats)
            query_stats[spec.query] = {
                "language": spec.language,
                "results": len(candidates),
                "accepted": 0,
                "rejected": 0,
                "skipped_seen": 0,
            }
            if not candidates:
                continue

            for candidate in candidates:
                if len(accepted_records) >= self.target_pdfs:
                    break
                canonical_id = candidate.canonical_id
                if not canonical_id or canonical_id in seen_ids:
                    stats["skipped_seen"] += 1
                    query_stats[spec.query]["skipped_seen"] += 1
                    continue

                seen_ids.add(canonical_id)
                candidate.query = spec.query
                candidate.source_term = spec.source_term
                candidate.template_id = spec.template_id
                candidate.workflow_language = spec.language

                accepted, score, reason_details = self._metadata_decision(candidate)
                if not candidate.pdf_url:
                    self._append_reason(reason_details, "no_pdf_url", "Rejected: no PDF URL available")
                    accepted = False

                candidate.accepted = accepted
                candidate.reason_details = reason_details
                candidate.reasons = [reason["text"] for reason in reason_details]
                candidate.score = score

                if not accepted:
                    if candidate.pdf_url or candidate.pmcid:
                        audit_flag = self._next_audit_flag()
                        if audit_flag:
                            record = self._download_candidate(
                                candidate,
                                force_audit=True,
                                skip_validation=True,
                                rejection_error="Rejected by metadata rules",
                            )
                            rejected_records.append(record)
                        else:
                            rejected_records.append(self._skip_record(candidate, "Rejected by metadata rules"))
                    else:
                        rejected_records.append(self._skip_record(candidate, "Rejected by metadata rules"))
                    stats["rejected"] += 1
                    query_stats[spec.query]["rejected"] += 1
                    continue

                record = self._download_candidate(candidate)
                if record.status == "success":
                    accepted_records.append(record)
                    stats["accepted"] += 1
                    query_stats[spec.query]["accepted"] += 1
                else:
                    rejected_records.append(record)
                    stats["rejected"] += 1
                    query_stats[spec.query]["rejected"] += 1

        harvested_at = datetime.now(timezone.utc).isoformat()
        audit_count = sum(1 for record in rejected_records if record.audit)
        accepted_count_by_language = {
            language: sum(1 for record in accepted_records if record.workflow_language == language)
            for language in SUPPORTED_LANGUAGES
        }
        rejected_count_by_language = {
            language: sum(1 for record in rejected_records if record.workflow_language == language)
            for language in SUPPORTED_LANGUAGES
        }

        manifest = {
            "harvested_at": harvested_at,
            "query_count": len(queries),
            "rule_version": "field-aware-soft-v2",
            "embedding": self.embedding_scorer.info(),
            "feedback": {
                "config_path": str(self.feedback_config.get("config_path", "")),
                "query_phrases_by_language": {
                    language: phrases[:20]
                    for language, phrases in self.query_phrases_by_language.items()
                },
                "anchor_phrases_by_language": {
                    language: phrases[:20]
                    for language, phrases in self.anchor_phrases_by_language.items()
                },
                "weighted_terms_count_by_language": {
                    language: len(self.feedback_weighted_terms_by_language.get(language, {}))
                    for language in SUPPORTED_LANGUAGES
                },
                "counts": self.feedback_config.get("counts"),
                "counts_by_language": self.feedback_config.get("counts_by_language"),
            },
            "target_pdfs": self.target_pdfs,
            "accepted_count": len(accepted_records),
            "rejected_count": len(rejected_records),
            "accepted_count_by_language": accepted_count_by_language,
            "rejected_count_by_language": rejected_count_by_language,
            "food_term_sample_by_language": {
                language: self.food_terms_by_language.get(language, [])[:20]
                for language in SUPPORTED_LANGUAGES
            },
            "nutrient_term_sample_by_language": {
                language: self.nutrient_terms_by_language.get(language, [])[:20]
                for language in SUPPORTED_LANGUAGES
            },
            "query_stats": query_stats,
            "query_log": query_log,
            "audit": {
                "every": AUDIT_EVERY_N,
                "sample_count": audit_count,
            },
            "results": [record.to_dict() for record in accepted_records + rejected_records],
        }
        self._write_json(self.manifest_path, manifest)
        self.state["seen_ids"] = sorted(seen_ids)
        self.state["audit_reject_counter"] = self.audit_reject_counter
        self._save_state()
        return manifest

    def _next_audit_flag(self) -> bool:
        self.audit_reject_counter += 1
        return self.audit_reject_counter % AUDIT_EVERY_N == 0

    def _build_queries(self) -> List[QuerySpec]:
        budgets = self._language_query_budget()
        per_language = {
            language: self._build_queries_for_language(language, budgets.get(language, 0))
            for language in SUPPORTED_LANGUAGES
        }
        queries: List[QuerySpec] = []
        max_len = max((len(items) for items in per_language.values()), default=0)
        for idx in range(max_len):
            for language in SUPPORTED_LANGUAGES:
                items = per_language.get(language, [])
                if idx < len(items):
                    queries.append(items[idx])
        return self._dedupe_queries(queries)[: self.max_queries]

    def _language_query_budget(self) -> Dict[str, int]:
        if self.max_queries <= 0:
            return {language: 0 for language in SUPPORTED_LANGUAGES}
        base_budget = self.max_queries // len(SUPPORTED_LANGUAGES)
        budgets = {language: base_budget for language in SUPPORTED_LANGUAGES}
        remainder = self.max_queries - sum(budgets.values())
        if remainder > 0:
            cursor = int(self.state.get("language_remainder_cursor", 0)) % len(SUPPORTED_LANGUAGES)
            for offset in range(remainder):
                language = SUPPORTED_LANGUAGES[(cursor + offset) % len(SUPPORTED_LANGUAGES)]
                budgets[language] += 1
            self.state["language_remainder_cursor"] = (cursor + remainder) % len(SUPPORTED_LANGUAGES)
        return budgets

    def _build_queries_for_language(self, language: str, budget: int) -> List[QuerySpec]:
        if budget <= 0:
            return []

        composition_frame = COMPOSITION_FRAMES[language]
        if language == "en":
            base_queries = [
                QuerySpec(
                    query=f'({composition_frame} AND ("table" OR "content" OR "analysis")) AND IN_PMC:y',
                    template_id="base_core_composition",
                    source_term=None,
                    term_type="base",
                    language=language,
                ),
                QuerySpec(
                    query='(("mineral content" OR "vitamin content" OR "fatty acid composition" OR '
                    f'"amino acid composition") AND {composition_frame}) AND IN_PMC:y',
                    template_id="base_nutrient_content",
                    source_term=None,
                    term_type="base",
                    language=language,
                ),
            ]
        else:
            base_queries = [
                QuerySpec(
                    query=f'({composition_frame} AND ("tablo" OR "içerik" OR "analiz")) AND IN_PMC:y',
                    template_id="base_core_composition",
                    source_term=None,
                    term_type="base",
                    language=language,
                ),
                QuerySpec(
                    query='(("mineral içeriği" OR "vitamin içeriği" OR "yağ asidi bileşimi" OR '
                    f'"amino asit bileşimi") AND {composition_frame}) AND IN_PMC:y',
                    template_id="base_nutrient_content",
                    source_term=None,
                    term_type="base",
                    language=language,
                ),
            ]

        concept_pool = self._build_concept_pool(language)
        phrase_pool = self.query_phrases_by_language.get(language) or list(SEED_QUERY_PHRASES_BY_LANGUAGE[language])
        queries: List[QuerySpec] = list(base_queries[: min(len(base_queries), budget)])
        remaining = max(0, budget - len(queries))
        if remaining <= 0 or not concept_pool:
            return self._dedupe_queries(queries)[:budget]

        # Each language keeps its own cursors so English labels only steer
        # English query rotation and Turkish labels only steer Turkish rotation.
        concept_cursor = int(
            self.state.get(f"concept_cursor_{language}", self.state.get("concept_cursor", self.state.get("term_cursor", 0)))
        ) % len(concept_pool)
        phrase_cursor = int(self.state.get(f"phrase_cursor_{language}", self.state.get("phrase_cursor", 0)))
        phrase_explore_cursor = int(
            self.state.get(f"phrase_explore_cursor_{language}", self.state.get("phrase_explore_cursor", 0))
        )

        exploration_pool_size = min(
            max(0, len(phrase_pool) - 1),
            max(1, round(len(phrase_pool) * QUERY_PHRASE_EXPLORATION_RATE)),
        ) if len(phrase_pool) > 1 else 0
        core_count = max(1, len(phrase_pool) - exploration_pool_size)
        core_phrases = phrase_pool[:core_count]
        exploration_phrases = phrase_pool[len(core_phrases):]
        exploration_slots = 0
        exploration_step = None
        if exploration_phrases:
            exploration_slots = min(
                len(exploration_phrases),
                max(1, round(remaining * QUERY_PHRASE_EXPLORATION_RATE)),
            )
            exploration_step = max(1, remaining // exploration_slots)

        primary_used = 0
        explore_used = 0
        for offset in range(remaining):
            concept_type, concept_term = concept_pool[(concept_cursor + offset) % len(concept_pool)]
            use_explore = (
                exploration_phrases
                and exploration_slots > 0
                and exploration_step is not None
                and (offset + 1) % exploration_step == 0
                and explore_used < exploration_slots
            )
            if use_explore:
                phrase = exploration_phrases[(phrase_explore_cursor + explore_used) % len(exploration_phrases)]
                explore_used += 1
                template_id = f"{concept_type}_phrase_explore"
            else:
                phrase = core_phrases[(phrase_cursor + primary_used) % len(core_phrases)]
                primary_used += 1
                template_id = f"{concept_type}_phrase_core"

            queries.append(self._build_learned_query(language, concept_type, concept_term, phrase, template_id))

        self.state[f"concept_cursor_{language}"] = (concept_cursor + remaining) % len(concept_pool)
        self.state[f"term_cursor_{language}"] = self.state[f"concept_cursor_{language}"]
        self.state[f"phrase_cursor_{language}"] = (phrase_cursor + primary_used) % max(1, len(core_phrases))
        if exploration_phrases:
            self.state[f"phrase_explore_cursor_{language}"] = (
                (phrase_explore_cursor + explore_used) % len(exploration_phrases)
            )
        return self._dedupe_queries(queries)[:budget]

    def _build_concept_pool(self, language: str) -> List[Tuple[str, str]]:
        pool: List[Tuple[str, str]] = []
        food_terms = self.food_terms_by_language.get(language, [])
        nutrient_terms = self.nutrient_terms_by_language.get(language, [])
        max_len = max(len(food_terms), len(nutrient_terms))
        for idx in range(max_len):
            if idx < len(food_terms):
                pool.append(("food", food_terms[idx]))
            if idx < len(nutrient_terms):
                pool.append(("nutrient", nutrient_terms[idx]))
        return pool

    def _build_learned_query(
        self,
        language: str,
        concept_type: str,
        concept_term: str,
        phrase: str,
        template_id: str,
    ) -> QuerySpec:
        safe_concept = concept_term.replace('"', "").strip()
        safe_phrase = phrase.replace('"', "").strip()
        composition_frame = COMPOSITION_FRAMES[language]
        query = f'("{safe_concept}" AND "{safe_phrase}" AND {composition_frame}) AND IN_PMC:y'
        if concept_type == "nutrient":
            query = (
                f'("{safe_concept}" AND "{safe_phrase}" AND '
                f'({composition_frame} OR "mg/100g" OR "g/100g")) AND IN_PMC:y'
            )
        return QuerySpec(
            query=query,
            template_id=template_id,
            source_term=concept_term,
            term_type=concept_type,
            language=language,
        )

    def _dedupe_queries(self, queries: List[QuerySpec]) -> List[QuerySpec]:
        seen: Set[str] = set()
        ordered: List[QuerySpec] = []
        for spec in queries:
            normalized_query = re.sub(r"\s+", " ", spec.query.strip())
            key = f"{spec.language}:{normalized_query}"
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(spec)
        return ordered

    def _metadata_decision(self, candidate: CandidatePaper) -> Tuple[bool, float, List[Dict[str, str]]]:
        details: List[Dict[str, str]] = []
        workflow_language = candidate.workflow_language if candidate.workflow_language in SUPPORTED_LANGUAGES else "en"
        title_text = " ".join((candidate.title or "").split())
        abstract_text = " ".join((candidate.abstract or "").split())
        raw_text = " ".join(part for part in (title_text, abstract_text) if part).strip()
        normalized = self._normalize_for_match(raw_text.lower())
        score = 0.0
        anchor_phrases = self.anchor_phrases_by_language.get(workflow_language, [])
        food_terms = self.food_terms_by_language.get(workflow_language, [])
        nutrient_terms = self.nutrient_terms_by_language.get(workflow_language, [])
        health_terms = HEALTH_OUTCOME_TERMS_BY_LANGUAGE.get(workflow_language, [])

        # Metadata acceptance is intentionally additive: explicit composition
        # cues, embedding similarity, and learned feedback n-grams all contribute.
        # That keeps obviously strong papers near the top while avoiding over-trust
        # in any single weak signal.
        composition_hit = self._first_term_hit(normalized, anchor_phrases)
        if composition_hit:
            self._append_reason(details, "composition_phrase", f"Positive: composition phrase '{composition_hit}'")
            score += 1.35

        unit_hit = bool(UNIT_PATTERN.search(raw_text))
        if unit_hit:
            self._append_reason(details, "unit_signal", "Positive: nutrient unit pattern (mg/100g or g/100g)")
            score += 1.25

        food_hit = self._first_term_hit(normalized, food_terms)
        if food_hit:
            self._append_reason(details, "food_term_hit", f"Positive: food term '{food_hit}'")
            score += 0.65

        nutrient_hit = self._first_term_hit(normalized, nutrient_terms)
        if nutrient_hit:
            self._append_reason(details, "nutrient_term_hit", f"Positive: nutrient term '{nutrient_hit}'")
            score += 0.65

        if food_hit and nutrient_hit:
            score += 0.75
            self._append_reason(details, "food_nutrient_combo", "Positive: matched both food and nutrient terms")

        health_hits = self._collect_term_hits(normalized, health_terms)
        if health_hits:
            penalty = min(MAX_HEALTH_PENALTY, 0.55 * len(health_hits))
            score -= penalty
            self._append_reason(
                details,
                "health_penalty",
                f"Penalty {penalty:.2f}: health-outcome terms {', '.join(health_hits[:4])}",
            )

        embedding_accept = False
        try:
            embedding_result = self.embedding_scorer.score(raw_text, workflow_language)
        except Exception as exc:
            identifier = candidate.canonical_id or candidate.title or "unknown"
            raise RuntimeError(f"Embedding scoring failed for candidate '{identifier}'.") from exc

        embed_code = f"embed_{workflow_language}"
        self._append_reason(
            details,
            embed_code,
            "Embedding {lang} sim {score:.3f} to '{anchor}' (thr {thr:.2f})".format(
                lang=workflow_language.upper(),
                score=embedding_result["max_similarity"],
                anchor=embedding_result["anchor"],
                thr=embedding_result["threshold"],
            ),
        )
        if embedding_result["max_similarity"] >= embedding_result["threshold"]:
            embedding_accept = True
            score += 1.45
        if embedding_accept:
            score += 0.75
            self._append_reason(details, "embedding_positive", "Positive: embedding similarity above threshold")

        score += self._feedback_score(title_text, abstract_text, workflow_language, details)

        accepted = score >= METADATA_ACCEPT_THRESHOLD
        if accepted:
            self._append_reason(details, "accepted_metadata", f"Accepted by metadata score {score:.2f}")
        else:
            self._append_reason(details, "rejected_metadata", f"Rejected by metadata score {score:.2f}")

        return accepted, score, details

    def _append_reason(self, details: List[Dict[str, str]], code: str, text: str) -> None:
        details.append({"code": code, "text": text})

    def _normalize_for_match(self, text: str) -> str:
        return normalize_language_text(text)

    def _first_term_hit(self, text: str, terms: List[str]) -> Optional[str]:
        if not text:
            return None
        padded = f" {text} "
        for term in terms:
            if not term:
                continue
            normalized_term = self._normalize_for_match(term)
            if not normalized_term:
                continue
            needle = f" {normalized_term} "
            if needle in padded:
                return normalized_term
        return None

    def _collect_term_hits(self, text: str, terms: List[str]) -> List[str]:
        if not text:
            return []
        padded = f" {text} "
        hits: List[str] = []
        for term in terms:
            normalized_term = self._normalize_for_match(term)
            if not normalized_term:
                continue
            needle = f" {normalized_term} "
            if needle in padded and normalized_term not in hits:
                hits.append(normalized_term)
        return hits

    def _feedback_score(
        self,
        title_text: str,
        abstract_text: str,
        workflow_language: str,
        details: List[Dict[str, str]],
    ) -> float:
        feedback_weighted_terms = self.feedback_weighted_terms_by_language.get(workflow_language, {})
        if not feedback_weighted_terms:
            return 0.0

        title_terms = set(
            extract_feedback_terms(
                title_text,
                max_ngram=self.feedback_max_ngram,
                min_token_len=self.feedback_min_token_len,
                max_phrase_len=self.feedback_max_phrase_len,
            )
        )
        ta_terms = set(
            extract_feedback_terms(
                " ".join(part for part in (title_text, abstract_text) if part),
                max_ngram=self.feedback_max_ngram,
                min_token_len=self.feedback_min_token_len,
                max_phrase_len=self.feedback_max_phrase_len,
            )
        )

        matched_terms = []
        for term in sorted(title_terms | ta_terms):
            weights = feedback_weighted_terms.get(term)
            if not weights:
                continue
            title_contrib = 0.0
            ta_contrib = 0.0
            if term in title_terms:
                title_contrib = self.filter_title_weight * float(weights.get("title_net", 0.0))
            if term in ta_terms:
                ta_contrib = self.filter_ta_weight * float(weights.get("ta_net", 0.0))
            contribution = max(-MAX_FEEDBACK_TERM_ABS, min(MAX_FEEDBACK_TERM_ABS, title_contrib + ta_contrib))
            if contribution == 0.0:
                continue
            matched_terms.append((term, contribution, title_contrib, ta_contrib))

        if not matched_terms:
            return 0.0

        raw_score = sum(contribution for _, contribution, _, _ in matched_terms)
        clamped_score = max(-MAX_FEEDBACK_SCORE_ABS, min(MAX_FEEDBACK_SCORE_ABS, raw_score))
        strongest = sorted(matched_terms, key=lambda item: abs(item[1]), reverse=True)[:6]
        summary = ", ".join(
            f"{term} ({contribution:+.2f}; title {title_part:+.2f}, ta {ta_part:+.2f})"
            for term, contribution, title_part, ta_part in strongest
        )
        self._append_reason(
            details,
            "feedback_score",
            f"Soft feedback score {clamped_score:.2f} from {len(matched_terms)} matched n-grams: {summary}",
        )
        return clamped_score

    def _download_candidate(
        self,
        candidate: CandidatePaper,
        force_audit: bool = False,
        skip_validation: bool = False,
        rejection_error: Optional[str] = None,
    ) -> DownloadRecord:
        if not candidate.pdf_url and not candidate.pmcid:
            return self._failed_record(candidate, "No PDF URL available", audit=force_audit)

        try:
            content, source_url = self._fetch_pdf_with_oa(candidate)
            candidate.pdf_url = source_url
        except Exception as exc:
            return self._failed_record(candidate, str(exc), audit=force_audit)

        file_name = self._build_filename(candidate)
        destination = self.raw_pdf_dir / file_name
        destination.write_bytes(content)
        if skip_validation:
            return DownloadRecord(
                status="skipped",
                title=candidate.title,
                score=candidate.score,
                source=candidate.source,
                query=candidate.query,
                reasons=candidate.reasons,
                reason_details=candidate.reason_details,
                audit=force_audit,
                file=str(destination.relative_to(self.data_dir.parent)),
                pmcid=candidate.pmcid,
                doi=candidate.doi,
                journal=candidate.journal,
                year=candidate.year,
                size_kb=max(1, round(len(content) / 1024)),
                pdf_url=candidate.pdf_url,
                error=rejection_error,
                source_term=candidate.source_term,
                template_id=candidate.template_id,
                workflow_language=candidate.workflow_language,
            )
        _, accepted, pdf_reasons = self._validate_downloaded_pdf(destination, candidate)
        pdf_reason_details = [
            {"code": "pdf_validation", "text": reason} for reason in pdf_reasons
        ]
        combined_reason_details = candidate.reason_details + pdf_reason_details
        combined_reasons = [reason["text"] for reason in combined_reason_details]
        if not accepted:
            candidate.reason_details = combined_reason_details
            candidate.reasons = combined_reasons
            audit_flag = force_audit or self._next_audit_flag()
            if not audit_flag:
                destination.unlink(missing_ok=True)
                return self._failed_record(candidate, "Rejected by PDF validation")
            return DownloadRecord(
                status="failed",
                title=candidate.title,
                score=candidate.score,
                source=candidate.source,
                query=candidate.query,
                reasons=combined_reasons,
                reason_details=combined_reason_details,
                audit=True,
                file=str(destination.relative_to(self.data_dir.parent)),
                pmcid=candidate.pmcid,
                doi=candidate.doi,
                journal=candidate.journal,
                year=candidate.year,
                size_kb=max(1, round(len(content) / 1024)),
                pdf_url=candidate.pdf_url,
                error="Rejected by PDF validation",
                source_term=candidate.source_term,
                template_id=candidate.template_id,
                workflow_language=candidate.workflow_language,
            )

        candidate.reason_details = combined_reason_details
        candidate.reasons = combined_reasons
        return DownloadRecord(
            status="success",
            title=candidate.title,
            score=candidate.score,
            source=candidate.source,
            query=candidate.query,
            reasons=combined_reasons,
            reason_details=combined_reason_details,
            audit=False,
            file=str(destination.relative_to(self.data_dir.parent)),
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            size_kb=max(1, round(len(content) / 1024)),
            pdf_url=candidate.pdf_url,
            source_term=candidate.source_term,
            template_id=candidate.template_id,
            workflow_language=candidate.workflow_language,
        )

    def _fetch_pdf_with_oa(self, candidate: CandidatePaper) -> Tuple[bytes, str]:
        if candidate.pmcid:
            oa_payload = self._fetch_pdf_from_oa_package(candidate.pmcid)
            if oa_payload:
                return oa_payload, f"{PMC_OA_API}?id={candidate.pmcid}"
        return self._fetch_pdf(candidate.pdf_url), candidate.pdf_url

    def _fetch_pdf_from_oa_package(self, pmcid: str) -> Optional[bytes]:
        pmc_id = pmcid if pmcid.startswith("PMC") else f"PMC{pmcid}"
        oa_url = f"{PMC_OA_API}?id={pmc_id}"
        try:
            with urlopen(oa_url, timeout=12) as response:
                xml_payload = response.read().decode("utf-8", errors="ignore")
        except (HTTPError, URLError, TimeoutError):
            return None

        try:
            root = ET.fromstring(xml_payload)
        except ET.ParseError:
            return None

        pdf_links: List[str] = []
        tgz_links: List[str] = []
        for link in root.findall(".//link"):
            href = link.attrib.get("href") or ""
            if not href:
                continue
            fmt = (link.attrib.get("format") or "").lower()
            if fmt == "pdf" or href.lower().endswith(".pdf"):
                pdf_links.append(href)
            elif fmt == "tgz" or href.lower().endswith(".tar.gz"):
                tgz_links.append(href)

        for pdf_url in pdf_links:
            pdf_url = self._normalize_oa_url(pdf_url)
            try:
                payload = self._fetch_pdf(pdf_url)
            except Exception:
                continue
            if payload.startswith(b"%PDF"):
                return payload

        for tgz_url in tgz_links:
            tgz_url = self._normalize_oa_url(tgz_url)
            payload = self._download_tgz_pdf(tgz_url)
            if payload:
                return payload
        return None

    def _normalize_oa_url(self, url: str) -> str:
        if url.startswith("ftp://ftp.ncbi.nlm.nih.gov"):
            return url.replace("ftp://ftp.ncbi.nlm.nih.gov", "https://ftp.ncbi.nlm.nih.gov", 1)
        return url

    def _download_tgz_pdf(self, url: str) -> Optional[bytes]:
        try:
            request = Request(url, headers={"User-Agent": "OpenNutriCompositionCrawler/2.0"})
            with urlopen(request, timeout=40) as response:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp:
                    shutil.copyfileobj(response, tmp)
                    tmp_path = Path(tmp.name)
        except (HTTPError, URLError, TimeoutError, OSError):
            return None

        try:
            with tarfile.open(tmp_path, "r:gz") as tar:
                pdf_members = [m for m in tar.getmembers() if m.name.lower().endswith(".pdf")]
                if not pdf_members:
                    return None
                pdf_members.sort(key=lambda m: m.size or 0, reverse=True)
                member = pdf_members[0]
                extracted = tar.extractfile(member)
                if not extracted:
                    return None
                return extracted.read()
        finally:
            tmp_path.unlink(missing_ok=True)

    def _fetch_pdf(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "OpenNutriCompositionCrawler/2.0"})
        try:
            with urlopen(request, timeout=20) as response:
                content_type = response.headers.get("Content-Type", "")
                final_url = response.geturl()
                payload = response.read()
        except HTTPError as exc:
            payload = self._fetch_pdf_with_curl(url)
            if payload.startswith(b"%PDF"):
                return payload
            raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
        except URLError as exc:
            payload = self._fetch_pdf_with_curl(url)
            if payload.startswith(b"%PDF"):
                return payload
            raise RuntimeError(f"URL error for {url}: {exc.reason}") from exc

        if payload.startswith(b"%PDF"):
            return payload

        if "html" in content_type.lower():
            html = payload.decode("utf-8", errors="ignore")
            pow_payload = self._solve_pmc_pow(html)
            if pow_payload:
                pow_request = Request(
                    final_url,
                    headers={
                        "User-Agent": "OpenNutriCompositionCrawler/2.0",
                        "Cookie": pow_payload,
                    },
                )
                try:
                    with urlopen(pow_request, timeout=20) as pow_response:
                        pow_bytes = pow_response.read()
                except (HTTPError, URLError) as exc:
                    raise RuntimeError(f"Failed POW retry for {final_url}: {exc}") from exc
                if pow_bytes.startswith(b"%PDF"):
                    return pow_bytes
            pdf_match = re.search(r'href=["\']([^"\']+\\.pdf[^"\']*)["\']', html, re.IGNORECASE)
            if pdf_match:
                nested_url = urljoin(final_url, pdf_match.group(1))
                nested_request = Request(nested_url, headers={"User-Agent": "OpenNutriCompositionCrawler/2.0"})
                try:
                    with urlopen(nested_request, timeout=20) as nested_response:
                        nested_payload = nested_response.read()
                except (HTTPError, URLError) as exc:
                    raise RuntimeError(f"Failed nested PDF fetch for {nested_url}: {exc}") from exc
                if nested_payload.startswith(b"%PDF"):
                    return nested_payload

            curl_payload = self._fetch_pdf_with_curl(url)
            if curl_payload.startswith(b"%PDF"):
                return curl_payload

        snippet = payload[:120].decode("utf-8", errors="ignore")
        if "pdf" not in content_type.lower():
            raise RuntimeError(f"Not a PDF ({content_type or 'unknown'}): {snippet[:80]}")
        return payload

    def _fetch_pdf_with_curl(self, url: str) -> bytes:
        try:
            return subprocess.check_output(
                [
                    "curl",
                    "-L",
                    "--silent",
                    "--show-error",
                    "-A",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    url,
                ],
                stderr=subprocess.DEVNULL,
                timeout=40,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return b""

    def _validate_downloaded_pdf(self, path: Path, candidate: CandidatePaper) -> Tuple[float, bool, List[str]]:
        try:
            text = subprocess.check_output(
                ["pdftotext", str(path), "-"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=20,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return 0.0, False, [f"pdf text extraction failed: {exc}"]

        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 200:
            return 0.0, False, ["pdf text too short to validate"]
        workflow_language = candidate.workflow_language if candidate.workflow_language in SUPPORTED_LANGUAGES else "en"
        food_terms = self.food_terms_by_language.get(workflow_language, [])
        nutrient_terms = self.nutrient_terms_by_language.get(workflow_language, [])
        return validate_pdf_text(text, candidate, food_terms, nutrient_terms)

    def _solve_pmc_pow(self, html: str) -> Optional[str]:
        challenge_match = re.search(r'POW_CHALLENGE = "([^"]+)"', html)
        difficulty_match = re.search(r'POW_DIFFICULTY = "([^"]+)"', html)
        cookie_match = re.search(r'POW_COOKIE_NAME = "([^"]+)"', html)
        if not challenge_match or not difficulty_match or not cookie_match:
            return None

        challenge = challenge_match.group(1)
        difficulty = int(difficulty_match.group(1))
        cookie_name = cookie_match.group(1)
        prefix = "0" * difficulty
        nonce = 0
        while True:
            digest = hashlib.md5(f"{challenge}{nonce}".encode("utf-8")).hexdigest()
            if digest.startswith(prefix):
                return f"{cookie_name}={challenge},{nonce}"
            nonce += 1

    def _build_filename(self, candidate: CandidatePaper) -> str:
        if candidate.pmcid:
            return f"{candidate.pmcid}.pdf"
        stem = candidate.title.lower()
        stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
        stem = stem[:80] or "paper"
        return f"{stem}.pdf"

    def _skip_record(self, candidate: CandidatePaper, error: str, audit: bool = False) -> DownloadRecord:
        return DownloadRecord(
            status="skipped",
            title=candidate.title,
            score=candidate.score,
            source=candidate.source,
            query=candidate.query,
            reasons=candidate.reasons,
            reason_details=candidate.reason_details,
            audit=audit,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            pdf_url=candidate.pdf_url,
            error=error,
            source_term=candidate.source_term,
            template_id=candidate.template_id,
            workflow_language=candidate.workflow_language,
        )

    def _failed_record(self, candidate: CandidatePaper, error: str, audit: bool = False) -> DownloadRecord:
        return DownloadRecord(
            status="failed",
            title=candidate.title,
            score=candidate.score,
            source=candidate.source,
            query=candidate.query,
            reasons=candidate.reasons,
            reason_details=candidate.reason_details,
            audit=audit,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            pdf_url=candidate.pdf_url,
            error=error,
            source_term=candidate.source_term,
            template_id=candidate.template_id,
            workflow_language=candidate.workflow_language,
        )

    def _default_state(self) -> Dict[str, object]:
        state = {
            "seen_ids": [],
            "language_remainder_cursor": 0,
            "audit_reject_counter": 0,
        }
        for language in SUPPORTED_LANGUAGES:
            state[f"term_cursor_{language}"] = 0
            state[f"concept_cursor_{language}"] = 0
            state[f"phrase_cursor_{language}"] = 0
            state[f"phrase_explore_cursor_{language}"] = 0
        return state

    def _load_state(self) -> Dict[str, object]:
        if not self.state_path.exists():
            return self._default_state()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return self._default_state()
        if not isinstance(payload, dict):
            return self._default_state()
        state = self._default_state()
        state.update(payload)
        return state

    def _save_state(self) -> None:
        self._write_json(self.state_path, self.state)

    def _write_json(self, path: Path, payload: Dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
