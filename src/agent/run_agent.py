from dataclasses import dataclass
from pathlib import Path
from typing import Any

import claude_agent_sdk
from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKError, HookMatcher, ResultError,
                               ResultMessage, ToolUseBlock)

from src.agent.guardrails import deny_env_reads, deny_git_writes
from src.agent.prompt import make_prompt


class AgentFailed(Exception):
    """The agent run didn't finish; the message says why."""

@dataclass
class AgentRun:
    result: ResultMessage
    tool_calls: list[tuple[str, dict[str, Any]]]


async def run_agent(workdir: Path, event: dict) -> AgentRun:
    """Run Claude in `workdir` to fix the Sentry issue in `event`."""

    options = ClaudeAgentOptions(
        model="claude-sonnet-5",
        cwd=str(workdir.resolve()),
        max_turns=200,
        permission_mode="bypassPermissions",
        tools=["Read", "Glob", "Grep", "Write", "Edit", "Bash", "WebSearch"],  # the only tools the agent has
        hooks={"PreToolUse": [
            HookMatcher(matcher="Bash", hooks=[deny_git_writes]),
            HookMatcher(matcher="Bash|Read|Grep", hooks=[deny_env_reads]),
        ]},
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
