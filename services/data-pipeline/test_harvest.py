#!/usr/bin/env python3
"""
Test Harvest — Run a live test of the crawler and inspect results.

Usage:
    cd /home/arciel/Tubitak_last_edition/services/data-pipeline
    python test_harvest.py --email your@email.com --foods 3 --papers 5

This will:
1. Run searches for a few foods
2. Show which papers passed/failed the relevance filter
3. Print titles, journals, and scores
4. Calculate precision metrics
"""

import argparse
import sys
import os
import json
import time
from pathlib import Path

# Add parent dir to path so 'crawler' package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.harvester.client import PMCClient
from crawler.harvester.query_builder import QueryBuilder
from crawler.harvester.relevance_filter import RelevanceFilter


def test_relevance_filter_standalone():
    """Test the relevance filter on known good/bad examples."""
    rf = RelevanceFilter(threshold=3.0)
    
    print("=" * 70)
    print("🧪 UNIT TEST: Relevance Filter on Known Examples")
    print("=" * 70)
    
    test_cases = [
        # (title, abstract, expected_pass)
        (
            "Nutritional Data on Selected Food Products Consumed in Oman",
            "This study presents the nutrient composition of foods consumed in Oman. "
            "Proximate analysis including protein, fat, carbohydrate, ash, and moisture "
            "was conducted. Results are presented in Table 1 as mg/100g and g/100g.",
            True
        ),
        (
            "Effect of Beverage Composition on RFID Performance Using PET Bottles",
            "This study evaluates the impact of beverage composition on radio frequency "
            "identification (RFID) tag performance in polyethylene terephthalate (PET) "
            "bottles for smart food packaging applications.",
            False
        ),
        (
            "Gut microbiota as a transducer of dietary cues to regulate host circadian rhythms",
            "The gut microbiome plays a crucial role in transducing dietary signals to "
            "regulate circadian rhythms and metabolism in the host organism.",
            False
        ),
        (
            "Fatty Acid Composition of Selected Street Foods in Malaysia",
            "The fatty acid composition and total fat content of 30 street food samples "
            "were determined. Results showed total fat ranged from 2.3 to 45.2 g/100g. "
            "Saturated fatty acids were predominant in fried foods. Table 2 presents "
            "the detailed fatty acid profile.",
            True
        ),
        (
            "Styrene Monomer Migration into Food Simulants from Polystyrene Packaging",
            "Migration of styrene monomer from polystyrene food packaging into food "
            "simulants was investigated. The study evaluated migration levels under "
            "different temperature and time conditions.",
            False
        ),
        (
            "Mineral Content and Nutritional Value of Wild Edible Mushrooms",
            "The mineral content including iron, calcium, zinc, potassium and magnesium "
            "of ten wild edible mushroom species was determined. Proximate analysis showed "
            "protein content ranged from 15.2 to 35.8 g/100g dry weight. Table 1.",
            True
        ),
        (
            "Analytical Strategies for Fingerprinting of Antioxidants",
            "This review provides an overview of analytical strategies for fingerprinting "
            "of antioxidants, nutritional substances, and bioactive compounds based on "
            "HPLC-MS. The methodological approaches are discussed systematically.",
            False
        ),
    ]
    
    passed_correct = 0
    for title, abstract, expected in test_cases:
        ok, score, reasons = rf.passes(title, abstract)
        correct = ok == expected
        passed_correct += int(correct)
        
        status = "✅" if correct else "❌ WRONG"
        print(f"\n{status} | Score: {score:+.0f} | Expected: {'PASS' if expected else 'FAIL'} | Got: {'PASS' if ok else 'FAIL'}")
        print(f"  Title: {title[:70]}")
        if not correct:
            for r in reasons:
                print(f"  {r}")
    
    print(f"\n{'='*70}")
    print(f"Filter accuracy: {passed_correct}/{len(test_cases)} correct")
    print(f"{'='*70}\n")
    
    return passed_correct == len(test_cases)


def test_live_harvest(email: str, foods: list, papers_per_food: int = 5, verbose: bool = True):
    """
    Run live searches against PubMed and evaluate results.
    """
    client = PMCClient(email)
    rf = RelevanceFilter(threshold=3.0)
    
    print("=" * 70)
    print("🌐 LIVE TEST: Searching PubMed for Food Composition Papers")
    print("=" * 70)
    
    all_passed = []
    all_filtered = []
    
    for food in foods:
        print(f"\n{'─'*60}")
        print(f"🔍 Food: {food}")
        print(f"{'─'*60}")
        
        # Build high-precision query
        query = QueryBuilder.build_composition_search(food)
        print(f"   Query: {query[:120]}...")
        
        # Search
        pmc_ids = client.search(query, max_results=papers_per_food * 3)
        print(f"   Found: {len(pmc_ids)} candidates")
        
        if not pmc_ids:
            print("   ⚠️ No results — query may be too restrictive")
            # Try fallback with track_a and a strong term
            query = QueryBuilder.build_track_a(food, "nutrient content")
            print(f"   🔄 Fallback query: {query[:120]}...")
            pmc_ids = client.search(query, max_results=papers_per_food * 3)
            print(f"   Found: {len(pmc_ids)} candidates")
        
        if not pmc_ids:
            print("   📭 Still no results, skipping this food")
            continue
        
        # Fetch abstracts
        print(f"   📝 Fetching abstracts for {len(pmc_ids[:papers_per_food*2])} papers...")
        summaries = client.fetch_summaries(pmc_ids[:papers_per_food * 2])
        
        # Filter
        passed, filtered = rf.filter_batch(summaries)
        all_passed.extend(passed)
        all_filtered.extend(filtered)
        
        # Print results
        print(f"\n   ✅ PASSED ({len(passed)}):")
        for p in passed[:papers_per_food]:
            score = p.get('relevance_score', 0)
            print(f"      [{score:+.0f}] {p.get('title', 'Unknown')[:80]}")
            print(f"           Journal: {p.get('journal', 'Unknown')}")
            if verbose:
                for r in p.get('relevance_reasons', [])[:3]:
                    print(f"           {r}")
        
        if filtered:
            print(f"\n   ❌ FILTERED ({len(filtered)}):")
            for p in filtered[:5]:
                score = p.get('relevance_score', 0)
                print(f"      [{score:+.0f}] {p.get('title', 'Unknown')[:80]}")
                if verbose:
                    for r in p.get('relevance_reasons', [])[:2]:
                        print(f"           {r}")
        
        time.sleep(1)
    
    # Summary
    total = len(all_passed) + len(all_filtered)
    print(f"\n{'='*70}")
    print(f"📊 LIVE TEST SUMMARY")
    print(f"{'='*70}")
    print(f"   Total papers evaluated: {total}")
    print(f"   Passed filter: {len(all_passed)}")
    print(f"   Filtered out: {len(all_filtered)}")
    if total > 0:
        print(f"   Pass rate: {len(all_passed)/total*100:.1f}%")
    
    # Show score distribution
    if all_passed:
        scores = [p.get('relevance_score', 0) for p in all_passed]
        print(f"   Passed score range: {min(scores):.0f} to {max(scores):.0f} (avg: {sum(scores)/len(scores):.1f})")
    if all_filtered:
        scores = [p.get('relevance_score', 0) for p in all_filtered]
        print(f"   Filtered score range: {min(scores):.0f} to {max(scores):.0f} (avg: {sum(scores)/len(scores):.1f})")
    
    print(f"{'='*70}")
    
    return all_passed, all_filtered


def main():
    parser = argparse.ArgumentParser(description="Test the improved food composition crawler")
    parser.add_argument("--email", required=True, help="Email for NCBI Entrez API")
    parser.add_argument("--foods", type=int, default=3, help="Number of foods to test (default: 3)")
    parser.add_argument("--papers", type=int, default=5, help="Papers per food (default: 5)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed filter reasons")
    parser.add_argument("--skip-unit-test", action="store_true", help="Skip unit tests")
    
    args = parser.parse_args()
    
    print("🤖 OpenNutri Crawler Test Suite")
    print("=" * 70)
    
    # 1. Unit test the filter
    if not args.skip_unit_test:
        filter_ok = test_relevance_filter_standalone()
        if not filter_ok:
            print("⚠️ Some filter unit tests failed, but continuing with live test...\n")
    
    # 2. Test foods — use a representative mix
    test_foods = [
        "Chickpea", "Spinach", "Salmon", "Rice", "Tomato",
        "Lentil", "Banana", "Beef", "Quinoa", "Sweet Potato",
        "Almond", "Egg", "Milk", "Broccoli", "Avocado"
    ][:args.foods]
    
    print(f"\n📋 Testing with foods: {', '.join(test_foods)}")
    
    # 3. Live test
    passed, filtered = test_live_harvest(
        email=args.email,
        foods=test_foods,
        papers_per_food=args.papers,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
