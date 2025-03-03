import os
from unittest.mock import MagicMock, patch

import pytest

from src.github import (
    GitHubClient,
    clean_up,
    clone_pr_repo,
    get_pr_target_branch,
    parse_pr_url,
)


class TestParseGithubUrl:
    def test_valid_url(self):
        """Test with a valid GitHub PR URL"""
        owner, repo, pr_number = parse_pr_url(
            "https://github.com/owner/repo/pull/123")
        assert owner == "owner"
        assert repo == "repo"
        assert pr_number == 123

    def test_https_url(self):
        """Test with https URL"""
        owner, repo, pr_number = parse_pr_url(
            "https://github.com/user/project/pull/456")
        assert owner == "user"
        assert repo == "project"
        assert pr_number == 456

    def test_invalid_url(self):
        """Test with invalid URL formats"""
        with pytest.raises(ValueError):
            parse_pr_url("https://github.com/owner/repo/issues/123")

        with pytest.raises(ValueError):
            parse_pr_url("https://gitlab.com/owner/repo/pull/123")

        with pytest.raises(ValueError):
            parse_pr_url("not a url")


class TestGitHubClient:
    @patch("src.github.Github")
    @patch("src.github.git")
    @patch("src.github.tempfile.mkdtemp")
    @patch("src.github.os.path.join")
    def test_clone_pr_repo_success(self, mock_join, mock_mkdtemp, mock_git, mock_github):
        """Test successful PR repo cloning with GitHubClient"""
        # Setup mocks
        mock_mkdtemp.return_value = "/tmp/tempdir"
        mock_join.return_value = "/tmp/tempdir/repo"

        # Mock GitHub objects
        mock_repo = MagicMock()
        mock_repo.clone_url = "https://github.com/owner/repo.git"

        mock_pr = MagicMock()
        mock_pr.head.ref = "feature-branch"

        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        # Mock git repo
        mock_git_repo = MagicMock()
        mock_git.Repo.clone_from.return_value = mock_git_repo

        # Create a client and call the method
        client = GitHubClient()
        repo_path, branch_name = client.clone_pr_repo(
            "https://github.com/owner/repo/pull/123")

        # Assertions
        mock_mkdtemp.assert_called_once()
        mock_github_instance.get_repo.assert_called_with("owner/repo")
        mock_repo.get_pull.assert_called_with(123)
        mock_git.Repo.clone_from.assert_called_with(
            "https://github.com/owner/repo.git",
            "/tmp/tempdir/repo"
        )
        mock_git_repo.git.checkout.assert_called_with("feature-branch")

        assert repo_path == "/tmp/tempdir/repo"
        assert branch_name == "feature-branch"

    @patch("src.github.Auth.Token")
    @patch("src.github.Github")
    @patch("src.github.git")
    @patch("src.github.tempfile.mkdtemp")
    def test_clone_pr_repo_with_token(self, mock_mkdtemp, mock_git, mock_github, mock_auth_token):
        """Test PR repo cloning with GitHub token using GitHubClient"""
        # Setup mocks
        mock_auth_token.return_value = "mock_auth_token"
        mock_mkdtemp.return_value = "/tmp/tempdir"

        # Mock GitHub objects
        mock_repo = MagicMock()
        mock_repo.clone_url = "https://github.com/owner/repo.git"

        mock_pr = MagicMock()
        mock_pr.head.ref = "feature-branch"

        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.return_value = mock_repo
        mock_repo.get_pull.return_value = mock_pr

        # Mock git repo
        mock_git_repo = MagicMock()
        mock_git.Repo.clone_from.return_value = mock_git_repo

        # Create a client with token and call the method
        client = GitHubClient(github_token="token123")
        client.clone_pr_repo("https://github.com/owner/repo/pull/123")

        # Assertions
        mock_auth_token.assert_called_with("token123")
        mock_github.assert_called_with(auth=mock_auth_token.return_value)

        # Assert authentication URL was used
        mock_git.Repo.clone_from.assert_called_with(
            "https://token123@github.com/owner/repo.git",
            os.path.join("/tmp/tempdir", "repo")
        )

    @patch("src.github.Github")
    @patch("src.github.tempfile.mkdtemp")
    def test_clone_pr_repo_exception(self, mock_mkdtemp, mock_github):
        """Test error handling during repo cloning with GitHubClient"""
        # Setup mocks
        mock_mkdtemp.return_value = "/tmp/tempdir"

        # Mock GitHub objects to raise exception
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.side_effect = Exception(
            "Connection error")

        # Create a client and call the method
        client = GitHubClient()

        # Call the function and assert exception
        with pytest.raises(RuntimeError) as excinfo:
            client.clone_pr_repo("https://github.com/owner/repo/pull/123")

        assert "Error cloning repository: Connection error" in str(
            excinfo.value)

    @patch("src.github.Github")
    def test_get_pr_target_branch_success(self, mock_github):
        """Test successful retrieval of PR target branch with GitHubClient"""
        # Setup mocks
        mock_pr = MagicMock()
        mock_pr.base.ref = "main"

        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.return_value = mock_repo

        # Create a client and call the method
        client = GitHubClient()  # No token provided
        target_branch = client.get_pr_target_branch(
            "https://github.com/owner/repo/pull/123")

        # Assertions
        mock_github.assert_called_with()  # Should be called without arguments
        mock_github_instance.get_repo.assert_called_with("owner/repo")
        mock_repo.get_pull.assert_called_with(123)
        assert target_branch == "main"

    @patch("src.github.Auth.Token")
    @patch("src.github.Github")
    def test_get_pr_target_branch_with_token(self, mock_github, mock_auth_token):
        """Test PR target branch retrieval with GitHub token using GitHubClient"""
        # Setup mocks
        mock_auth_token.return_value = "mock_auth_token"

        mock_pr = MagicMock()
        mock_pr.base.ref = "development"

        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.return_value = mock_repo

        # Create a client with token and call the method
        client = GitHubClient(github_token="token123")
        target_branch = client.get_pr_target_branch(
            "https://github.com/owner/repo/pull/123")

        # Assertions
        mock_auth_token.assert_called_with("token123")
        mock_github.assert_called_with(auth=mock_auth_token.return_value)
        mock_repo.get_pull.assert_called_with(123)
        assert target_branch == "development"

    @patch("src.github.Github")
    def test_get_pr_target_branch_exception(self, mock_github):
        """Test error handling during PR target branch retrieval with GitHubClient"""
        # Mock GitHub objects to raise exception
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.side_effect = Exception(
            "API rate limit exceeded"
        )

        # Create a client and call the method
        client = GitHubClient()

        # Call the function and assert exception
        with pytest.raises(RuntimeError) as excinfo:
            client.get_pr_target_branch(
                "https://github.com/owner/repo/pull/123")

        assert "Error retrieving PR information: API rate limit exceeded" in str(
            excinfo.value
        )

    @patch("src.github.shutil.rmtree")
    @patch("os.path.exists")
    def test_client_clean_up_success(self, mock_exists, mock_rmtree):
        """Test successful repository cleanup with GitHubClient"""
        # Setup mocks
        mock_exists.return_value = True

        # Create a client and call the method
        client = GitHubClient()
        client.clean_up("/tmp/tempdir/repo")

        # Assertions
        mock_exists.assert_called_once_with("/tmp/tempdir/repo")
        mock_rmtree.assert_called_once()


# Legacy function tests to ensure backwards compatibility
class TestClonePrRepo:
    @patch("src.github.GitHubClient.clone_pr_repo")
    def test_legacy_clone_pr_repo(self, mock_clone_pr_repo):
        """Test that the legacy function correctly delegates to the GitHubClient"""
        mock_clone_pr_repo.return_value = ("/path/to/repo", "branch-name")

        result = clone_pr_repo(
            "https://github.com/owner/repo/pull/123", "token123")

        assert result == ("/path/to/repo", "branch-name")
        mock_clone_pr_repo.assert_called_once()


class TestCleanUp:
    @patch("src.github.shutil.rmtree")
    @patch("os.path.dirname")
    @patch("os.path.exists")
    def test_clean_up_success(self, mock_exists, mock_dirname, mock_rmtree):
        """Test successful repository cleanup with legacy function"""
        # Setup mocks
        mock_exists.return_value = True
        mock_dirname.return_value = "/tmp/tempdir"

        # Call the function
        clean_up("/tmp/tempdir/repo")

        # Assertions
        mock_exists.assert_called_once_with("/tmp/tempdir/repo")
        mock_dirname.assert_called_once_with("/tmp/tempdir/repo")
        mock_rmtree.assert_called_once_with("/tmp/tempdir")

    @patch("os.path.exists")
    def test_clean_up_invalid_path(self, mock_exists):
        """Test with invalid repository path"""
        # Setup mock for non-existent path
        mock_exists.return_value = False

        # Test with non-existent path - should return without error
        clean_up("/non/existent/path")  # This should not raise an exception

        # Test with empty path - should still raise ValueError
        with pytest.raises(ValueError) as excinfo:
            clean_up("")
        assert "Repository path must be a non-empty string" in str(
            excinfo.value)

        # Test with non-string path - should still raise ValueError
        with pytest.raises(ValueError) as excinfo:
            clean_up(None)
        assert "Repository path must be a non-empty string" in str(
            excinfo.value)


class TestGetPrTargetBranch:
    @patch("src.github.GitHubClient.get_pr_target_branch")
    def test_legacy_get_pr_target_branch(self, mock_get_pr_target_branch):
        """Test that the legacy function correctly delegates to the GitHubClient"""
        mock_get_pr_target_branch.return_value = "main"

        result = get_pr_target_branch(
            "https://github.com/owner/repo/pull/123", "token123")

        assert result == "main"
        mock_get_pr_target_branch.assert_called_once()
