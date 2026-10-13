import base64
import subprocess
from unittest.mock import patch

import pytest

from src.host.github_repo import GitError, GitHubRepo

REPO = "user/repo"
CLONE_URL = f"https://github.com/{REPO}.git"
TOKEN = "test-token"
PR_URL = f"https://github.com/{REPO}/pull/1"
AUTH_HEADER = "Authorization: Basic " + base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()


@pytest.fixture
def github():
    """Fake PyGithub: no network, the repo has a clone URL and a `main` default branch."""
    with patch("src.host.github_repo.Github") as github_cls:
        gh_repo = github_cls.return_value.get_repo.return_value
        gh_repo.clone_url = CLONE_URL
        gh_repo.default_branch = "main"
        yield github_cls


@pytest.fixture
def gh_repo(github):
    """The fake repo PyGithub returns: what `GitHubRepo` talks to."""
    return github.return_value.get_repo.return_value


@pytest.fixture
def repo(github):  # `github` creates mock for GitHubRepo
    return GitHubRepo(REPO, token=TOKEN)


@pytest.fixture
def git_run():
    """Fake `subprocess.run`, to check which git commands would run."""
    with patch("src.host.github_repo.subprocess.run") as run:
        yield run


def commands(git_run):
    return [call.args[0] for call in git_run.call_args_list]


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


class TestInit:
    @pytest.mark.parametrize(
        "given",
        [REPO, f"https://github.com/{REPO}", CLONE_URL],
        ids=["full name", "web url", "clone url"],
    )
    def test_accepts_url_or_full_name(self, github, given):
        assert GitHubRepo(given, token=TOKEN).full_name == REPO


class TestAuth:
    def test_token_goes_in_env_not_command_line(self, repo, git_run, tmp_path):
        repo.clone(tmp_path / "repo")

        command, env = git_run.call_args.args[0], git_run.call_args.kwargs["env"]
        assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
        assert env["GIT_CONFIG_VALUE_0"] == AUTH_HEADER
        assert not any(TOKEN in arg for arg in command)


class TestClone:
    def test_clones_into_dest(self, repo, git_run, tmp_path):
        dest = tmp_path / "repo"

        assert repo.clone(dest) == dest
        assert commands(git_run) == [["git", "clone", CLONE_URL, str(dest)]]

    def test_checks_out_ref(self, repo, git_run, tmp_path):
        dest = tmp_path / "repo"

        repo.clone(dest, ref="1-bug")

        assert commands(git_run) == [
            ["git", "clone", CLONE_URL, str(dest)],
            ["git", "-C", str(dest), "-c", "advice.detachedHead=false", "checkout", "1-bug"],
        ]

    def test_replaces_existing_dir(self, repo, git_run, tmp_path):
        dest = tmp_path / "repo"
        dest.mkdir()
        (dest / "stale.txt").touch()

        repo.clone(dest)

        assert not dest.exists()  # removed before cloning; the clone itself is faked


class TestCloneTag:
    def test_shallow_clones_at_tag(self, repo, git_run, tmp_path):
        dest = tmp_path / "repo"

        assert repo.clone_tag("1-bug", dest) == dest
        assert commands(git_run) == [[
            "git", "-c", "advice.detachedHead=false",
            "clone", "--quiet", "--depth", "1", "--branch", "1-bug",
            CLONE_URL, str(dest),
        ]]


class TestPush:
    def test_pushes_branch_and_sets_upstream(self, repo, git_run, tmp_path):
        repo.push(tmp_path, "fix/x")

        assert commands(git_run) == [["git", "-C", str(tmp_path), "push", "-u", "origin", "fix/x"]]


class TestOpenPullRequest:
    def test_targets_default_branch(self, repo, gh_repo):
        gh_repo.create_pull.return_value.html_url = PR_URL

        assert repo.open_pull_request("fix/x", title="t", body="b") == PR_URL
        gh_repo.create_pull.assert_called_once_with(base="main", head="fix/x", title="t", body="b")


class TestCommitAll:
    """Real git against a local 'origin' -- no network."""

    @pytest.fixture
    def workdir(self, tmp_path):
        """A clone of a local bare repo whose `main` has one commit."""
        git("init", "--bare", "-b", "main", "origin.git", cwd=tmp_path)
        git("clone", "origin.git", "work", cwd=tmp_path)
        work = tmp_path / "work"
        (work / "app.txt").write_text("buggy\n")
        git("add", "-A", cwd=work)
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init", cwd=work)
        git("push", "origin", "main", cwd=work)
        return work

    def test_commits_every_change_on_new_branch(self, repo, workdir):
        (workdir / "app.txt").write_text("fixed\n")
        (workdir / "new_test.txt").write_text("test\n")

        assert repo.commit_all(workdir, "fix/x", message="fix: it") is True

        assert git("branch", "--show-current", cwd=workdir).strip() == "fix/x"
        assert git("log", "-1", "--format=%s", cwd=workdir).strip() == "fix: it"
        assert git("show", "--name-only", "--format=", cwd=workdir).split() == ["app.txt", "new_test.txt"]

    def test_returns_false_without_changes(self, repo, workdir):
        assert repo.commit_all(workdir, "fix/x", message="fix: it") is False


class TestGitErrors:
    def test_include_git_stderr(self, repo, tmp_path):
        with pytest.raises(GitError, match="not a git repository"):
            repo._run_git("-C", str(tmp_path), "status")
