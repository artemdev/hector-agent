import pytest


@pytest.fixture
def source_file():
    """Where the file that raised the error lives, relative to the clone."""
    return "backend/src/routes/index.ts"


@pytest.fixture
def workdir(tmp_path, source_file):
    """A clone containing one file, `source_file`."""
    (tmp_path / source_file).parent.mkdir(parents=True)
    (tmp_path / source_file).touch()
    return tmp_path
