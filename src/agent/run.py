from dataclasses import dataclass
from pathlib import Path
from typing import Any

import claude_agent_sdk
from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKError, HookMatcher, ResultError,                      ResultMessage, ToolUseBlock)
from claude_agent_sdk.types import HookEvent

from src.agent.guardrails import deny_git_writes, deny_paths_outside
from src.agent.utils import repo_relative

AGENT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class AgentFailed(Exception):
    """The agent run didn't finish; the message says why."""

@dataclass
class AgentRun:
    result: ResultMessage
    tool_calls: list[tuple[str, dict[str, Any]]]


def make_prompt(event: dict, workdir: Path) -> str:
    issue = event["data"]["issue"]
    return f"""A Sentry issue was reported in this repository.
            Issue:
            - Title: {issue['title']}
            - Culprit: {issue['culprit']}
            - File: {repo_relative(issue['metadata'].get('filename'), workdir)}
            - Details: {issue['metadata'].get('value')}

            Do the following, in order:
            1. Write a failing test that reproduces the issue, then fix the issue so the test passes.
            2. Run the test suite and confirm the failing test now passes and nothing else broke.

            Work only inside the current working directory: paths outside it are blocked.
            To review your changes, you may run `git diff` and `git status`. Run no other git command (no stash, checkout, or commit): after you finish, the harness creates the branch, commits, pushes, and opens the PR.
            Return a short summary of the root cause and the fix; it becomes the PR description."""


async def run_agent(
    workdir: Path,
    event: dict,
    extra_hooks: dict[HookEvent, list[HookMatcher]] | None = None,
) -> AgentRun:
    """Run Claude in `workdir` to fix the Sentry issue in `event`.

    The agent only edits and tests files locally; shipping the fix (commit, push,
    PR) is up to the caller. Returns on success, raises `AgentFailed` on failure. Run it inside
    `trace_issue` so the agent's spans join the issue's trace.

    `extra_hooks` run after the built-in ones, which they can't replace (evals use it to observe
    the run).
    """
    hooks: dict[HookEvent, list[HookMatcher]] = {
        "PreToolUse": [
            HookMatcher(matcher="Read|Write|Edit|MultiEdit|NotebookEdit|Glob|Grep", hooks=[deny_paths_outside(workdir)]),
            HookMatcher(matcher="Bash", hooks=[deny_git_writes]),
        ],
    }
    for hook_event, matchers in (extra_hooks or {}).items():
        hooks.setdefault(hook_event, []).extend(matchers)

    options = ClaudeAgentOptions(
        model="claude-sonnet-5",
        cwd=str(workdir.resolve()),
        max_turns=200,
        permission_mode="bypassPermissions",
        tools=["Read", "Glob", "Grep", "Write", "Edit", "Bash"],  # the only tools the agent has
        sandbox={
            "enabled": True,
            "allowUnsandboxedCommands": False,
            "network": {"allowedDomains": ["registry.npmjs.org"]},
        },
        disallowed_tools=[f"Read(/{AGENT_ENV_FILE})", "Read(~/.ssh/**)"],
        hooks=hooks,
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
        },
        setting_sources=[],  # avoid using local CLI configurations
    )

    result_msg = None
    tool_calls: list[tuple[str, dict[str, Any]]] = []

    try:

        async for message in claude_agent_sdk.query(prompt=make_prompt(event, workdir), options=options):
            if isinstance(message, AssistantMessage):
                tool_calls += [(b.name, b.input) for b in message.content if isinstance(b, ToolUseBlock)]
            elif isinstance(message, ResultMessage):
                result_msg = message

    except ResultError as e:
        raise AgentFailed(
            f"{e.subtype} {e.terminal_reason} {e.api_error_status or ''} "
            f"{e.errors} cost=${e.data.get('total_cost_usd') or 0:.4f}"
        ) from e
    except ClaudeSDKError as e:
        raise AgentFailed(f"agent crashed: {e}") from e

    if result_msg is None:
        raise AgentFailed("agent finished without a ResultMessage")

    return AgentRun(result_msg, tool_calls)
