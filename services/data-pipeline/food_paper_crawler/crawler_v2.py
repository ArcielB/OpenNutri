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

from .europe_pmc import EuropePMCClient
from .models import CandidatePaper, DownloadRecord
from .ranking import validate_pdf_text
from .supabase_terms import fetch_food_terms, fetch_nutrient_terms


HEALTH_OUTCOME_TERMS = [
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
]

STRONG_POSITIVE_PHRASES = [
    "food composition",
    "composition table",
    "food composition table",
    "nutrient composition",
    "nutritional composition",
    "chemical composition",
    "proximate composition",
    "proximate analysis",
    "mineral content",
    "vitamin content",
    "fatty acid composition",
    "amino acid composition",
    "nutrient content",
]

UNIT_PATTERN = re.compile(r"\b(?:mg|g|µg|ug)\s*/?\s*100\s*g\b", re.IGNORECASE)

PMC_OA_API = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
AUDIT_EVERY_N = 100


@dataclass(frozen=True)
class QuerySpec:
    query: str
    template_id: str
    source_term: Optional[str]
    term_type: str


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
        self.food_terms = fetch_food_terms(supabase_url, supabase_key, limit=food_limit)
        self.nutrient_terms = fetch_nutrient_terms(supabase_url, supabase_key, limit=nutrient_limit)
        self.max_queries = max_queries
        self.state = self._load_state()

    def run(self, replace_existing: bool = False) -> Dict[str, object]:
        self.audit_reject_counter = int(self.state.get("audit_reject_counter", 0))
        if replace_existing and self.raw_pdf_dir.exists():
            shutil.rmtree(self.raw_pdf_dir)
        if replace_existing:
            self.state = {"seen_ids": [], "term_cursor": 0}
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

                accepted, reason_details = self._metadata_decision(candidate)
                if not candidate.pdf_url:
                    self._append_reason(reason_details, "no_pdf_url", "Rejected: no PDF URL available")
                    accepted = False

                candidate.accepted = accepted
                candidate.reason_details = reason_details
                candidate.reasons = [reason["text"] for reason in reason_details]
                candidate.score = 0.0

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

        manifest = {
            "harvested_at": harvested_at,
            "query_count": len(queries),
            "rule_version": "l1-balanced-v1",
            "target_pdfs": self.target_pdfs,
            "accepted_count": len(accepted_records),
            "rejected_count": len(rejected_records),
            "food_term_sample": self.food_terms[:20],
            "nutrient_term_sample": self.nutrient_terms[:20],
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
        base_queries = [
            QuerySpec(
                query='("food composition" OR "nutrient composition" OR "proximate analysis" OR '
                '"chemical composition" OR "food composition table") AND IN_PMC:y',
                template_id="base_core_composition",
                source_term=None,
                term_type="base",
            ),
            QuerySpec(
                query='("nutrient content" OR "mineral content" OR "vitamin content" OR '
                '"fatty acid composition" OR "amino acid composition") AND IN_PMC:y',
                template_id="base_nutrient_content",
                source_term=None,
                term_type="base",
            ),
        ]

        term_pool = self._build_term_pool()
        if not term_pool:
            return self._dedupe_queries(base_queries)[: max(1, self.max_queries)]

        queries: List[QuerySpec] = list(base_queries)
        remaining = max(0, self.max_queries - len(queries))
        cursor = int(self.state.get("term_cursor", 0)) % len(term_pool)
        for offset in range(remaining):
            term_type, term = term_pool[(cursor + offset) % len(term_pool)]
            queries.append(self._build_term_query(term_type, term))

        self.state["term_cursor"] = (cursor + remaining) % len(term_pool)
        return self._dedupe_queries(queries)[: self.max_queries]

    def _build_term_pool(self) -> List[Tuple[str, str]]:
        pool: List[Tuple[str, str]] = []
        max_len = max(len(self.food_terms), len(self.nutrient_terms))
        for idx in range(max_len):
            if idx < len(self.food_terms):
                pool.append(("food", self.food_terms[idx]))
            if idx < len(self.nutrient_terms):
                pool.append(("nutrient", self.nutrient_terms[idx]))
        return pool

    def _build_term_query(self, term_type: str, term: str) -> QuerySpec:
        safe_term = term.replace('"', "").strip()
        if term_type == "nutrient":
            return QuerySpec(
                query=(
                    f'("{safe_term}" AND ("food composition" OR "nutrient composition" OR '
                    '"nutrient content" OR "mg/100g" OR "g/100g")) AND IN_PMC:y'
                ),
                template_id="nutrient_composition",
                source_term=term,
                term_type="nutrient",
            )
        return QuerySpec(
            query=(
                f'("{safe_term}" AND ("food composition" OR "nutrient composition" OR '
                '"nutrient content" OR "proximate analysis" OR "chemical composition")) AND IN_PMC:y'
            ),
            template_id="food_composition",
            source_term=term,
            term_type="food",
        )

    def _dedupe_queries(self, queries: List[QuerySpec]) -> List[QuerySpec]:
        seen: Set[str] = set()
        ordered: List[QuerySpec] = []
        for spec in queries:
            key = re.sub(r"\s+", " ", spec.query.strip())
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(spec)
        return ordered

    def _metadata_decision(self, candidate: CandidatePaper) -> Tuple[bool, List[Dict[str, str]]]:
        details: List[Dict[str, str]] = []
        raw_text = f"{candidate.title} {candidate.abstract}".strip().lower()
        normalized = self._normalize_for_match(raw_text)

        hard_negative = self._first_term_hit(normalized, HEALTH_OUTCOME_TERMS)
        if hard_negative:
            self._append_reason(details, "hard_negative", f"Rejected: hard negative term '{hard_negative}'")
            return False, details

        composition_hit = self._first_term_hit(normalized, STRONG_POSITIVE_PHRASES)
        if composition_hit:
            self._append_reason(details, "composition_phrase", f"Positive: composition phrase '{composition_hit}'")

        unit_hit = bool(UNIT_PATTERN.search(raw_text))
        if unit_hit:
            self._append_reason(details, "unit_signal", "Positive: nutrient unit pattern (mg/100g or g/100g)")

        food_hit = self._first_term_hit(normalized, self.food_terms)
        if food_hit:
            self._append_reason(details, "food_term_hit", f"Positive: food term '{food_hit}'")

        nutrient_hit = self._first_term_hit(normalized, self.nutrient_terms)
        if nutrient_hit:
            self._append_reason(details, "nutrient_term_hit", f"Positive: nutrient term '{nutrient_hit}'")

        accepted = bool(composition_hit or unit_hit or (food_hit and nutrient_hit))
        if accepted:
            self._append_reason(details, "accepted_metadata", "Accepted by metadata rules")
        else:
            self._append_reason(details, "rejected_no_positive", "Rejected: no strong positive signals")

        return accepted, details

    def _append_reason(self, details: List[Dict[str, str]], code: str, text: str) -> None:
        details.append({"code": code, "text": text})

    def _normalize_for_match(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

    def _first_term_hit(self, text: str, terms: List[str]) -> Optional[str]:
        if not text:
            return None
        padded = f" {text} "
        for term in terms:
            if not term:
                continue
            normalized_term = re.sub(r"[^a-z0-9]+", " ", term.lower()).strip()
            if not normalized_term:
                continue
            needle = f" {normalized_term} "
            if needle in padded:
                return normalized_term
        return None

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
            candidate.score = 0.0
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
            )

        candidate.reason_details = combined_reason_details
        candidate.reasons = combined_reasons
        candidate.score = 0.0
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
        return validate_pdf_text(text, candidate, self.food_terms, self.nutrient_terms)

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
        )

    def _load_state(self) -> Dict[str, object]:
        if not self.state_path.exists():
            return {"seen_ids": []}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"seen_ids": []}

    def _save_state(self) -> None:
        self._write_json(self.state_path, self.state)

    def _write_json(self, path: Path, payload: Dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
