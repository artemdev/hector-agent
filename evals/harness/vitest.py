"""Run the fixture's vitest suite and read its JSON report."""

import json
import re
import subprocess
import tempfile
from pathlib import Path

TEST_FILE = re.compile(r"\.(test|spec)\.[cm]?[jt]sx?$")  # files vitest runs as tests


def run_vitest(package_path: Path, files: list[str], *args: str) -> tuple[dict | None, str]:
    """Vitest's JSON report for `files` (None if it didn't write one) and its console output.

    `args` go to vitest as-is, e.g. `"-t", pattern` to run only matching test names.
    """
    with tempfile.TemporaryDirectory() as d:
        report_path = Path(d) / "report.json"
        try:
            proc = subprocess.run(
                ["npm", "test", "--", "--run", *files, *args,
                 "--reporter=default", "--reporter=json", f"--outputFile.json={report_path}"],
                cwd=package_path, capture_output=True, text=True, timeout=300,
            )
        except subprocess.TimeoutExpired:
            return None, "vitest timed out after 300s"
        output = proc.stdout + proc.stderr
        if not report_path.exists():
            return None, output
        return json.loads(report_path.read_text()), output
