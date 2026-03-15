"""
OpenNutri Harvester CLI

Usage:
    python3 crawler/main.py --email you@example.com --mode quick --foods 10
    python3 crawler/main.py --email you@example.com --mode full --max-searches 100
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawler.core.orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser(description="OpenNutri Systematic Harvester")
    parser.add_argument("--email", required=True, help="Email for NCBI Entrez API")
    parser.add_argument("--mode", choices=["quick", "full"], default="quick",
                        help="quick: sample a few foods; full: systematic all")
    parser.add_argument("--foods", type=int, default=10, help="Foods to process (quick mode)")
    parser.add_argument("--papers", type=int, default=3, help="Papers per search")
    parser.add_argument("--max-searches", type=int, default=None, help="Max searches (full mode)")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    
    args = parser.parse_args()
    
    print("🤖 OpenNutri Systematic Harvester")
    print("="*50)
    
    try:
        orchestrator = Orchestrator(email=args.email, data_dir=args.data_dir)
        
        if args.mode == "quick":
            orchestrator.run_quick_harvest(
                num_foods=args.foods, 
                papers_per_search=args.papers
            )
        else:
            orchestrator.run_systematic_harvest(
                papers_per_search=args.papers,
                max_searches=args.max_searches
            )
            
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user. Progress saved.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
