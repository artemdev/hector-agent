"""Run commands in the agent image, for graders that execute code the agent wrote."""

import subprocess
import uuid
from collections.abc import Sequence
from pathlib import Path

from src.agent.run_container import run_docker_command


def run_in_image(workdir: Path, command: Sequence[str], cwd: str = ".", mounts: Sequence[str] = (),
                 timeout: int = 300) -> subprocess.CompletedProcess[str]:
    """Run `command` in the image on the checkout at `workdir`, without the API key.

    For running code the agent wrote, such as its tests, somewhere other than the host. `cwd` is relative
    to `workdir`; `mounts` are extra `-v` specs. Raises `subprocess.TimeoutExpired` after `timeout` seconds,
    once the container is killed; an interrupt kills it too.
    """
    name = f"watchdog-run-{uuid.uuid4().hex[:12]}"
    options = ["-w", f"/work/{cwd}", "--entrypoint", command[0], *[arg for m in mounts for arg in ("-v", m)]]
    try:
        return subprocess.run(run_docker_command(name, workdir.resolve(), options, command[1:]),
                              capture_output=True, text=True, timeout=timeout)
    except BaseException:  # timed out or interrupted: stop it before the caller deletes the workdir under it
        subprocess.run(["docker", "kill", name], capture_output=True)
        raise
