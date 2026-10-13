from pathlib import Path
from unittest.mock import MagicMock

import pytest
from claude_agent_sdk import ResultMessage

import src.host.observability as observability
from src.agent import AgentFailed, AgentRun

EVENT = {"data": {"issue": {"shortId": "WATCHDOG-1", "title": "TypeError"}}}
RESULT = ResultMessage(
    subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=2, session_id="s",
    result="fixed the trim", total_cost_usd=0.5,
    model_usage={"claude-sonnet-5": {"inputTokens": 3, "outputTokens": 4, "cacheReadInputTokens": 5,
                                     "cacheCreationInputTokens": 6, "costUSD": 0.5}},
)


@pytest.fixture
def agent(monkeypatch):
    """The agent observation `trace_container` opens, with Langfuse mocked out."""
    langfuse = MagicMock()
    monkeypatch.setattr(observability, "langfuse", langfuse)
    return langfuse.start_as_current_observation.return_value.__enter__.return_value


def container_returning(outcome):
    """A fake `run_container` that returns `outcome`, or raises it if it's an exception."""
    async def run_container(workdir, event):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    return run_container


class TestTraceContainer:
    async def test_records_a_tool_per_call_in_order(self, agent):
        run_container = container_returning(AgentRun(RESULT, [("Bash", {"command": "ls"}), ("Edit", {"file_path": "a.ts"})]))

        await observability.trace_container(run_container(Path("/clone"), EVENT))

        tools = [c.kwargs for c in agent.start_observation.call_args_list if c.kwargs["as_type"] == "tool"]
        assert [(t["name"], t["input"]) for t in tools] == [("Bash", {"command": "ls"}), ("Edit", {"file_path": "a.ts"})]

    async def test_records_each_models_tokens_and_cost(self, agent):
        run_container = container_returning(AgentRun(RESULT, []))

        await observability.trace_container(run_container(Path("/clone"), EVENT))

        (generation,) = [c.kwargs for c in agent.start_observation.call_args_list if c.kwargs["as_type"] == "generation"]
        assert generation["model"] == "claude-sonnet-5"
        assert generation["usage_details"]["input"] == 3
        assert generation["cost_details"] == {"total": 0.5}

    async def test_returns_the_run_with_its_result_as_output(self, agent):
        run = AgentRun(RESULT, [])
        run_container = container_returning(run)

        assert await observability.trace_container(run_container(Path("/clone"), EVENT)) is run
        assert agent.update.call_args.kwargs["output"] == "fixed the trim"

    async def test_marks_a_failed_run_as_an_error(self, agent):
        run_container = container_returning(AgentFailed("timed out"))

        with pytest.raises(AgentFailed):
            await observability.trace_container(run_container(Path("/clone"), EVENT))

        agent.update.assert_called_once_with(level="ERROR", status_message="timed out")
