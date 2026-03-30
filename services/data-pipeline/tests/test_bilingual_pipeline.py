from __future__ import annotations

import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from food_paper_crawler.crawler_v2 import FoodCompositionCrawlerV2
from food_paper_crawler.feedback.update_terms import (
    build_concept_feedback,
    build_search_pair_feedback,
    classify_papers_by_language,
    dedupe_search_hits,
)
from food_paper_crawler.models import CandidatePaper, DiscoveryHit, DownloadRecord, QuerySpec, SearchTask
from food_paper_crawler.ranking import score_candidate, validate_pdf_text
from food_paper_crawler.search_sources import DergiParkOAISource, OAI_NS, OpenAlexSearchSource, SemanticScholarSearchSource
from food_paper_crawler import supabase_terms
from scripts import upload_to_supabase


class SearchSourceTests(unittest.TestCase):
    def test_turkish_metadata_query_is_concise(self) -> None:
        spec = QuerySpec(
            query='(("gıda bileşimi") AND ("tablo" OR "analiz")) AND IN_PMC:y',
            keywords=("gıda bileşimi", "besin bileşimi", "tablo", "analiz"),
            template_id="base_core_composition",
            source_term=None,
            term_type="base",
            language="tr",
            query_phrase="gıda bileşimi",
        )
        self.assertEqual(OpenAlexSearchSource().query_text(spec), '"gıda bileşimi"')
        self.assertEqual(SemanticScholarSearchSource().query_text(spec), '"gıda bileşimi"')

    def test_turkish_learned_metadata_query_keeps_only_concept_and_phrase(self) -> None:
        spec = QuerySpec(
            query='("elma" AND "gıda bileşimi") AND IN_PMC:y',
            keywords=("elma", "gıda bileşimi", "food composition", "mg/100g", "g/100g"),
            template_id="food_phrase_core",
            source_term="elma",
            term_type="food",
            language="tr",
            query_phrase="gıda bileşimi",
        )
        expected = 'elma "gıda bileşimi"'
        self.assertEqual(OpenAlexSearchSource().query_text(spec), expected)
        self.assertEqual(SemanticScholarSearchSource().query_text(spec), expected)

    def test_dergipark_parser_handles_oai_dc_namespace(self) -> None:
        xml_text = """<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"
         xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <ListRecords>
    <record>
      <header>
        <identifier>oai:dergipark.org.tr:article/10</identifier>
      </header>
      <metadata>
        <oai_dc:dc>
          <dc:title>Yenilebilir Mantarların Besin Bileşimi</dc:title>
          <dc:creator>Test Author</dc:creator>
          <dc:description>Bu çalışma mantarların besin bileşimini incelemektedir.</dc:description>
          <dc:identifier>https://dergipark.org.tr/en/pub/test/article/10</dc:identifier>
          <dc:identifier>https://dergipark.org.tr/en/download/article-file/10.pdf</dc:identifier>
          <dc:source>Test Journal</dc:source>
          <dc:date>2025-01-01</dc:date>
          <dc:language>tr</dc:language>
        </oai_dc:dc>
      </metadata>
    </record>
  </ListRecords>
</OAI-PMH>
"""
        root = ET.fromstring(xml_text)
        record_node = root.find(".//oai:record", OAI_NS)
        self.assertIsNotNone(record_node)
        with tempfile.TemporaryDirectory() as tmpdir:
            source = DergiParkOAISource(data_dir=Path(tmpdir))
            parsed = source._parse_record(record_node)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["language"], "tr")
        self.assertEqual(parsed["title"], "Yenilebilir Mantarların Besin Bileşimi")
        self.assertEqual(parsed["pdf_url"], "https://dergipark.org.tr/en/download/article-file/10.pdf")

    def test_dergipark_weighted_matching_prefers_stronger_turkish_candidate(self) -> None:
        spec = QuerySpec(
            query='("gıda bileşimi" AND ("tablo" OR "analiz")) AND IN_PMC:y',
            keywords=("gıda bileşimi", "besin bileşimi", "tablo", "analiz"),
            template_id="base_core_composition",
            source_term=None,
            term_type="base",
            language="tr",
            query_phrase="gıda bileşimi",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            source = DergiParkOAISource(data_dir=Path(tmpdir), scan_budget=1)
            source._records = [
                {
                    "article_url": "https://dergipark.org.tr/tr/pub/test/article/weak",
                    "journal_slug": "test",
                    "journal_title": "Test Journal",
                    "title": "Yerel ürünlerde analiz",
                    "abstract": "Bu çalışma ürünleri tanımlar.",
                    "keywords": [],
                    "language": "tr",
                    "article_type": "Araştırma Makalesi",
                    "pdf_url": None,
                    "last_seen_at": "2026-03-30T00:00:00+00:00",
                    "year": "2023",
                },
                {
                    "article_url": "https://dergipark.org.tr/tr/pub/test/article/strong",
                    "journal_slug": "test",
                    "journal_title": "Food Composition Journal",
                    "title": "Mantarların Besin Bileşimi ve Mineral İçeriği",
                    "abstract": "Tablo halinde analiz sonuçları verilmiştir.",
                    "keywords": ["gıda bileşimi", "mineral içeriği"],
                    "language": "tr",
                    "article_type": "Araştırma Makalesi",
                    "pdf_url": "https://example.com/strong.pdf",
                    "last_seen_at": "2026-03-30T00:00:00+00:00",
                    "year": "2025",
                },
                {
                    "article_url": "https://dergipark.org.tr/tr/pub/test/article/medium",
                    "journal_slug": "test",
                    "journal_title": "Test Journal",
                    "title": "Mantarlarda gıda bileşimi",
                    "abstract": "Tanımlayıcı analiz özeti",
                    "keywords": [],
                    "language": "tr",
                    "article_type": "Araştırma Makalesi",
                    "pdf_url": None,
                    "last_seen_at": "2026-03-30T00:00:00+00:00",
                    "year": "2024",
                },
            ]
            matches = source.search(spec, limit=5)

        self.assertEqual(
            [item.external_id for item in matches],
            [
                "https://dergipark.org.tr/tr/pub/test/article/strong",
                "https://dergipark.org.tr/tr/pub/test/article/medium",
            ],
        )

    def test_dergipark_refresh_indexes_archive_articles_and_reuses_existing_rows(self) -> None:
        spec = QuerySpec(
            query='("gıda bileşimi" AND ("tablo" OR "analiz")) AND IN_PMC:y',
            keywords=("gıda bileşimi", "besin bileşimi", "tablo", "analiz"),
            template_id="base_core_composition",
            source_term=None,
            term_type="base",
            language="tr",
            query_phrase="gıda bileşimi",
        )

        archive_html = """
<html><body>
  <a href="/tr/pub/gida/issue/100412">Cilt 51 Sayı 1</a>
</body></html>
"""
        issue_html = """
<html><body>
  <a href="/tr/pub/gida/article/1776088">Fatty acid compositions</a>
  <a href="/tr/download/article-file/5204385">PDF</a>
</body></html>
"""
        article_html = """
<html><head>
  <meta name="citation_journal_title" content="Gıda">
  <meta name="citation_title" content="FATTY ACID COMPOSITIONS OF SOME WILD MUSHROOMS">
  <meta name="citation_doi" content="10.15237/gida.GD25114">
  <meta name="citation_abstract" content="The food composition and fatty acid compositions of wild mushrooms were examined and analysis tables were reported.">
  <meta name="citation_keywords" content="yabani mantarlar; gıda bileşimi; yağ asidi bileşimi; analiz">
  <meta name="citation_pdf_url" content="/tr/download/article-file/5204385">
  <meta name="citation_language" content="tr">
  <meta name="citation_article_type" content="Araştırma Makalesi">
  <meta name="citation_publication_date" content="2026-01-21">
</head><body></body></html>
"""

        class FakeDergiParkSource(DergiParkOAISource):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fetch_log: list[str] = []
                self.responses: dict[str, str] = {}

            def _fetch_text(self, url: str) -> str:
                self.fetch_log.append(url)
                if url not in self.responses:
                    raise RuntimeError(url)
                return self.responses[url]

        with tempfile.TemporaryDirectory() as tmpdir:
            source = FakeDergiParkSource(data_dir=Path(tmpdir), max_issues_per_journal=4)
            source.registry_path.write_text('[{"slug": "gida", "enabled": true}]', encoding="utf-8")
            source.responses = {
                "https://dergipark.org.tr/tr/pub/gida/archive": archive_html,
                "https://dergipark.org.tr/tr/pub/gida/issue/100412": issue_html,
                "https://dergipark.org.tr/tr/pub/gida/article/1776088": article_html,
            }
            report = source.refresh_index(journal_limit=1, max_issues_per_journal=4)
            matches = source.search(spec, limit=1)
            second_report = source.refresh_index(journal_limit=1, max_issues_per_journal=4)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].external_id, "https://dergipark.org.tr/tr/pub/gida/article/1776088")
        self.assertEqual(matches[0].pdf_url, "https://dergipark.org.tr/tr/download/article-file/5204385")
        self.assertEqual(report["journal_count"], 1)
        self.assertEqual(report["article_count"], 1)
        self.assertEqual(report["articles_with_pdf_url"], 1)
        self.assertEqual(second_report["article_count"], 1)
        self.assertEqual(sum(1 for url in source.fetch_log if "/article/" in url), 1)

    def test_dergipark_allows_simple_phrase_inflection_matches(self) -> None:
        spec = QuerySpec(
            query='("fatty acid composition" AND "analysis")',
            keywords=("fatty acid composition", "analysis", "food composition"),
            template_id="base_nutrient_content",
            source_term=None,
            term_type="base",
            language="en",
            query_phrase="fatty acid composition",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            source = DergiParkOAISource(data_dir=Path(tmpdir))
            source._records = [
                {
                    "article_url": "https://dergipark.org.tr/tr/pub/test/article/1",
                    "journal_slug": "test",
                    "journal_title": "Gıda",
                    "title": "Fatty acid compositions of some wild mushrooms",
                    "abstract": "Analysis tables were reported for mushroom samples.",
                    "keywords": [],
                    "doi": "10.1000/test",
                    "pdf_url": "https://dergipark.org.tr/tr/download/article-file/1",
                    "language": "en",
                    "year": "2026",
                    "article_type": "Research Article",
                    "authors": ["A. Author"],
                    "last_seen_at": "2026-03-30T00:00:00+00:00",
                }
            ]

            matches = source.search(spec, limit=5)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].title, "Fatty acid compositions of some wild mushrooms")


class FeedbackTests(unittest.TestCase):
    def test_workflow_language_beats_heuristic_detection(self) -> None:
        papers = [
            {
                "id": 1,
                "title": "Food composition table update",
                "abstract": "English abstract that would normally classify as EN.",
                "workflow_language": "tr",
            }
        ]
        buckets = classify_papers_by_language(papers)
        self.assertEqual(buckets["tr"], {1})
        self.assertEqual(buckets["en"], set())


class FoodTermTests(unittest.TestCase):
    def test_fetch_food_terms_ignores_local_fdc_noise(self) -> None:
        with patch.object(
            supabase_terms,
            "_fetch_remote_food_terms_by_language",
            return_value={"en": [], "tr": []},
        ), patch.object(
            supabase_terms,
            "_load_local_food_terms",
            return_value=["niacin", "kroger", "acerola juice"],
        ):
            terms = supabase_terms.fetch_food_terms_by_language("url", "key", limit=20)
        self.assertNotIn("niacin", terms["en"])
        self.assertNotIn("kroger", terms["en"])
        self.assertNotIn("acerola juice", terms["en"])


class RankingTests(unittest.TestCase):
    def test_metadata_negative_signal_is_soft_not_veto(self) -> None:
        candidate = CandidatePaper(
            source="openalex",
            query="food composition",
            external_id="paper-1",
            source_record_id="paper-1",
            pmcid=None,
            doi=None,
            title="Mushroom food composition and mineral content",
            abstract=(
                "The food composition of edible mushrooms was analyzed in table 1 with protein, fat, "
                "calcium, iron, potassium and moisture reported. Growth conditions were also noted."
            ),
            journal="Food Chemistry",
            year="2025",
        )
        score, acceptable, reasons = score_candidate(
            candidate,
            food_terms=["mushroom", "milk"],
            nutrient_terms=["protein", "fat", "calcium", "iron", "potassium", "moisture"],
        )
        self.assertTrue(acceptable)
        self.assertGreaterEqual(score, 8)
        self.assertIn("negative signal: growth", reasons)

    def test_pdf_validation_ignores_reference_section_negative_terms(self) -> None:
        candidate = CandidatePaper(
            source="dergipark",
            query="fatty acid composition",
            external_id="paper-2",
            source_record_id="paper-2",
            pmcid=None,
            doi="10.1000/test",
            title="Fatty acid composition of wild mushrooms",
            abstract="Composition study",
            journal="Gıda",
            year="2026",
        )
        body = (
            "Fatty acid composition of edible mushroom samples was determined by gc and reported in table 1. "
            "Moisture protein fat lipid ash fiber carbohydrate calcium iron potassium phosphorus magnesium "
            "values were measured in mg/100 g and % for mushroom samples. "
        ) * 10
        text = body + " References growth review association between unrelated studies. "
        score, acceptable, reasons = validate_pdf_text(
            text,
            candidate,
            food_terms=["mushroom", "milk"],
            nutrient_terms=["moisture", "protein", "fat", "lipid", "ash", "fiber", "carbohydrate", "calcium", "iron", "potassium", "phosphorus", "magnesium"],
        )
        self.assertTrue(acceptable)
        self.assertGreaterEqual(score, 18)
        self.assertNotIn("negative signal: growth", reasons)


class CrawlerQuotaTests(unittest.TestCase):
    def make_candidate(self, title: str, language: str, score: float) -> CandidatePaper:
        candidate = CandidatePaper(
            source="source",
            query="query",
            external_id=title,
            source_record_id=title,
            pmcid=None,
            doi=None,
            title=title,
            abstract="abstract",
            journal=None,
            year=None,
        )
        candidate.filter_pass = True
        candidate.filter_score = score
        candidate.search_gate_score = score
        candidate.workflow_language = language
        candidate.pdf_url = f"https://example.com/{title}.pdf"
        return candidate

    def test_language_query_budget_uses_only_active_languages(self) -> None:
        crawler = object.__new__(FoodCompositionCrawlerV2)
        crawler.target_pdfs_by_language = {"en": 0, "tr": 6}
        crawler.max_queries = 8
        crawler.state = {"language_remainder_cursor": 0}
        budgets = crawler._language_query_budget()
        self.assertEqual(budgets["en"], 0)
        self.assertEqual(budgets["tr"], 8)

    def test_concept_pool_uses_learned_term_scores(self) -> None:
        crawler = object.__new__(FoodCompositionCrawlerV2)
        crawler.food_terms_by_language = {"en": ["apple", "spinach"], "tr": []}
        crawler.nutrient_terms_by_language = {"en": ["protein", "calcium"], "tr": []}
        crawler.concept_scores_by_language = {
            "en": {"spinach": 2.0, "calcium": 1.5, "protein": 0.25},
            "tr": {},
        }
        pool = crawler._build_concept_pool("en")
        self.assertEqual(
            pool[:4],
            [
                ("food", "spinach"),
                ("nutrient", "calcium"),
                ("food", "apple"),
                ("nutrient", "protein"),
            ],
        )

    def test_acquire_candidates_respects_language_targets(self) -> None:
        crawler = object.__new__(FoodCompositionCrawlerV2)
        crawler.target_pdfs_by_language = {"en": 1, "tr": 1}
        crawler._next_audit_flag = lambda: False
        crawler._skip_record = lambda candidate, error, audit=False: DownloadRecord(
            status="skipped",
            title=candidate.title,
            score=candidate.score,
            source=candidate.source,
            query=candidate.query,
            reasons=[],
            workflow_language=candidate.workflow_language,
        )
        crawler._download_candidate = lambda candidate: DownloadRecord(
            status="success",
            title=candidate.title,
            score=candidate.filter_score,
            source=candidate.source,
            query=candidate.query,
            reasons=[],
            workflow_language=candidate.workflow_language,
        )

        accepted, rejected = crawler._acquire_candidates(
            [
                self.make_candidate("en-strong", "en", 10.0),
                self.make_candidate("en-overflow", "en", 9.0),
                self.make_candidate("tr-strong", "tr", 8.0),
            ]
        )
        self.assertEqual([record.title for record in accepted], ["en-strong", "tr-strong"])
        self.assertEqual(rejected, [])


class CrawlerStateTests(unittest.TestCase):
    def make_candidate(
        self,
        title: str,
        *,
        year: str | None = "2025",
        journal: str | None = "Journal",
    ) -> CandidatePaper:
        return CandidatePaper(
            source="openalex",
            query="food composition",
            external_id=title,
            source_record_id=title,
            pmcid=None,
            doi=None,
            title=title,
            abstract="abstract",
            journal=journal,
            year=year,
        )

    def make_crawler(self) -> FoodCompositionCrawlerV2:
        crawler = object.__new__(FoodCompositionCrawlerV2)
        crawler.state = {"paper_states": {}, "seen_ids": []}
        return crawler

    def test_terminal_accept_records_acquisition_stage(self) -> None:
        crawler = self.make_crawler()
        candidate = self.make_candidate("accepted-paper")
        accepted = DownloadRecord(
            status="success",
            title=candidate.title,
            score=3.0,
            source=candidate.source,
            query=candidate.query,
            reasons=[],
            canonical_key=candidate.canonical_key,
            workflow_language="en",
            decision_stage="acquisition",
        )
        crawler._record_terminal_states([candidate], [], [accepted], [])
        self.assertEqual(
            crawler.state["paper_states"][candidate.canonical_key],
            {"decision": "accepted", "stage": "acquisition"},
        )

    def test_search_gate_reject_records_terminal_state(self) -> None:
        crawler = self.make_crawler()
        candidate = self.make_candidate("search-gate-reject")
        hit = DiscoveryHit(
            canonical_key=candidate.canonical_key,
            source="openalex",
            source_record_id="search-gate-reject",
            external_id="search-gate-reject",
            pmcid=None,
            doi=None,
            title=candidate.title,
            abstract=candidate.abstract,
            workflow_language="en",
            query="food composition",
            template_id="base_core_composition",
            source_term=None,
            term_type="base",
            query_phrase="food composition",
            search_gate_score=-1.0,
            search_gate_pass=False,
        )
        crawler._record_terminal_states([], [hit], [], [])
        self.assertEqual(
            crawler.state["paper_states"][candidate.canonical_key],
            {"decision": "rejected", "stage": "search_gate"},
        )

    def test_metadata_reject_records_terminal_state(self) -> None:
        crawler = self.make_crawler()
        candidate = self.make_candidate("metadata-reject")
        rejected = DownloadRecord(
            status="skipped",
            title=candidate.title,
            score=0.5,
            source=candidate.source,
            query=candidate.query,
            reasons=[],
            canonical_key=candidate.canonical_key,
            workflow_language="en",
            decision_stage="metadata_filter",
        )
        crawler._record_terminal_states([candidate], [], [], [rejected])
        self.assertEqual(
            crawler.state["paper_states"][candidate.canonical_key],
            {"decision": "rejected", "stage": "metadata_filter"},
        )

    def test_pdf_validation_failure_records_terminal_state(self) -> None:
        crawler = self.make_crawler()
        candidate = self.make_candidate("pdf-validation-reject")
        rejected = DownloadRecord(
            status="failed",
            title=candidate.title,
            score=1.5,
            source=candidate.source,
            query=candidate.query,
            reasons=[],
            canonical_key=candidate.canonical_key,
            workflow_language="en",
            decision_stage="pdf_validation",
        )
        crawler._record_terminal_states([candidate], [], [], [rejected])
        self.assertEqual(
            crawler.state["paper_states"][candidate.canonical_key],
            {"decision": "rejected", "stage": "pdf_validation"},
        )

    def test_quota_skips_do_not_create_terminal_state(self) -> None:
        crawler = self.make_crawler()
        candidate = self.make_candidate("quota-skip")
        crawler._record_terminal_states([candidate], [], [], [])
        self.assertEqual(crawler.state["paper_states"], {})

    def test_recorded_terminal_keys_are_skipped_during_search(self) -> None:
        candidate = self.make_candidate("already-decided")

        class FakeSearchSource:
            def search(self, spec: QuerySpec, limit: int) -> list[CandidatePaper]:
                return [candidate]

        crawler = self.make_crawler()
        crawler.search_sources = {"openalex": FakeSearchSource()}
        crawler.query_limit = 10
        task = SearchTask(
            source="openalex",
            spec=QuerySpec(
                query="food composition",
                keywords=("food composition",),
                template_id="base_core_composition",
                source_term=None,
                term_type="base",
                language="en",
                query_phrase="food composition",
            ),
            query_text="food composition",
        )

        candidates, hits, _, stats = crawler._search_candidates([task], {candidate.canonical_key})
        self.assertEqual(candidates, [])
        self.assertEqual(hits, [])
        self.assertEqual(next(iter(stats.values()))["skipped_seen"], 1)

    def test_non_pmc_filenames_use_identity_hash(self) -> None:
        crawler = self.make_crawler()
        candidate_one = self.make_candidate("same title", year="2024")
        candidate_two = self.make_candidate("same title", year="2025")
        filename_one = crawler._build_filename(candidate_one)
        filename_two = crawler._build_filename(candidate_two)
        self.assertTrue(filename_one.startswith("paper_"))
        self.assertTrue(filename_one.endswith(".pdf"))
        self.assertNotEqual(filename_one, filename_two)

    def test_run_summary_counts_hits_and_rejections_by_stage(self) -> None:
        crawler = self.make_crawler()
        crawler.search_sources = {"openalex": object(), "dergipark": object()}
        candidate = self.make_candidate("summary-paper")
        candidate.workflow_language = "tr"
        candidate.filter_pass = True
        hit_pass = DiscoveryHit(
            canonical_key=candidate.canonical_key,
            source="dergipark",
            source_record_id="summary-paper",
            external_id="summary-paper",
            pmcid=None,
            doi=None,
            title=candidate.title,
            abstract=candidate.abstract,
            workflow_language="tr",
            query="gıda bileşimi",
            template_id="base_core_composition",
            source_term=None,
            term_type="base",
            query_phrase="gıda bileşimi",
            search_gate_score=1.0,
            search_gate_pass=True,
        )
        hit_reject = DiscoveryHit(
            canonical_key="title:reject",
            source="dergipark",
            source_record_id="reject",
            external_id="reject",
            pmcid=None,
            doi=None,
            title="reject",
            abstract="reject",
            workflow_language="tr",
            query="gıda bileşimi",
            template_id="base_core_composition",
            source_term=None,
            term_type="base",
            query_phrase="gıda bileşimi",
            search_gate_score=-1.0,
            search_gate_pass=False,
        )
        accepted = DownloadRecord(
            status="success",
            title=candidate.title,
            score=3.0,
            source="dergipark",
            query=candidate.query,
            reasons=[],
            canonical_key=candidate.canonical_key,
            workflow_language="tr",
            decision_stage="acquisition",
        )
        rejected = DownloadRecord(
            status="failed",
            title="pdf-fetch-fail",
            score=0.0,
            source="dergipark",
            query="gıda bileşimi",
            reasons=[],
            canonical_key="title:fetch-fail",
            workflow_language="tr",
            decision_stage="pdf_fetch",
        )

        summary = crawler._build_run_summary([candidate], [hit_pass, hit_reject], [accepted], [rejected])
        self.assertEqual(summary["languages"]["tr"]["hits"], 2)
        self.assertEqual(summary["languages"]["tr"]["search_gate_pass"], 1)
        self.assertEqual(summary["languages"]["tr"]["metadata_pass"], 1)
        self.assertEqual(summary["languages"]["tr"]["pdf_fetch_fail"], 1)
        self.assertEqual(summary["languages"]["tr"]["accepted"], 1)
        self.assertEqual(summary["sources"]["dergipark"]["hits"], 2)
        self.assertEqual(summary["rejections"]["search_gate"], 1)
        self.assertEqual(summary["rejections"]["pdf_fetch"], 1)


class FeedbackDeduplicationTests(unittest.TestCase):
    def test_duplicate_search_hits_do_not_inflate_feedback_retrieval_counts(self) -> None:
        rows = [
            {
                "paper_id": 1,
                "canonical_key": "doi:10.1000/test",
                "source": "openalex",
                "template_id": "food_phrase_core",
                "source_term": "spinach",
                "workflow_language": "en",
                "title": "Spinach food composition",
                "abstract": "Measured nutrient values.",
                "query_text": 'spinach "food composition"',
                "query_phrase": "food composition",
                "search_gate_pass": True,
                "filter_pass": True,
                "is_duplicate": False,
            },
            {
                "paper_id": 1,
                "canonical_key": "doi:10.1000/test",
                "source": "openalex",
                "template_id": "food_phrase_core",
                "source_term": "spinach",
                "workflow_language": "en",
                "title": "Spinach food composition",
                "abstract": "Measured nutrient values.",
                "query_text": 'spinach "food composition"',
                "query_phrase": "food composition",
                "search_gate_pass": True,
                "filter_pass": True,
                "is_duplicate": False,
            },
        ]

        deduped = dedupe_search_hits(rows)
        self.assertEqual(len(deduped), 1)

        pair_scores, _ = build_search_pair_feedback(deduped, {1}, set(), language="en")
        self.assertEqual(pair_scores[0]["retrieved"], 1)
        self.assertEqual(pair_scores[0]["novel_positive_count"], 1)

        concept_scores = build_concept_feedback(deduped, {1}, set(), language="en")
        self.assertEqual(concept_scores[0]["retrieved"], 1)
        self.assertEqual(concept_scores[0]["positive_count"], 1)


class UploadTests(unittest.TestCase):
    def test_prepare_search_hits_keeps_metadata_only_rows_and_uses_existing_paper_lookup(self) -> None:
        rows = [
            {
                "canonical_key": "doi:10.1000/test",
                "source": "dergipark",
                "source_record_id": "oai:1",
                "external_id": "oai:1",
                "pmcid": None,
                "doi": "10.1000/test",
                "title": "Türkçe makale",
                "abstract": "Besin bileşimi ve tablo sonuçları.",
                "workflow_language": "tr",
                "query": '"gıda bileşimi" tablo',
                "template_id": "base_core_composition",
                "source_term": None,
                "term_type": "base",
                "query_phrase": "gıda bileşimi",
                "search_gate_score": 1.25,
                "search_gate_pass": True,
                "filter_score": None,
                "filter_pass": None,
                "is_duplicate": False,
            }
        ]

        prepared = upload_to_supabase._prepare_search_hits(
            rows,
            paper_id_by_key={},
            existing_paper_id_lookup=lambda canonical_key: 77 if canonical_key == "doi:10.1000/test" else None,
        )

        self.assertEqual(len(prepared), 1)
        self.assertEqual(prepared[0]["paper_id"], 77)
        self.assertEqual(prepared[0]["workflow_language"], "tr")
        self.assertEqual(prepared[0]["query_text"], '"gıda bileşimi" tablo')


if __name__ == "__main__":
    unittest.main()
