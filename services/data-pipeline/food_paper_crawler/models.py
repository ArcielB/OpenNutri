from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def _normalize_space(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize_identity_text(value: object) -> str:
    text = _normalize_space(value).lower()
    return re.sub(r"[\W_]+", " ", text, flags=re.UNICODE).strip()


def _normalize_free_text(value: object) -> str:
    return _normalize_space(value).lower()


def build_canonical_key(
    *,
    pmcid: Optional[str],
    doi: Optional[str],
    title: str,
    year: Optional[str],
    journal: Optional[str],
    source: str,
    source_record_id: Optional[str],
    external_id: str,
) -> str:
    normalized_pmcid = re.sub(r"[^a-z0-9]+", "", _normalize_free_text(pmcid))
    if normalized_pmcid:
        if not normalized_pmcid.startswith("pmc"):
            normalized_pmcid = f"pmc{normalized_pmcid}"
        return f"pmcid:{normalized_pmcid}"

    normalized_doi = _normalize_free_text(doi)
    if normalized_doi:
        return f"doi:{normalized_doi}"

    normalized_title = _normalize_identity_text(title)
    if normalized_title:
        parts = [normalized_title]
        normalized_year = re.sub(r"[^0-9]+", "", _normalize_space(year))[:4]
        normalized_journal = _normalize_identity_text(journal)
        if normalized_year:
            parts.append(normalized_year)
        if normalized_journal:
            parts.append(normalized_journal)
        else:
            source_key = _normalize_free_text(source)
            record_key = _normalize_free_text(source_record_id or external_id)
            if source_key or record_key:
                parts.append(f"{source_key}:{record_key}")
        digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:24]
        return f"title:{digest}"

    normalized_source = _normalize_free_text(source) or "unknown"
    normalized_record = _normalize_free_text(source_record_id or external_id) or "unknown"
    return f"source:{normalized_source}:{normalized_record}"


def build_storage_filename(
    *,
    canonical_key: str,
    pmcid: Optional[str],
    doi: Optional[str],
) -> str:
    normalized_pmcid = re.sub(r"[^a-z0-9]+", "", _normalize_free_text(pmcid))
    if normalized_pmcid:
        if not normalized_pmcid.startswith("pmc"):
            normalized_pmcid = f"pmc{normalized_pmcid}"
        return f"pmcid_{normalized_pmcid}.pdf"

    normalized_doi = _normalize_free_text(doi)
    if normalized_doi:
        digest = hashlib.sha1(normalized_doi.encode("utf-8")).hexdigest()[:24]
        return f"doi_{digest}.pdf"

    digest = hashlib.sha1(_normalize_free_text(canonical_key).encode("utf-8")).hexdigest()[:24]
    return f"paper_{digest}.pdf"


def build_search_hit_key(
    *,
    canonical_key: object,
    source: object,
    workflow_language: object,
    template_id: object,
    source_term: object = None,
    query_phrase: object = None,
    query_text: object = None,
) -> str:
    parts = (
        _normalize_free_text(canonical_key),
        _normalize_free_text(source),
        _normalize_free_text(workflow_language),
        _normalize_free_text(template_id),
        _normalize_free_text(source_term),
        _normalize_free_text(query_phrase),
        _normalize_free_text(query_text),
    )
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()


@dataclass
class CandidatePaper:
    source: str
    query: str
    external_id: str
    source_record_id: Optional[str]
    pmcid: Optional[str]
    doi: Optional[str]
    title: str
    abstract: str
    journal: Optional[str]
    year: Optional[str]
    authors: List[str] = field(default_factory=list)
    pdf_url: Optional[str] = None
    landing_url: Optional[str] = None
    score: float = 0.0
    search_gate_score: float = 0.0
    filter_score: float = 0.0
    accepted: bool = False
    search_gate_pass: bool = False
    filter_pass: bool = False
    reasons: List[str] = field(default_factory=list)
    reason_details: List[Dict[str, str]] = field(default_factory=list)
    source_term: Optional[str] = None
    template_id: Optional[str] = None
    query_phrase: Optional[str] = None
    workflow_language: str = "en"

    @property
    def canonical_id(self) -> str:
        if self.pmcid:
            return self.pmcid
        if self.doi:
            return self.doi.lower()
        return self.external_id

    @property
    def canonical_key(self) -> str:
        return build_canonical_key(
            pmcid=self.pmcid,
            doi=self.doi,
            title=self.title,
            year=self.year,
            journal=self.journal,
            source=self.source,
            source_record_id=self.source_record_id,
            external_id=self.external_id,
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "source": self.source,
            "query": self.query,
            "external_id": self.external_id,
            "source_record_id": self.source_record_id,
            "canonical_key": self.canonical_key,
            "pmcid": self.pmcid,
            "doi": self.doi,
            "title": self.title,
            "abstract": self.abstract,
            "journal": self.journal,
            "year": self.year,
            "authors": self.authors,
            "pdf_url": self.pdf_url,
            "landing_url": self.landing_url,
            "score": round(self.score, 2),
            "search_gate_score": round(self.search_gate_score, 2),
            "filter_score": round(self.filter_score, 2),
            "accepted": self.accepted,
            "search_gate_pass": self.search_gate_pass,
            "filter_pass": self.filter_pass,
            "reasons": self.reasons,
            "reason_details": self.reason_details,
            "source_term": self.source_term,
            "template_id": self.template_id,
            "query_phrase": self.query_phrase,
            "workflow_language": self.workflow_language,
        }


@dataclass
class DownloadRecord:
    status: str
    title: str
    score: float
    source: str
    query: str
    reasons: List[str]
    audit: bool = False
    file: Optional[str] = None
    source_record_id: Optional[str] = None
    canonical_key: Optional[str] = None
    pmcid: Optional[str] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[str] = None
    size_kb: Optional[int] = None
    pdf_url: Optional[str] = None
    error: Optional[str] = None
    reason_details: List[Dict[str, str]] = field(default_factory=list)
    source_term: Optional[str] = None
    template_id: Optional[str] = None
    query_phrase: Optional[str] = None
    workflow_language: str = "en"
    search_gate_score: float = 0.0
    filter_score: float = 0.0
    search_gate_pass: bool = False
    filter_pass: bool = False
    decision_stage: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        payload = {
            "status": self.status,
            "title": self.title,
            "score": round(self.score, 2),
            "source": self.source,
            "query": self.query,
            "reasons": self.reasons,
            "reason_details": self.reason_details,
            "audit": self.audit,
            "file": self.file,
            "source_record_id": self.source_record_id,
            "canonical_key": self.canonical_key,
            "pmcid": self.pmcid,
            "doi": self.doi,
            "journal": self.journal,
            "year": self.year,
            "size_kb": self.size_kb,
            "pdf_url": self.pdf_url,
            "source_term": self.source_term,
            "template_id": self.template_id,
            "query_phrase": self.query_phrase,
            "workflow_language": self.workflow_language,
            "search_gate_score": round(self.search_gate_score, 2),
            "filter_score": round(self.filter_score, 2),
            "search_gate_pass": self.search_gate_pass,
            "filter_pass": self.filter_pass,
            "decision_stage": self.decision_stage,
        }
        if self.error:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True)
class QuerySpec:
    query: str
    keywords: Tuple[str, ...]
    template_id: str
    source_term: Optional[str]
    term_type: str
    language: str
    query_phrase: Optional[str] = None


@dataclass(frozen=True)
class SearchTask:
    source: str
    spec: QuerySpec
    query_text: str
    pair_score: float = 0.0


@dataclass
class DiscoveryHit:
    canonical_key: str
    source: str
    source_record_id: Optional[str]
    external_id: str
    pmcid: Optional[str]
    doi: Optional[str]
    title: str
    abstract: str
    workflow_language: str
    query: str
    template_id: str
    source_term: Optional[str]
    term_type: str
    query_phrase: Optional[str]
    search_gate_score: float
    search_gate_pass: bool
    filter_score: Optional[float] = None
    filter_pass: Optional[bool] = None
    is_duplicate: bool = False
    paper_id: Optional[int] = None

    @property
    def hit_key(self) -> str:
        return build_search_hit_key(
            canonical_key=self.canonical_key,
            source=self.source,
            workflow_language=self.workflow_language,
            template_id=self.template_id,
            source_term=self.source_term,
            query_phrase=self.query_phrase,
            query_text=self.query,
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "hit_key": self.hit_key,
            "canonical_key": self.canonical_key,
            "source": self.source,
            "source_record_id": self.source_record_id,
            "external_id": self.external_id,
            "pmcid": self.pmcid,
            "doi": self.doi,
            "title": self.title,
            "abstract": self.abstract,
            "workflow_language": self.workflow_language,
            "query": self.query,
            "template_id": self.template_id,
            "source_term": self.source_term,
            "term_type": self.term_type,
            "query_phrase": self.query_phrase,
            "search_gate_score": round(self.search_gate_score, 2),
            "search_gate_pass": self.search_gate_pass,
            "filter_score": round(self.filter_score, 2) if self.filter_score is not None else None,
            "filter_pass": self.filter_pass,
            "is_duplicate": self.is_duplicate,
            "paper_id": self.paper_id,
        }
