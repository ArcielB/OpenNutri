from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .dergipark_source import DergiParkOAISource, OAI_NS
from .europe_pmc import EuropePMCClient
from .language_utils import normalize_language_text
from .models import CandidatePaper, QuerySpec


DEFAULT_SEARCH_SOURCES = ("europepmc", "openalex", "semanticscholar", "dergipark")
OPENALEX_ALLOWED_TYPES = {"article", "preprint"}
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", re.IGNORECASE)
PMCID_PATTERN = re.compile(r"PMC\d+", re.IGNORECASE)
UNIT_QUERY_TERMS = {"mg/100g", "g/100g", "ug/100g", "µg/100g"}
NORMALIZED_UNIT_QUERY_TERMS = {normalize_language_text(term) for term in UNIT_QUERY_TERMS}


def build_search_sources(
    names: List[str],
    *,
    data_dir: Path,
    page_size: int,
    dergipark_scan_budget: int = 400,
) -> Dict[str, object]:
    available = {
        "europepmc": EuropePMCSearchSource(page_size=page_size),
        "openalex": OpenAlexSearchSource(),
        "semanticscholar": SemanticScholarSearchSource(),
        "dergipark": DergiParkOAISource(data_dir=data_dir, scan_budget=dergipark_scan_budget),
    }
    selected: Dict[str, object] = {}
    for raw_name in names:
        name = raw_name.strip().lower()
        if name and name in available:
            selected[name] = available[name]
    return selected


def build_plain_query(spec: QuerySpec) -> str:
    seen = set()
    parts: List[str] = []
    candidates: List[str] = []
    if spec.query_phrase:
        candidates.append(spec.query_phrase)
    if spec.source_term:
        candidates.append(spec.source_term)
    candidates.extend(spec.keywords)

    for keyword in candidates:
        normalized = " ".join((keyword or "").split())
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        parts.append(f'"{normalized}"' if " " in normalized else normalized)
        if len(parts) >= 5:
            break
    return " ".join(parts) if parts else spec.query


def build_metadata_query(spec: QuerySpec) -> str:
    candidates: List[str] = []
    seen = set()

    def append(term: object) -> None:
        normalized = " ".join(str(term or "").split())
        if not normalized:
            return
        lowered = normalized.lower()
        if lowered in seen or lowered in UNIT_QUERY_TERMS:
            return
        seen.add(lowered)
        candidates.append(normalized)

    if spec.source_term:
        append(spec.source_term)
    if spec.query_phrase:
        append(spec.query_phrase)

    if not candidates:
        for keyword in spec.keywords:
            append(keyword)
            if len(candidates) >= 2:
                break

    # Metadata search APIs work better with one concise composition phrase for
    # base discovery and two terms for learned concept queries.
    if not spec.source_term and candidates:
        candidates = candidates[:1]
    else:
        candidates = candidates[:2]

    if not candidates:
        return build_plain_query(spec)

    rendered: List[str] = []
    for term in candidates:
        rendered.append(f'"{term}"' if " " in term else term)
    return " ".join(rendered)


class EuropePMCSearchSource:
    def __init__(self, *, page_size: int) -> None:
        self.client = EuropePMCClient(page_size=page_size)

    def query_text(self, spec: QuerySpec) -> str:
        return spec.query

    def search(self, spec: QuerySpec, limit: int) -> List[CandidatePaper]:
        return self.client.search(self.query_text(spec), limit=limit)


class OpenAlexSearchSource:
    base_url = "https://api.openalex.org/works"

    def query_text(self, spec: QuerySpec) -> str:
        return build_metadata_query(spec)

    def search(self, spec: QuerySpec, limit: int) -> List[CandidatePaper]:
        query = self.query_text(spec)
        url = f"{self.base_url}?search={quote(query)}&per-page={min(limit, 200)}"
        request = Request(url, headers={"User-Agent": "OpenNutri/1.0"})
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return []

        results = payload.get("results", [])
        candidates: List[CandidatePaper] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            work_type = str(item.get("type") or "").strip().lower()
            if work_type and work_type not in OPENALEX_ALLOWED_TYPES:
                continue
            language = str(item.get("language") or "").strip().lower()
            if language in {"en", "tr"} and language != spec.language:
                continue
            ids = item.get("ids") or {}
            doi = self._strip_doi(ids.get("doi") or item.get("doi"))
            pmcid = self._extract_pmcid(ids)
            pdf_url = None
            primary_location = item.get("primary_location") or {}
            if isinstance(primary_location, dict):
                pdf_url = primary_location.get("pdf_url")
            if not pdf_url:
                open_access = item.get("open_access") or {}
                if isinstance(open_access, dict):
                    pdf_url = open_access.get("oa_url")
            abstract = self._reconstruct_abstract(item.get("abstract_inverted_index"))
            title = str(item.get("display_name") or item.get("title") or "").strip()
            if not title:
                continue
            journal = None
            host_venue = primary_location.get("source") if isinstance(primary_location, dict) else None
            if isinstance(host_venue, dict):
                journal = str(host_venue.get("display_name") or "").strip() or None
            year = str(item.get("publication_year") or "").strip() or None
            landing_url = primary_location.get("landing_page_url") if isinstance(primary_location, dict) else None
            if not landing_url:
                landing_url = item.get("id")
            if not abstract and not (pdf_url or pmcid):
                continue
            candidates.append(
                CandidatePaper(
                    source="openalex",
                    query=query,
                    external_id=str(item.get("id") or ""),
                    source_record_id=str(item.get("id") or ""),
                    pmcid=pmcid,
                    doi=doi,
                    title=title,
                    abstract=abstract,
                    journal=journal,
                    year=year,
                    authors=[],
                    pdf_url=str(pdf_url or "").strip() or None,
                    landing_url=str(landing_url or "").strip() or None,
                )
            )
        return candidates

    def _reconstruct_abstract(self, inverted_index: object) -> str:
        if not isinstance(inverted_index, dict):
            return ""
        positions: Dict[int, str] = {}
        for word, raw_positions in inverted_index.items():
            if not isinstance(raw_positions, list):
                continue
            for pos in raw_positions:
                if isinstance(pos, int):
                    positions[pos] = str(word)
        return " ".join(positions[idx] for idx in sorted(positions))

    def _strip_doi(self, value: object) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        if text.startswith("https://doi.org/"):
            return text.split("https://doi.org/", 1)[1]
        return text

    def _extract_pmcid(self, ids: object) -> Optional[str]:
        if isinstance(ids, dict):
            for value in ids.values():
                match = PMCID_PATTERN.search(str(value or ""))
                if match:
                    return match.group(0).upper()
        return None


class SemanticScholarSearchSource:
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    fields = "paperId,title,abstract,year,externalIds,openAccessPdf,url,journal"

    def query_text(self, spec: QuerySpec) -> str:
        return build_metadata_query(spec)

    def search(self, spec: QuerySpec, limit: int) -> List[CandidatePaper]:
        query = self.query_text(spec)
        url = (
            f"{self.base_url}?query={quote(query)}&limit={min(limit, 100)}"
            f"&fields={quote(self.fields, safe=',')}"
        )
        request = Request(url, headers={"User-Agent": "OpenNutri/1.0"})
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return []

        results = payload.get("data", [])
        candidates: List[CandidatePaper] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            external_ids = item.get("externalIds") or {}
            doi = str(external_ids.get("DOI") or "").strip() or None
            pmcid = str(external_ids.get("PubMedCentral") or "").strip() or None
            if pmcid and not pmcid.upper().startswith("PMC"):
                pmcid = f"PMC{pmcid}"
            open_access_pdf = item.get("openAccessPdf") or {}
            pdf_url = open_access_pdf.get("url") if isinstance(open_access_pdf, dict) else None
            journal = None
            if isinstance(item.get("journal"), dict):
                journal = str(item["journal"].get("name") or "").strip() or None
            title = str(item.get("title") or "").strip()
            abstract = str(item.get("abstract") or "").strip()
            if not title:
                continue
            if not abstract and not (pdf_url or pmcid):
                continue
            candidates.append(
                CandidatePaper(
                    source="semanticscholar",
                    query=query,
                    external_id=str(item.get("paperId") or ""),
                    source_record_id=str(item.get("paperId") or ""),
                    pmcid=pmcid,
                    doi=doi,
                    title=title,
                    abstract=abstract,
                    journal=journal,
                    year=str(item.get("year") or "").strip() or None,
                    authors=[],
                    pdf_url=str(pdf_url or "").strip() or None,
                    landing_url=str(item.get("url") or "").strip() or None,
                )
            )
        return candidates
