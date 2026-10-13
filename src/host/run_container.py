"""Run the agent in the agent image (Dockerfile.agent): the host side of `src/agent/__main__.py`.

The repo to fix, checked out by the caller, is mounted at /work with its .git read-only, so the agent's
edits land in the checkout while git hooks and config, which the host runs when it commits, stay out of
its reach. The only secrets that enter the container are the agent's Claude credentials: ANTHROPIC_API_KEY
or CLAUDE_CODE_OAUTH_TOKEN (from `claude setup-token`, to use a Claude subscription). Build the image first:
`make image`.
"""
import asyncio
import json
import tempfile
import uuid
from collections.abc import Sequence
from pathlib import Path

from claude_agent_sdk import ResultMessage

from src.agent.run_agent import AgentFailed, AgentRun

IMAGE = "watchdog-agent:dev"
TIMEOUT_SECONDS = 30 * 60
AGENT_UID = "uid=1000,gid=1000"  # the image's `node` user


def run_docker_command(name: str, workdir: Path, options: Sequence[str] = (), command: Sequence[str] = ()) -> list[str]:
    """`docker run` of the image on the checkout at `workdir`, locked down; `options` go before the image."""
    return [
        "docker", "run", "--rm", "--name", name,
        "-v", f"{workdir}:/work",
        "-v", f"{workdir}/.git:/work/.git:ro",
        "--read-only",
        "--tmpfs", f"/tmp:rw,noexec,nosuid,size=256m,{AGENT_UID}",
        "--tmpfs", f"/home/node:rw,nosuid,size=256m,{AGENT_UID}",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--memory", "4g", "--cpus", "2", "--pids-limit", "512",
        *options,
        IMAGE,
        *command,
    ]


def read_run(output: str) -> AgentRun:
    """"Parse the container's stdout into an `AgentRun`;
    raise `AgentFailed` if the agent reported a failure."""

    record = json.loads(output.splitlines()[-1])

    if "failed" in record:
        raise AgentFailed(record["failed"])
    return AgentRun(ResultMessage(**record["result"]), [tuple(call) for call in record["tool_calls"]])


async def run_container(workdir: Path, event: dict) -> AgentRun:
    """Run the agent in a fresh container on the repo checked out at `workdir`."""

    name = f"watchdog-agent-{uuid.uuid4().hex[:12]}"

    with tempfile.TemporaryDirectory() as tmp:
        event_file = Path(tmp) / "event.json"
        event_file.write_text(json.dumps(event))
        command = run_docker_command(name, workdir.resolve(), [
            "-v", f"{event_file}:/event.json:ro",
            "-e", "ANTHROPIC_API_KEY",
            "-e", "CLAUDE_CODE_OAUTH_TOKEN",
        ])

        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), TIMEOUT_SECONDS)
        except BaseException as e:
            kill = await asyncio.create_subprocess_exec(
                "docker", "kill", name, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )

            await kill.wait()

            if isinstance(e, TimeoutError):
                raise AgentFailed(f"agent container timed out after {TIMEOUT_SECONDS}s")
            raise

    output = stdout.decode().strip()

    if not output:
        raise AgentFailed(f"agent container exited with {process.returncode}: {stderr.decode()[-2000:]}")

    return read_run(output)
