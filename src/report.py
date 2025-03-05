import datetime
import os
from pathlib import Path
from typing import Optional

from .github import parse_pr_url


class ReportGenerator:
    """
    A class for generating and saving markdown reports for GitHub PRs.

    Reports are saved in the 'reviews/<repo>/' directory with filenames like 'PR-<number>_<timestamp>.md'.
    """

    def __init__(self, base_dir: str = "reviews"):
        """
        Initialize a ReportGenerator.

        Args:
            base_dir: Base directory where reports will be saved. Defaults to "reviews".
        """
        self.base_dir = base_dir

    def generate_report(self, pr_url: str, content: str) -> str:
        """
        Generate a report for a GitHub PR and save it to a file.

        Args:
            pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number
            content: Content of the report in markdown format

        Returns:
            str: Path to the generated report file

        Raises:
            ValueError: If the PR URL is invalid
        """
        # Parse PR URL to extract owner, repo, and PR number
        owner, repo, pr_number = parse_pr_url(pr_url)

        # Create timestamp with a more readable format
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Create directory path for the repo
        dir_path = Path(self.base_dir) / repo

        # Create directories if they don't exist
        os.makedirs(dir_path, exist_ok=True)

        # Create file path with PR number and timestamp in the filename
        file_name = f"PR-{pr_number}_{timestamp}.md"
        file_path = dir_path / file_name

        # Write content to file
        with open(file_path, "w") as f:
            f.write(content)

        return str(file_path)

    def get_latest_report(self, pr_url: str) -> Optional[str]:
        """
        Get the path to the latest report for a GitHub PR.

        Args:
            pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number

        Returns:
            Optional[str]: Path to the latest report file, or None if no report exists

        Raises:
            ValueError: If the PR URL is invalid
        """
        # Parse PR URL to extract owner, repo, and PR number
        owner, repo, pr_number = parse_pr_url(pr_url)

        # Create repo directory path
        repo_dir = Path(self.base_dir) / repo

        if not repo_dir.exists():
            return None

        # Find all files for this PR
        pr_files = [
            f
            for f in repo_dir.iterdir()
            if f.is_file()
            and f.name.startswith(f"PR-{pr_number}_")
            and f.name.endswith(".md")
        ]

        if not pr_files:
            return None

        # Sort files by timestamp (newest first)
        pr_files.sort(reverse=True)

        # Get the latest file
        latest_file = pr_files[0]

        return str(latest_file)
