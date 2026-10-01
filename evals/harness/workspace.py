"""Prepare a case's workspace before the agent runs."""

import subprocess
from pathlib import Path


def install_npm_deps(root_path: Path) -> None:
    """`npm install` in the package at `root_path`, so the agent and the grader start from a ready workspace."""
    subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=root_path,
                   capture_output=True, text=True, timeout=300, check=True)
