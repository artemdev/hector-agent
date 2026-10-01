"""Eval hook: did the agent have a failing test before it started fixing the source?

A PreToolUse hook watches the agent's Write/Edit calls. The first time the agent is about to
edit a non-test file, the hook runs the agent's test files itself, on the still-buggy source,
and records whether one of them fails. It only observes: it never blocks the agent, so the eval
measures how the agent works on its own.

    failing_test_first = FailingTestFirstHook(repo_path, root_path="backend")
    await run_agent(repo_path, event, extra_hooks=failing_test_first.hooks())
    ok, reason = failing_test_first.verdict()

It runs code the agent wrote outside the sandbox: don't use it in adversarial (security) evals.
"""

import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import HookContext, HookMatcher
from claude_agent_sdk.types import HookEvent

from evals.harness.changes import changed_files, is_test_side, source_changes
from evals.harness.vitest import TEST_FILE, run_vitest


class FailingTestFirstHook:
    def __init__(self, repo_path: Path, root_path: str):
        self.repo_path = repo_path.resolve()
        self.package_path = self.repo_path / root_path  # where `npm test` runs
        self.started = False                            # the agent's first source edit was seen
        self.result: tuple[bool, str] | None = None     # set once the tests have run

    def hooks(self) -> dict[HookEvent, list[HookMatcher]]:
        return {"PreToolUse": [HookMatcher(matcher="Write|Edit|MultiEdit", hooks=[self._before_edit])]}

    def verdict(self) -> tuple[bool, str]:
        if self.result is not None:
            return self.result
        if source_changes(self.repo_path):
            return False, "the agent changed source only through Bash, so the hook never ran"
        return False, "the agent never edited source"

    async def _before_edit(self, input_data: dict[str, Any], tool_use_id: str | None, context: HookContext) -> dict[str, Any]:
        if self.started:  # also set while the tests run, so parallel edits don't run them again
            return {}
        path = self._repo_relative(input_data["tool_input"].get("file_path"))
        if path and not is_test_side(path):
            self.started = True
            self.result = await asyncio.to_thread(self._check_tests_fail, path)
        return {}  # never block the agent

    def _check_tests_fail(self, about_to_edit: str) -> tuple[bool, str]:
        """On the still-buggy source, at least one of the agent's tests fails on an assertion."""
        changed = changed_files(self.repo_path)
        if already_changed := [p for p in changed if not is_test_side(p)]:
            return False, f"source was changed through Bash before the agent edited {about_to_edit}: {already_changed}"

        test_paths = (self.repo_path / p for p in changed if TEST_FILE.search(p))
        tests = [str(f.relative_to(self.package_path))
                 for f in test_paths if f.is_relative_to(self.package_path) and f.exists()]
        if not tests:
            return False, f"no test existed when the agent first edited {about_to_edit}"

        report, output = run_vitest(self.package_path, tests)
        if report is None:
            return False, f"vitest produced no report for {tests}:\n{output}"
        failed = [test["fullName"] for file in report["testResults"] for test in file["assertionResults"]
                  if test["status"] == "failed"]
        if failed:
            return True, f"before editing {about_to_edit}, failing: {failed}"
        # No test failed, so a failed file means it didn't load (e.g. imports what the fix adds).
        broken = [file["name"] for file in report["testResults"] if file["status"] == "failed"]
        why = f"these failed to load: {broken}" if broken else "they all passed"
        return False, f"before editing {about_to_edit}, the agent's tests {tests} didn't catch the bug, {why}\n{output}"

    def _repo_relative(self, raw: str | None) -> str | None:
        """`raw` relative to the repo, or None if missing or outside (`deny_paths_outside` blocks those)."""
        if not raw:
            return None
        target = (self.repo_path / Path(raw).expanduser()).resolve()
        return str(target.relative_to(self.repo_path)) if target.is_relative_to(self.repo_path) else None
