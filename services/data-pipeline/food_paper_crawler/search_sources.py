from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .europe_pmc import EuropePMCClient
from .language_utils import detect_supported_language, normalize_language_text
from .models import CandidatePaper, QuerySpec


DEFAULT_SEARCH_SOURCES = ("europepmc", "openalex", "semanticscholar", "dergipark")
OPENALEX_ALLOWED_TYPES = {"article", "preprint"}
OAI_NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "dc": "http://purl.org/dc/elements/1.1/",
}
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


class DergiParkOAISource:
    base_url = "https://dergipark.org.tr/api/public/oai/"
    FIELD_WEIGHTS = {
        "title": 2,
        "abstract": 1,
        "subjects": 1,
    }
    SUPPORT_TERMS_BY_LANGUAGE = {
        "en": {"table", "content", "analysis"},
        "tr": {"tablo", "içerik", "icerik", "analiz"},
    }
    ANCHOR_HINTS_BY_LANGUAGE = {
        "en": ("composition", "content", "analysis", "proximate"),
        "tr": ("bileşim", "bilesim", "kompozisyon", "içeri", "icerigi", "yaklasik"),
    }

    def __init__(self, *, data_dir: Path, scan_budget: int = 400) -> None:
        self.cache_path = data_dir / "dergipark_oai_cache.jsonl"
        self.state_path = data_dir / "dergipark_oai_state.json"
        self.scan_budget = scan_budget
        self.remaining_scan_budget = scan_budget
        self._records: List[dict] = self._load_cache()
        self._state = self._load_state()

    def query_text(self, spec: QuerySpec) -> str:
        return build_plain_query(spec)

    def search(self, spec: QuerySpec, limit: int) -> List[CandidatePaper]:
        normalized_keywords = self._normalized_keywords(spec)
        if not normalized_keywords:
            return []

        matches = self._match_records(spec, normalized_keywords, limit)
        if len(matches) >= limit:
            return matches[:limit]

        while len(matches) < limit and self.remaining_scan_budget > 0:
            fetched = self._fetch_next_batch()
            if not fetched:
                break
            self.remaining_scan_budget = max(0, self.remaining_scan_budget - fetched)
            matches = self._match_records(spec, normalized_keywords, limit)
        return matches[:limit]

    def _normalized_keywords(self, spec: QuerySpec) -> List[str]:
        seen = set()
        keywords: List[str] = []
        for raw_keyword in ((spec.query_phrase, spec.source_term) + spec.keywords):
            normalized = normalize_language_text(raw_keyword)
            if len(normalized) < 3 or normalized in seen:
                continue
            if normalized in NORMALIZED_UNIT_QUERY_TERMS:
                continue
            seen.add(normalized)
            keywords.append(normalized)
        return keywords

    def _match_records(self, spec: QuerySpec, keywords: List[str], limit: int) -> List[CandidatePaper]:
        results: List[tuple[tuple[int, int, int, int], CandidatePaper]] = []
        anchor_terms = self._anchor_terms(spec, keywords)
        for record in self._records:
            score = self._score_record(record, spec, keywords, anchor_terms)
            if score is None:
                continue
            results.append((score, self._to_candidate(record, spec)))
        results.sort(key=lambda item: item[0], reverse=True)
        return [candidate for _, candidate in results[:limit]]

    def _anchor_terms(self, spec: QuerySpec, keywords: List[str]) -> set[str]:
        support_terms = self.SUPPORT_TERMS_BY_LANGUAGE.get(spec.language, set())
        anchor_hints = self.ANCHOR_HINTS_BY_LANGUAGE.get(spec.language, ())
        anchors: set[str] = set()
        for term in keywords:
            if term in support_terms:
                continue
            if any(hint in term for hint in anchor_hints):
                anchors.add(term)
        return anchors

    def _score_record(
        self,
        record: dict,
        spec: QuerySpec,
        keywords: List[str],
        anchor_terms: set[str],
    ) -> Optional[tuple[int, int, int, int]]:
        record_language = str(record.get("language") or "").strip().lower()
        if record_language in {"en", "tr"} and record_language != spec.language:
            return None

        field_texts = {
            "title": normalize_language_text(record.get("title", "")),
            "abstract": normalize_language_text(record.get("abstract", "")),
            "subjects": normalize_language_text(" ".join(record.get("subjects", []))),
        }
        term_scores: Dict[str, int] = {}
        title_match_terms: set[str] = set()
        matched_anchors: set[str] = set()
        matched_source_term = False
        normalized_source_term = normalize_language_text(spec.source_term or "")

        for term in keywords:
            field_score = 0
            for field_name, text in field_texts.items():
                if not text:
                    continue
                if f" {term} " not in f" {text} ":
                    continue
                field_score = max(field_score, self.FIELD_WEIGHTS[field_name])
                if field_name == "title":
                    title_match_terms.add(term)
            if field_score <= 0:
                continue
            term_scores[term] = field_score
            if term in anchor_terms:
                matched_anchors.add(term)
            if normalized_source_term and term == normalized_source_term:
                matched_source_term = True

        total_score = sum(term_scores.values())
        if spec.source_term:
            if not matched_source_term or total_score < 3:
                return None
        elif not matched_anchors or total_score < 3:
            return None

        has_pdf = 1 if record.get("pdf_url") else 0
        year = self._sort_year(record.get("year"))
        return total_score, len(title_match_terms), has_pdf, year

    def _sort_year(self, raw_year: object) -> int:
        match = re.search(r"\d{4}", str(raw_year or ""))
        if not match:
            return 0
        return int(match.group(0))

    def _to_candidate(self, record: dict, spec: QuerySpec) -> CandidatePaper:
        return CandidatePaper(
            source="dergipark",
            query=self.query_text(spec),
            external_id=str(record.get("oai_id") or record.get("landing_url") or ""),
            source_record_id=str(record.get("oai_id") or ""),
            pmcid=None,
            doi=record.get("doi"),
            title=str(record.get("title") or "").strip(),
            abstract=str(record.get("abstract") or "").strip(),
            journal=str(record.get("journal") or "").strip() or None,
            year=str(record.get("year") or "").strip() or None,
            authors=list(record.get("authors") or []),
            pdf_url=record.get("pdf_url"),
            landing_url=record.get("landing_url"),
        )

    def _fetch_next_batch(self) -> int:
        token = self._state.get("resumption_token")
        if token:
            url = f"{self.base_url}?verb=ListRecords&resumptionToken={quote(token)}"
        else:
            url = f"{self.base_url}?verb=ListRecords&metadataPrefix=oai_dc"
        request = Request(url, headers={"User-Agent": "OpenNutri/1.0"})
        try:
            with urlopen(request, timeout=25) as response:
                payload = response.read().decode("utf-8", errors="ignore")
        except (HTTPError, URLError, TimeoutError):
            return 0

        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return 0

        fetched = 0
        seen = {record.get("oai_id") for record in self._records}
        for record_node in root.findall(".//oai:record", OAI_NS):
            record = self._parse_record(record_node)
            if not record:
                continue
            oai_id = record.get("oai_id")
            if oai_id in seen:
                continue
            seen.add(oai_id)
            self._records.append(record)
            self._append_cache(record)
            fetched += 1

        token_node = root.find(".//oai:resumptionToken", OAI_NS)
        self._state["resumption_token"] = (
            token_node.text.strip()
            if token_node is not None and token_node.text and token_node.text.strip()
            else None
        )
        self._save_state()
        return fetched

    def _parse_record(self, record_node: ET.Element) -> Optional[dict]:
        header = record_node.find("oai:header", OAI_NS)
        if header is None:
            return None
        oai_id = header.findtext("oai:identifier", default="", namespaces=OAI_NS).strip()
        metadata = record_node.find("oai:metadata", OAI_NS)
        if metadata is None:
            return None
        dc = metadata.find(".//oai_dc:dc", OAI_NS)
        if dc is None:
            return None

        identifiers = [node.text.strip() for node in dc.findall("dc:identifier", OAI_NS) if node.text and node.text.strip()]
        descriptions = [node.text.strip() for node in dc.findall("dc:description", OAI_NS) if node.text and node.text.strip()]
        title = dc.findtext("dc:title", default="", namespaces=OAI_NS).strip()
        journal = dc.findtext("dc:source", default="", namespaces=OAI_NS).strip()
        year = dc.findtext("dc:date", default="", namespaces=OAI_NS).strip()[:4] or None
        authors = [node.text.strip() for node in dc.findall("dc:creator", OAI_NS) if node.text and node.text.strip()]
        subjects = [node.text.strip() for node in dc.findall("dc:subject", OAI_NS) if node.text and node.text.strip()]
        language = dc.findtext("dc:language", default="", namespaces=OAI_NS).strip().lower()

        landing_url = None
        pdf_url = None
        doi = None
        for identifier in identifiers:
            match = DOI_PATTERN.search(identifier)
            if match and not doi:
                doi = match.group(0)
            if identifier.lower().endswith(".pdf") and not pdf_url:
                pdf_url = identifier
            if identifier.startswith("http") and not landing_url:
                landing_url = identifier

        abstract = descriptions[0] if descriptions else ""
        if not title and not abstract:
            return None
        if language not in {"en", "tr"}:
            language = detect_supported_language(" ".join(part for part in (title, abstract) if part), default="tr")
        return {
            "oai_id": oai_id,
            "title": title,
            "abstract": abstract,
            "journal": journal or None,
            "year": year,
            "authors": authors,
            "subjects": subjects,
            "language": language,
            "landing_url": landing_url,
            "pdf_url": pdf_url,
            "doi": doi,
        }

    def _load_cache(self) -> List[dict]:
        if not self.cache_path.exists():
            return []
        records: List[dict] = []
        for line in self.cache_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records

    def _append_cache(self, record: dict) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            return {"resumption_token": None}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"resumption_token": None}
        return payload if isinstance(payload, dict) else {"resumption_token": None}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
