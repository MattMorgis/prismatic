import logging
import os
import re
import shutil
import tempfile
from typing import Any, Optional, Tuple

import git
import requests

from github import Auth, Github

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


class GitHubClient:
    """
    Client for interacting with GitHub repositories.

    This class handles operations related to GitHub repositories and pull requests,
    such as cloning repositories and retrieving PR information.
    """

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize a GitHubClient.

        Args:
            github_token: Optional GitHub token for authentication (for private repos)
        """
        self.github_token = github_token
        if github_token:
            auth = Auth.Token(github_token)
            self.github = Github(auth=auth)
        else:
            self.github = Github()

    def _get_github_objects(self, pr_url: str) -> Tuple[Any, Any, str, str, int]:
        """
        Helper function to get GitHub objects from a PR URL.

        Args:
            pr_url: GitHub PR URL

        Returns:
            Tuple containing the repository object, pull request object, owner, repo name, and PR number

        Raises:
            ValueError: If the URL is not a valid GitHub PR URL
            Exception: Propagates any exceptions from the GitHub API
        """
        # Parse the PR URL
        owner, repo, pr_number = parse_pr_url(pr_url)

        # Get the repository and PR
        # Note: We intentionally don't catch exceptions here to propagate them to the caller
        repository = self.github.get_repo(f"{owner}/{repo}")
        pull_request = repository.get_pull(pr_number)

        return repository, pull_request, owner, repo, pr_number

    def _safe_remove_directory(self, dir_path: str) -> None:
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
            logger.warning(
                f"Failed to clean up directory {dir_path}: {str(e)}")

    def clean_up(self, repo_path: str) -> None:
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

        # Get the parent directory (the temp directory) if it's a subdirectory
        # Otherwise, remove the directory directly
        if os.path.dirname(repo_path):
            temp_dir = os.path.dirname(repo_path)
            self._safe_remove_directory(temp_dir)
        else:
            self._safe_remove_directory(repo_path)

    def clone_pr_repo(self, pr_url: str) -> Tuple[str, str]:
        """
        Clone the repository from a PR URL to a local temporary directory.
        Note: This method only clones the repository and does not check out any branch.

        Args:
            pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number

        Returns:
            Tuple[str, str]: Path to the cloned repository, branch name of the PR (not checked out)

        Raises:
            ValueError: If the URL is not a valid GitHub PR URL
            RuntimeError: If there's an error cloning the repository
        """
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()

        try:
            # Get GitHub objects
            repository, pull_request, owner, repo, _ = self._get_github_objects(
                pr_url)

            # Get the clone URL
            clone_url = repository.clone_url
            if self.github_token:
                # Insert token for authenticated clone
                clone_url = clone_url.replace(
                    'https://', f'https://{self.github_token}@')

            # Clone the repository
            repo_path = os.path.join(temp_dir, repo)
            git_repo = git.Repo.clone_from(clone_url, repo_path)

            # Get the PR branch name without checking it out
            branch_name = pull_request.head.ref

            return repo_path, branch_name
        except Exception as e:
            # Clean up the temporary directory in case of failure
            self._safe_remove_directory(temp_dir)
            raise RuntimeError(f"Error cloning repository: {str(e)}")

    def get_pr_target_branch(self, pr_url: str) -> str:
        """
        Get the target branch (base branch) of a GitHub pull request.

        Args:
            pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number

        Returns:
            str: The name of the target branch (base branch) of the pull request

        Raises:
            ValueError: If the URL is not a valid GitHub PR URL
            RuntimeError: If there's an error retrieving the PR information
        """
        try:
            # Get GitHub objects
            _, pull_request, _, _, _ = self._get_github_objects(pr_url)

            # Return the base branch (target branch) name
            return pull_request.base.ref
        except Exception as e:
            raise RuntimeError(f"Error retrieving PR information: {str(e)}")

    def get_and_apply_pr_patch(self, pr_url: str, repo_path: str) -> str:
        """
        Get the diff from a GitHub PR and apply it to a local repository.
        This method also checks out the target branch before applying the patch.

        Args:
            pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number
            repo_path: Path to the local repository where the patch should be applied

        Returns:
            str: Path to the applied patch file

        Raises:
            ValueError: If the URL is not a valid GitHub PR URL or repo_path is invalid
            RuntimeError: If there's an error retrieving or applying the patch
        """
        if not os.path.exists(repo_path) or not os.path.isdir(repo_path):
            raise ValueError(f"Invalid repository path: {repo_path}")

        try:
            # Get GitHub objects
            _, pull_request, owner, repo, pr_number = self._get_github_objects(
                pr_url)

            # Get the git repository
            git_repo = git.Repo(repo_path)

            # Checkout the target branch (base branch)
            target_branch = pull_request.base.ref
            origin = git_repo.remote()

            # Fetch the target branch
            origin.fetch(
                f'{target_branch}:refs/remotes/origin/{target_branch}')

            # Checkout the target branch
            git_repo.git.checkout(target_branch)

            # Construct the patch URL
            patch_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}.patch"

            # Create a patch file path
            patch_file = os.path.join(repo_path, f"pr-{pr_number}.patch")

            # Authenticate request if token is available
            headers = {}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"

            # Get the patch content
            response = requests.get(patch_url, headers=headers)
            response.raise_for_status()

            # Save the patch to a file
            with open(patch_file, 'wb') as f:
                f.write(response.content)

            # Apply the patch using git
            git_repo.git.execute(['git', 'apply', patch_file])

            return patch_file
        except Exception as e:
            raise RuntimeError(
                f"Error retrieving or applying PR patch: {str(e)}")


# For backwards compatibility
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


# For backwards compatibility
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


# For backwards compatibility, expose the instance methods as module-level functions
def clone_pr_repo(pr_url: str, github_token: Optional[str] = None) -> Tuple[str, str]:
    """
    Clone the repository from a PR URL to a local temporary directory.
    Note: This function only clones the repository and does not check out any branch.

    Backwards compatibility function that creates a GitHubClient instance.

    Args:
        pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number
        github_token: Optional GitHub token for authentication (for private repos)

    Returns:
        Tuple[str, str]: Path to the cloned repository, branch name of the PR (not checked out)
    """
    client = GitHubClient(github_token=github_token)
    return client.clone_pr_repo(pr_url)


def get_pr_target_branch(pr_url: str, github_token: Optional[str] = None) -> str:
    """
    Get the target branch (base branch) of a GitHub pull request.

    Backwards compatibility function that creates a GitHubClient instance.

    Args:
        pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number
        github_token: Optional GitHub token for authentication (for private repos)

    Returns:
        str: The name of the target branch (base branch) of the pull request
    """
    client = GitHubClient(github_token=github_token)
    return client.get_pr_target_branch(pr_url)


# For backwards compatibility, expose the new method as a module-level function
def get_and_apply_pr_patch(pr_url: str, repo_path: str, github_token: Optional[str] = None) -> str:
    """
    Get the diff from a GitHub PR and apply it to a local repository.

    Backwards compatibility function that creates a GitHubClient instance.

    Args:
        pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number
        repo_path: Path to the local repository where the patch should be applied
        github_token: Optional GitHub token for authentication (for private repos)

    Returns:
        str: Path to the applied patch file
    """
    client = GitHubClient(github_token=github_token)
    return client.get_and_apply_pr_patch(pr_url, repo_path)
