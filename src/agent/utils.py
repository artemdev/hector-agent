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
