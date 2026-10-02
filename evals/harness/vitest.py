"""Run the fixture's vitest suite in the agent image and read its JSON report."""

import json
import re
import subprocess
import tempfile
from pathlib import Path

from evals.harness.image import run_in_image

TEST_FILE = re.compile(r"\.(test|spec)\.[cm]?[jt]sx?$")  # files vitest runs as tests


def run_vitest(repo_path: Path, root_path: str, files: list[str], *args: str) -> tuple[dict | None, str]:
    """Vitest's JSON report for `files` in the package at `root_path` (None if it didn't write one) and its
    console output.

    `files` are relative to the package. `args` go to vitest as-is, e.g. `"-t", pattern` to run only
    matching test names.
    """
    with tempfile.TemporaryDirectory() as d:
        try:
            proc = run_in_image(
                repo_path,
                ["npm", "test", "--", "--run", *files, *args,
                 "--reporter=default", "--reporter=json", "--outputFile.json=/report/report.json"],
                cwd=root_path, mounts=[f"{d}:/report"],
            )
        except subprocess.TimeoutExpired:
            return None, "vitest timed out after 300s"
        output = proc.stdout + proc.stderr
        report_path = Path(d) / "report.json"
        if not report_path.exists():
            return None, output
        return json.loads(report_path.read_text()), output
