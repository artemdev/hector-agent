import logging
import os
import time

import pytest

from src import workspace
from src.workspace import STALE_AFTER_SECONDS, SUFFIX, temp_workdir


@pytest.fixture(autouse=True)
def work_root(tmp_path, monkeypatch):
    """Point WORK_ROOT at a throwaway dir instead of the real `.tmp`."""
    root = tmp_path / ".tmp"
    monkeypatch.setattr(workspace, "WORK_ROOT", root)
    return root


def make_dir(path, age_seconds=0):
    path.mkdir(parents=True)
    then = time.time() - age_seconds
    os.utime(path, (then, then))
    return path


class TestTempWorkdir:
    def test_yields_a_fresh_repo_path_and_deletes_its_dir_on_exit(self, work_root):
        with temp_workdir(prefix="eval-x-") as repo:
            assert not repo.exists()
            assert repo.parent.parent == work_root
            assert repo.parent.name.startswith("eval-x-") and repo.parent.name.endswith(SUFFIX)
            (repo / "backend").mkdir(parents=True)

        assert not repo.parent.exists()

    def test_deletes_its_dir_when_the_block_raises(self):
        with pytest.raises(RuntimeError), temp_workdir() as repo:
            repo.mkdir()
            raise RuntimeError("agent failed")

        assert not repo.parent.exists()

    def test_logs_what_it_could_not_delete(self, caplog):
        with caplog.at_level(logging.WARNING), temp_workdir() as repo:
            locked = repo / "locked"
            locked.mkdir(parents=True)
            (locked / "file").touch()
            locked.chmod(0o500)  # no write permission: its file can't be removed
        try:
            assert "could not delete" in caplog.text
            assert str(locked / "file") in caplog.text
        finally:
            locked.chmod(0o700)

    def test_sweeps_stale_workdirs_and_leaves_everything_else(self, work_root):
        stale = make_dir(work_root / f"eval-old{SUFFIX}", age_seconds=STALE_AFTER_SECONDS + 60)
        recent = make_dir(work_root / f"eval-running{SUFFIX}", age_seconds=60)
        not_ours = make_dir(work_root / "pytest-of-someone", age_seconds=STALE_AFTER_SECONDS + 60)

        with temp_workdir():
            assert not stale.exists()
            assert recent.exists()
            assert not_ours.exists()
