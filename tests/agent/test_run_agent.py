import pytest

from src.agent.run_agent import AgentFailed, run_agent


class TestRunAgentHooks:
    async def test_guards_bash_against_git_writes(self, workdir, monkeypatch):
        captured = {}

        async def fake_query(prompt, options):
            captured["hooks"] = options.hooks
            return
            yield

        monkeypatch.setattr("claude_agent_sdk.query", fake_query)
        event = {"data": {"issue": {"title": "t", "culprit": "c", "metadata": {}}}}

        with pytest.raises(AgentFailed):  # the fake query yields no ResultMessage
            await run_agent(workdir, event)

        [guard] = captured["hooks"]["PreToolUse"]
        assert (guard.matcher, guard.hooks[0].__name__) == ("Bash", "deny_git_writes")
