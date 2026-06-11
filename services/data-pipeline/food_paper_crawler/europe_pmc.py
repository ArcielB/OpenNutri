from __future__ import annotations

import json
import http.client
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote
from urllib.request import urlopen
import xml.etree.ElementTree as ET

from .models import CandidatePaper


# urllib only wraps connect-phase failures in URLError; timeouts and resets while
# reading the response surface as raw OSError subclasses (TimeoutError,
# ConnectionResetError) and RemoteDisconnected is an HTTPException. Catch them all
# so one flaky upstream request degrades to "no results" instead of crashing the run.
TRANSIENT_NETWORK_ERRORS = (OSError, http.client.HTTPException)


class EuropePMCClient:
    def __init__(self, page_size: int = 50):
        self.page_size = page_size
        self.base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        self.timeout_seconds = 8

    def search(self, query: str, limit: int) -> List[CandidatePaper]:
        url = (
            f"{self.base_url}?query={quote(query)}&format=json"
            f"&pageSize={min(limit, self.page_size)}&resultType=core"
        )
        try:
            with urlopen(url, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except TRANSIENT_NETWORK_ERRORS:
            return self._search_ncbi(query, limit)

        results = payload.get("resultList", {}).get("result", [])
        return [self._to_candidate(item, query) for item in results]

    def _to_candidate(self, item: Dict[str, object], query: str) -> CandidatePaper:
        pmcid = item.get("pmcid")
        if isinstance(pmcid, str) and not pmcid.startswith("PMC"):
            pmcid = f"PMC{pmcid}"

        full_text_urls = item.get("fullTextUrlList", {}).get("fullTextUrl", [])
        pdf_url = self._extract_pdf_url(full_text_urls, pmcid)

        authors = []
        author_string = item.get("authorString")
        if isinstance(author_string, str):
            authors = [part.strip() for part in author_string.split(",") if part.strip()]

        return CandidatePaper(
            source="europepmc",
            query=query,
            external_id=str(item.get("id") or pmcid or item.get("doi") or ""),
            source_record_id=str(item.get("id") or pmcid or item.get("doi") or ""),
            pmcid=pmcid,
            doi=item.get("doi"),
            title=str(item.get("title") or "").strip(),
            abstract=str(item.get("abstractText") or "").strip(),
            journal=str(item.get("journalTitle") or "").strip() or None,
            year=str(item.get("pubYear") or "").strip() or None,
            authors=authors,
            pdf_url=pdf_url,
            landing_url=str(item.get("fullTextUrl") or item.get("source") or "").strip() or None,
        )

    def _extract_pdf_url(self, full_text_urls: object, pmcid: Optional[str]) -> Optional[str]:
        urls: Iterable[Dict[str, object]]
        if isinstance(full_text_urls, dict):
            urls = [full_text_urls]
        elif isinstance(full_text_urls, list):
            urls = [entry for entry in full_text_urls if isinstance(entry, dict)]
        else:
            urls = []

        for entry in urls:
            url = str(entry.get("url") or "").strip()
            if not url:
                continue
            url = self._normalize_pdf_url(url)
            style = str(entry.get("documentStyle") or "").lower()
            if style == "pdf" or url.lower().endswith(".pdf"):
                return url

        if pmcid:
            return f"https://europepmc.org/api/getPdf?pmcid={pmcid}"
        return None

    def _search_ncbi(self, query: str, limit: int) -> List[CandidatePaper]:
        ncbi_query = self._to_ncbi_query(query)
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pmc&term={quote(ncbi_query)}&retmode=json&retmax={min(limit, self.page_size)}"
        )
        try:
            with urlopen(search_url, timeout=self.timeout_seconds) as response:
                search_payload = json.loads(response.read().decode("utf-8"))
        except TRANSIENT_NETWORK_ERRORS:
            return []

        ids = search_payload.get("esearchresult", {}).get("idlist", [])
        candidates: List[CandidatePaper] = []
        for identifier in ids:
            candidate = self._fetch_ncbi_candidate(identifier, query)
            if candidate:
                candidates.append(candidate)
        return candidates

    def _fetch_ncbi_candidate(self, identifier: str, query: str) -> Optional[CandidatePaper]:
        fetch_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pmc&id={quote(identifier)}&retmode=xml"
        )
        try:
            with urlopen(fetch_url, timeout=self.timeout_seconds) as response:
                xml_text = response.read().decode("utf-8", errors="ignore")
        except TRANSIENT_NETWORK_ERRORS:
            return None

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return None

        article = root.find(".//article")
        if article is None:
            return None

        title = self._collect_text(article.find(".//article-title"))
        abstract = self._collect_text(article.find(".//abstract"))
        journal = self._collect_text(article.find(".//journal-title"))
        year = self._collect_text(article.find(".//pub-date/year"))
        doi = None
        for article_id in article.findall(".//article-id"):
            if article_id.attrib.get("pub-id-type") == "doi":
                doi = self._collect_text(article_id)
                break

        pmcid = f"PMC{identifier}" if not str(identifier).startswith("PMC") else str(identifier)
        return CandidatePaper(
            source="ncbi-pmc",
            query=query,
            external_id=pmcid,
            source_record_id=pmcid,
            pmcid=pmcid,
            doi=doi,
            title=title,
            abstract=abstract,
            journal=journal or None,
            year=year or None,
            authors=[],
            pdf_url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/",
            landing_url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
        )

    def _to_ncbi_query(self, query: str) -> str:
        rewritten = query.replace("OPEN_ACCESS:y", '"open access"[filter]')
        rewritten = rewritten.replace("AND IN_PMC:y", "")
        rewritten = rewritten.replace("IN_PMC:y AND ", "")
        rewritten = rewritten.replace("IN_PMC:y", "")
        return rewritten

    def _collect_text(self, node: Optional[ET.Element]) -> str:
        if node is None:
            return ""
        return " ".join(part.strip() for part in node.itertext() if part and part.strip())

    def _normalize_pdf_url(self, url: str) -> str:
        # Canonicalize any PMC PDF URL to the direct getPdf endpoint, which
        # serves application/pdf with CORS headers and no redirect (required for
        # in-browser react-pdf rendering). Already-canonical URLs pass through.
        if "europepmc.org/api/getpdf" in url.lower():
            return url
        pmcid = ""
        if "europepmc.org/articles/PMC" in url:
            pmcid = url.split("/articles/")[-1].split("?")[0].split("/")[0]
        elif "www.ncbi.nlm.nih.gov/pmc/articles/PMC" in url:
            pmcid = url.split("/pmc/articles/")[-1].split("?")[0].split("/")[0]
        elif "pmc.ncbi.nlm.nih.gov/articles/PMC" in url:
            pmcid = url.split("/articles/")[-1].split("?")[0].split("/")[0]
        if pmcid:
            return f"https://europepmc.org/api/getPdf?pmcid={pmcid}"
        return url
