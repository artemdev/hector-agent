from typing import Any


def deny(reason: str) -> dict[str, Any]:
    """PreToolUse hook output that denies the tool call, telling the agent `reason`."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
