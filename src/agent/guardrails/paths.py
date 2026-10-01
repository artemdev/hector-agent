from pathlib import Path
from typing import Any
from claude_agent_sdk import HookContext
from src.agent.guardrails.deny import deny


def deny_paths_outside(workdir: Path):
    """PreToolUse hook: deny file tools any path outside `workdir`."""
    root = workdir.resolve()

    async def hook(input_data: dict[str, Any], tool_use_id: str | None, context: HookContext) -> dict[str, Any]:
        tool_input = input_data["tool_input"]

        for key in ("file_path", "notebook_path", "path"):
            raw = tool_input.get(key)
            if not raw:
                continue

            target = (root / Path(raw).expanduser()).resolve()

            if not target.is_relative_to(root):
                return deny(
                    "deny_paths_outside",
                    {"tool": input_data.get("tool_name"), "path": raw},
                    f"{raw} is outside the repository ({root}); use repo-relative paths.",
                )
        return {}

    return hook
