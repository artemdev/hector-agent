from pathlib import Path, PurePath


def repo_relative(filename: str | None, workdir: Path) -> str | None:
    """Map a path from the machine that raised the error onto the clone at `workdir`.

    Sentry reports absolute paths (e.g. /Users/me/app/backend/src/x.ts); returns the
    longest suffix that exists in the clone ("backend/src/x.ts"), else the bare file name.
    """
    if not filename:
        return None

    parts = PurePath(filename).parts

    for i in range(len(parts)):
        candidate = PurePath(*parts[i:])

        if not candidate.is_absolute() and (workdir / candidate).exists():
            return str(candidate)

    return parts[-1]


def make_prompt(event: dict, workdir: Path) -> str:
    issue = event["data"]["issue"]
    return f"""A Sentry issue was reported in this repository.
            Issue:
            - Title: {issue["title"]}
            - Culprit: {issue["culprit"]}
            - File: {repo_relative(issue["metadata"].get("filename"), workdir)}
            - Details: {issue["metadata"].get("value")}

            Do the following, in order:
            1. Check that the error comes from this repository's code. If it doesn't (e.g. a browser extension, a third-party script, or a frame that isn't in this repo), change nothing and stop: say why in your summary.
            2. Write a test that reproduces the issue and run it to see it fail before you edit any source file. Then fix the issue so the test passes. Don't undo your fix to re-check the failure: you already saw it.
            3. Run the test suite and confirm the failing test now passes and nothing else broke.

            Work only inside the current working directory.
            Do not read .env files, credentials or tokens: the fix never needs them.
            To review your changes, you may run `git diff` and `git status`. Run no other git command (no log, show, stash, checkout, restore, or commit): after you finish, the harness creates the branch, commits, pushes, and opens the PR.
            Return a short summary of the root cause and the fix; it becomes the PR description."""
