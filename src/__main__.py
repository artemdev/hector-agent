import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.logging import RichHandler

from src.agent import run_container
from src.github_repo import GitHubRepo
from src.observability import langfuse, trace_container, trace_issue
from src.progress import console, step, track_issue
from src.workspace import temp_workdir

logger = logging.getLogger(__name__)


async def main() -> str | None:
    """Try to fix the issue: returns the PR URL, or None if the agent had nothing to change.

    Raises `AgentFailed` when the agent itself fails."""

    git_token = os.environ.pop("GIT_AUTH_TOKEN", None)

    if not git_token:
        raise RuntimeError("GIT_AUTH_TOKEN is not set")

    issue = error["data"]["issue"]

    with (
        track_issue(issue["shortId"], issue["title"]) as tracked,
        trace_issue(issue, tags=["deliver"]) as trace,
        temp_workdir() as workdir,
    ):
        with step("connecting to GitHub", tool="connect github") as connect:
            repo = GitHubRepo(os.environ["GIT_REPO_NAME"], token=git_token)

            connect.output = {
                "repo": repo.full_name,
                "default_branch": repo.default_branch,
            }
        with step(
            f"cloning {repo.full_name} at {BUGGY_REF}", tool="clone repo"
        ) as clone:
            repo.clone(workdir, ref=BUGGY_REF)

            clone.output = {"path": str(workdir), "ref": BUGGY_REF}
        pr_url = await autofix(repo, workdir, error)

        tracked.status = "resolved" if pr_url else "unchanged"

        trace.update(output={"pr_url": pr_url})

        return pr_url


async def autofix(repo: GitHubRepo, workdir: Path, event: dict) -> str | None:
    issue = event["data"]["issue"]

    with step("agent working"):
        outcome = await trace_container(run_container(workdir, event))

    branch_name = f'fix/{issue["shortId"].lower()}-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}'
    title = f"fix: {issue['title']} ({issue['shortId']})"

    with step("committing changes", tool="commit") as commit:
        has_changes = repo.commit_all(workdir, branch_name, message=title)
        commit.output = {"branch": branch_name, "committed": has_changes}
    if not has_changes:
        logger.info("agent made no changes; nothing to ship")
        langfuse.create_event(name="no changes")

        return None
    with step(f"pushing {branch_name}", tool="push") as push:
        repo.push(workdir, branch_name)

        push.output = {"branch": branch_name}
    with step("opening pull request", tool="open pull request") as pr:
        pr_url = repo.open_pull_request(
            branch_name, title=title, body=outcome.result.result or ""
        )
        pr.output = {"pr_url": pr_url}

    return pr_url


# `main` already has the fix for the hardcoded issue below, so run on the tag that has the bug.
BUGGY_REF = "2-type-error-cannot-read-undefined"

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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s: %(message)s",
        handlers=[
            RichHandler(console=console, omit_repeated_times=False)
        ],  # log lines print above the live view
    )
    logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)
    # Stop on SIGTERM (`docker stop`, systemd, a deploy) the way Ctrl-C does, so the workdir and the agent's
    # container are cleaned up; Python's default SIGTERM exits without running any `finally`.
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
