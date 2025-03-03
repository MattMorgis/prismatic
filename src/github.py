import os
import re
import tempfile
from typing import Optional, Tuple

import git

from github import Github


def parse_pr_url(pr_url: str) -> Tuple[str, str, int]:
    """
    Parse a GitHub PR URL to extract owner, repo, and PR number.

    Args:
        pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number

    Returns:
        Tuple[str, str, int]: owner, repo, PR number

    Raises:
        ValueError: If the URL is not a valid GitHub PR URL
    """
    # Match pattern for GitHub PR URL
    pattern = r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.match(pattern, pr_url)

    if not match:
        raise ValueError(f"Invalid GitHub PR URL: {pr_url}")

    owner, repo, pr_number = match.groups()
    return owner, repo, int(pr_number)


def clone_pr_repo(pr_url: str, github_token: Optional[str] = None) -> Tuple[str, str]:
    """
    Clone the repository from a PR URL to a local temporary directory.

    Args:
        pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number
        github_token: Optional GitHub token for authentication (for private repos)

    Returns:
        Tuple[str, str]: Path to the cloned repository, branch name

    Raises:
        ValueError: If the URL is not a valid GitHub PR URL
        RuntimeError: If there's an error cloning the repository
    """
    # Parse the PR URL
    owner, repo, pr_number = parse_pr_url(pr_url)

    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()

    try:
        # Create a GitHub instance
        g = Github(github_token) if github_token else Github()

        # Get the repository
        repository = g.get_repo(f"{owner}/{repo}")

        # Get the PR
        pull_request = repository.get_pull(pr_number)

        # Get the clone URL
        clone_url = repository.clone_url
        if github_token:
            # Insert token for authenticated clone
            clone_url = clone_url.replace(
                'https://', f'https://{github_token}@')

        # Clone the repository
        repo_path = os.path.join(temp_dir, repo)
        git_repo = git.Repo.clone_from(clone_url, repo_path)

        # Fetch the PR branch
        branch_name = pull_request.head.ref
        origin = git_repo.remote()
        origin.fetch(f'{branch_name}:refs/remotes/origin/{branch_name}')

        # Checkout the PR branch
        git_repo.git.checkout(branch_name)

        return repo_path, branch_name
    except Exception as e:
        # Clean up the temporary directory in case of failure
        os.system(f"rm -rf {temp_dir}")
        raise RuntimeError(f"Error cloning repository: {str(e)}")


def clean_up(repo_path: str) -> None:
    """
    Clean up a repository directory created by clone_pr_repo.

    Args:
        repo_path: Path to the cloned repository directory

    Raises:
        ValueError: If the provided path is invalid
    """
    if not repo_path or not isinstance(repo_path, str):
        raise ValueError("Repository path must be a non-empty string")

    if not os.path.exists(repo_path):
        # Path doesn't exist, nothing to clean up
        return

    # Get the parent directory (the temp directory)
    temp_dir = os.path.dirname(repo_path)

    try:
        # Use shutil.rmtree for a more reliable cleanup
        import shutil
        shutil.rmtree(temp_dir)
    except Exception:
        # Fallback to system command if shutil fails
        os.system(f"rm -rf {temp_dir}")
