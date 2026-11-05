import pytest

from src.host.dependencies import InstallFailed, install_command, install_dependencies
from src.host.run_container import IMAGE


class FakeProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode, self._out = returncode, (stdout.encode(), stderr.encode())

    async def communicate(self):
        return self._out


def package(path, *files):
    path.mkdir(parents=True, exist_ok=True)
    for name in ("package.json", *files):
        (path / name).write_text("{}")
    return path


class TestInstallCommand:
    @pytest.mark.parametrize("lockfile, manager", [
        ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("package-lock.json", "npm"),
    ])
    def test_picks_the_package_manager_from_the_lockfile(self, tmp_path, lockfile, manager):
        assert install_command(package(tmp_path, lockfile))[0] == manager

    def test_installs_frozen_so_the_lockfile_stays_out_of_the_pr(self, tmp_path):
        assert install_command(package(tmp_path, "package-lock.json"))[1] == "ci"
        assert "--frozen-lockfile" in install_command(package(tmp_path / "p", "pnpm-lock.yaml"))
        assert "--no-package-lock" in install_command(package(tmp_path / "bare"))

    def test_skips_a_repo_without_package_json(self, tmp_path):
        assert install_command(tmp_path) is None


class TestInstallDependencies:
    @pytest.fixture
    def docker(self, monkeypatch):
        """Fake `docker run`: set `.process` to what it returns; `.commands` records each call."""
        class Docker:
            process = FakeProcess(0)
            commands: list[tuple] = []

        async def create_subprocess_exec(*command, **kwargs):
            Docker.commands.append(command)
            return Docker.process

        monkeypatch.setattr("asyncio.create_subprocess_exec", create_subprocess_exec)
        return Docker

    async def test_runs_the_install_in_the_package_inside_the_image(self, docker, tmp_path):
        package(tmp_path / "backend", "package-lock.json")

        assert await install_dependencies(tmp_path, "backend") == ["npm", "ci", "--no-audit", "--no-fund"]

        [command] = docker.commands
        image = command.index(IMAGE)
        assert command[command.index("-w") + 1] == "/work/backend"
        assert command[command.index("--entrypoint") + 1] == "npm"
        assert command[image + 1:] == ("ci", "--no-audit", "--no-fund")
        assert "ANTHROPIC_API_KEY" not in " ".join(command)

    async def test_keeps_node_modules_out_of_the_commit(self, docker, tmp_path):
        package(tmp_path)

        await install_dependencies(tmp_path)

        assert "node_modules/" in (tmp_path / ".git/info/exclude").read_text().splitlines()

    async def test_does_nothing_without_package_json(self, docker, tmp_path):
        assert await install_dependencies(tmp_path) is None
        assert docker.commands == []

    async def test_raises_with_the_install_error(self, docker, tmp_path):
        package(tmp_path)
        docker.process = FakeProcess(1, stderr="ERESOLVE could not resolve")

        with pytest.raises(InstallFailed, match="exited with 1: ERESOLVE"):
            await install_dependencies(tmp_path)
