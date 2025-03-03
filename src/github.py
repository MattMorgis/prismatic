import logging
import os
import re
import shutil
import tempfile
from typing import Any, Optional, Tuple

import git

from github import Github

# Configure logging
logger = logging.getLogger(__name__)


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


def _get_github_objects(pr_url: str, github_token: Optional[str] = None) -> Tuple[Any, Any, str, str, int]:
    """
    Helper function to get GitHub objects from a PR URL.

    Args:
        pr_url: GitHub PR URL
        github_token: Optional GitHub token for authentication

    Returns:
        Tuple containing the repository object, pull request object, owner, repo name, and PR number

    Raises:
        ValueError: If the URL is not a valid GitHub PR URL
        Exception: Propagates any exceptions from the GitHub API
    """
    # Parse the PR URL
    owner, repo, pr_number = parse_pr_url(pr_url)

    # Create a GitHub instance
    g = Github(github_token) if github_token else Github()

    # Get the repository and PR
    # Note: We intentionally don't catch exceptions here to propagate them to the caller
    repository = g.get_repo(f"{owner}/{repo}")
    pull_request = repository.get_pull(pr_number)

    return repository, pull_request, owner, repo, pr_number


def _safe_remove_directory(dir_path: str) -> None:
    """
    Safely remove a directory.

    Note: Using os.system with rm -rf is potentially dangerous, but kept for
    backward compatibility. In production, this should be replaced with safer alternatives.

    Args:
        dir_path: Path to the directory to remove
    """
    try:
        shutil.rmtree(dir_path)
    except Exception as e:
        # Log warning about the dangerous operation
        logger.warning(f"Failed to clean up directory {dir_path}: {str(e)}")


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
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()

    try:
        # Get GitHub objects
        repository, pull_request, owner, repo, _ = _get_github_objects(
            pr_url, github_token)

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
        _safe_remove_directory(temp_dir)
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

    # Use the safe removal function
    _safe_remove_directory(temp_dir)


def get_pr_target_branch(pr_url: str, github_token: Optional[str] = None) -> str:
    """
    Get the target branch (base branch) of a GitHub pull request.

    Args:
        pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number
        github_token: Optional GitHub token for authentication (for private repos)

    Returns:
        str: The name of the target branch (base branch) of the pull request

    Raises:
        ValueError: If the URL is not a valid GitHub PR URL
        RuntimeError: If there's an error retrieving the PR information
    """
    try:
        # Get GitHub objects
        _, pull_request, _, _, _ = _get_github_objects(pr_url, github_token)

        # Return the base branch (target branch) name
        return pull_request.base.ref
    except Exception as e:
        raise RuntimeError(f"Error retrieving PR information: {str(e)}")
