import dataclasses
import json
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from src.run_container import IMAGE, run_docker_command, read_run, run_container
from src.agent.run_agent import AgentFailed

RESULT = ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1,
                       session_id="s", result="fixed the trim", total_cost_usd=0.5)


def printed(tool_calls=()) -> str:
    """What `__main__.py` prints when the agent finishes."""
    return json.dumps({"result": dataclasses.asdict(RESULT), "tool_calls": tool_calls}) + "\n"


def env_names(command) -> list[str]:
    return [command[i + 1] for i, arg in enumerate(command) if arg == "-e"]


class TestRunDockerCommand:
    def test_mounts_the_clone_with_git_read_only(self):
        command = run_docker_command("n", Path("/clone"))

        assert "/clone:/work" in command
        assert "/clone/.git:/work/.git:ro" in command

    def test_puts_options_before_the_image_and_the_command_after_it(self):
        command = run_docker_command("n", Path("/clone"), ["-w", "/work/backend"], ["test", "--run"])

        image = command.index(IMAGE)
        assert command.index("-w") < image
        assert command[image + 1:] == ["test", "--run"]


class TestReadRun:
    def test_rebuilds_the_tool_calls_and_the_result(self):
        agent_run = read_run(printed([["Bash", {"command": "ls"}], ["Edit", {"file_path": "a.ts"}]]))

        assert agent_run.tool_calls == [("Bash", {"command": "ls"}), ("Edit", {"file_path": "a.ts"})]
        assert (agent_run.result.result, agent_run.result.total_cost_usd) == ("fixed the trim", 0.5)

    def test_reads_only_the_last_line(self):
        agent_run = read_run("stray output\n" + printed())

        assert agent_run.result.result == "fixed the trim"

    def test_raises_the_agents_error(self):
        with pytest.raises(AgentFailed, match="boom"):
            read_run(json.dumps({"failed": "boom"}))


class FakeProcess:
    def __init__(self, returncode: int, stdout: str, stderr: str = ""):
        self.returncode, self._out = returncode, (stdout.encode(), stderr.encode())

    async def communicate(self):
        return self._out

    async def wait(self):
        return self.returncode


class TestRunContainer:
    @pytest.fixture
    def docker(self, monkeypatch):
        """Fake `docker run`: set `.process` to what it returns; `.command` records how it was called,
        `.kills` each `docker kill`."""
        class Docker:
            process: FakeProcess
            command: tuple = ()
            kills: list[tuple] = []

        async def create_subprocess_exec(*command, **kwargs):
            if command[:2] == ("docker", "kill"):
                Docker.kills.append(command)
                return FakeProcess(0, "")
            Docker.command = command
            [event_mount] = [arg for arg in command if arg.endswith(":/event.json:ro")]
            assert json.loads(Path(event_mount.split(":")[0]).read_text()) == {"id": 1}  # the event goes in
            return Docker.process

        monkeypatch.setattr("asyncio.create_subprocess_exec", create_subprocess_exec)
        return Docker

    async def test_returns_the_run(self, docker, tmp_path):
        docker.process = FakeProcess(0, printed())

        agent_run = await run_container(tmp_path, {"id": 1})

        assert agent_run.result.result == "fixed the trim"
        assert f"{tmp_path.resolve()}:/work" in docker.command
        assert env_names(docker.command) == ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]  # names only

    async def test_reports_dockers_own_error(self, docker, tmp_path):
        docker.process = FakeProcess(125, "", "Unable to find image 'watchdog-agent:dev'")

        with pytest.raises(AgentFailed, match="exited with 125: Unable to find image"):
            await run_container(tmp_path, {"id": 1})

    async def test_kills_the_container_when_interrupted(self, docker, tmp_path):
        class Interrupted(FakeProcess):
            async def communicate(self):
                raise KeyboardInterrupt

        docker.process = Interrupted(0, "")

        with pytest.raises(KeyboardInterrupt):
            await run_container(tmp_path, {"id": 1})

        assert docker.kills == [("docker", "kill", docker.command[docker.command.index("--name") + 1])]

