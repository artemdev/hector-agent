"""Fix a Sentry issue end to end: clone the repo, run the agent in its container, ship the fix as a PR."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from src.run_container import run_container
from src.github_repo import GitHubRepo
from src.observability import langfuse, trace_container, trace_issue
from src.progress import step, track_issue
from src.workspace import temp_workdir

logger = logging.getLogger(__name__)


async def fix_issue(event: dict, ref: str | None) -> str | None:
    """Try to fix the issue in the Sentry `event` on the repo at `ref` (the default branch if None): returns
    the PR URL, or None if the agent had nothing to change.

    Raises `AgentFailed` when the agent itself fails."""

    git_token = os.environ.pop("GIT_AUTH_TOKEN", None)

    if not git_token:
        raise RuntimeError("GIT_AUTH_TOKEN is not set")

    issue = event["data"]["issue"]

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
            f"cloning {repo.full_name} at {ref or repo.default_branch}", tool="clone repo"
        ) as clone:
            repo.clone(workdir, ref=ref)

            clone.output = {"path": str(workdir), "ref": ref}
        pr_url = await ship_fix(repo, workdir, event)

        tracked.status = "resolved" if pr_url else "unchanged"

        trace.update(output={"pr_url": pr_url})

        return pr_url


async def ship_fix(repo: GitHubRepo, workdir: Path, event: dict) -> str | None:
    """Run the agent on the clone at `workdir`, then commit, push and open a PR: returns its URL, or None
    if the agent changed nothing."""
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
