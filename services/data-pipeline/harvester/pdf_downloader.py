"""
PDF Downloader - Multi-strategy PMC PDF retrieval.
"""

import re
import time
from pathlib import Path
from typing import List, Tuple

import requests

PMC_OA_API = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"


class PDFDownloader:
    def __init__(self, email: str, request_delay: float = 1.0, timeout: int = 60):
        self.email = email
        self.request_delay = request_delay
        self.timeout = timeout
        self.session = requests.Session()

    def _get_pdf_candidates(self, pmc_id: str) -> List[Tuple[str, str]]:
        candidates: List[Tuple[str, str]] = []

        # Strategy 1: Europe PMC (fast check)
        try:
            epmc_xml = f"https://www.ebi.ac.uk/europepmc/webservices/rest/PMC{pmc_id}/fullTextXML"
            resp = self.session.get(epmc_xml, timeout=20)
            if resp.status_code == 200:
                pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC{pmc_id}&blobtype=pdf"
                candidates.append((pdf_url, "europepmc"))
        except Exception:
            pass

        # Strategy 2: NCBI OA API - FTP or HTTPS links
        try:
            resp = self.session.get(PMC_OA_API, params={"id": f"PMC{pmc_id}"}, timeout=20)
            if resp.status_code == 200:
                content = resp.text
                if "idIsNotOpenAccess" not in content and "error" not in content.lower():
                    ftp_matches = re.findall(r'href="(ftp://[^\"]+\.pdf)"', content)
                    for ftp_url in ftp_matches:
                        https_url = ftp_url.replace("ftp://ftp.ncbi.nlm.nih.gov", "https://ftp.ncbi.nlm.nih.gov")
                        candidates.append((https_url, "ncbi_oa_ftp"))

                    https_matches = re.findall(r'href="(https://[^\"]+\.pdf[^\"]*)"', content)
                    for https_url in https_matches:
                        candidates.append((https_url, "ncbi_oa_https"))
        except Exception:
            pass

        # Strategy 3: Direct PMC URL
        candidates.append((f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/", "direct_fallback"))

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for url, strategy in candidates:
            if url not in seen:
                seen.add(url)
                deduped.append((url, strategy))
        return deduped

    def download_pdf(self, pmc_id: str, out_dir: Path) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / f"PMC{pmc_id}.pdf"

        if file_path.exists():
            return {"status": "skipped", "pmc_id": pmc_id, "reason": "already_exists", "file": str(file_path)}

        candidates = self._get_pdf_candidates(pmc_id)
        last_error = None

        for pdf_url, strategy in candidates:
            try:
                resp = self.session.get(
                    pdf_url,
                    timeout=self.timeout,
                    stream=True,
                    allow_redirects=True,
                    headers={
                        "User-Agent": f"OpenNutri_PDFHarvester/1.0 (Contact: {self.email})"
                    }
                )

                content_type = resp.headers.get("Content-Type", "")
                content = resp.content
                first_bytes = content[:10] if content else b""
                is_pdf = b"%PDF" in first_bytes or "pdf" in content_type.lower()

                if resp.status_code == 200 and is_pdf:
                    with open(file_path, "wb") as f:
                        f.write(content)
                    time.sleep(self.request_delay)
                    return {
                        "status": "success",
                        "pmc_id": pmc_id,
                        "file": str(file_path),
                        "size_kb": file_path.stat().st_size // 1024,
                        "strategy": strategy,
                        "pdf_url": pdf_url,
                    }
                last_error = f"Not a PDF (status {resp.status_code}, type {content_type})"
            except Exception as e:
                last_error = str(e)

        return {"status": "failed", "pmc_id": pmc_id, "error": last_error or "no_pdf_candidates"}
