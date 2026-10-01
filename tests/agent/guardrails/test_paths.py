import pytest

from src.agent.guardrails import deny_paths_outside


class TestDenyPathsOutside:
    @pytest.mark.parametrize(
        "tool_input",
        [
            {"file_path": "src/app.ts"},
            {"file_path": "{workdir}/src/app.ts"},
            {"path": "src"},
            {"pattern": "**/*.ts"},
        ],
        ids=["relative file", "absolute file inside", "directory", "no path at all"],
    )
    async def test_allows_paths_inside_workdir(self, call_hook, workdir, tool_input):
        tool_input = {key: value.format(workdir=workdir) for key, value in tool_input.items()}

        assert (await call_hook(deny_paths_outside(workdir), tool_input))[0] == "allow"

    @pytest.mark.parametrize(
        "tool_input",
        [
            {"file_path": "/Users/me/projects/app/src/app.ts"},
            {"file_path": "../outside.ts"},
            {"file_path": "~/.ssh/id_rsa"},
            {"path": "/etc"},
            {"notebook_path": "/tmp/x.ipynb"},
        ],
        ids=["absolute file elsewhere", "parent dir escape", "home dir", "system dir", "notebook"],
    )
    async def test_denies_paths_outside_workdir(self, call_hook, workdir, tool_input):
        assert (await call_hook(deny_paths_outside(workdir), tool_input))[0] == "deny"

    async def test_tells_the_agent_why_it_was_denied(self, call_hook, workdir):
        _, reason = await call_hook(deny_paths_outside(workdir), {"path": "/etc"})

        assert "/etc is outside the repository" in reason
        assert "use repo-relative paths" in reason
