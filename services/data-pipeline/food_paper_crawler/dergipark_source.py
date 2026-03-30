from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

from .language_utils import detect_supported_language, normalize_language_text
from .models import CandidatePaper, QuerySpec


OAI_NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "dc": "http://purl.org/dc/elements/1.1/",
}
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", re.IGNORECASE)
UNIT_QUERY_TERMS = {"mg/100g", "g/100g", "ug/100g", "µg/100g"}
NORMALIZED_UNIT_QUERY_TERMS = {normalize_language_text(term) for term in UNIT_QUERY_TERMS}
DERGIPARK_BASE_URL = "https://dergipark.org.tr"
SEED_JOURNALS_PATH = Path(__file__).with_name("dergipark_seed_journals.json")
NEGATIVE_ARTICLE_TYPE_HINTS = (
    "editorial",
    "editoryal",
    "book review",
    "kitap inceleme",
    "duyuru",
    "announcement",
    "foreword",
    "onsoz",
    "önsöz",
    "letter to the editor",
    "editore mektup",
    "kongre",
    "sempozyum",
)
POSITIVE_ARTICLE_TYPE_HINTS = (
    "research article",
    "arastirma makalesi",
    "araştırma makalesi",
    "original article",
)


def _build_plain_query(spec: QuerySpec) -> str:
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


def _canonical_dergipark_url(raw_url: str) -> str:
    text = str(raw_url or "").strip()
    if not text:
        return ""
    absolute = urljoin(DERGIPARK_BASE_URL, text)
    parsed = urlparse(absolute)
    path = re.sub(r"/+", "/", parsed.path or "")
    if path.endswith("/") and path != "/":
        path = path[:-1]
    return f"{parsed.scheme}://{parsed.netloc}{path}"


class _HrefCollector(HTMLParser):
    def __init__(self, *, patterns: tuple[str, ...]) -> None:
        super().__init__()
        self.patterns = patterns
        self.hrefs: List[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {key.lower(): value for key, value in attrs}
        href = str(attr_map.get("href") or "").strip()
        if href and any(pattern in href for pattern in self.patterns):
            self.hrefs.append(href)


class _MetaCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: Dict[str, List[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "meta":
            return
        attr_map = {key.lower(): value for key, value in attrs}
        name = str(attr_map.get("name") or attr_map.get("property") or "").strip().lower()
        content = str(attr_map.get("content") or "").strip()
        if not name or not content:
            return
        self.meta.setdefault(name, []).append(unescape(content))


class DergiParkOAISource:
    FIELD_WEIGHTS = {
        "title": 3,
        "keywords": 2,
        "abstract": 2,
        "journal_title": 1,
    }
    SUPPORT_TERMS_BY_LANGUAGE = {
        "en": {"table", "content", "analysis"},
        "tr": {"tablo", "içerik", "icerik", "analiz"},
    }
    ANCHOR_HINTS_BY_LANGUAGE = {
        "en": ("composition", "content", "analysis", "proximate"),
        "tr": ("bileşim", "bilesim", "kompozisyon", "içeri", "icerigi", "yaklasik"),
    }

    def __init__(
        self,
        *,
        data_dir: Path,
        scan_budget: int = 400,
        max_journals: int = 0,
        max_issues_per_journal: int = 12,
    ) -> None:
        self.data_dir = data_dir
        self.scan_budget = scan_budget
        self.max_journals = max(0, int(max_journals))
        self.max_issues_per_journal = max(1, int(max_issues_per_journal))
        self.registry_path = self.data_dir / "dergipark_journals.json"
        self.index_path = self.data_dir / "dergipark_articles.jsonl"
        self.report_path = self.data_dir / "dergipark_refresh_report.json"
        self.state_path = self.data_dir / "dergipark_refresh_state.json"
        self._records = self._load_index()
        self._report = self._load_report()

    def query_text(self, spec: QuerySpec) -> str:
        return _build_plain_query(spec)

    def search(self, spec: QuerySpec, limit: int) -> List[CandidatePaper]:
        normalized_keywords = self._normalized_keywords(spec)
        if not normalized_keywords:
            return []
        matches = self._match_records(spec, normalized_keywords, limit)
        return matches[:limit]

    def refresh_index(
        self,
        *,
        journal_limit: int = 0,
        max_issues_per_journal: Optional[int] = None,
        force: bool = False,
    ) -> dict:
        refreshed_at = datetime.now(timezone.utc).isoformat()
        registry = self._load_registry()
        selected = self._select_journals(registry, journal_limit)
        existing = {
            _canonical_dergipark_url(record.get("article_url", "")): dict(record)
            for record in self._records
            if _canonical_dergipark_url(record.get("article_url", ""))
        }
        issue_limit = max_issues_per_journal or self.max_issues_per_journal
        state = self._load_state()

        articles_by_journal: Dict[str, int] = {}
        issues_by_journal: Dict[str, int] = {}
        journal_titles: Dict[str, str] = {}
        failed_journals: List[str] = []

        for journal in selected:
            slug = str(journal.get("slug") or "").strip()
            if not slug:
                continue
            archive_url = self._resolve_archive_url(slug)
            if not archive_url:
                failed_journals.append(slug)
                continue
            try:
                archive_html = self._fetch_text(archive_url)
            except RuntimeError:
                failed_journals.append(slug)
                continue

            issue_urls = self._parse_issue_urls(archive_html, archive_url)[:issue_limit]
            if not issue_urls:
                failed_journals.append(slug)
                continue

            issues_by_journal[slug] = len(issue_urls)
            article_count = 0
            for issue_url in issue_urls:
                try:
                    issue_html = self._fetch_text(issue_url)
                except RuntimeError:
                    continue
                article_urls = self._parse_article_urls(issue_html, issue_url)
                for article_url in article_urls:
                    canonical_url = _canonical_dergipark_url(article_url)
                    if not canonical_url:
                        continue
                    if not force and canonical_url in existing:
                        record = existing[canonical_url]
                        record["last_seen_at"] = refreshed_at
                        record["journal_slug"] = slug
                        article_count += 1
                        journal_titles.setdefault(slug, str(record.get("journal_title") or "").strip())
                        continue
                    try:
                        article_html = self._fetch_text(canonical_url)
                    except RuntimeError:
                        continue
                    record = self._parse_article_page(article_html, canonical_url, slug)
                    if not record:
                        continue
                    record["last_seen_at"] = refreshed_at
                    existing[canonical_url] = record
                    article_count += 1
                    journal_titles.setdefault(slug, str(record.get("journal_title") or "").strip())
            articles_by_journal[slug] = article_count
            state[slug] = {
                "last_refreshed_at": refreshed_at,
                "archive_url": archive_url,
                "issue_count": issues_by_journal.get(slug, 0),
                "article_count": articles_by_journal.get(slug, 0),
            }

        records = sorted(existing.values(), key=lambda item: (_canonical_dergipark_url(item.get("article_url", "")), str(item.get("year") or "")))
        self._write_index(records)
        self._save_state(state)
        report = self._build_report(
            records,
            refreshed_at=refreshed_at,
            issues_by_journal=issues_by_journal,
            articles_by_journal=articles_by_journal,
            journal_titles=journal_titles,
            failed_journals=failed_journals,
            journal_count=len(selected),
        )
        self._save_report(report)
        self._records = records
        self._report = report
        return report

    def index_info(self) -> dict:
        if self._report:
            return dict(self._report)
        return self._build_report(
            self._records,
            refreshed_at=None,
            issues_by_journal={},
            articles_by_journal={},
            journal_titles={},
            failed_journals=[],
            journal_count=0,
        )

    def _build_report(
        self,
        records: List[dict],
        *,
        refreshed_at: Optional[str],
        issues_by_journal: Dict[str, int],
        articles_by_journal: Dict[str, int],
        journal_titles: Dict[str, str],
        failed_journals: List[str],
        journal_count: int,
    ) -> dict:
        language_counts: Dict[str, int] = {}
        with_abstract = 0
        with_pdf = 0
        for record in records:
            language = str(record.get("language") or "unknown").strip().lower() or "unknown"
            language_counts[language] = language_counts.get(language, 0) + 1
            if record.get("abstract"):
                with_abstract += 1
            if record.get("pdf_url"):
                with_pdf += 1
        top_journals = sorted(
            articles_by_journal.items(),
            key=lambda item: (-item[1], item[0]),
        )[:10]
        return {
            "refreshed_at": refreshed_at or (self._report.get("refreshed_at") if self._report else None),
            "journal_count": journal_count or len({record.get("journal_slug") for record in records if record.get("journal_slug")}),
            "issue_count": sum(issues_by_journal.values()),
            "article_count": len(records),
            "articles_with_abstract": with_abstract,
            "articles_with_pdf_url": with_pdf,
            "articles_by_language": language_counts,
            "top_journals_by_article_count": [
                {
                    "slug": slug,
                    "journal_title": journal_titles.get(slug) or slug,
                    "article_count": count,
                    "issue_count": int(issues_by_journal.get(slug, 0)),
                }
                for slug, count in top_journals
            ],
            "failed_journals": sorted(set(failed_journals)),
            "index_path": str(self.index_path),
            "registry_path": str(self.registry_path),
        }

    def _select_journals(self, registry: List[dict], limit: int) -> List[dict]:
        selected = [
            journal
            for journal in registry
            if bool(journal.get("enabled", True)) and str(journal.get("slug") or "").strip()
        ]
        if limit > 0:
            return selected[:limit]
        if self.max_journals > 0:
            return selected[: self.max_journals]
        return selected

    def _load_registry(self) -> List[dict]:
        payload = self._load_json_file(self.registry_path)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

        seed_payload = self._load_json_file(SEED_JOURNALS_PATH)
        journals = [item for item in seed_payload if isinstance(item, dict)] if isinstance(seed_payload, list) else []
        if journals:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            self.registry_path.write_text(json.dumps(journals, ensure_ascii=False, indent=2), encoding="utf-8")
        return journals

    def _resolve_archive_url(self, slug: str) -> Optional[str]:
        for prefix in ("tr", "en"):
            url = f"{DERGIPARK_BASE_URL}/{prefix}/pub/{slug}/archive"
            try:
                self._fetch_text(url)
                return url
            except RuntimeError:
                continue
        return None

    def _parse_issue_urls(self, html_text: str, base_url: str) -> List[str]:
        parser = _HrefCollector(patterns=("/issue/",))
        parser.feed(html_text)
        urls = []
        seen = set()
        for href in parser.hrefs:
            absolute = _canonical_dergipark_url(urljoin(base_url, href))
            if absolute and absolute not in seen:
                seen.add(absolute)
                urls.append(absolute)
        return urls

    def _parse_article_urls(self, html_text: str, base_url: str) -> List[str]:
        parser = _HrefCollector(patterns=("/article/",))
        parser.feed(html_text)
        urls = []
        seen = set()
        for href in parser.hrefs:
            absolute = _canonical_dergipark_url(urljoin(base_url, href))
            if absolute and absolute not in seen:
                seen.add(absolute)
                urls.append(absolute)
        return urls

    def _parse_article_page(self, html_text: str, article_url: str, journal_slug: str) -> Optional[dict]:
        parser = _MetaCollector()
        parser.feed(html_text)
        meta = parser.meta

        title = self._first_meta(meta, "citation_title")
        abstract = self._first_meta(meta, "citation_abstract")
        journal_title = self._first_meta(meta, "citation_journal_title")
        language = (self._first_meta(meta, "citation_language") or "").strip().lower()
        article_type = self._first_meta(meta, "citation_article_type")
        publication_date = self._first_meta(meta, "citation_publication_date")
        pdf_url = self._first_meta(meta, "citation_pdf_url")
        doi = self._strip_doi(self._first_meta(meta, "citation_doi"))
        keywords = self._split_keywords(meta.get("citation_keywords") or [])
        authors = [value.strip() for value in meta.get("citation_author", []) if value.strip()]

        if not title:
            return None
        if language not in {"en", "tr"}:
            language = detect_supported_language(" ".join(part for part in (title, abstract) if part), default="tr")

        return {
            "article_url": article_url,
            "journal_slug": journal_slug,
            "journal_title": journal_title,
            "title": title,
            "abstract": abstract,
            "keywords": keywords,
            "doi": doi,
            "pdf_url": urljoin(DERGIPARK_BASE_URL, pdf_url) if pdf_url else None,
            "language": language,
            "year": self._extract_year(publication_date),
            "article_type": article_type,
            "authors": authors,
        }

    def _split_keywords(self, raw_values: List[str]) -> List[str]:
        seen = set()
        keywords: List[str] = []
        for raw_value in raw_values:
            for token in re.split(r"[;,|]", raw_value):
                normalized = " ".join(unescape(token).split())
                if len(normalized) < 2:
                    continue
                lowered = normalized.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                keywords.append(normalized)
        return keywords

    def _extract_year(self, value: Optional[str]) -> Optional[str]:
        match = re.search(r"\d{4}", str(value or ""))
        if not match:
            return None
        return match.group(0)

    def _strip_doi(self, value: Optional[str]) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        match = DOI_PATTERN.search(text)
        if match:
            return match.group(0)
        return text

    def _fetch_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": "OpenNutri/1.0"})
        try:
            with urlopen(request, timeout=25) as response:
                return response.read().decode("utf-8", errors="ignore")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"Failed to fetch DergiPark URL: {url}") from exc

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
        results: List[tuple[tuple[int, int, int, int, int], CandidatePaper]] = []
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
    ) -> Optional[tuple[int, int, int, int, int]]:
        record_language = str(record.get("language") or "").strip().lower()
        if record_language in {"en", "tr"} and record_language != spec.language:
            return None

        article_type = normalize_language_text(record.get("article_type", ""))
        if article_type and any(hint in article_type for hint in NEGATIVE_ARTICLE_TYPE_HINTS):
            return None

        field_texts = {
            "title": normalize_language_text(record.get("title", "")),
            "abstract": normalize_language_text(record.get("abstract", "")),
            "keywords": normalize_language_text(" ".join(record.get("keywords", []))),
            "journal_title": normalize_language_text(record.get("journal_title", "")),
        }
        term_scores: Dict[str, int] = {}
        title_match_terms: set[str] = set()
        matched_anchors: set[str] = set()
        matched_source_term = False
        keyword_overlap = 0
        normalized_source_term = normalize_language_text(spec.source_term or "")

        for term in keywords:
            field_score = 0
            matched_keyword_field = False
            for field_name, text in field_texts.items():
                if not text:
                    continue
                if not self._term_matches(text, term):
                    continue
                field_score = max(field_score, self.FIELD_WEIGHTS[field_name])
                if field_name == "title":
                    title_match_terms.add(term)
                if field_name == "keywords":
                    matched_keyword_field = True
            if field_score <= 0:
                continue
            term_scores[term] = field_score
            if matched_keyword_field:
                keyword_overlap += 1
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

        research_preference = 1 if article_type and any(hint in article_type for hint in POSITIVE_ARTICLE_TYPE_HINTS) else 0
        has_pdf = 1 if record.get("pdf_url") else 0
        year = self._sort_year(record.get("year"))
        return total_score, keyword_overlap, research_preference, has_pdf, year

    def _term_matches(self, text: str, term: str) -> bool:
        bounded_text = f" {text} "
        bounded_term = f" {term} "
        if bounded_term in bounded_text:
            return True
        if " " in term and term in text:
            return True
        return False

    def _sort_year(self, raw_year: object) -> int:
        match = re.search(r"\d{4}", str(raw_year or ""))
        if not match:
            return 0
        return int(match.group(0))

    def _to_candidate(self, record: dict, spec: QuerySpec) -> CandidatePaper:
        article_url = _canonical_dergipark_url(record.get("article_url", ""))
        return CandidatePaper(
            source="dergipark",
            query=self.query_text(spec),
            external_id=article_url or str(record.get("doi") or ""),
            source_record_id=article_url or str(record.get("doi") or ""),
            pmcid=None,
            doi=record.get("doi"),
            title=str(record.get("title") or "").strip(),
            abstract=str(record.get("abstract") or "").strip(),
            journal=str(record.get("journal_title") or "").strip() or None,
            year=str(record.get("year") or "").strip() or None,
            authors=list(record.get("authors") or []),
            pdf_url=record.get("pdf_url"),
            landing_url=article_url or None,
        )

    def _first_meta(self, meta: Dict[str, List[str]], key: str) -> Optional[str]:
        values = meta.get(key.lower()) or []
        for value in values:
            normalized = " ".join(str(value or "").split())
            if normalized:
                return normalized
        return None

    def _load_index(self) -> List[dict]:
        if not self.index_path.exists():
            return []
        records: List[dict] = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records

    def _write_index(self, records: List[dict]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _load_report(self) -> dict:
        payload = self._load_json_file(self.report_path)
        return payload if isinstance(payload, dict) else {}

    def _save_report(self, report: dict) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_state(self) -> dict:
        payload = self._load_json_file(self.state_path)
        return payload if isinstance(payload, dict) else {}

    def _save_state(self, state: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_json_file(self, path: Path) -> object:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

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
