from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.github_repo import GitHubRepo


@pytest.fixture
def gh():
    with patch("src.github_repo.Github") as github_cls:
        repo = MagicMock()
        repo.clone_url = "https://github.com/artemdev/watchdog-fixtures.git"
        github_cls.return_value.get_repo.return_value = repo
        yield github_cls


def test_init_authenticates_and_resolves_repo(gh):
    GitHubRepo("artemdev/watchdog-fixtures", token="ghp_x")

    gh.return_value.get_repo.assert_called_once_with("artemdev/watchdog-fixtures")


@pytest.mark.parametrize(
    "given",
    [
        "artemdev/watchdog-fixtures",
        "https://github.com/artemdev/watchdog-fixtures",
        "https://github.com/artemdev/watchdog-fixtures.git",
    ],
)
def test_init_accepts_url_or_full_name(gh, given):
    GitHubRepo(given, token="ghp_x")

    gh.return_value.get_repo.assert_called_once_with("artemdev/watchdog-fixtures")


def test_clone_runs_git_with_token_url(gh, tmp_path):
    dest = tmp_path / "fixtures"
    with patch("src.github_repo.subprocess.run") as run:
        result = GitHubRepo("artemdev/watchdog-fixtures", token="ghp_x").clone(dest)

    run.assert_called_once_with(
        ["git", "clone", "https://x-access-token:ghp_x@github.com/artemdev/watchdog-fixtures.git", str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result == dest


def test_clone_skips_if_already_cloned(gh, tmp_path):
    dest = tmp_path / "fixtures"
    (dest / ".git").mkdir(parents=True)
    with patch("src.github_repo.subprocess.run") as run:
        GitHubRepo("artemdev/watchdog-fixtures", token="ghp_x").clone(dest)

    run.assert_not_called()
