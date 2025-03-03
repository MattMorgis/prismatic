from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.main import run_multi_code_review


@pytest.mark.asyncio
@patch("src.main.get_github_token")
@patch("src.main.GitHubClient")
@patch("src.main.app.run")
async def test_run_multi_code_review_cleanup(mock_app_run, mock_github_client, mock_get_github_token):
    """Test that the clean_up function is called in the finally block even when an exception occurs."""
    # Setup mocks
    mock_get_github_token.return_value = "fake_token"

    # Mock the GitHubClient instance and its methods
    mock_client_instance = MagicMock()
    mock_client_instance.clone_pr_repo.return_value = (
        "/tmp/repo_path", "feature-branch")
    mock_github_client.return_value = mock_client_instance

    # Mock app context manager
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = MagicMock()
    mock_context.__aenter__.return_value.logger = MagicMock()
    mock_app_run.return_value = mock_context

    # Test normal execution
    await run_multi_code_review("https://github.com/owner/repo/pull/123")

    # Assert client was created with the token and methods were called
    mock_github_client.assert_called_once_with(github_token="fake_token")
    mock_client_instance.clone_pr_repo.assert_called_once_with(
        "https://github.com/owner/repo/pull/123")
    mock_client_instance.get_pr_target_branch.assert_called_once_with(
        "https://github.com/owner/repo/pull/123")

    # Assert clean_up was called with the correct path
    mock_client_instance.clean_up.assert_called_once_with("/tmp/repo_path")

    # Reset mocks
    mock_client_instance.clean_up.reset_mock()
    mock_client_instance.clone_pr_repo.reset_mock()

    # Test with exception during clone
    mock_client_instance.clone_pr_repo.side_effect = RuntimeError("Test error")

    # Expect the exception to be raised
    with pytest.raises(RuntimeError):
        await run_multi_code_review("https://github.com/owner/repo/pull/123")

    # Assert clean_up was not called since repo_path would be None in this case
    mock_client_instance.clean_up.assert_not_called()


@pytest.mark.asyncio
@patch("src.main.get_github_token")
@patch("src.main.GitHubClient")
@patch("src.main.app.run")
async def test_run_multi_code_review_exception_after_clone(mock_app_run, mock_github_client, mock_get_github_token):
    """Test that the clean_up function is called in the finally block when an exception occurs after cloning."""
    # Setup mocks
    mock_get_github_token.return_value = "fake_token"

    # Mock the GitHubClient instance and its methods
    mock_client_instance = MagicMock()
    mock_client_instance.clone_pr_repo.return_value = (
        "/tmp/repo_path", "feature-branch")
    mock_github_client.return_value = mock_client_instance

    # Mock app context manager
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = MagicMock()
    mock_context.__aenter__.return_value.logger = MagicMock()
    mock_app_run.return_value = mock_context

    # Create a function that will raise an exception after the repo is cloned
    # We'll patch print to simulate an exception happening after cloning but before the function completes
    with patch("builtins.print") as mock_print:
        def print_side_effect(message):
            if isinstance(message, str) and "Cloned repository" in message:
                raise ValueError("Test error after clone")

        mock_print.side_effect = print_side_effect

        # Expect the exception to be raised
        with pytest.raises(ValueError):
            await run_multi_code_review("https://github.com/owner/repo/pull/123")

    # Assert clean_up was called even though an exception occurred
    mock_client_instance.clean_up.assert_called_once_with("/tmp/repo_path")
