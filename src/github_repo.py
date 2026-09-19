import subprocess
from pathlib import Path

from github import Auth, Github

class GitHubRepo:
    """A GitHub repository plus the auth needed to talk to it over both the REST API and git.

    One token drives both transports: PyGithub for API calls (metadata, PRs later)
    and a tokenized HTTPS URL for git subprocess calls (clone, and later push).
    """

    def __init__(self, repo: str, token: str):
        self.full_name = self._to_full_name(repo)
        self._token = token
        self._github = Github(auth=Auth.Token(token))
        self._repo = self._github.get_repo(self.full_name)
        self._clone_url = self._repo.clone_url.replace(
            "https://", f"https://x-access-token:{token}@", 1
        )

    @staticmethod
    def _to_full_name(repo: str) -> str:
        return repo.removeprefix("https://github.com/").removesuffix(".git").strip("/")

    def clone(self, dest: Path) -> Path:
        """Clone the repo into `dest`"""
        if (dest / ".git").exists():
            return dest
        subprocess.run(
            ["git", "clone", self._clone_url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
        return dest
