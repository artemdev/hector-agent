"""What the agent changed in the clone, relative to HEAD (the case's buggy tag)."""

import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from evals.harness.vitest import TEST_FILE

TEST_DIRS = {"test", "tests", "__tests__"}


def changed_files(repo_path: Path) -> list[str]:
    """Files changed vs HEAD (the buggy tag), new ones included; `package-lock.json` is ignored."""
    def git(*args: str) -> list[str]:
        out = subprocess.run(["git", *args, "-z", "--", ".", ":!**/package-lock.json"],
                             cwd=repo_path, capture_output=True, text=True, check=True).stdout
        return [p for p in out.split("\0") if p]

    return (git("diff", "--name-only", "--no-renames", "HEAD")
            + git("ls-files", "--others", "--exclude-standard"))


def is_test_side(path: str) -> bool:
    """A test file, or a helper inside a test directory."""
    return bool(TEST_FILE.search(path)) or any(part in TEST_DIRS for part in Path(path).parts[:-1])


@contextmanager
def buggy_source(repo_path: Path, source: list[str]) -> Iterator[None]:
    """Temporarily put `source` (repo-relative) back to HEAD, then restore the agent's versions."""
    with tempfile.TemporaryDirectory() as backup:
        saved = Path(backup)
        for p in source:
            if (repo_path / p).exists():
                (saved / p).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo_path / p, saved / p)
        try:
            new = set(subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z", "--", *source],
                                     cwd=repo_path, capture_output=True, text=True, check=True).stdout.split("\0"))
            for p in source:
                if p in new:
                    (repo_path / p).unlink()
                else:  # modified or deleted by the agent
                    subprocess.run(["git", "checkout", "HEAD", "--", p], cwd=repo_path, capture_output=True, check=True)
            yield
        finally:
            for p in source:
                if (saved / p).exists():
                    shutil.copy2(saved / p, repo_path / p)
                else:  # the agent deleted it
                    (repo_path / p).unlink(missing_ok=True)
