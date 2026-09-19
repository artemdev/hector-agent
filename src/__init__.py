import os
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from dotenv import load_dotenv

from src.github_repo import GitHubRepo

load_dotenv()

async def main():
    repo = GitHubRepo(os.environ["GIT_REPO_NAME"], token=os.environ["GIT_AUTH_TOKEN"])
    workdir = repo.clone(Path(os.environ["GIT_LOCAL_REPO_PATH"]))

    options = ClaudeAgentOptions(
        model="claude-sonnet-5",
        allowed_tools=["Read", "Glob", "Grep"],
        max_turns=8,
        cwd=str(workdir.resolve()),
    )

    prompt = f"Fix this issue {error} Write failing test first, then fix the issue."
 
    async for message in query(
        prompt=prompt,
        options=options,
    ):
        if isinstance(message, ResultMessage) and not message.is_error:
            print(message.result)


error = {
    "action": "created",
    "installation": {"uuid": "076051af-9343-4b08-a249-a59330043598"},
    "data": {
        "issue": {
            "url": "https://sentry.io/api/0/organizations/test-etk/issues/147285274/",
            "web_url": "https://test-etk.sentry.io/issues/147285274/",
            "project_url": "https://test-etk.sentry.io/issues/?project=4512092227960912",
            "id": "147285274",
            "shortId": "WATCHDOG-FIXTURE-FASTIFY-5",
            "title": "ReferenceError: stateNonExistent is not defined",
            "culprit": "GET /",
            "permalink": "https://test-etk.sentry.io/issues/147285274/",
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
                "value": "stateNonExistent is not defined",
                "type": "ReferenceError",
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
            "firstSeen": "2026-09-15T21:13:57.657000+00:00",
            "lastSeen": "2026-09-15T21:13:57.657000+00:00",
        }
    },
    "actor": {"type": "application", "id": "sentry", "name": "Sentry"},
}
