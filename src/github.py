import os
import re
import shutil
import tempfile
from typing import Any, Optional, Tuple

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


class GitHubClient:
    """
    Client for interacting with GitHub repositories.

    This class handles operations related to GitHub repositories and pull requests,
    such as cloning repositories and retrieving PR information.
    """

    def __init__(self, github_token: Optional[str] = None, logger=None):
        """
        Initialize a GitHubClient.

        Args:
            github_token: Optional GitHub token for authentication (for private repos)
            logger: Optional custom logger to use instead of the default module logger
        """
        self.github_token = github_token
        if github_token:
            # Directly pass the token to Github constructor to match the tests
            self.github = Github(github_token)
        else:
            self.github = Github()

        # Use custom logger if provided, otherwise use module logger
        self.logger = logger

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

        Args:
            dir_path: Path to the directory to remove
        """
        try:
            shutil.rmtree(dir_path)
        except Exception as e:
            self.logger.warning(
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
            raise ValueError("Invalid repository path")

        if not os.path.exists(repo_path):
            # Path doesn't exist, nothing to clean up
            return

        # Since we're always creating repos in temp directories now,
        # we should remove the parent temp directory
        temp_dir = os.path.dirname(repo_path)

        # If we have a valid parent directory, remove it
        # Otherwise fall back to removing just the repo path
        if temp_dir and os.path.exists(temp_dir):
            self.logger.info(f"Cleaning up temporary directory: {temp_dir}")
            self._safe_remove_directory(temp_dir)
        else:
            self.logger.info(f"Cleaning up repository directory: {repo_path}")
            self._safe_remove_directory(repo_path)

    def clone_pr_repo(self, pr_url: str) -> str:
        """
        Clone the repository from a PR URL to a local temporary directory.
        Note: This method only clones the repository and does not check out any branch.

        Args:
            pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number

        Returns:
            str: Path to the cloned repository

        Raises:
            ValueError: If the URL is not a valid GitHub PR URL
            RuntimeError: If there's an error cloning the repository
        """
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        self.logger.info(f"Created temporary directory: {temp_dir}")

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
            self.logger.info(f"Cloning repository to: {repo_path}")
            git.Repo.clone_from(clone_url, repo_path)

            return repo_path
        except Exception as e:
            # Clean up the temporary directory in case of failure
            self.logger.info(f"Error during cloning, cleaning up: {temp_dir}")
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
        Get the changes from a GitHub PR and apply them to a local repository using fetch and merge.
        This method checks out the target branch and merges the PR branch.

        Args:
            pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number
            repo_path: Path to the local repository where the changes should be applied

        Returns:
            str: Path to a file containing the diff of the changes

        Raises:
            ValueError: If the URL is not a valid GitHub PR URL or repo_path is invalid
            RuntimeError: If there's an error retrieving or applying the changes
        """
        self.logger.info(
            f"Starting get_and_apply_pr_patch with PR URL: {pr_url}, repo path: {repo_path}")

        if not os.path.exists(repo_path) or not os.path.isdir(repo_path):
            self.logger.error(f"Invalid repository path: {repo_path}")
            raise ValueError(f"Invalid repository path: {repo_path}")

        try:
            # Get GitHub objects
            self.logger.info("Retrieving GitHub objects from PR URL")
            _, pull_request, owner, repo, pr_number = self._get_github_objects(
                pr_url)
            self.logger.info(f"PR is from {owner}/{repo}#{pr_number}")

            # Get the git repository
            self.logger.info(f"Loading local repository from {repo_path}")
            git_repo = git.Repo(repo_path)

            # Log local repo origin
            try:
                local_origin_url = next(iter(git_repo.remote().urls))
                # Redact any tokens in the URL before logging
                redacted_url = local_origin_url
                if '@' in redacted_url:
                    # If URL contains authentication, redact it
                    protocol_part = redacted_url.split('://')[0] + '://'
                    auth_and_rest = redacted_url.split('://')[1]
                    rest_part = auth_and_rest.split('@', 1)[1]
                    redacted_url = f"{protocol_part}***@{rest_part}"

                self.logger.info(
                    f"Local repository origin: {redacted_url}")

                # Keep logs for debugging but without conditional
                pr_repo_url = f"https://github.com/{owner}/{repo}.git"
                self.logger.info(f"PR repository URL: {pr_repo_url}")
                self.logger.info(f"Local repository URL: {redacted_url}")

            except Exception as e:
                self.logger.warning(
                    f"Could not retrieve local repository URL: {str(e)}")

            # Get PR and target branch information
            target_branch = pull_request.base.ref
            pr_branch = pull_request.head.ref
            pr_sha = pull_request.head.sha
            pr_repo_owner = pull_request.head.repo.owner.login
            pr_repo_name = pull_request.head.repo.name
            self.logger.info(
                f"PR info - target branch: {target_branch}, PR branch: {pr_branch}, PR SHA: {pr_sha}")
            self.logger.info(f"PR repository: {pr_repo_owner}/{pr_repo_name}")

            # Setup remotes
            origin = git_repo.remote()
            # Redact any tokens in the URLs before logging
            origin_urls = list(origin.urls)
            redacted_origin_urls = []
            for url in origin_urls:
                redacted_url = url
                if '@' in redacted_url:
                    # If URL contains authentication, redact it
                    protocol_part = redacted_url.split('://')[0] + '://'
                    auth_and_rest = redacted_url.split('://')[1]
                    rest_part = auth_and_rest.split('@', 1)[1]
                    redacted_url = f"{protocol_part}***@{rest_part}"
                redacted_origin_urls.append(redacted_url)

            self.logger.info(
                f"Local origin remote: {origin.name} -> {redacted_origin_urls}")

            # Add PR's repo as a remote if it's a fork
            if pr_repo_owner != owner or pr_repo_name != repo:
                self.logger.info(
                    f"PR is from a fork: {pr_repo_owner}/{pr_repo_name} != {owner}/{repo}")
                pr_remote_name = f"pr-{pr_number}"
                pr_remote_url = f"https://github.com/{pr_repo_owner}/{pr_repo_name}.git"
                if self.github_token:
                    pr_remote_url = pr_remote_url.replace(
                        'https://', 'https://***@')  # Log redacted token
                    self.logger.info("Using authenticated URL for PR remote")
                else:
                    self.logger.info("Using unauthenticated URL for PR remote")

                # Add the remote if it doesn't exist
                existing_remotes = [r.name for r in git_repo.remotes]
                self.logger.info(f"Existing remotes: {existing_remotes}")

                if pr_remote_name not in existing_remotes:
                    self.logger.info(
                        f"Creating new remote: {pr_remote_name} -> {pr_remote_url}")
                    git_repo.create_remote(pr_remote_name, pr_remote_url)
                else:
                    self.logger.info(f"Remote {pr_remote_name} already exists")

                pr_remote = git_repo.remote(pr_remote_name)
                self.logger.info(f"Fetching from PR remote: {pr_remote_name}")
                pr_remote.fetch()
            else:
                # If it's not a fork, use origin
                self.logger.info(
                    "PR is from the same repository, using origin remote")
                pr_remote = origin
                self.logger.info("Fetching from origin")
                origin.fetch()

           # Checkout target branch
            self.logger.info(f"Checking out target branch: {target_branch}")
            git_repo.git.checkout(target_branch)

            # Create a branch for the PR changes
            pr_local_branch = f"pr-{pr_number}"
            self.logger.info(
                f"Creating local branch for PR: {pr_local_branch}")
            if pr_local_branch in git_repo.heads:
                self.logger.info(
                    f"Branch {pr_local_branch} already exists, deleting it")
                git_repo.delete_head(pr_local_branch, force=True)

            # Use the appropriate remote based on whether it's a fork or not
            if pr_repo_owner != owner or pr_repo_name != repo:
                # For forks, use the PR remote
                remote_to_use = pr_remote
                self.logger.info(
                    f"Creating branch {pr_local_branch} from {remote_to_use.name}/{pr_branch}")
                try:
                    git_repo.create_head(
                        pr_local_branch, remote_to_use.refs[pr_branch])
                except Exception as e:
                    self.logger.error(f"Error creating branch: {str(e)}")
                    self.logger.info(
                        f"Available references on {remote_to_use.name}: {[ref.name for ref in remote_to_use.refs]}")
                    raise
            else:
                # For same-repo PRs, use origin
                self.logger.info(
                    f"Creating branch {pr_local_branch} from {origin.name}/{pr_branch}")
                try:
                    git_repo.create_head(
                        pr_local_branch, origin.refs[pr_branch])
                except Exception as e:
                    self.logger.error(f"Error creating branch: {str(e)}")
                    self.logger.info(
                        f"Available references on {origin.name}: {[ref.name for ref in origin.refs]}")
                    raise

            # Checkout the PR branch
            self.logger.info(f"Checking out PR branch: {pr_local_branch}")
            git_repo.heads[pr_local_branch].checkout()

            # Create a diff file
            diff_file = os.path.join(repo_path, f"pr-{pr_number}.diff")
            self.logger.info(f"Creating diff file: {diff_file}")
            with open(diff_file, 'w') as f:
                diff_content = git_repo.git.diff(
                    f"{target_branch}..{pr_local_branch}")
                f.write(diff_content)
                self.logger.info(f"Diff size: {len(diff_content)} characters")

            self.logger.info(
                f"Successfully completed get_and_apply_pr_patch, returning diff file: {diff_file}")
            return diff_file
        except ValueError as e:
            # Re-raise ValueError directly
            self.logger.error(
                f"Validation error: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(
                f"Error retrieving or applying PR changes: {str(e)}", exc_info=True)
            raise ValueError(
                f"Error retrieving or applying PR changes: {str(e)}")

    def is_pr_open(self, pr_url: str) -> bool:
        """
        Check if a GitHub pull request is still open.

        Args:
            pr_url: GitHub PR URL in the format https://github.com/owner/repo/pull/number

        Returns:
            bool: True if the PR is open, False if it's closed or merged

        Raises:
            ValueError: If the URL is not a valid GitHub PR URL
            RuntimeError: If there's an error retrieving the PR information
        """
        try:
            # Get GitHub objects
            _, pull_request, _, _, _ = self._get_github_objects(pr_url)

            # Check if the PR is open (not closed and not merged)
            return pull_request.state == "open"
        except Exception as e:
            raise RuntimeError(f"Error checking PR status: {str(e)}")
