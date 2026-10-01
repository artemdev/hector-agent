import pytest
from claude_agent_sdk import HookMatcher

from src.agent.run import AgentFailed, make_prompt, run_agent


class TestMakePrompt:
    def test_describes_the_issue_with_a_repo_relative_file(self, workdir, source_file):
        event = {"data": {"issue": {
            "title": "ReferenceError: x is not defined",
            "culprit": "GET /",
            "metadata": {"filename": f"/Users/me/app/{source_file}", "value": "x is not defined"},
        }}}

        prompt = make_prompt(event, workdir)

        assert "- Title: ReferenceError: x is not defined" in prompt
        assert "- Culprit: GET /" in prompt
        assert f"- File: {source_file}" in prompt
        assert "- Details: x is not defined" in prompt


class TestRunAgentHooks:
    async def test_extra_hooks_run_after_the_path_guard(self, workdir, monkeypatch):
        captured = {}

        async def fake_query(prompt, options):
            captured["hooks"] = options.hooks
            return
            yield

        monkeypatch.setattr("claude_agent_sdk.query", fake_query)
        extra_pre = HookMatcher(matcher="Edit")
        extra_stop = HookMatcher()
        event = {"data": {"issue": {"title": "t", "culprit": "c", "metadata": {}}}}

        with pytest.raises(AgentFailed):  # the fake query yields no ResultMessage
            await run_agent(workdir, event, extra_hooks={"PreToolUse": [extra_pre], "Stop": [extra_stop]})

        pre = captured["hooks"]["PreToolUse"]
        assert len(pre) == 3
        assert pre[0].hooks[0].__qualname__.startswith("deny_paths_outside")
        assert (pre[1].matcher, pre[1].hooks[0].__name__) == ("Bash", "deny_git_writes")
        assert pre[2] is extra_pre
        assert captured["hooks"]["Stop"] == [extra_stop]
