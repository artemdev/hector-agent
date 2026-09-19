
import os
import asyncio
from pathlib import Path
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, AssistantMessage, query
from dotenv import load_dotenv
from src.github_repo import GitHubRepo
from src.observability import langfuse, observe, propagate_attributes
from src.utils import show_spinner

load_dotenv()

@observe(name="watchdog-autofix")
async def main():
    token = os.environ["GIT_AUTH_TOKEN"]
    repo = GitHubRepo(os.environ["GIT_REPO_NAME"], token=token)
    workdir = repo.clone(
        Path(os.environ["GIT_LOCAL_REPO_PATH"])
    )
    model_used = None
    result = None
    spinner = asyncio.create_task(show_spinner())
    issue = error["data"]["issue"]

    options = ClaudeAgentOptions(
        model="claude-sonnet-5",
        cwd=str(workdir.resolve()),
        max_turns=200,
        permission_mode="bypassPermissions",
        allowed_tools=[
            "Read",
            "Glob",
            "Grep",
            "Write",
            "Edit",
            "Bash",
            "mcp__github",  # all tools from the github server, incl. create_pull_request
        ],
        system_prompt={
            "type": "preset",
            "preset": "claude_code",  # Use Claude Code's system prompt
        },
        setting_sources=[], # avoid using local CLI configurations
        mcp_servers={
            "github": {
                "type": "http",
                "url": "https://api.githubcopilot.com/mcp/",
                "headers": {"Authorization": f"Bearer {token}"},
            },
        },
    )

    langfuse.update_current_span(
        input={
            "issue": issue["shortId"],
            "repo": repo.full_name,
            "title": issue["title"],
        },
    )

    try:
        with propagate_attributes(
            session_id=issue["shortId"],
            tags=["watchdog"],
            metadata={"repo": repo.full_name, "issue_title": issue["title"]},
        ):
            async for message in query(
                prompt=make_prompt(repo, error),
                options=options,
            ):
                if isinstance(message, AssistantMessage):
                    model_used = message.model
                if isinstance(message, ResultMessage):
                    spinner.cancel()
                    await asyncio.gather(spinner, return_exceptions=True)

                    if not message.is_error:
                        result = message.result
                    usage = message.usage or {}
                    total_tokens = sum(v for v in usage.values() if isinstance(v, int))
                    langfuse.update_current_span(
                        metadata={
                            "model": model_used,
                            "total_tokens": total_tokens,
                            "usage": usage,
                            "cost_usd": message.total_cost_usd,
                        },
                    )
    finally:
        if not spinner.done():
            spinner.cancel()
            await asyncio.gather(spinner, return_exceptions=True)
        langfuse.flush()

    return result



def make_prompt(repo, error):
    owner, name = repo.full_name.split("/", 1)
    issue = error["data"]["issue"]
    branch = f"fix/{issue['shortId'].lower()}"

    return f"""A Sentry issue was reported in the repository {repo.full_name}.
            Issue:
            - Title: {issue['title']}
            - Culprit: {issue['culprit']}
            - File: {issue['metadata'].get('filename')}
            - Details: {issue['metadata'].get('value')}

            Do the following, in order:
            1. Create a new branch off `{repo.default_branch}` named `{branch}`.
            2. Write a failing test that reproduces the issue, then fix the issue so the test passes.
            3. Run the test suite and confirm the failing test now passes and nothing else broke.
            4. Commit your changes and push the branch `{branch}` to origin with `git push -u origin {branch}`.
            5. Open a pull request using the `create_pull_request` tool with:
            owner="{owner}", repo="{name}", head="{branch}", base="{repo.default_branch}",
            a clear title referencing {issue['shortId']}, and a body summarizing the root cause and fix.

            Return the URL of the pull request you created."""


error = {
    "action": "created",
    "installation": {"uuid": "076051af-9343-4b08-a249-a59330043598"},
    "data": {
        "issue": {
            "url": "https://sentry.io/api/0/organizations/test-etk/issues/147286482/",
            "web_url": "https://test-etk.sentry.io/issues/147286482/",
            "project_url": "https://test-etk.sentry.io/issues/?project=4512092227960912",
            "id": "147286482",
            "shareId": None,
            "shortId": "WATCHDOG-FIXTURE-FASTIFY-6",
            "title": "TypeError: Cannot read properties of undefined (reading 'trim')",
            "culprit": "GET /greeting",
            "permalink": "https://test-etk.sentry.io/issues/147286482/",
            "logger": None,
            "level": "error",
            "status": "unresolved",
            "statusDetails": {},
            "substatus": "new",
            "isPublic": False,
            "platform": "node",
            "project": {
                "id": "4512092227960912",
                "name": "watchdog-fixture-fastify",
                "slug": "watchdog-fixture-fastify",
                "platform": "node-fastify",
            },
            "type": "error",
            "metadata": {
                "value": "Cannot read properties of undefined (reading 'trim')",
                "type": "TypeError",
                "synthetic": False,
                "filename": "/Users/artem/Desktop/projects/own/watchdog/fixtures/backend/src/routes/index.ts",
                "function": "Object.?",
                "in_app_frame_mix": "mixed",
                "sdk": {
                    "name": "sentry.javascript.node",
                    "name_normalized": "sentry.javascript.node",
                },
                "initial_priority": 75,
            },
            "numComments": 0,
            "assignedTo": None,
            "isBookmarked": False,
            "isSubscribed": False,
            "subscriptionDetails": None,
            "hasSeen": False,
            "annotations": [],
            "issueType": "error",
            "issueCategory": "error",
            "priority": "high",
            "priorityLockedAt": None,
            "seerFixabilityScore": None,
            "seerAutofixLastTriggered": None,
            "seerExplorerAutofixLastTriggered": None,
            "isUnhandled": True,
            "count": "1",
            "userCount": 0,
            "firstSeen": "2026-09-15T21:23:55.533000+00:00",
            "lastSeen": "2026-09-15T21:23:55.533000+00:00",
        }
    },
    "actor": {"type": "application", "id": "sentry", "name": "Sentry"},
}
