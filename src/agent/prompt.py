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
            - Title: {issue['title']}
            - Culprit: {issue['culprit']}
            - File: {repo_relative(issue['metadata'].get('filename'), workdir)}
            - Details: {issue['metadata'].get('value')}

            Do the following, in order:
            1. Write a failing test that reproduces the issue, then fix the issue so the test passes.
            2. Run the test suite and confirm the failing test now passes and nothing else broke.

            Work only inside the current working directory.
            To review your changes, you may run `git diff` and `git status`. Run no other git command (no stash, checkout, or commit): after you finish, the harness creates the branch, commits, pushes, and opens the PR.
            Return a short summary of the root cause and the fix; it becomes the PR description."""
