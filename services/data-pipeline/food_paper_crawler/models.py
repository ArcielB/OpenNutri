from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CandidatePaper:
    source: str
    query: str
    external_id: str
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
    accepted: bool = False
    reasons: List[str] = field(default_factory=list)

    @property
    def canonical_id(self) -> str:
        if self.pmcid:
            return self.pmcid
        if self.doi:
            return self.doi.lower()
        return self.external_id

    def to_dict(self) -> Dict[str, object]:
        return {
            "source": self.source,
            "query": self.query,
            "external_id": self.external_id,
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
            "accepted": self.accepted,
            "reasons": self.reasons,
        }


@dataclass
class DownloadRecord:
    status: str
    title: str
    score: float
    source: str
    query: str
    reasons: List[str]
    file: Optional[str] = None
    pmcid: Optional[str] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    year: Optional[str] = None
    size_kb: Optional[int] = None
    pdf_url: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        payload = {
            "status": self.status,
            "title": self.title,
            "score": round(self.score, 2),
            "source": self.source,
            "query": self.query,
            "reasons": self.reasons,
            "file": self.file,
            "pmcid": self.pmcid,
            "doi": self.doi,
            "journal": self.journal,
            "year": self.year,
            "size_kb": self.size_kb,
            "pdf_url": self.pdf_url,
        }
        if self.error:
            payload["error"] = self.error
        return payload

