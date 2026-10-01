from typing import Any
from opentelemetry import trace
from src.observability import langfuse


def deny(guardrail: str, observed: dict[str, Any], reason: str) -> dict[str, Any]:
    """Deny a tool call inside a run."""

    if trace.get_current_span().get_span_context().is_valid:
        langfuse.start_observation(
            name=guardrail, as_type="guardrail", input=observed, output="deny", level="WARNING",
        ).end()
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
