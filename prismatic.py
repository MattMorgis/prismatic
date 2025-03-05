#!/usr/bin/env python3
"""
Entry point script for the multi-code-reviewer tool.
This script simply imports and runs the main functionality from the src package.
"""

import asyncio

from src.main import run_multi_code_review
from src.report import ReportGenerator

if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser(
        description="PRismatic code reviewer"
    )
    parser.add_argument("pr_url", help="GitHub Pull Request URL to review")
    args = parser.parse_args()

    start_time = time.time()
    review_result = asyncio.run(run_multi_code_review(args.pr_url))
    end_time = time.time()

    print("\n" + "=" * 80)
    print("PRismatic REPORT")
    print("=" * 80 + "\n")
    if review_result:
        print(review_result)
        # Use ReportGenerator to save the report
        report_gen = ReportGenerator()
        report_path = report_gen.generate_report(args.pr_url, review_result)
        print(f"\nReport saved to: {report_path}")
    else:
        print("PR is not open, skipping review")
    print(f"\nReview completed in {end_time - start_time:.2f} seconds")
