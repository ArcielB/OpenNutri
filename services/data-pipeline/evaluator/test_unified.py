"""
Test script for UnifiedEvaluator

Usage:
    python -m crawler.evaluator.test_unified --api-key YOUR_KEY
"""

import argparse
import sys
import os
import json
from pathlib import Path

sys.path.append(os.getcwd())

from crawler.evaluator.unified_evaluator import UnifiedEvaluator


def main():
    parser = argparse.ArgumentParser(description="Test Unified Evaluator")
    parser.add_argument("--api-key", default=None, help="Gemini API key")
    parser.add_argument("--data-dir", default="data/raw_lake", help="Raw papers directory")
    parser.add_argument("--limit", type=int, default=5, help="Number of papers to test")
    parser.add_argument("--output-dir", default="data/extracted", help="Output directory")
    
    args = parser.parse_args()
    
    print("🧪 Testing Unified Evaluator\n")
    
    # Initialize evaluator
    evaluator = UnifiedEvaluator(
        raw_lake_dir=args.data_dir,
        api_key=args.api_key
    )
    
    # Get sample papers
    papers_dir = Path(args.data_dir)
    if not papers_dir.exists():
        print(f"❌ Data directory not found: {args.data_dir}")
        return
    
    paper_files = list(papers_dir.glob("PMC*.json"))
    if not paper_files:
        print(f"❌ No papers found in {args.data_dir}")
        return
    
    print(f"Found {len(paper_files)} papers. Testing on {min(args.limit, len(paper_files))}...\n")
    
    # Test each paper
    results = []
    for i, paper_file in enumerate(paper_files[:args.limit], 1):
        print(f"[{i}/{args.limit}] Processing {paper_file.name}...")
        
        with open(paper_file, 'r', encoding='utf-8') as f:
            paper = json.load(f)
        
        # Extract
        result = evaluator.evaluate_and_extract(paper)
        results.append(result)
        
        # Print summary
        print(f"   Verdict: {result.verdict}")
        print(f"   Reason: {result.reason}")
        if result.data:
            print(f"   Records: {len(result.data)}")
            # Show first record
            first = result.data[0]
            print(f"   Sample: {first.food_name} - {first.nutrient_name}: {first.amount} {first.unit}")
        print()
        
        # Save result
        evaluator.save_result(result, args.output_dir)
    
    # Summary
    pass_count = sum(1 for r in results if r.verdict == "PASS")
    total_records = sum(len(r.data) for r in results)
    
    print("\n" + "="*60)
    print(f"📊 Test Summary:")
    print(f"   Papers Tested: {len(results)}")
    print(f"   PASS: {pass_count}")
    print(f"   FAIL: {len(results) - pass_count}")
    print(f"   Total Records Extracted: {total_records}")
    if pass_count > 0:
        print(f"   Avg Records/Paper: {total_records / pass_count:.1f}")
    print(f"   Results saved to: {args.output_dir}")
    print("="*60)


if __name__ == "__main__":
    main()
