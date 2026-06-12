import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from food_paper_crawler import search_sources
from food_paper_crawler.europe_pmc import EuropePMCClient
from food_paper_crawler.models import QuerySpec
from food_paper_crawler.search_sources import (
    EuropePMCSearchSource,
    YEAR_WINDOWS,
    current_openalex_page,
    current_year_window,
)


def make_spec(query: str = 'apple AND OPEN_ACCESS:y') -> QuerySpec:
    return QuerySpec(
        query=query,
        keywords=("apple",),
        template_id="t1",
        source_term="apple",
        term_type="food",
        language="en",
        query_phrase="food composition",
    )


class YearWindowRotationTests(unittest.TestCase):
    def test_rotation_is_deterministic_and_covers_all_windows(self) -> None:
        base = datetime(2026, 6, 1, tzinfo=timezone.utc)
        seen = {current_year_window(base + timedelta(days=offset)) for offset in range(len(YEAR_WINDOWS))}
        self.assertEqual(seen, set(YEAR_WINDOWS))
        # Same day always yields the same window regardless of time of day.
        self.assertEqual(
            current_year_window(base.replace(hour=1)),
            current_year_window(base.replace(hour=23)),
        )

    def test_openalex_page_advances_once_per_window_cycle(self) -> None:
        # Align the base date to the start of a window cycle so all days in
        # range share the same page.
        raw_ordinal = datetime(2026, 6, 1, tzinfo=timezone.utc).toordinal()
        base = datetime.fromordinal(raw_ordinal - raw_ordinal % len(YEAR_WINDOWS)).replace(tzinfo=timezone.utc)
        first_cycle = {current_openalex_page(base + timedelta(days=offset)) for offset in range(len(YEAR_WINDOWS))}
        self.assertEqual(len(first_cycle), 1)
        next_cycle_page = current_openalex_page(base + timedelta(days=len(YEAR_WINDOWS)))
        self.assertNotEqual(first_cycle.pop(), next_cycle_page)
        pages = {
            current_openalex_page(base + timedelta(days=offset))
            for offset in range(len(YEAR_WINDOWS) * search_sources.OPENALEX_PAGE_CYCLE)
        }
        self.assertEqual(pages, set(range(1, search_sources.OPENALEX_PAGE_CYCLE + 1)))

    def test_europepmc_query_gains_pub_year_clause_on_window_days(self) -> None:
        source = EuropePMCSearchSource(page_size=10)
        with patch.object(search_sources, "current_year_window", return_value=(2014, 2017)):
            self.assertEqual(
                source.query_text(make_spec()),
                "(apple AND OPEN_ACCESS:y) AND (PUB_YEAR:[2014 TO 2017])",
            )
        with patch.object(search_sources, "current_year_window", return_value=None):
            self.assertEqual(source.query_text(make_spec()), "apple AND OPEN_ACCESS:y")

    def test_ncbi_fallback_translates_pub_year_to_pdat(self) -> None:
        client = EuropePMCClient()
        rewritten = client._to_ncbi_query(
            '("food composition" AND OPEN_ACCESS:y) AND (PUB_YEAR:[2014 TO 2017])'
        )
        self.assertIn("2014:2017[pdat]", rewritten)
        self.assertNotIn("PUB_YEAR", rewritten)
        self.assertIn('"open access"[filter]', rewritten)




class PmcPowTests(unittest.TestCase):
    def test_solver_uses_sha256_and_cookie_format(self) -> None:
        import hashlib

        from food_paper_crawler.pmc_pow import solve_pmc_pow

        html = (
            'const POW_CHALLENGE = "abc:def"\n'
            'const POW_DIFFICULTY = "2"\n'
            'const POW_COOKIE_NAME = "cloudpmc-viewer-pow"\n'
        )
        cookie = solve_pmc_pow(html)
        self.assertIsNotNone(cookie)
        name, value = cookie.split("=", 1)
        challenge, nonce = value.rsplit(",", 1)
        self.assertEqual(name, "cloudpmc-viewer-pow")
        self.assertEqual(challenge, "abc:def")
        digest = hashlib.sha256(f"{challenge}{nonce}".encode()).hexdigest()
        self.assertTrue(digest.startswith("00"))

    def test_solver_ignores_non_challenge_pages(self) -> None:
        from food_paper_crawler.pmc_pow import solve_pmc_pow

        self.assertIsNone(solve_pmc_pow("<html>plain error page</html>"))


if __name__ == "__main__":
    unittest.main()
