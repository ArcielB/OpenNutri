import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from food_paper_crawler.cli_v2 import run_cli

if __name__ == "__main__":
    raise SystemExit(run_cli())
