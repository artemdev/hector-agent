import logging
import os
from collections.abc import Generator
from contextlib import contextmanager

from langfuse import LangfuseChain, get_client, propagate_attributes
from openinference.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor

__all__ = ["langfuse", "trace_issue"]

logger = logging.getLogger(__name__)


langfuse = get_client()

if os.getenv("LANGFUSE_PUBLIC_KEY"):

    ClaudeAgentSDKInstrumentor().instrument()

    if not langfuse.auth_check():
        logger.warning("Langfuse credentials set but auth_check failed — traces may not export")


@contextmanager
def trace_issue(issue: dict, tags: list[str]) -> Generator[LangfuseChain, None, None]:
    """Make the block one Langfuse trace: a `watchdog-autofix` chain for resolving `issue`.

    Everything traced inside (clone, agent, commit, PR) nests under it
    """
    try:
        with (
            langfuse.start_as_current_observation(
                name="watchdog-autofix",
                as_type="chain",
                input={"issue": issue["shortId"], "title": issue["title"]},
            ) as chain,
            propagate_attributes(
                session_id=issue["shortId"],
                tags=tags,
                metadata={"issue_title": issue["title"]},
            ),
        ):
            yield chain
    finally:
        langfuse.flush()
