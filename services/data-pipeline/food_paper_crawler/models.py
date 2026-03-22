from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


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
        if self.pmcid:
            return f"pmcid:{self.pmcid.lower()}"
        if self.doi:
            return f"doi:{self.doi.lower()}"
        normalized_title = re.sub(r"[^a-z0-9]+", " ", (self.title or "").lower()).strip()
        if normalized_title:
            digest = hashlib.sha1(normalized_title.encode("utf-8")).hexdigest()[:16]
            return f"title:{digest}"
        return f"source:{self.source}:{self.external_id}"

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

    def to_dict(self) -> Dict[str, object]:
        return {
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
