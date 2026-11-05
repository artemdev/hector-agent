"""Install the clone's JS dependencies before the agent runs, so it can run the test suite from the start.

Runs in the agent image, so native modules get Linux binaries, with the same lockdown as the agent but
without its Claude credentials. The package manager comes from the lockfile, and the install is frozen so the
lockfile never changes and never lands in the PR. GIT_ROOT_PATH picks the package in a monorepo (default:
the repo root).
"""

import asyncio
import uuid
from pathlib import Path

from src.host.run_container import AGENT_UID, run_docker_command

TIMEOUT_SECONDS = 10 * 60

# first match wins: a repo that switched package managers may still have an old lockfile around
LOCKFILES = (
    ("pnpm-lock.yaml", ["pnpm", "install", "--frozen-lockfile"]),
    ("yarn.lock", ["yarn", "install", "--frozen-lockfile"]),
    ("package-lock.json", ["npm", "ci", "--no-audit", "--no-fund"]),
)
WITHOUT_LOCKFILE = ["npm", "install", "--no-audit", "--no-fund", "--no-package-lock"]

# package caches go to a tmpfs of their own: the image's home is too small for a real app's
CACHE_ENV = {
    "npm_config_cache": "/cache/npm",
    "pnpm_config_store_dir": "/cache/pnpm",
    "YARN_CACHE_FOLDER": "/cache/yarn",
    "HUSKY": "0",  # husky's `prepare` writes git config, and .git is read-only in the container
}


class InstallFailed(Exception):
    pass


def install_command(package_dir: Path) -> list[str] | None:
    """The command that installs the dependencies of the package at `package_dir`; None if it has none."""
    if not (package_dir / "package.json").exists():
        return None

    for lockfile, command in LOCKFILES:
        if (package_dir / lockfile).exists():
            return command

    return WITHOUT_LOCKFILE


async def install_dependencies(workdir: Path, root_path: str = ".") -> list[str] | None:
    """Install the dependencies of the package at `root_path` in the clone at `workdir`: returns the command
    it ran, or None if the package has no package.json. Raises `InstallFailed` if the install fails."""
    command = install_command(workdir / root_path)

    if not command:
        return None

    name = f"hector-install-{uuid.uuid4().hex[:12]}"
    options = [
        "-w", f"/work/{root_path}",
        "--entrypoint", command[0],
        "--tmpfs", f"/cache:rw,nosuid,size=2g,{AGENT_UID}",
        *[arg for key, value in CACHE_ENV.items() for arg in ("-e", f"{key}={value}")],
    ]

    process = await asyncio.create_subprocess_exec(
        *run_docker_command(name, workdir.resolve(), options, command[1:]),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), TIMEOUT_SECONDS)
    except BaseException as e:
        kill = await asyncio.create_subprocess_exec(
            "docker", "kill", name, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )

        await kill.wait()

        if isinstance(e, TimeoutError):
            raise InstallFailed(f"`{' '.join(command)}` timed out after {TIMEOUT_SECONDS}s")
        raise

    if process.returncode != 0:
        output = (stderr or stdout).decode()[-2000:]
        raise InstallFailed(f"`{' '.join(command)}` exited with {process.returncode}: {output}")

    exclude_node_modules(workdir)

    return command


def exclude_node_modules(workdir: Path) -> None:
    """Keep node_modules out of the fix's commit (`git add -A`) even if the repo doesn't ignore it."""
    exclude = workdir / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)

    with exclude.open("a") as f:
        f.write("\nnode_modules/\n")
