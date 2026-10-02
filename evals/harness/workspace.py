"""Prepare a case's workspace before the agent runs."""

import subprocess
from pathlib import Path

from evals.harness.image import run_in_image


def install_npm_deps(repo_path: Path, root_path: str) -> None:
    """`npm install` in the package at `root_path`, inside the agent image, so the agent and the graders
    start from a ready workspace with Linux binaries."""
    proc = run_in_image(repo_path, ["npm", "install", "--no-audit", "--no-fund"], cwd=root_path)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, proc.args, proc.stdout, proc.stderr)
