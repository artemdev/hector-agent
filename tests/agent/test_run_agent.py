import pytest

from src.agent.run_agent import AgentFailed, run_agent


class TestRunAgentHooks:
    async def test_guards_git_writes_and_env_reads(self, workdir, monkeypatch):
        captured = {}

        async def fake_query(prompt, options):
            captured["hooks"] = options.hooks
            return
            yield

        monkeypatch.setattr("claude_agent_sdk.query", fake_query)
        event = {"data": {"issue": {"title": "t", "culprit": "c", "metadata": {}}}}

        with pytest.raises(AgentFailed):  # the fake query yields no ResultMessage
            await run_agent(workdir, event)

        guards = [
            (g.matcher, g.hooks[0].__name__) for g in captured["hooks"]["PreToolUse"]
        ]
        assert guards == [
            ("Bash", "deny_git_writes"),
            ("Bash|Read|Grep", "deny_env_reads"),
        ]
