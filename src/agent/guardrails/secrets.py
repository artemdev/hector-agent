import re
from typing import Any

from claude_agent_sdk import HookContext

from src.agent.guardrails.deny import deny


async def deny_env_reads(
    input_data: dict[str, Any], tool_use_id: str | None, context: HookContext
) -> dict[str, Any]:
    """PreToolUse hook: deny tool calls that name a .env file; the fix never needs secrets."""

    if _touches_env_file(input_data["tool_input"]):
        return deny(
            ".env files hold secrets and are off limits; the fix never needs them."
        )
    return {}

def _touches_env_file(tool_input: dict[str, Any]) -> bool:
    """The Bash command, or the Read/Grep path or glob, names a .env file."""

    fields = ("command", "file_path", "path", "glob")

    # `.env`, `.env.local`, `backend/.env`; not `.env.example`/`.sample`/`.template`, not `process.env`
    env_file = re.compile(
        r"(?:^|[\s/'\"=<])\.env(?!\.(?:example|sample|template)\b)(?:\.[\w-]+)*(?=$|[\s'\";|&)>*])"
    )

    return any(env_file.search(str(tool_input.get(f, ""))) for f in fields)
