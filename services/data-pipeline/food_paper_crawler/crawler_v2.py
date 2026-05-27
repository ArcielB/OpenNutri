from __future__ import annotations

import json
import re
import shutil
import hashlib
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

from .embeddings import DualEmbeddingScorer
from .feedback_config import (
    extract_batch_scores,
    extract_concept_scores,
    extract_pair_scores,
    extract_source_priors,
    extract_terms,
    load_feedback_config,
)
from .feedback_seed_terms import SEED_ANCHOR_PHRASES_BY_LANGUAGE, SEED_QUERY_PHRASES_BY_LANGUAGE
from .feedback_terms import extract_scored_terms, extract_terms as extract_feedback_terms
from .language_utils import SUPPORTED_LANGUAGES, normalize_language_text
from .models import (
    CandidatePaper,
    DiscoveryHit,
    DownloadRecord,
    QuerySpec,
    SearchTask,
    build_search_batch_key,
    build_storage_filename,
)
from .ranking import SOFT_NEGATIVE_TERMS, STRONG_NEGATIVE_SIGNAL_TERMS, validate_pdf_text
from .search_sources import DEFAULT_SEARCH_SOURCES, build_search_sources
from .supabase_terms import fetch_food_terms_by_language, fetch_nutrient_terms_by_language
from pdf_limits import max_paper_pdf_bytes, pdf_size_limit_message


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
SEARCH_GATE_REJECT_THRESHOLD = -0.35
MAX_FEEDBACK_TERM_ABS = 2.5
MAX_FEEDBACK_SCORE_ABS = 6.0
MAX_HEALTH_PENALTY = 2.0
FILTER_TITLE_WEIGHT = 1.5
FILTER_TA_WEIGHT = 1.0
MAX_SOURCE_PRIOR_ABS = 0.9
QUERY_BASE_FLOOR = 2
QUERY_PHRASE_EXPLORATION_RATE = 0.02
RAW_SEARCH_RESULT_MULTIPLIER = 4
MIN_RAW_SEARCH_LIMIT = 100
MAX_RAW_SEARCH_LIMIT = 400
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
DEFAULT_SOURCE_BIAS_BY_LANGUAGE = {
    "en": {
        "europepmc": 0.35,
        "openalex": 0.15,
        "semanticscholar": 0.05,
        "dergipark": -0.15,
    },
    "tr": {
        "dergipark": 0.35,
        "openalex": 0.2,
        "semanticscholar": 0.1,
        "europepmc": -0.3,
    },
}
TERMINAL_DECISIONS = {"accepted", "rejected"}
TERMINAL_DECISION_STAGES = {
    "search_gate",
    "metadata_filter",
    "pdf_fetch",
    "pdf_validation",
    "acquisition",
}


class FoodCompositionCrawlerV2:
    def __init__(
        self,
        data_dir: str,
        supabase_url: str,
        supabase_key: str,
        target_pdfs: int = 12,
        target_pdfs_en: Optional[int] = None,
        target_pdfs_tr: Optional[int] = None,
        query_limit: int = 50,
        food_term_limit: int = 0,
        nutrient_term_limit: int = 0,
        max_queries: int = 80,
        sources: Optional[List[str]] = None,
        dergipark_scan_budget: int = 400,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.raw_pdf_dir = self.data_dir / "raw_pdfs"
        self.state_path = self.data_dir / "crawl_state.json"
        self.manifest_path = self.raw_pdf_dir / "_harvest_metadata.json"
        self.candidate_store_path = self.data_dir / "search_candidates.json"
        self.search_hits_path = self.data_dir / "search_hits.json"
        self.target_pdfs_by_language = self._resolve_target_pdfs_by_language(
            target_pdfs=target_pdfs,
            target_pdfs_en=target_pdfs_en,
            target_pdfs_tr=target_pdfs_tr,
        )
        self.target_pdfs = sum(self.target_pdfs_by_language.values())
        self.query_limit = max(1, int(query_limit))
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
        self.source_priors_by_language = {
            language: extract_source_priors(self.feedback_config, language)
            for language in SUPPORTED_LANGUAGES
        }
        self.pair_scores_by_language = {
            language: extract_pair_scores(self.feedback_config, language)
            for language in SUPPORTED_LANGUAGES
        }
        self.batch_scores_by_language = {
            language: extract_batch_scores(self.feedback_config, language)
            for language in SUPPORTED_LANGUAGES
        }
        self.concept_scores_by_language = {
            language: extract_concept_scores(self.feedback_config, language)
            for language in SUPPORTED_LANGUAGES
        }
        self.embedding_scorer = DualEmbeddingScorer()
        self.max_queries = max_queries
        self.dergipark_scan_budget = max(1, int(dergipark_scan_budget))
        self.search_sources = build_search_sources(
            list(sources or DEFAULT_SEARCH_SOURCES),
            data_dir=self.data_dir,
            page_size=self._raw_search_limit(query_limit),
            dergipark_scan_budget=self.dergipark_scan_budget,
        )
        self.state = self._load_state()

    def run(self, replace_existing: bool = False) -> Dict[str, object]:
        self.audit_reject_counter = int(self.state.get("audit_reject_counter", 0))
        if replace_existing and self.raw_pdf_dir.exists():
            shutil.rmtree(self.raw_pdf_dir)
        if replace_existing:
            self.state = self._default_state()
            self.candidate_store_path.unlink(missing_ok=True)
            self.search_hits_path.unlink(missing_ok=True)
        self.raw_pdf_dir.mkdir(parents=True, exist_ok=True)
        skip_keys = self._state_skip_keys() | self._live_paper_skip_keys()
        crawl_run_id = uuid4().hex
        search_tasks = self._build_search_tasks(run_id=crawl_run_id)
        (
            candidates,
            discovery_hits,
            query_log,
            query_stats,
            accepted_records,
            rejected_records,
        ) = self._run_search_batches(search_tasks, skip_keys)

        harvested_at = datetime.now(timezone.utc).isoformat()
        audit_count = sum(1 for record in rejected_records if record.audit)
        search_gate_pass_count = sum(1 for hit in discovery_hits if hit.search_gate_pass)
        filter_pass_count = sum(1 for candidate in candidates if candidate.filter_pass)
        accepted_count_by_language = {
            language: sum(1 for record in accepted_records if record.workflow_language == language)
            for language in SUPPORTED_LANGUAGES
        }
        rejected_count_by_language = {
            language: sum(1 for record in rejected_records if record.workflow_language == language)
            for language in SUPPORTED_LANGUAGES
        }
        candidate_count_by_language = {
            language: sum(1 for candidate in candidates if candidate.workflow_language == language)
            for language in SUPPORTED_LANGUAGES
        }
        summary = self._build_run_summary(candidates, discovery_hits, accepted_records, rejected_records)
        self._write_candidate_artifacts(harvested_at, candidates, discovery_hits)
        dergipark_source = self.search_sources.get("dergipark")
        dergipark_index = dergipark_source.index_info() if hasattr(dergipark_source, "index_info") else None

        manifest = {
            "crawl_run_id": crawl_run_id,
            "harvested_at": harvested_at,
            "query_count": len(search_tasks),
            "search_batch_count": len(query_log),
            "rule_version": "search-filter-acquisition-v5",
            "sources": list(self.search_sources.keys()),
            "dergipark_scan_budget": self.dergipark_scan_budget,
            "dergipark_index": dergipark_index,
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
                "concept_scores_count_by_language": {
                    language: len(self.concept_scores_by_language.get(language, {}))
                    for language in SUPPORTED_LANGUAGES
                },
                "counts": self.feedback_config.get("counts"),
                "counts_by_language": self.feedback_config.get("counts_by_language"),
            },
            "target_pdfs": self.target_pdfs,
            "target_pdfs_by_language": self.target_pdfs_by_language,
            "candidate_count": len(candidates),
            "candidate_count_by_language": candidate_count_by_language,
            "search_hit_count": len(discovery_hits),
            "search_gate_pass_count": search_gate_pass_count,
            "filter_pass_count": filter_pass_count,
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
            "summary": summary,
            "audit": {
                "every": AUDIT_EVERY_N,
                "sample_count": audit_count,
            },
            "candidate_store": str(self.candidate_store_path.relative_to(self.data_dir.parent)),
            "search_hits": str(self.search_hits_path.relative_to(self.data_dir.parent)),
            "results": [record.to_dict() for record in accepted_records + rejected_records],
        }
        self._write_json(self.manifest_path, manifest)
        self._record_terminal_states(candidates, discovery_hits, accepted_records, rejected_records)
        self.state["audit_reject_counter"] = self.audit_reject_counter
        self._save_state()
        return manifest

    def _run_search_batches(
        self,
        tasks: List[SearchTask],
        skip_keys: Set[str],
    ) -> Tuple[
        List[CandidatePaper],
        List[DiscoveryHit],
        List[Dict[str, object]],
        Dict[str, Dict[str, object]],
        List[DownloadRecord],
        List[DownloadRecord],
    ]:
        query_log: List[Dict[str, object]] = []
        query_stats: Dict[str, Dict[str, object]] = {}
        candidates_by_key: Dict[str, CandidatePaper] = {}
        discovery_hits: List[DiscoveryHit] = []
        accepted_records: List[DownloadRecord] = []
        rejected_records: List[DownloadRecord] = []
        accepted_counts = {language: 0 for language in SUPPORTED_LANGUAGES}
        active_languages = self._active_languages()
        raw_limit = self._raw_search_limit()

        for task in tasks:
            language = task.spec.language
            if language not in active_languages:
                continue
            if accepted_counts[language] >= self.target_pdfs_by_language.get(language, 0):
                continue

            client = self.search_sources.get(task.source)
            if client is None:
                continue

            raw_candidates = client.search(task.spec, limit=raw_limit)[:raw_limit]
            stat_key = self._task_key(task)
            stats: Dict[str, object] = {
                "batch_id": task.batch_id,
                "batch_key": task.batch_key,
                "batch_rank": task.batch_rank,
                "priority_score": round(task.priority_score, 4),
                "pair_score": round(task.pair_score, 4),
                "batch_score": round(task.batch_score, 4),
                "query_limit": self.query_limit,
                "raw_result_limit": raw_limit,
                "source": task.source,
                "query": task.query_text,
                "language": language,
                "template_id": task.spec.template_id,
                "source_term": task.spec.source_term,
                "term_type": task.spec.term_type,
                "query_phrase": task.spec.query_phrase,
                "results": 0,
                "raw_results": len(raw_candidates),
                "search_gate_passed": 0,
                "search_gate_pass_total": 0,
                "search_gate_rejected": 0,
                "filter_passed": 0,
                "duplicates": 0,
                "skipped_seen": 0,
                "accepted": 0,
                "pdf_fetch_fail": 0,
                "pdf_validation_fail": 0,
                "metadata_rejected": 0,
            }
            query_log.append(stats)
            query_stats[stat_key] = stats

            batch_hits: List[DiscoveryHit] = []
            batch_candidates_by_key: Dict[str, CandidatePaper] = {}
            for result_rank, candidate in enumerate(raw_candidates, start=1):
                candidate.query = task.query_text
                candidate.source_term = task.spec.source_term
                candidate.template_id = task.spec.template_id
                candidate.query_phrase = task.spec.query_phrase
                candidate.workflow_language = language
                candidate.source_record_id = candidate.source_record_id or candidate.external_id
                candidate.batch_id = task.batch_id
                candidate.batch_key = task.batch_key
                candidate.batch_rank = task.batch_rank
                canonical_key = candidate.canonical_key
                if not canonical_key or canonical_key in skip_keys:
                    stats["skipped_seen"] = int(stats["skipped_seen"]) + 1
                    continue

                gate_pass, gate_score, reason_details = self._search_gate_decision(candidate)
                candidate.search_gate_pass = gate_pass
                candidate.search_gate_score = gate_score
                is_duplicate = canonical_key in candidates_by_key
                hit = DiscoveryHit(
                    canonical_key=canonical_key,
                    source=task.source,
                    source_record_id=candidate.source_record_id,
                    external_id=candidate.external_id,
                    pmcid=candidate.pmcid,
                    doi=candidate.doi,
                    title=candidate.title,
                    abstract=candidate.abstract,
                    workflow_language=language,
                    query=task.query_text,
                    template_id=task.spec.template_id,
                    source_term=task.spec.source_term,
                    term_type=task.spec.term_type,
                    query_phrase=task.spec.query_phrase,
                    search_gate_score=gate_score,
                    search_gate_pass=gate_pass,
                    is_duplicate=is_duplicate,
                    batch_id=task.batch_id,
                    batch_key=task.batch_key,
                    batch_rank=task.batch_rank,
                    result_rank=result_rank,
                )
                batch_hits.append(hit)
                discovery_hits.append(hit)

                if not gate_pass:
                    stats["search_gate_rejected"] = int(stats["search_gate_rejected"]) + 1
                    continue

                stats["search_gate_pass_total"] = int(stats["search_gate_pass_total"]) + 1
                candidate.reason_details = reason_details
                candidate.reasons = [reason["text"] for reason in reason_details]

                if is_duplicate:
                    stats["duplicates"] = int(stats["duplicates"]) + 1
                    existing_candidate = candidates_by_key[canonical_key]
                    existing_signature = self._candidate_merge_signature(existing_candidate)
                    existing_accepted = existing_candidate.accepted
                    self._merge_candidate(existing_candidate, candidate)
                    if not existing_accepted and existing_signature != self._candidate_merge_signature(existing_candidate):
                        batch_candidates_by_key[canonical_key] = existing_candidate
                    continue

                candidates_by_key[canonical_key] = candidate
                batch_candidates_by_key[canonical_key] = candidate
                stats["results"] = int(stats["results"]) + 1
                stats["search_gate_passed"] = int(stats["search_gate_passed"]) + 1
                if int(stats["results"]) >= self.query_limit:
                    break

            batch_candidates = list(batch_candidates_by_key.values())
            self._filter_candidates(batch_candidates, batch_hits, [stats], {stat_key: stats})
            remaining_by_language = {
                current_language: max(
                    0,
                    self.target_pdfs_by_language.get(current_language, 0)
                    - accepted_counts.get(current_language, 0),
                )
                for current_language in SUPPORTED_LANGUAGES
            }
            batch_accepted, batch_rejected = self._acquire_batch_candidates(
                batch_candidates,
                remaining_by_language=remaining_by_language,
            )
            accepted_records.extend(batch_accepted)
            rejected_records.extend(batch_rejected)
            self._update_batch_outcome_stats(stats, batch_accepted, batch_rejected)
            accepted_counts[language] += sum(1 for record in batch_accepted if record.workflow_language == language)

            if all(
                accepted_counts[current_language] >= self.target_pdfs_by_language.get(current_language, 0)
                for current_language in active_languages
            ):
                break

        return list(candidates_by_key.values()), discovery_hits, query_log, query_stats, accepted_records, rejected_records

    def _candidate_merge_signature(self, candidate: CandidatePaper) -> Tuple[object, ...]:
        return (
            candidate.title,
            candidate.abstract,
            candidate.pdf_url,
            candidate.landing_url,
            candidate.doi,
            candidate.pmcid,
            candidate.journal,
            candidate.year,
        )

    def _acquire_batch_candidates(
        self,
        candidates: List[CandidatePaper],
        remaining_by_language: Optional[Dict[str, int]] = None,
    ) -> Tuple[List[DownloadRecord], List[DownloadRecord]]:
        accepted_records: List[DownloadRecord] = []
        rejected_records: List[DownloadRecord] = []
        remaining_slots = {
            language: max(
                0,
                int(
                    (remaining_by_language or self.target_pdfs_by_language).get(
                        language,
                        0,
                    )
                ),
            )
            for language in SUPPORTED_LANGUAGES
        }
        ranked_candidates = sorted(
            candidates,
            key=lambda item: (item.filter_pass, item.filter_score, item.search_gate_score),
            reverse=True,
        )

        for candidate in ranked_candidates:
            candidate_language = (
                candidate.workflow_language if candidate.workflow_language in SUPPORTED_LANGUAGES else "en"
            )
            if (
                candidate.filter_pass
                and all(
                    remaining_slots.get(language, 0) <= 0
                    for language in self._active_languages()
                )
            ):
                break

            if not candidate.filter_pass:
                if candidate.pdf_url or candidate.pmcid:
                    audit_flag = self._next_audit_flag()
                    if audit_flag:
                        rejected_records.append(
                            self._download_candidate(
                                candidate,
                                force_audit=True,
                                skip_validation=True,
                                rejection_error="Rejected by metadata filter",
                                rejection_stage="metadata_filter",
                            )
                        )
                    else:
                        rejected_records.append(
                            self._skip_record(candidate, "Rejected by metadata filter", decision_stage="metadata_filter")
                        )
                else:
                    rejected_records.append(
                        self._skip_record(candidate, "Rejected by metadata filter", decision_stage="metadata_filter")
                    )
                continue

            if not candidate.pdf_url and not candidate.pmcid:
                candidate.reason_details = candidate.reason_details + [
                    {"code": "no_pdf_url", "text": "Rejected: no PDF URL available"}
                ]
                candidate.reasons = [reason["text"] for reason in candidate.reason_details]
                rejected_records.append(
                    self._skip_record(candidate, "Rejected: no PDF URL available", decision_stage="pdf_fetch")
                )
                continue

            if remaining_slots.get(candidate_language, 0) <= 0:
                continue

            record = self._download_candidate(candidate)
            if record.status == "success":
                accepted_records.append(record)
                remaining_slots[candidate_language] = max(
                    0,
                    remaining_slots.get(candidate_language, 0) - 1,
                )
            else:
                rejected_records.append(record)
        return accepted_records, rejected_records

    def _update_batch_outcome_stats(
        self,
        stats: Dict[str, object],
        accepted_records: List[DownloadRecord],
        rejected_records: List[DownloadRecord],
    ) -> None:
        stats["accepted"] = int(stats.get("accepted", 0)) + len(accepted_records)
        for record in rejected_records:
            if record.decision_stage == "metadata_filter":
                stats["metadata_rejected"] = int(stats.get("metadata_rejected", 0)) + 1
            elif record.decision_stage == "pdf_fetch":
                stats["pdf_fetch_fail"] = int(stats.get("pdf_fetch_fail", 0)) + 1
            elif record.decision_stage == "pdf_validation":
                stats["pdf_validation_fail"] = int(stats.get("pdf_validation_fail", 0)) + 1

    def _next_audit_flag(self) -> bool:
        self.audit_reject_counter += 1
        return self.audit_reject_counter % AUDIT_EVERY_N == 0

    def _resolve_target_pdfs_by_language(
        self,
        *,
        target_pdfs: int,
        target_pdfs_en: Optional[int],
        target_pdfs_tr: Optional[int],
    ) -> Dict[str, int]:
        if target_pdfs_en is not None or target_pdfs_tr is not None:
            return {
                "en": max(0, int(target_pdfs_en or 0)),
                "tr": max(0, int(target_pdfs_tr or 0)),
            }

        total = max(0, int(target_pdfs))
        return {"en": total, "tr": 0}

    def _raw_search_limit(self, query_limit: Optional[int] = None) -> int:
        batch_size = max(1, int(query_limit if query_limit is not None else self.query_limit))
        return min(
            MAX_RAW_SEARCH_LIMIT,
            max(batch_size, MIN_RAW_SEARCH_LIMIT, batch_size * RAW_SEARCH_RESULT_MULTIPLIER),
        )

    def _active_languages(self) -> List[str]:
        return [
            language
            for language in SUPPORTED_LANGUAGES
            if self.target_pdfs_by_language.get(language, 0) > 0
        ]

    def _build_search_tasks(self, *, run_id: Optional[str] = None) -> List[SearchTask]:
        active_languages = self._active_languages()
        if not active_languages:
            return []
        budgets = self._language_query_budget()
        per_language_specs = {
            language: self._build_queries_for_language(
                language,
                max(1, (budgets.get(language, 0) + max(1, len(self.search_sources)) - 1) // max(1, len(self.search_sources))),
            )
            for language in active_languages
        }
        per_language_tasks = {
            language: self._expand_search_tasks(language, per_language_specs.get(language, []), budgets.get(language, 0))
            for language in active_languages
        }
        tasks: List[SearchTask] = []
        max_len = max((len(items) for items in per_language_tasks.values()), default=0)
        for idx in range(max_len):
            for language in active_languages:
                items = per_language_tasks.get(language, [])
                if idx < len(items):
                    tasks.append(items[idx])
        return self._assign_batch_metadata(tasks[: self.max_queries], run_id=run_id or uuid4().hex)

    def _language_query_budget(self) -> Dict[str, int]:
        active_languages = self._active_languages()
        budgets = {language: 0 for language in SUPPORTED_LANGUAGES}
        if self.max_queries <= 0:
            return budgets
        if not active_languages:
            return budgets
        base_budget = self.max_queries // len(active_languages)
        for language in active_languages:
            budgets[language] = base_budget
        remainder = self.max_queries - sum(budgets.values())
        if remainder > 0:
            cursor = int(self.state.get("language_remainder_cursor", 0)) % len(active_languages)
            for offset in range(remainder):
                language = active_languages[(cursor + offset) % len(active_languages)]
                budgets[language] += 1
            self.state["language_remainder_cursor"] = (cursor + remainder) % len(active_languages)
        return budgets

    def _build_queries_for_language(self, language: str, budget: int) -> List[QuerySpec]:
        if budget <= 0:
            return []

        composition_frame = COMPOSITION_FRAMES[language]
        if language == "en":
            base_queries = [
                QuerySpec(
                    query=f'({composition_frame} AND ("table" OR "content" OR "analysis")) AND IN_PMC:y',
                    keywords=("food composition", "nutrient composition", "table", "analysis"),
                    template_id="base_core_composition",
                    source_term=None,
                    term_type="base",
                    language=language,
                    query_phrase="food composition",
                ),
                QuerySpec(
                    query='(("mineral content" OR "vitamin content" OR "fatty acid composition" OR '
                    f'"amino acid composition") AND {composition_frame}) AND IN_PMC:y',
                    keywords=("mineral content", "vitamin content", "fatty acid composition", "food composition"),
                    template_id="base_nutrient_content",
                    source_term=None,
                    term_type="base",
                    language=language,
                    query_phrase="mineral content",
                ),
            ]
        else:
            base_queries = [
                QuerySpec(
                    query=f'({composition_frame} AND ("tablo" OR "içerik" OR "analiz")) AND IN_PMC:y',
                    keywords=("gıda bileşimi", "besin bileşimi", "tablo", "analiz"),
                    template_id="base_core_composition",
                    source_term=None,
                    term_type="base",
                    language=language,
                    query_phrase="gıda bileşimi",
                ),
                QuerySpec(
                    query='(("mineral içeriği" OR "vitamin içeriği" OR "yağ asidi bileşimi" OR '
                    f'"amino asit bileşimi") AND {composition_frame}) AND IN_PMC:y',
                    keywords=("mineral içeriği", "vitamin içeriği", "yağ asidi bileşimi", "gıda bileşimi"),
                    template_id="base_nutrient_content",
                    source_term=None,
                    term_type="base",
                    language=language,
                    query_phrase="mineral içeriği",
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
        concept_scores = self.concept_scores_by_language.get(language, {})

        def sort_terms(terms: List[str]) -> List[str]:
            enumerated = list(enumerate(terms))
            enumerated.sort(
                key=lambda item: (
                    concept_scores.get(self._normalize_for_match(item[1]), 0.0),
                    -item[0],
                ),
                reverse=True,
            )
            return [term for _, term in enumerated]

        food_terms = sort_terms(self.food_terms_by_language.get(language, []))
        nutrient_terms = sort_terms(self.nutrient_terms_by_language.get(language, []))
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
            keywords=(
                safe_concept,
                safe_phrase,
                "food composition" if language == "en" else "gıda bileşimi",
                "mg/100g",
                "g/100g",
            ),
            template_id=template_id,
            source_term=concept_term,
            term_type=concept_type,
            language=language,
            query_phrase=phrase,
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

    def _expand_search_tasks(self, language: str, specs: List[QuerySpec], budget: int) -> List[SearchTask]:
        if budget <= 0 or not specs:
            return []
        expanded: List[SearchTask] = []
        source_names = list(self.search_sources.keys())
        for spec in specs:
            source_tasks = [
                SearchTask(
                    source=source,
                    spec=spec,
                    query_text=self._source_query_text(source, spec),
                    pair_score=self._pair_score(language, source, spec),
                    batch_score=self._batch_score(language, source, spec),
                    priority_score=(
                        self._pair_score(language, source, spec)
                        + self._batch_score(language, source, spec)
                    ),
                )
                for source in source_names
            ]
            source_tasks.sort(key=lambda item: item.priority_score, reverse=True)
            expanded.extend(source_tasks)
        return expanded[:budget]

    def _assign_batch_metadata(self, tasks: List[SearchTask], *, run_id: str) -> List[SearchTask]:
        assigned: List[SearchTask] = []
        for index, task in enumerate(tasks):
            batch_rank = index + 1
            batch_key = build_search_batch_key(
                source=task.source,
                workflow_language=task.spec.language,
                template_id=task.spec.template_id,
                source_term=task.spec.source_term,
                query_phrase=task.spec.query_phrase,
                query_text=task.query_text,
            )
            batch_id = f"{run_id}:{batch_rank:04d}"
            assigned.append(
                SearchTask(
                    source=task.source,
                    spec=task.spec,
                    query_text=task.query_text,
                    pair_score=task.pair_score,
                    batch_score=task.batch_score,
                    priority_score=task.priority_score,
                    batch_id=batch_id,
                    batch_key=batch_key,
                    batch_rank=batch_rank,
                )
            )
        return assigned

    def _source_query_text(self, source: str, spec: QuerySpec) -> str:
        client = self.search_sources.get(source)
        if client is None:
            return spec.query
        query_text_fn = getattr(client, "query_text", None)
        if callable(query_text_fn):
            return str(query_text_fn(spec) or spec.query)
        return spec.query

    def _pair_score(self, language: str, source: str, spec: QuerySpec) -> float:
        normalized_term = self._normalize_for_match(spec.source_term or "")
        key = f"{source}|{spec.template_id}|{normalized_term}"
        pair_score = float(self.pair_scores_by_language.get(language, {}).get(key, 0.0))
        source_prior = float(self.source_priors_by_language.get(language, {}).get(source, 0.0))
        static_bias = float(DEFAULT_SOURCE_BIAS_BY_LANGUAGE.get(language, {}).get(source, 0.0))
        return pair_score + 0.15 * source_prior + static_bias

    def _batch_score(self, language: str, source: str, spec: QuerySpec) -> float:
        key = build_search_batch_key(
            source=source,
            workflow_language=language,
            template_id=spec.template_id,
            source_term=spec.source_term,
            query_phrase=spec.query_phrase,
            query_text=self._source_query_text(source, spec),
        )
        return float(self.batch_scores_by_language.get(language, {}).get(key, 0.0))

    def _search_candidates(
        self,
        tasks: List[SearchTask],
        skip_keys: Set[str],
    ) -> Tuple[List[CandidatePaper], List[DiscoveryHit], List[Dict[str, object]], Dict[str, Dict[str, int]]]:
        query_log: List[Dict[str, object]] = []
        query_stats: Dict[str, Dict[str, int]] = {}
        candidates_by_key: Dict[str, CandidatePaper] = {}
        discovery_hits: List[DiscoveryHit] = []

        for task in tasks:
            client = self.search_sources.get(task.source)
            if client is None:
                continue
            spec = task.spec
            raw_candidates = client.search(spec, limit=self.query_limit)[: self.query_limit]
            stat_key = self._task_key(task)
            stats = {
                "batch_id": task.batch_id,
                "batch_key": task.batch_key,
                "batch_rank": task.batch_rank,
                "priority_score": round(task.priority_score, 4),
                "pair_score": round(task.pair_score, 4),
                "batch_score": round(task.batch_score, 4),
                "query_limit": self.query_limit,
                "source": task.source,
                "query": task.query_text,
                "language": spec.language,
                "template_id": spec.template_id,
                "source_term": spec.source_term,
                "term_type": spec.term_type,
                "query_phrase": spec.query_phrase,
                "results": len(raw_candidates),
                "search_gate_passed": 0,
                "search_gate_rejected": 0,
                "filter_passed": 0,
                "rejected": 0,
                "duplicates": 0,
                "skipped_seen": 0,
            }
            query_log.append(stats)
            query_stats[stat_key] = dict(stats)

            for candidate in raw_candidates:
                candidate.query = task.query_text
                candidate.source_term = spec.source_term
                candidate.template_id = spec.template_id
                candidate.query_phrase = spec.query_phrase
                candidate.workflow_language = spec.language
                candidate.source_record_id = candidate.source_record_id or candidate.external_id
                candidate.batch_id = task.batch_id
                candidate.batch_key = task.batch_key
                candidate.batch_rank = task.batch_rank
                canonical_key = candidate.canonical_key
                if not canonical_key or canonical_key in skip_keys:
                    stats["skipped_seen"] += 1
                    query_stats[stat_key]["skipped_seen"] += 1
                    continue

                gate_pass, gate_score, reason_details = self._search_gate_decision(candidate)
                candidate.search_gate_pass = gate_pass
                candidate.search_gate_score = gate_score
                hit = DiscoveryHit(
                    canonical_key=canonical_key,
                    source=task.source,
                    source_record_id=candidate.source_record_id,
                    external_id=candidate.external_id,
                    pmcid=candidate.pmcid,
                    doi=candidate.doi,
                    title=candidate.title,
                    abstract=candidate.abstract,
                    workflow_language=spec.language,
                    query=task.query_text,
                    template_id=spec.template_id,
                    source_term=spec.source_term,
                    term_type=spec.term_type,
                    query_phrase=spec.query_phrase,
                    search_gate_score=gate_score,
                    search_gate_pass=gate_pass,
                    is_duplicate=canonical_key in candidates_by_key,
                    batch_id=task.batch_id,
                    batch_key=task.batch_key,
                    batch_rank=task.batch_rank,
                )
                discovery_hits.append(hit)

                if not gate_pass:
                    stats["search_gate_rejected"] += 1
                    query_stats[stat_key]["search_gate_rejected"] += 1
                    continue

                stats["search_gate_passed"] += 1
                query_stats[stat_key]["search_gate_passed"] += 1
                candidate.reason_details = reason_details
                candidate.reasons = [reason["text"] for reason in reason_details]

                if canonical_key in candidates_by_key:
                    stats["duplicates"] += 1
                    query_stats[stat_key]["duplicates"] += 1
                    self._merge_candidate(candidates_by_key[canonical_key], candidate)
                    continue

                candidates_by_key[canonical_key] = candidate

        ordered_candidates = list(candidates_by_key.values())
        return ordered_candidates, discovery_hits, query_log, query_stats

    def _filter_candidates(
        self,
        candidates: List[CandidatePaper],
        discovery_hits: List[DiscoveryHit],
        query_log: List[Dict[str, object]],
        query_stats: Dict[str, Dict[str, int]],
    ) -> None:
        hits_by_key: Dict[str, List[DiscoveryHit]] = {}
        for hit in discovery_hits:
            hits_by_key.setdefault(hit.canonical_key, []).append(hit)

        log_index = {
            self._stat_hit_key(
                hit_source=entry["source"],
                query=entry["query"],
                template_id=entry["template_id"],
                source_term=entry["source_term"],
            ): entry
            for entry in query_log
        }
        for candidate in candidates:
            accepted, score, reason_details = self._metadata_decision(candidate)
            candidate.filter_pass = accepted
            candidate.accepted = accepted
            candidate.filter_score = score
            candidate.score = score
            candidate.reason_details = reason_details
            candidate.reasons = [reason["text"] for reason in reason_details]
            for hit in hits_by_key.get(candidate.canonical_key, []):
                hit.filter_score = score
                hit.filter_pass = accepted
                stat_key = self._stat_hit_key(
                    hit_source=hit.source,
                    query=hit.query,
                    template_id=hit.template_id,
                    source_term=hit.source_term,
                )
                if accepted:
                    if stat_key in log_index:
                        log_index[stat_key]["filter_passed"] += 1
                    if stat_key in query_stats:
                        query_stats[stat_key]["filter_passed"] += 1

    def _acquire_candidates(
        self,
        candidates: List[CandidatePaper],
    ) -> Tuple[List[DownloadRecord], List[DownloadRecord]]:
        accepted_records: List[DownloadRecord] = []
        rejected_records: List[DownloadRecord] = []
        accepted_counts = {language: 0 for language in SUPPORTED_LANGUAGES}
        ranked_candidates = sorted(
            candidates,
            key=lambda item: (item.filter_pass, item.filter_score, item.search_gate_score),
            reverse=True,
        )

        for candidate in ranked_candidates:
            candidate_language = (
                candidate.workflow_language if candidate.workflow_language in SUPPORTED_LANGUAGES else "en"
            )
            if (
                candidate.filter_pass
                and all(
                    accepted_counts[language] >= self.target_pdfs_by_language.get(language, 0)
                    for language in self._active_languages()
                )
            ):
                break

            if not candidate.filter_pass:
                if candidate.pdf_url or candidate.pmcid:
                    audit_flag = self._next_audit_flag()
                    if audit_flag:
                        rejected_records.append(
                            self._download_candidate(
                                candidate,
                                force_audit=True,
                                skip_validation=True,
                                rejection_error="Rejected by metadata filter",
                                rejection_stage="metadata_filter",
                            )
                        )
                    else:
                        rejected_records.append(
                            self._skip_record(candidate, "Rejected by metadata filter", decision_stage="metadata_filter")
                        )
                else:
                    rejected_records.append(
                        self._skip_record(candidate, "Rejected by metadata filter", decision_stage="metadata_filter")
                    )
                continue

            if not candidate.pdf_url and not candidate.pmcid:
                candidate.reason_details = candidate.reason_details + [
                    {"code": "no_pdf_url", "text": "Rejected: no PDF URL available"}
                ]
                candidate.reasons = [reason["text"] for reason in candidate.reason_details]
                rejected_records.append(
                    self._skip_record(candidate, "Rejected: no PDF URL available", decision_stage="pdf_fetch")
                )
                continue

            if accepted_counts[candidate_language] >= self.target_pdfs_by_language.get(candidate_language, 0):
                continue

            record = self._download_candidate(candidate)
            if record.status == "success":
                accepted_records.append(record)
                accepted_counts[candidate_language] += 1
            else:
                rejected_records.append(record)
        return accepted_records, rejected_records

    def _write_candidate_artifacts(
        self,
        harvested_at: str,
        candidates: List[CandidatePaper],
        discovery_hits: List[DiscoveryHit],
    ) -> None:
        candidate_payload = {
            "harvested_at": harvested_at,
            "candidate_count": len(candidates),
            "candidates": [candidate.to_dict() for candidate in candidates],
        }
        hit_payload = {
            "harvested_at": harvested_at,
            "hit_count": len(discovery_hits),
            "hits": [hit.to_dict() for hit in discovery_hits],
        }
        self._write_json(self.candidate_store_path, candidate_payload)
        self._write_json(self.search_hits_path, hit_payload)

    def _empty_summary_bucket(self) -> Dict[str, int]:
        return {
            "hits": 0,
            "search_gate_pass": 0,
            "metadata_pass": 0,
            "pdf_fetch_fail": 0,
            "pdf_validation_fail": 0,
            "accepted": 0,
        }

    def _bump_summary_metric(
        self,
        container: Dict[str, Dict[str, int]],
        key: str,
        metric: str,
    ) -> None:
        if key not in container:
            container[key] = self._empty_summary_bucket()
        container[key][metric] += 1

    def _build_run_summary(
        self,
        candidates: List[CandidatePaper],
        discovery_hits: List[DiscoveryHit],
        accepted_records: List[DownloadRecord],
        rejected_records: List[DownloadRecord],
    ) -> Dict[str, object]:
        languages = {
            language: self._empty_summary_bucket()
            for language in SUPPORTED_LANGUAGES
        }
        sources = {
            source: self._empty_summary_bucket()
            for source in self.search_sources.keys()
        }
        rejections = {
            "search_gate": 0,
            "metadata_filter": 0,
            "pdf_fetch": 0,
            "pdf_validation": 0,
        }

        for hit in discovery_hits:
            if hit.workflow_language in SUPPORTED_LANGUAGES:
                self._bump_summary_metric(languages, hit.workflow_language, "hits")
            self._bump_summary_metric(sources, hit.source, "hits")
            if hit.search_gate_pass:
                if hit.workflow_language in SUPPORTED_LANGUAGES:
                    self._bump_summary_metric(languages, hit.workflow_language, "search_gate_pass")
                self._bump_summary_metric(sources, hit.source, "search_gate_pass")
            else:
                rejections["search_gate"] += 1

        for candidate in candidates:
            if not candidate.filter_pass:
                continue
            if candidate.workflow_language in SUPPORTED_LANGUAGES:
                self._bump_summary_metric(languages, candidate.workflow_language, "metadata_pass")
            self._bump_summary_metric(sources, candidate.source, "metadata_pass")

        for record in accepted_records:
            if record.workflow_language in SUPPORTED_LANGUAGES:
                self._bump_summary_metric(languages, record.workflow_language, "accepted")
            self._bump_summary_metric(sources, record.source, "accepted")

        for record in rejected_records:
            stage = record.decision_stage or ""
            if stage in rejections:
                rejections[stage] += 1
            if stage == "pdf_fetch":
                if record.workflow_language in SUPPORTED_LANGUAGES:
                    self._bump_summary_metric(languages, record.workflow_language, "pdf_fetch_fail")
                self._bump_summary_metric(sources, record.source, "pdf_fetch_fail")
            elif stage == "pdf_validation":
                if record.workflow_language in SUPPORTED_LANGUAGES:
                    self._bump_summary_metric(languages, record.workflow_language, "pdf_validation_fail")
                self._bump_summary_metric(sources, record.source, "pdf_validation_fail")

        return {
            "languages": languages,
            "sources": dict(sorted(sources.items())),
            "rejections": {stage: count for stage, count in rejections.items() if count > 0},
        }

    def _task_key(self, task: SearchTask) -> str:
        if task.batch_id:
            return task.batch_id
        return self._stat_hit_key(
            hit_source=task.source,
            query=task.query_text,
            template_id=task.spec.template_id,
            source_term=task.spec.source_term,
        )

    def _stat_hit_key(
        self,
        *,
        hit_source: str,
        query: str,
        template_id: str,
        source_term: Optional[str],
    ) -> str:
        normalized_term = self._normalize_for_match(source_term or "")
        return f"{hit_source}:{template_id}:{normalized_term}:{query}"

    def _merge_candidate(self, target: CandidatePaper, incoming: CandidatePaper) -> None:
        if not target.abstract and incoming.abstract:
            target.abstract = incoming.abstract
        if not target.pdf_url and incoming.pdf_url:
            target.pdf_url = incoming.pdf_url
        if not target.landing_url and incoming.landing_url:
            target.landing_url = incoming.landing_url
        if not target.doi and incoming.doi:
            target.doi = incoming.doi
        if not target.pmcid and incoming.pmcid:
            target.pmcid = incoming.pmcid

    def _normalize_seen_key(self, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if text.startswith("pmcid:") or text.startswith("doi:") or text.startswith("title:") or text.startswith("source:"):
            return text.lower()
        if text.upper().startswith("PMC"):
            return f"pmcid:{text.lower()}"
        if text.startswith("10."):
            return f"doi:{text.lower()}"
        return text.lower()

    def _normalize_paper_states(self, payload: object) -> Dict[str, Dict[str, str]]:
        if not isinstance(payload, dict):
            return {}
        normalized: Dict[str, Dict[str, str]] = {}
        for raw_key, raw_value in payload.items():
            key = self._normalize_seen_key(raw_key)
            if not key or not isinstance(raw_value, dict):
                continue
            decision = str(raw_value.get("decision") or "").strip().lower()
            stage = str(raw_value.get("stage") or "").strip().lower()
            if decision not in TERMINAL_DECISIONS or stage not in TERMINAL_DECISION_STAGES:
                continue
            normalized[key] = {"decision": decision, "stage": stage}
        return dict(sorted(normalized.items()))

    def _paper_states(self) -> Dict[str, Dict[str, str]]:
        payload = self.state.get("paper_states")
        if not isinstance(payload, dict):
            payload = {}
            self.state["paper_states"] = payload
        return payload

    def _state_skip_keys(self) -> Set[str]:
        return set(self._paper_states().keys())

    def _live_paper_skip_keys(self) -> Set[str]:
        keys: Set[str] = set()
        offset = 0
        batch_size = 1000
        while True:
            rows = self._fetch_supabase_rows(
                "papers",
                "canonical_key",
                filters={"canonical_key": "not.is.null"},
                offset=offset,
                limit=batch_size,
            )
            for row in rows:
                normalized_key = self._normalize_seen_key(row.get("canonical_key"))
                if normalized_key:
                    keys.add(normalized_key)
            if len(rows) < batch_size:
                return keys
            offset += batch_size

    def _fetch_supabase_rows(
        self,
        table_name: str,
        select: str,
        *,
        filters: Optional[Dict[str, str]] = None,
        offset: int = 0,
        limit: int = 1000,
    ) -> List[dict]:
        endpoint = self.supabase_url.rstrip("/") + f"/rest/v1/{table_name}"
        params = {
            "select": select,
            "limit": str(max(1, int(limit))),
            "offset": str(max(0, int(offset))),
        }
        if filters:
            params.update(filters)
        request = Request(
            f"{endpoint}?{urlencode(params)}",
            headers={
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected Supabase payload for {table_name}: {payload}")
        return [row for row in payload if isinstance(row, dict)]

    def _record_terminal_state(self, canonical_key: Optional[str], *, decision: str, stage: str) -> None:
        normalized_key = self._normalize_seen_key(canonical_key)
        if not normalized_key or decision not in TERMINAL_DECISIONS or stage not in TERMINAL_DECISION_STAGES:
            return
        self._paper_states()[normalized_key] = {"decision": decision, "stage": stage}

    def _record_terminal_states(
        self,
        candidates: List[CandidatePaper],
        discovery_hits: List[DiscoveryHit],
        accepted_records: List[DownloadRecord],
        rejected_records: List[DownloadRecord],
    ) -> None:
        for record in accepted_records + rejected_records:
            if not record.decision_stage:
                continue
            decision = "accepted" if record.status == "success" else "rejected"
            self._record_terminal_state(record.canonical_key, decision=decision, stage=record.decision_stage)

        candidate_keys = {
            self._normalize_seen_key(candidate.canonical_key)
            for candidate in candidates
            if self._normalize_seen_key(candidate.canonical_key)
        }
        for hit in discovery_hits:
            normalized_key = self._normalize_seen_key(hit.canonical_key)
            if not normalized_key or hit.search_gate_pass or normalized_key in candidate_keys:
                continue
            self._record_terminal_state(normalized_key, decision="rejected", stage="search_gate")

    def _search_gate_decision(self, candidate: CandidatePaper) -> Tuple[bool, float, List[Dict[str, str]]]:
        details: List[Dict[str, str]] = []
        workflow_language = candidate.workflow_language if candidate.workflow_language in SUPPORTED_LANGUAGES else "en"
        title_text = " ".join((candidate.title or "").split())
        abstract_text = " ".join((candidate.abstract or "").split())
        raw_text = " ".join(part for part in (title_text, abstract_text) if part).strip()
        if not raw_text:
            self._append_reason(details, "missing_metadata", "Rejected by search gate: missing title/abstract")
            return False, -2.0, details

        normalized = self._normalize_for_match(raw_text.lower())
        score = 0.0
        anchor_phrases = self.anchor_phrases_by_language.get(workflow_language, [])
        food_terms = self.food_terms_by_language.get(workflow_language, [])
        nutrient_terms = self.nutrient_terms_by_language.get(workflow_language, [])
        health_terms = HEALTH_OUTCOME_TERMS_BY_LANGUAGE.get(workflow_language, [])

        composition_hit = self._first_term_hit(normalized, anchor_phrases)
        if composition_hit:
            score += 0.9
            self._append_reason(details, "composition_phrase", f"Search gate: composition phrase '{composition_hit}'")

        food_hit = self._first_term_hit(normalized, food_terms)
        if food_hit:
            score += 0.35
            self._append_reason(details, "food_term_hit", f"Search gate: food term '{food_hit}'")

        nutrient_hit = self._first_term_hit(normalized, nutrient_terms)
        if nutrient_hit:
            score += 0.35
            self._append_reason(details, "nutrient_term_hit", f"Search gate: nutrient term '{nutrient_hit}'")

        unit_hit = bool(UNIT_PATTERN.search(raw_text))
        if unit_hit:
            score += 0.7
            self._append_reason(details, "unit_signal", "Search gate: nutrient unit pattern")

        if food_hit and nutrient_hit:
            score += 0.45
            self._append_reason(details, "food_nutrient_combo", "Search gate: matched both food and nutrient terms")

        if not abstract_text:
            penalty = 1.3 if not (food_hit or nutrient_hit or unit_hit) else 0.45
            score -= penalty
            self._append_reason(
                details,
                "missing_abstract_penalty",
                f"Search gate penalty {penalty:.2f}: missing abstract",
            )

        strong_negative_hits = self._collect_term_hits(normalized, STRONG_NEGATIVE_SIGNAL_TERMS)
        if strong_negative_hits:
            penalty = min(2.5, 0.95 * len(strong_negative_hits))
            score -= penalty
            self._append_reason(
                details,
                "negative_signal",
                f"Search gate penalty {penalty:.2f}: negative signals {', '.join(strong_negative_hits[:4])}",
            )

        soft_negative_hits = self._collect_term_hits(normalized, SOFT_NEGATIVE_TERMS)
        if soft_negative_hits:
            penalty = min(1.5, 0.45 * len(soft_negative_hits))
            score -= penalty
            self._append_reason(
                details,
                "soft_negative",
                f"Search gate penalty {penalty:.2f}: soft negatives {', '.join(soft_negative_hits[:4])}",
            )

        health_hits = self._collect_term_hits(normalized, health_terms)
        if health_hits:
            penalty = min(1.6, 0.35 * len(health_hits))
            score -= penalty
            self._append_reason(
                details,
                "health_penalty",
                f"Search gate penalty {penalty:.2f}: health terms {', '.join(health_hits[:4])}",
            )

        accepted = score >= SEARCH_GATE_REJECT_THRESHOLD
        self._append_reason(
            details,
            "search_gate_pass" if accepted else "search_gate_reject",
            f"{'Passed' if accepted else 'Rejected'} search gate with score {score:.2f}",
        )
        return accepted, score, details

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

        if not abstract_text:
            penalty = 1.1 if not (food_hit or nutrient_hit or unit_hit) else 0.35
            score -= penalty
            self._append_reason(details, "missing_abstract_penalty", f"Penalty {penalty:.2f}: missing abstract")

        health_hits = self._collect_term_hits(normalized, health_terms)
        if health_hits:
            penalty = min(MAX_HEALTH_PENALTY, 0.55 * len(health_hits))
            score -= penalty
            self._append_reason(
                details,
                "health_penalty",
                f"Penalty {penalty:.2f}: health-outcome terms {', '.join(health_hits[:4])}",
            )

        source_prior = float(self.source_priors_by_language.get(workflow_language, {}).get(candidate.source, 0.0))
        if source_prior:
            source_prior = max(-MAX_SOURCE_PRIOR_ABS, min(MAX_SOURCE_PRIOR_ABS, source_prior))
            score += source_prior
            self._append_reason(details, "source_prior", f"Source prior {source_prior:+.2f} from '{candidate.source}'")

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
        rejection_stage: Optional[str] = None,
    ) -> DownloadRecord:
        if not candidate.pdf_url and not candidate.pmcid:
            return self._failed_record(candidate, "No PDF URL available", audit=force_audit, decision_stage="pdf_fetch")

        try:
            content, source_url = self._fetch_pdf_with_oa(candidate)
            candidate.pdf_url = source_url
        except Exception as exc:
            return self._failed_record(candidate, str(exc), audit=force_audit, decision_stage="pdf_fetch")

        max_pdf_bytes = max_paper_pdf_bytes()
        if len(content) > max_pdf_bytes:
            reason = pdf_size_limit_message(len(content), limit_bytes=max_pdf_bytes)
            self._append_reason(candidate.reason_details, "pdf_too_large", reason)
            candidate.reasons = [detail["text"] for detail in candidate.reason_details]
            return self._failed_record(candidate, reason, audit=force_audit, decision_stage="pdf_fetch")

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
                source_record_id=candidate.source_record_id,
                canonical_key=candidate.canonical_key,
                pmcid=candidate.pmcid,
                doi=candidate.doi,
                journal=candidate.journal,
                year=candidate.year,
                size_kb=max(1, round(len(content) / 1024)),
                pdf_url=candidate.pdf_url,
                error=rejection_error,
                source_term=candidate.source_term,
                template_id=candidate.template_id,
                query_phrase=candidate.query_phrase,
                workflow_language=candidate.workflow_language,
                search_gate_score=candidate.search_gate_score,
                filter_score=candidate.filter_score,
                search_gate_pass=candidate.search_gate_pass,
                filter_pass=candidate.filter_pass,
                decision_stage=rejection_stage,
                batch_id=candidate.batch_id,
                batch_key=candidate.batch_key,
                batch_rank=candidate.batch_rank,
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
                return self._failed_record(
                    candidate,
                    "Rejected by PDF validation",
                    decision_stage="pdf_validation",
                )
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
                source_record_id=candidate.source_record_id,
                canonical_key=candidate.canonical_key,
                pmcid=candidate.pmcid,
                doi=candidate.doi,
                journal=candidate.journal,
                year=candidate.year,
                size_kb=max(1, round(len(content) / 1024)),
                pdf_url=candidate.pdf_url,
                error="Rejected by PDF validation",
                source_term=candidate.source_term,
                template_id=candidate.template_id,
                query_phrase=candidate.query_phrase,
                workflow_language=candidate.workflow_language,
                search_gate_score=candidate.search_gate_score,
                filter_score=candidate.filter_score,
                search_gate_pass=candidate.search_gate_pass,
                    filter_pass=candidate.filter_pass,
                    decision_stage="pdf_validation",
                    batch_id=candidate.batch_id,
                    batch_key=candidate.batch_key,
                    batch_rank=candidate.batch_rank,
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
            source_record_id=candidate.source_record_id,
            canonical_key=candidate.canonical_key,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            size_kb=max(1, round(len(content) / 1024)),
            pdf_url=candidate.pdf_url,
            source_term=candidate.source_term,
            template_id=candidate.template_id,
            query_phrase=candidate.query_phrase,
            workflow_language=candidate.workflow_language,
            search_gate_score=candidate.search_gate_score,
            filter_score=candidate.filter_score,
            search_gate_pass=candidate.search_gate_pass,
            filter_pass=candidate.filter_pass,
            decision_stage="acquisition",
            batch_id=candidate.batch_id,
            batch_key=candidate.batch_key,
            batch_rank=candidate.batch_rank,
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
        return build_storage_filename(
            canonical_key=candidate.canonical_key,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
        )

    def _skip_record(
        self,
        candidate: CandidatePaper,
        error: str,
        audit: bool = False,
        decision_stage: Optional[str] = None,
    ) -> DownloadRecord:
        return DownloadRecord(
            status="skipped",
            title=candidate.title,
            score=candidate.score,
            source=candidate.source,
            query=candidate.query,
            reasons=candidate.reasons,
            reason_details=candidate.reason_details,
            audit=audit,
            source_record_id=candidate.source_record_id,
            canonical_key=candidate.canonical_key,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            pdf_url=candidate.pdf_url,
            error=error,
            source_term=candidate.source_term,
            template_id=candidate.template_id,
            query_phrase=candidate.query_phrase,
            workflow_language=candidate.workflow_language,
            search_gate_score=candidate.search_gate_score,
            filter_score=candidate.filter_score,
            search_gate_pass=candidate.search_gate_pass,
            filter_pass=candidate.filter_pass,
            decision_stage=decision_stage,
            batch_id=candidate.batch_id,
            batch_key=candidate.batch_key,
            batch_rank=candidate.batch_rank,
        )

    def _failed_record(
        self,
        candidate: CandidatePaper,
        error: str,
        audit: bool = False,
        decision_stage: Optional[str] = None,
    ) -> DownloadRecord:
        return DownloadRecord(
            status="failed",
            title=candidate.title,
            score=candidate.score,
            source=candidate.source,
            query=candidate.query,
            reasons=candidate.reasons,
            reason_details=candidate.reason_details,
            audit=audit,
            source_record_id=candidate.source_record_id,
            canonical_key=candidate.canonical_key,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            pdf_url=candidate.pdf_url,
            error=error,
            source_term=candidate.source_term,
            template_id=candidate.template_id,
            query_phrase=candidate.query_phrase,
            workflow_language=candidate.workflow_language,
            search_gate_score=candidate.search_gate_score,
            filter_score=candidate.filter_score,
            search_gate_pass=candidate.search_gate_pass,
            filter_pass=candidate.filter_pass,
            decision_stage=decision_stage,
            batch_id=candidate.batch_id,
            batch_key=candidate.batch_key,
            batch_rank=candidate.batch_rank,
        )

    def _default_state(self) -> Dict[str, object]:
        state = {
            "seen_ids": [],
            "paper_states": {},
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
        state["paper_states"] = self._normalize_paper_states(state.get("paper_states"))
        return state

    def _save_state(self) -> None:
        self.state["paper_states"] = self._normalize_paper_states(self.state.get("paper_states"))
        self._write_json(self.state_path, self.state)

    def _write_json(self, path: Path, payload: Dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
