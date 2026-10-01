import re
import shlex
from typing import Any
from claude_agent_sdk import HookContext
from src.agent.guardrails.deny import deny

GIT_COMMAND = re.compile(r"(?:^|[;&|(`]|\$\()\s*(?:\S*/)?git(?:\s|$)")
READ_ONLY_GIT = {"diff", "status"}


def is_read_only_git(command: str) -> bool:
    """Every git call in `command` is a plain `git diff` or `git status`.

    Chains like `cd backend && git diff` or `git status && git diff` are fine: the non-git parts
    are allowed in Bash anyway. Git hidden in `$(...)` or backticks, redirects, and --output are not.
    """
    if re.search(r"`|\$\(", command):
        return not GIT_COMMAND.search(command)
    segments = re.split(r"&&|\|\||[;&|\n]", command.replace("2>&1", ""))
    return all(_is_one_read_only_git(s.strip()) for s in segments if GIT_COMMAND.search(s))


def _is_one_read_only_git(command: str) -> bool:
    """`command` is a single `git diff` or `git status`, with no redirect or output file."""
    if re.search(r"[()<>]", command):
        return False
    try:
        args = shlex.split(command)
    except ValueError:
        return False
    if args[:1] != ["git"]:
        return False
    rest = args[2:] if args[1:2] == ["--no-pager"] else args[1:]
    return bool(rest) and rest[0] in READ_ONLY_GIT and not any(a.startswith("--output") for a in rest)


async def deny_git_writes(input_data: dict[str, Any], tool_use_id: str | None, context: HookContext) -> dict[str, Any]:
    """PreToolUse hook on Bash: deny git commands other than `git diff` and `git status`."""
    command = input_data["tool_input"].get("command", "")

    if GIT_COMMAND.search(command) and not is_read_only_git(command):
        return deny(
            "deny_git_writes",
            {"command": command},
            "Only `git diff` and `git status` are allowed (no --output, redirects or $(...)); "
            "use `git diff -- <path>` to scope. The harness does all other git work.",
        )
    return {}
