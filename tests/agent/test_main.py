import json

from claude_agent_sdk import ResultMessage

from src.agent import __main__ as entrypoint
from src.agent.run_agent import AgentFailed, AgentRun

EVENT = {"data": {"issue": {"title": "TypeError"}}}
RESULT = ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1,
                       session_id="s", result="fixed the trim", total_cost_usd=0.5)


def fake_agent(monkeypatch, fail=False):
    """Replace `run_agent` with one that finishes with one tool call, or fails."""
    async def run_agent(workdir, event):
        assert event == EVENT
        if fail:
            raise AgentFailed("boom")
        return AgentRun(RESULT, [("Bash", {"command": "ls"})])

    monkeypatch.setattr(entrypoint, "run_agent", run_agent)


def run_main(tmp_path, capsys):
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps(EVENT))
    code = entrypoint.main(tmp_path, event_file)
    return code, json.loads(capsys.readouterr().out)


class TestMain:
    def test_prints_the_result_and_tool_calls(self, tmp_path, capsys, monkeypatch):
        fake_agent(monkeypatch)

        code, printed = run_main(tmp_path, capsys)

        assert code == 0
        assert printed["result"]["result"] == "fixed the trim"
        assert printed["tool_calls"] == [["Bash", {"command": "ls"}]]

    def test_prints_the_error_when_the_agent_fails(self, tmp_path, capsys, monkeypatch):
        fake_agent(monkeypatch, fail=True)

        code, printed = run_main(tmp_path, capsys)

        assert code == 1
        assert printed == {"failed": "boom"}
