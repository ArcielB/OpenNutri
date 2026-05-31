from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE_ROOT))
sys.path.insert(0, str(PIPELINE_ROOT / "scripts"))

from ai_routing import RoutingStageConfig
import process_stage_queue as psq


def _stage(model_name: str) -> RoutingStageConfig:
    return RoutingStageConfig.from_row(
        {
            "stage_key": "s",
            "stage_kind": "ai_model",
            "display_name": "d",
            "model_name": model_name,
            "prompt_version": "v",
            "active": True,
        }
    )


class AnnotatePdfPageBreaksTests(unittest.TestCase):
    def test_numbers_pages_from_one(self):
        out = psq.annotate_pdf_page_breaks("A\fB\fC")
        self.assertEqual(
            out,
            "===== PDF PAGE 1 =====\n\nA\n\n===== PDF PAGE 2 =====\n\nB\n\n===== PDF PAGE 3 =====\n\nC",
        )

    def test_drops_trailing_empty_page(self):
        out = psq.annotate_pdf_page_breaks("only page\f")
        self.assertIn("PDF PAGE 1", out)
        self.assertNotIn("PDF PAGE 2", out)

    def test_empty_text_unchanged(self):
        self.assertEqual(psq.annotate_pdf_page_breaks(""), "")

    def test_single_page_gets_marker(self):
        out = psq.annotate_pdf_page_breaks("no form feeds here")
        self.assertTrue(out.startswith("===== PDF PAGE 1 ====="))


class StageTextTruncationTests(unittest.TestCase):
    def test_truncation_preserves_head_and_tail_page_numbers(self):
        # 20 pages of filler, marked, then truncated to a small budget. Because
        # markers are inserted before truncation, the surviving first and last
        # pages must keep their correct numbers (1 and 20).
        raw = "\f".join(f"page {i} " + ("x " * 80) for i in range(1, 21))
        marked = psq.annotate_pdf_page_breaks(raw)
        os.environ["GEMMA_STAGE_TEXT_LIMIT_CHARS"] = "600"
        try:
            out = psq.stage_text_for_model(marked, stage_config=_stage("gemma-4-31b-it"))
        finally:
            del os.environ["GEMMA_STAGE_TEXT_LIMIT_CHARS"]
        self.assertIn("[TRUNCATED FOR AI STAGE INPUT]", out)
        self.assertIn("===== PDF PAGE 1 =====", out)
        self.assertIn("===== PDF PAGE 20 =====", out)

    def test_gemini_uncapped_returns_full_marked_text(self):
        marked = psq.annotate_pdf_page_breaks("\f".join(f"page {i}" for i in range(1, 6)))
        out = psq.stage_text_for_model(marked, stage_config=_stage("gemini-3.5-flash"))
        self.assertEqual(out, marked)


if __name__ == "__main__":
    unittest.main()
