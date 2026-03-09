"""
Evaluator CLI

Run paper evaluation and feed results back to the Harvester.
"""

import argparse
import sys
import os

sys.path.append(os.getcwd())

from crawler.evaluator import LLMEvaluator
from crawler.core.orchestrator import Orchestrator

def main():
    parser = argparse.ArgumentParser(description="OpenNutri Paper Evaluator (Phase 2)")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--limit", type=int, default=None, help="Max papers to evaluate")
    parser.add_argument("--api-key", default=None, help="Gemini API key (or set GEMINI_API_KEY env)")
    parser.add_argument("--email", required=True, help="Email for Orchestrator (for feedback)")
    parser.add_argument("--dry-run", action="store_true", help="Don't update scores, just evaluate")
    
    args = parser.parse_args()
    
    print("📖 OpenNutri Paper Evaluator (Phase 2)")
    
    # Initialize evaluator
    evaluator = LLMEvaluator(
        raw_lake_dir=f"{args.data_dir}/raw_lake",
        api_key=args.api_key
    )
    
    # Run evaluation
    results = evaluator.run_evaluation(limit=args.limit)
    
    # Summary
    good_count = sum(1 for r in results if r.is_good)
    bad_count = len(results) - good_count
    print(f"\n📊 Summary: {good_count} GOOD, {bad_count} BAD out of {len(results)} papers")
    
    # Feed back to Harvester (unless dry run)
    if not args.dry_run and results:
        print("\n🔄 Sending feedback to Harvester...")
        orchestrator = Orchestrator(email=args.email, data_dir=args.data_dir)
        
        for result in results:
            if result.source_term:
                orchestrator.receive_evaluation(
                    pmc_id=result.pmc_id,
                    is_good=result.is_good,
                    source_term=result.source_term
                )
                
        print("✅ Term scores updated based on evaluation results.")
    else:
        print("ℹ️ Dry run mode: No scores updated.")

if __name__ == "__main__":
    main()
