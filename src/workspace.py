import logging
import shutil
import tempfile
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

WORK_ROOT = Path(__file__).resolve().parents[2] / ".tmp"
# Every dir `temp_workdir` makes ends with this, so the stale sweep never touches anything else in WORK_ROOT.
SUFFIX = ".workdir"
# Older than any run can last: a dir this old was left by a run that was killed before cleanup.
STALE_AFTER_SECONDS = 6 * 60 * 60


@contextmanager
def temp_workdir(prefix: str = "watchdog-") -> Generator[Path, None, None]:
    """Yield a fresh, not-yet-existing `repo` path inside a unique dir under `WORK_ROOT`.

    The whole dir is deleted when the block exits, even on error; whatever can't be deleted is
    logged. Dirs left behind by killed runs are swept on the next call.
    """
    WORK_ROOT.mkdir(exist_ok=True)
    remove_stale_workdirs()

    workdir = Path(tempfile.mkdtemp(prefix=prefix, suffix=SUFFIX, dir=WORK_ROOT))
    try:
        yield workdir / "repo"
    finally:
        remove_workdir(workdir)


def remove_stale_workdirs() -> None:
    """Delete `temp_workdir` dirs older than `STALE_AFTER_SECONDS`."""
    cutoff = time.time() - STALE_AFTER_SECONDS
    for workdir in WORK_ROOT.glob(f"*{SUFFIX}"):
        if workdir.is_dir() and workdir.stat().st_mtime < cutoff:
            logger.info("removing stale workdir %s", workdir)
            remove_workdir(workdir)


def remove_workdir(workdir: Path) -> None:
    """Delete `workdir`, logging each path that can't be deleted instead of stopping at it."""
    def log_failure(function, path, exc: BaseException) -> None:
        logger.warning("could not delete %s: %s", path, exc)

    shutil.rmtree(workdir, onexc=log_failure)
