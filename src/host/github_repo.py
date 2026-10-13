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
        stays full so a fix branch based on it can still be pushed.
        """
        if (dest).exists():
            try:
                shutil.rmtree(dest)
            except OSError:
                logger.warning("could not remove %s", dest, exc_info=True)

        self._run_git("clone", self._clone_url, str(dest))
        if ref:
            self._run_git("-C", str(dest), "-c", "advice.detachedHead=false", "checkout", ref)

        return dest

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

        Returns False when there is nothing to ship (no changes vs the default branch).
        """
        git = ("-C", str(workdir))
        self._run_git(*git, "checkout", "-B", branch)
        self._run_git(*git, "add", "-A")
        if self._run_git(*git, "status", "--porcelain").stdout.strip():
            self._run_git(
                *git,
                "-c", "user.name=watchdog",
                "-c", "user.email=watchdog@users.noreply.github.com",
                "commit", "-m", message,
            )
        ahead = self._run_git(
            *git, "rev-list", "--count", f"origin/{self.default_branch}..HEAD"
        ).stdout.strip()
        return int(ahead) > 0

    def push(self, workdir: Path, branch: str) -> None:
        """Push `branch` from the clone at `workdir` to origin and set upstream."""
        self._run_git("-C", str(workdir), "push", "-u", "origin", branch)

    def open_pull_request(self, branch: str, title: str, body: str) -> str:
        """Open a PR from `branch` into the default branch and return its URL."""
        pr = self._repo.create_pull(
            base=self.default_branch, head=branch, title=title, body=body
        )
        return pr.html_url
