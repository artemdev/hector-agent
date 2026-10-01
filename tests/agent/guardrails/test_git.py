import pytest

from src.agent.guardrails import deny_git_writes


class TestDenyGitWrites:
    @pytest.mark.parametrize(
        "command",
        [
            "git diff",
            "git --no-pager diff --stat",
            "git diff -- backend/src/routes/index.ts",
            "git status --porcelain",
            'git status && echo "---" && git diff',
            "cd backend && git diff 2>&1 | head -50",
            "npx vitest run 2>&1 | tail -30",
            "find . -not -path '*/.git/*' | sort",
        ],
        ids=["diff", "diff stat", "diff scoped", "status", "status then diff", "cd then diff piped",
             "not git", "dot-git path"],
    )
    async def test_allows_read_only_git_and_non_git(self, call_hook, command):
        assert (await call_hook(deny_git_writes, {"command": command}))[0] == "allow"

    @pytest.mark.parametrize(
        "command",
        [
            "git stash push -- a.ts",
            "cd backend && git stash push -- a.ts && npm test; git stash pop",
            "git diff; git push origin HEAD:main",
            "git diff & git commit -am x",
            "git diff --output=/tmp/x",
            "git -c core.pager=sh diff",
            "git diff > changes.patch",
            "echo $(git rev-parse HEAD)",
            "/usr/bin/git commit -am x",
        ],
        ids=["stash", "stash chained", "diff then push", "diff then background commit", "output file", "config override", "redirect",
             "subshell", "absolute path"],
    )
    async def test_denies_other_git(self, call_hook, command):
        assert (await call_hook(deny_git_writes, {"command": command}))[0] == "deny"

    async def test_tells_the_agent_what_is_allowed(self, call_hook):
        _, reason = await call_hook(deny_git_writes, {"command": "git stash"})

        assert "Only `git diff` and `git status` are allowed" in reason
