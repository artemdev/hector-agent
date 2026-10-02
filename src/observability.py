import logging
import os
from collections.abc import Awaitable, Generator
from contextlib import contextmanager

from dotenv import load_dotenv

load_dotenv()  # before the imports below: the Langfuse client reads the environment

from langfuse import LangfuseChain, get_client, propagate_attributes
from openinference.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor

from src.agent import AgentFailed, AgentRun

__all__ = ["langfuse", "trace_container", "trace_issue"]

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


async def trace_container(run_container: Awaitable[AgentRun]) -> AgentRun:
    """Await `run_container`, recorded as a `ClaudeAgentSDK.query` agent observation under the current one."""
    with langfuse.start_as_current_observation(name="ClaudeAgentSDK.query", as_type="agent") as agent:
        try:
            run = await run_container
        except AgentFailed as e:
            agent.update(level="ERROR", status_message=str(e))
            raise

        for name, tool_input in run.tool_calls:
            agent.start_observation(name=name, as_type="tool", input=tool_input).end()

        result = run.result

        for model, usage in (result.model_usage or {}).items():
            agent.start_observation(
                name=model,
                as_type="generation",
                model=model,
                usage_details={
                    "input": usage["inputTokens"],
                    "output": usage["outputTokens"],
                    "cache_read_input_tokens": usage["cacheReadInputTokens"],
                    "cache_creation_input_tokens": usage["cacheCreationInputTokens"],
                },
                cost_details={"total": usage["costUSD"]},
            ).end()

        agent.update(
            output=result.result,
            metadata={
                "session_id": result.session_id,
                "num_turns": result.num_turns,
                "duration_ms": result.duration_ms,
                "total_cost_usd": result.total_cost_usd,
                "terminal_reason": result.terminal_reason,
                "permission_denials": result.permission_denials,
            },
        )
    return run
