import subprocess

import pytest

from evals.harness.image import run_in_image
from src.run_container import IMAGE


class TestRunInImage:
    @pytest.fixture
    def docker(self, monkeypatch):
        """Fake `subprocess.run`: `.calls` records each command; set `.error` to make `docker run` raise it."""
        class Docker:
            calls: list[list[str]] = []
            error: BaseException | None = None

        def run(command, **kwargs):
            Docker.calls.append(command)
            if command[:2] == ["docker", "run"] and Docker.error:
                raise Docker.error
            return subprocess.CompletedProcess(command, 0, "ok", "")

        monkeypatch.setattr("subprocess.run", run)
        return Docker

    def test_runs_the_command_in_the_package_without_the_api_key(self, docker, tmp_path):
        run_in_image(tmp_path, ["npm", "test", "--", "--run"], cwd="backend", mounts=["/tmp/r:/report"])

        [command] = docker.calls
        image = command.index(IMAGE)
        assert command[command.index("--entrypoint") + 1] == "npm"
        assert command[image + 1:] == ["test", "--", "--run"]
        assert "/work/backend" in command and "/tmp/r:/report" in command
        assert "-e" not in command

    @pytest.mark.parametrize("error", [subprocess.TimeoutExpired("docker", 300), KeyboardInterrupt()],
                             ids=["timeout", "interrupt"])
    def test_kills_the_container_when_it_stops_early(self, docker, tmp_path, error):
        docker.error = error

        with pytest.raises(type(error)):
            run_in_image(tmp_path, ["npm", "test"])

        run, kill = docker.calls
        assert kill == ["docker", "kill", run[run.index("--name") + 1]]
