import os
from unittest.mock import MagicMock, patch

import pytest

from src.github import clean_up, clone_pr_repo, get_pr_target_branch, parse_pr_url


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


class TestClonePrRepo:
    @patch("src.github.Github")
    @patch("src.github.git")
    @patch("src.github.tempfile.mkdtemp")
    @patch("src.github.os.path.join")
    def test_clone_pr_repo_success(self, mock_join, mock_mkdtemp, mock_git, mock_github):
        """Test successful PR repo cloning"""
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

        # Call the function
        repo_path, branch_name = clone_pr_repo(
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

    @patch("src.github.Github")
    @patch("src.github.git")
    @patch("src.github.tempfile.mkdtemp")
    @patch("src.github.os.system")
    def test_clone_pr_repo_with_token(self, mock_os_system, mock_mkdtemp, mock_git, mock_github):
        """Test PR repo cloning with GitHub token"""
        # Setup mocks
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

        # Call the function with a token
        clone_pr_repo("https://github.com/owner/repo/pull/123",
                      github_token="token123")

        # Assert authentication URL was used
        mock_git.Repo.clone_from.assert_called_with(
            "https://token123@github.com/owner/repo.git",
            os.path.join("/tmp/tempdir", "repo")
        )

    @patch("src.github.Github")
    @patch("src.github.tempfile.mkdtemp")
    @patch("src.github.os.system")
    def test_clone_pr_repo_exception(self, mock_os_system, mock_mkdtemp, mock_github):
        """Test error handling during repo cloning"""
        # Setup mocks
        mock_mkdtemp.return_value = "/tmp/tempdir"

        # Mock GitHub objects to raise exception
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.side_effect = Exception(
            "Connection error")

        # Call the function and assert exception
        with pytest.raises(RuntimeError) as excinfo:
            clone_pr_repo("https://github.com/owner/repo/pull/123")

        # Verify temporary directory cleanup was attempted
        mock_os_system.assert_called_with("rm -rf /tmp/tempdir")
        assert "Error cloning repository: Connection error" in str(
            excinfo.value)


class TestCleanUp:
    @patch("shutil.rmtree")
    @patch("os.path.dirname")
    @patch("os.path.exists")
    def test_clean_up_success(self, mock_exists, mock_dirname, mock_rmtree):
        """Test successful repository cleanup"""
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

    @patch("os.system")
    @patch("shutil.rmtree")
    @patch("os.path.dirname")
    @patch("os.path.exists")
    def test_clean_up_fallback(self, mock_exists, mock_dirname, mock_rmtree, mock_system):
        """Test fallback to os.system when shutil.rmtree fails"""
        # Setup mocks
        mock_exists.return_value = True
        mock_dirname.return_value = "/tmp/tempdir"
        mock_rmtree.side_effect = Exception("Permission denied")

        # Call the function
        clean_up("/tmp/tempdir/repo")

        # Assertions
        mock_rmtree.assert_called_once_with("/tmp/tempdir")
        mock_system.assert_called_once_with("rm -rf /tmp/tempdir")


class TestGetPrTargetBranch:
    @patch("src.github.Github")
    def test_get_pr_target_branch_success(self, mock_github):
        """Test successful retrieval of PR target branch"""
        # Setup mocks
        mock_pr = MagicMock()
        mock_pr.base.ref = "main"

        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.return_value = mock_repo

        # Call the function
        target_branch = get_pr_target_branch(
            "https://github.com/owner/repo/pull/123")

        # Assertions
        mock_github_instance.get_repo.assert_called_with("owner/repo")
        mock_repo.get_pull.assert_called_with(123)
        assert target_branch == "main"

    @patch("src.github.Github")
    def test_get_pr_target_branch_with_token(self, mock_github):
        """Test PR target branch retrieval with GitHub token"""
        # Setup mocks
        mock_pr = MagicMock()
        mock_pr.base.ref = "development"

        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.return_value = mock_repo

        # Call the function with a token
        target_branch = get_pr_target_branch(
            "https://github.com/owner/repo/pull/123",
            github_token="token123"
        )

        # Assertions
        mock_github.assert_called_with("token123")
        assert target_branch == "development"

    @patch("src.github.Github")
    def test_get_pr_target_branch_exception(self, mock_github):
        """Test error handling during PR target branch retrieval"""
        # Mock GitHub objects to raise exception
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_repo.side_effect = Exception(
            "API rate limit exceeded"
        )

        # Call the function and assert exception
        with pytest.raises(RuntimeError) as excinfo:
            get_pr_target_branch("https://github.com/owner/repo/pull/123")

        assert "Error retrieving PR information: API rate limit exceeded" in str(
            excinfo.value
        )
