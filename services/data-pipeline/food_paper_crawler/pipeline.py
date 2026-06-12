from __future__ import annotations

import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .europe_pmc import EuropePMCClient
from .models import CandidatePaper, DownloadRecord
from .pmc_pow import solve_pmc_pow
from .ranking import score_candidate, validate_pdf_text
from .supabase_terms import fetch_food_terms, fetch_nutrient_terms

PMC_OA_API = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
AUDIT_EVERY_N = 100

class FoodCompositionCrawler:
    def __init__(
        self,
        data_dir: str,
        supabase_url: str,
        supabase_key: str,
        target_pdfs: int = 12,
        query_limit: int = 40,
        food_term_limit: int = 80,
    ):
        self.data_dir = Path(data_dir)
        self.raw_pdf_dir = self.data_dir / "raw_pdfs"
        self.state_path = self.data_dir / "crawl_state.json"
        self.manifest_path = self.raw_pdf_dir / "_harvest_metadata.json"
        self.feedback_path = self.data_dir / "crawl_feedback.json"
        self.client = EuropePMCClient(page_size=query_limit)
        self.target_pdfs = target_pdfs
        self.query_limit = query_limit
        self.food_terms = fetch_food_terms(supabase_url, supabase_key, limit=food_term_limit)
        self.nutrient_terms = fetch_nutrient_terms(supabase_url, supabase_key, limit=max(24, food_term_limit // 2))
        self.state = self._load_state()
        self.feedback = self._load_feedback()

    def run(self, replace_existing: bool = False) -> Dict[str, object]:
        self.audit_reject_counter = int(self.state.get("audit_reject_counter", 0))
        if replace_existing and self.raw_pdf_dir.exists():
            shutil.rmtree(self.raw_pdf_dir)
        if replace_existing:
            self.state = {"seen_ids": []}
        self.raw_pdf_dir.mkdir(parents=True, exist_ok=True)

        accepted_records: List[DownloadRecord] = []
        rejected_records: List[DownloadRecord] = []
        seen_ids: Set[str] = set(self.state.get("seen_ids", []))
        candidates_by_id: Dict[str, CandidatePaper] = {}

        query_budget = self._build_queries()
        query_budget = self._prioritize_queries(query_budget)
        max_queries = min(60, max(15, self.target_pdfs * 6))
        if len(query_budget) > max_queries:
            query_budget = query_budget[:max_queries]
        for query in query_budget:
            candidates = self.client.search(query, limit=self.query_limit)
            for candidate in candidates:
                canonical_id = candidate.canonical_id
                if not canonical_id or canonical_id in seen_ids:
                    continue

                score, accepted, reasons = score_candidate(candidate, self.food_terms, self.nutrient_terms)
                candidate.score = score
                candidate.accepted = accepted
                candidate.reasons = reasons
                seen_ids.add(canonical_id)
                candidates_by_id[canonical_id] = candidate

        ranked_candidates = sorted(
            candidates_by_id.values(),
            key=lambda item: (item.accepted, item.score, item.year or ""),
            reverse=True,
        )

        for candidate in ranked_candidates:
            if len(accepted_records) >= self.target_pdfs:
                break

            if not candidate.accepted:
                if candidate.pdf_url or candidate.pmcid:
                    audit_flag = self._next_audit_flag()
                    if audit_flag:
                        record = self._download_candidate(
                            candidate,
                            force_audit=True,
                            skip_validation=True,
                            rejection_error="Rejected by metadata ranking",
                        )
                        rejected_records.append(record)
                    else:
                        rejected_records.append(self._skip_record(candidate, "Rejected by metadata ranking"))
                else:
                    rejected_records.append(self._skip_record(candidate, "Rejected by metadata ranking"))
                self._update_feedback(candidate, accepted=False, reason="metadata")
                continue

            record = self._download_candidate(candidate)
            if record.status == "success":
                accepted_records.append(record)
                self._update_feedback(candidate, accepted=True, reason="pdf")
            else:
                rejected_records.append(record)
                self._update_feedback(candidate, accepted=False, reason=record.error or "download")

        harvested_at = datetime.now(timezone.utc).isoformat()
        audit_count = sum(1 for record in rejected_records if record.audit)

        manifest = {
            "harvested_at": harvested_at,
            "query_count": len(self._build_queries()),
            "target_pdfs": self.target_pdfs,
            "accepted_count": len(accepted_records),
            "rejected_count": len(rejected_records),
            "food_term_sample": self.food_terms[:20],
            "nutrient_term_sample": self.nutrient_terms[:20],
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
        self._save_feedback()
        return manifest

    def _next_audit_flag(self) -> bool:
        self.audit_reject_counter += 1
        return self.audit_reject_counter % AUDIT_EVERY_N == 0

    def _build_queries(self) -> List[str]:
        proximate_panel = '("moisture" OR "protein" OR "fat" OR "ash" OR "carbohydrate" OR "fiber")'
        nutrient_panel = self._build_nutrient_or_query(self.nutrient_terms[:18])
        composition_bundle = (
            '("food composition" OR "food composition table" OR "proximate composition" '
            'OR "proximate analysis" OR "nutrient composition" OR "mineral content" '
            'OR "vitamin content" OR "fatty acid composition" OR "amino acid composition" '
            'OR "chemical composition" OR "chemical compositions")'
        )
        titleish_bundle = (
            '("chemical composition" OR "chemical compositions" OR "data on" OR '
            '"nutritional composition" OR "proximate composition" OR "mineral composition")'
        )
        method_bundle = '("table" OR "tables" OR "aoac" OR "analyzed" OR "determined" OR "content of" OR "analysis of")'
        negative_terms = (
            "effect OR health OR disease OR clinical trial OR microbiota OR review OR "
            "systematic review OR supplementation OR essential oil OR extract OR antioxidant "
            "OR antimicrobial OR insecticidal OR toxicity OR feed OR veterinary "
            "OR genome OR gene OR packaging OR nanoparticle OR erratum OR viscosity "
            "OR rheology OR rheological OR pasting OR dough OR gel OR emulsification "
            "OR water absorption OR swelling power OR solubility OR body composition "
            "OR energy allocation OR ecolog*"
        )

        queries = [
            f'({composition_bundle} AND {proximate_panel} AND {method_bundle}) AND OPEN_ACCESS:y AND IN_PMC:y NOT ({negative_terms})',
            f'("food composition table" OR "nutritional composition") AND {nutrient_panel} AND OPEN_ACCESS:y AND IN_PMC:y NOT ({negative_terms})',
            f'({titleish_bundle} AND {proximate_panel}) AND OPEN_ACCESS:y AND IN_PMC:y NOT ({negative_terms})',
            f'({composition_bundle}) AND OPEN_ACCESS:y AND IN_PMC:y NOT ({negative_terms})',
        ]

        for category in ("fruit", "vegetable", "grain", "tuber", "mushroom", "milk"):
            queries.append(
                f'("{category}" AND {composition_bundle}) AND OPEN_ACCESS:y AND IN_PMC:y NOT ({negative_terms})'
            )

        for food in self.food_terms[:60]:
            queries.append(
                f'("{food}" AND {composition_bundle}) AND OPEN_ACCESS:y AND IN_PMC:y NOT ({negative_terms})'
            )
            queries.append(
                f'("{food}" AND {composition_bundle} AND {proximate_panel}) AND OPEN_ACCESS:y AND IN_PMC:y NOT ({negative_terms})'
            )
            queries.append(
                f'("{food}" AND {nutrient_panel} AND {method_bundle}) AND OPEN_ACCESS:y AND IN_PMC:y NOT ({negative_terms})'
            )
            queries.append(
                f'("{food}" AND {titleish_bundle} AND {proximate_panel}) AND OPEN_ACCESS:y AND IN_PMC:y NOT ({negative_terms})'
            )
            if food in {"potato", "cassava", "rice", "wheat", "milk", "tomato", "banana", "fish", "mushroom", "maize", "corn", "soybean"}:
                queries.append(
                    f'("{food}" AND ("proximate composition" OR "mineral content" OR "vitamin content") AND ("edible" OR "raw" OR "food" OR "tuber" OR "fruit" OR "seed" OR "grain" OR "fillet" OR "milk")) AND OPEN_ACCESS:y AND IN_PMC:y NOT ({negative_terms})'
                )
                queries.append(
                    f'("{food}" AND ("chemical composition" OR "chemical compositions" OR "data on") AND ("food processing" OR "tuber" OR "fruit" OR "grain" OR "milk" OR "fillet" OR "edible")) AND OPEN_ACCESS:y AND IN_PMC:y NOT ({negative_terms})'
                )

        return queries


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
                audit=force_audit,
                file=str(destination.relative_to(self.data_dir.parent)),
                pmcid=candidate.pmcid,
                doi=candidate.doi,
                journal=candidate.journal,
                year=candidate.year,
                size_kb=max(1, round(len(content) / 1024)),
                pdf_url=candidate.pdf_url,
                error=rejection_error,
            )

        pdf_score, accepted, pdf_reasons = self._validate_downloaded_pdf(destination, candidate)
        combined_reasons = candidate.reasons + pdf_reasons
        if not accepted:
            candidate.reasons = combined_reasons
            candidate.score = round(candidate.score + pdf_score, 2)
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
                audit=True,
                file=str(destination.relative_to(self.data_dir.parent)),
                pmcid=candidate.pmcid,
                doi=candidate.doi,
                journal=candidate.journal,
                year=candidate.year,
                size_kb=max(1, round(len(content) / 1024)),
                pdf_url=candidate.pdf_url,
                error="Rejected by PDF validation",
            )

        candidate.reasons = combined_reasons
        candidate.score = round(candidate.score + pdf_score, 2)
        return DownloadRecord(
            status="success",
            title=candidate.title,
            score=candidate.score,
            source=candidate.source,
            query=candidate.query,
            reasons=combined_reasons,
            audit=False,
            file=str(destination.relative_to(self.data_dir.parent)),
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            size_kb=max(1, round(len(content) / 1024)),
            pdf_url=candidate.pdf_url,
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
            with urlopen(request, timeout=30) as response:
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
                    with urlopen(pow_request, timeout=30) as pow_response:
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
                    with urlopen(nested_request, timeout=30) as nested_response:
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
                timeout=60,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return b""

    def _validate_downloaded_pdf(self, path: Path, candidate: CandidatePaper) -> Tuple[float, bool, List[str]]:
        try:
            text = subprocess.check_output(
                ["pdftotext", str(path), "-"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return 0.0, False, [f"pdf text extraction failed: {exc}"]

        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 200:
            return 0.0, False, ["pdf text too short to validate"]
        return validate_pdf_text(text, candidate, self.food_terms, self.nutrient_terms)

    def _build_nutrient_or_query(self, nutrient_terms: List[str]) -> str:
        if not nutrient_terms:
            return '("moisture" OR "protein" OR "fat" OR "ash" OR "carbohydrate")'
        quoted = [f'"{term}"' for term in nutrient_terms[:18]]
        return "(" + " OR ".join(quoted) + ")"

    def _load_feedback(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        if not self.feedback_path.exists():
            return {"queries": {}, "foods": {}, "nutrients": {}, "reasons": {}}
        try:
            return json.loads(self.feedback_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"queries": {}, "foods": {}, "nutrients": {}, "reasons": {}}

    def _save_feedback(self) -> None:
        self._write_json(self.feedback_path, self.feedback)

    def _update_feedback(self, candidate: CandidatePaper, accepted: bool, reason: str) -> None:
        query = candidate.query or ""
        if query:
            self._bump_counter(self.feedback["queries"], query, accepted)
        food = self._extract_query_food(query)
        if food:
            self._bump_counter(self.feedback["foods"], food, accepted)
        for nutrient in self._extract_query_nutrients(query):
            self._bump_counter(self.feedback["nutrients"], nutrient, accepted)
        self._bump_reason(reason)

    def _bump_counter(self, bucket: Dict[str, Dict[str, int]], key: str, accepted: bool) -> None:
        stats = bucket.setdefault(key, {"seen": 0, "accepted": 0})
        stats["seen"] += 1
        if accepted:
            stats["accepted"] += 1

    def _bump_reason(self, reason: str) -> None:
        if not reason:
            return
        stats = self.feedback["reasons"].setdefault(reason, {"count": 0})
        stats["count"] += 1

    def _extract_query_food(self, query: str) -> str:
        match = re.match(r'^\("([^"]+)"', query or "")
        if not match:
            return ""
        return match.group(1).strip().lower()

    def _extract_query_nutrients(self, query: str) -> List[str]:
        hits: List[str] = []
        for term in self.nutrient_terms[:20]:
            if f'"{term}"' in query:
                hits.append(term)
        return hits

    def _prioritize_queries(self, queries: List[str]) -> List[str]:
        def score(q: str) -> float:
            stats = self.feedback.get("queries", {}).get(q, {})
            seen = stats.get("seen", 0)
            accepted = stats.get("accepted", 0)
            base = (accepted + 1) / (seen + 2)
            food = self._extract_query_food(q)
            if food:
                fstats = self.feedback.get("foods", {}).get(food, {})
                base += 0.5 * ((fstats.get("accepted", 0) + 1) / (fstats.get("seen", 0) + 2))
            return base
        return sorted(queries, key=score, reverse=True)

    def _solve_pmc_pow(self, html: str) -> Optional[str]:
        return solve_pmc_pow(html)

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
            audit=audit,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            pdf_url=candidate.pdf_url,
            error=error,
        )

    def _failed_record(self, candidate: CandidatePaper, error: str, audit: bool = False) -> DownloadRecord:
        return DownloadRecord(
            status="failed",
            title=candidate.title,
            score=candidate.score,
            source=candidate.source,
            query=candidate.query,
            reasons=candidate.reasons,
            audit=audit,
            pmcid=candidate.pmcid,
            doi=candidate.doi,
            journal=candidate.journal,
            year=candidate.year,
            pdf_url=candidate.pdf_url,
            error=error,
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
