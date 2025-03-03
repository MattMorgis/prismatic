#!/usr/bin/env python3
"""
Entry point script for the multi-code-reviewer tool.
This script simply imports and runs the main functionality from the src package.
"""

import asyncio

from src.main import run_multi_code_review

if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser(
        description="Multi-perspective code reviewer for GitHub PRs"
    )
    parser.add_argument("pr_url", help="GitHub Pull Request URL to review")
    args = parser.parse_args()

    start_time = time.time()
    review_result = asyncio.run(run_multi_code_review(args.pr_url))
    end_time = time.time()

    print("\n" + "=" * 80)
    print("MULTI-CODE REVIEWER REPORT")
    print("=" * 80 + "\n")
    print(review_result)
    print(f"\nReview completed in {end_time - start_time:.2f} seconds")
