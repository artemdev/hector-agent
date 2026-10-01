import pytest


async def _call_hook(hook, tool_input):
    """Run a PreToolUse `hook` on one tool call, as the SDK would: ("allow" | "deny", reason)."""
    output = await hook({"tool_input": tool_input}, None, {"signal": None})
    specific = output.get("hookSpecificOutput", {})
    return specific.get("permissionDecision", "allow"), specific.get("permissionDecisionReason")


@pytest.fixture
def call_hook():
    return _call_hook
