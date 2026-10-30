import base64
import logging
import os
import subprocess
import shutil
from pathlib import Path
from github import Auth, Github

logger = logging.getLogger(__name__)


class GitError(Exception):
    """A git command failed; the message includes git's own error output."""


class GitHubRepo:
    """A GitHub repository plus the auth needed to talk to it over both the REST API and git.

    One token drives both transports: PyGithub for API calls (metadata, PRs)
    and an Authorization header for git subprocess calls (clone, push).
    """

    def __init__(self, repo: str, token: str):
        self.full_name = (
            repo.removeprefix("https://github.com/").removesuffix(".git").strip("/")
        )
        self._github = Github(auth=Auth.Token(token))
        self._repo = self._github.get_repo(self.full_name)
        self._clone_url = self._repo.clone_url
        # what fix branches are compared against and PRs target: the default branch, or the branch `clone` checked out
        self.base_branch = self._repo.default_branch
        # what `commit_all` counts new commits from: where `clone` left HEAD
        self._clone_point = f"origin/{self.base_branch}"
        self._git_env = {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {base64.b64encode(f"x-access-token:{token}".encode()).decode()}",
        }

    @property
    def default_branch(self) -> str:
        return self._repo.default_branch

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["git", *args],
                env={**os.environ, **self._git_env},
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise GitError(f"git {' '.join(args)} failed:\n{e.stderr.strip()}") from e

    def clone(self, dest: Path, ref: str | None = None) -> Path:
        """Clone the repo into `dest`, replacing anything already there.

        With `ref` (a tag, branch or commit) the clone is checked out there; history
        stays full so a fix branch based on it can still be pushed. When `ref` is a
        branch it becomes `base_branch`, so the PR goes back into it; a tag or commit
        keeps the default branch as `base_branch`.
        """
        if (dest).exists():
            try:
                shutil.rmtree(dest)
            except OSError:
                logger.warning("could not remove %s", dest, exc_info=True)

        self._run_git("clone", self._clone_url, str(dest))
        if ref:
            try:
                self._run_git("-C", str(dest), "-c", "advice.detachedHead=false", "checkout", ref)
            except GitError as e:
                raise GitError(f"{self.full_name} has no branch, tag or commit {ref!r}; push it to GitHub first") from e
            if self._is_remote_branch(dest, ref):
                self.base_branch = ref
                self._clone_point = f"origin/{ref}"
            else:
                self._clone_point = ref

        return dest

    def _is_remote_branch(self, workdir: Path, ref: str) -> bool:
        try:
            self._run_git("-C", str(workdir), "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{ref}")
        except GitError:
            return False
        return True

    def clone_tag(self, tag: str, dest: Path) -> Path:
        """Shallow-clone the repo into `dest`, checked out at `tag` (detached HEAD)."""
        self._run_git(
            "-c", "advice.detachedHead=false",
            "clone", "--quiet", "--depth", "1", "--branch", tag,
            self._clone_url, str(dest),
        )
        return dest

    def commit_all(self, workdir: Path, branch: str, message: str) -> bool:
        """Put every change in `workdir` on a new `branch` as one commit.

        Returns False when there is nothing to ship (no commits since what `clone` checked out).
        """
        git = ("-C", str(workdir))
        self._run_git(*git, "checkout", "-B", branch)
        self._run_git(*git, "add", "-A")
        if self._run_git(*git, "status", "--porcelain").stdout.strip():
            self._run_git(
                *git,
                "-c", "user.name=hector",
                "-c", "user.email=hector@users.noreply.github.com",
                "commit", "-m", message,
            )
        ahead = self._run_git(
            *git, "rev-list", "--count", f"{self._clone_point}..HEAD"
        ).stdout.strip()
        return int(ahead) > 0

    def push(self, workdir: Path, branch: str) -> None:
        """Push `branch` from the clone at `workdir` to origin and set upstream."""
        self._run_git("-C", str(workdir), "push", "-u", "origin", branch)

    def open_pull_request(self, branch: str, title: str, body: str) -> str:
        """Open a PR from `branch` into `base_branch` and return its URL."""
        pr = self._repo.create_pull(
            base=self.base_branch, head=branch, title=title, body=body
        )
        return pr.html_url
