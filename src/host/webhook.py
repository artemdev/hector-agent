"""Receive Sentry's webhooks: `POST /sentry` starts a fix for each newly created issue.

Sentry signs every webhook: `Sentry-Hook-Signature` is the HMAC-SHA256 hex digest of the raw body, keyed
with the integration's client secret (SENTRY_CLIENT_SECRET). Serve it with `make serve`.

Where the fix runs depends on ENV:
- prod (default): the event is sent as a `repository_dispatch` to HECTOR_REPO, whose `fix-issue` workflow
  runs `fix_issue` on a GitHub runner. Needs DISPATCH_TOKEN, a token allowed to dispatch to that repo.
- dev: `fix_issue` runs in this process, after the response, like `make run`.
"""

import asyncio
import hmac
import json
import logging
import os
import urllib.request

import uvicorn
from rich.logging import RichHandler
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.host.fix_issue import fix_issue
from src.host.progress import console

logger = logging.getLogger(__name__)

DISPATCH_EVENT_TYPE = "sentry-issue"  # the `repository_dispatch` type .github/workflows/fix-issue.yml listens for


def is_dev() -> bool:
    return os.environ.get("ENV", "prod") == "dev"


def is_signed(body: bytes, signature: str | None) -> bool:
    """Whether `signature` is `body`'s HMAC-SHA256 keyed with SENTRY_CLIENT_SECRET."""
    secret = os.environ.get("SENTRY_CLIENT_SECRET")

    if not secret or not signature:
        return False

    expected = hmac.new(secret.encode(), body, "sha256").hexdigest()

    return hmac.compare_digest(expected, signature)


def dispatch(event: dict) -> None:
    """Start the `fix-issue` workflow in HECTOR_REPO on the Sentry `event`."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{os.environ['HECTOR_REPO']}/dispatches",
        data=json.dumps({"event_type": DISPATCH_EVENT_TYPE, "client_payload": {"event": event}}).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['DISPATCH_TOKEN']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10):
        pass


async def sentry(request: Request) -> JSONResponse:
    body = await request.body()

    if not is_signed(body, request.headers.get("Sentry-Hook-Signature")):
        return JSONResponse({"detail": "invalid signature"}, status_code=401)

    event = await request.json()

    # comments and errors are "created" too; only an issue has `data.issue`
    if event.get("action") != "created" or "issue" not in event.get("data", {}):
        return JSONResponse({"status": "ignored"}, status_code=200)

    issue = event["data"]["issue"]

    logger.info("%s: %s", issue["shortId"], issue["title"])

    accepted = {"status": "accepted", "issue": issue["shortId"]}

    if is_dev():
        # runs after the response, on the default branch
        return JSONResponse(accepted, status_code=202, background=BackgroundTask(fix_issue, event, None))

    try:
        await asyncio.to_thread(dispatch, event)
    except Exception:
        # not 2xx, so Sentry delivers the webhook again
        logger.exception("%s: could not start the fix workflow", issue["shortId"])
        return JSONResponse({"detail": "could not start the fix"}, status_code=502)

    return JSONResponse(accepted, status_code=202)


app = Starlette(routes=[Route("/sentry", sentry, methods=["POST"])])


if __name__ == "__main__":
    if not os.environ.get("SENTRY_CLIENT_SECRET"):
        raise SystemExit("SENTRY_CLIENT_SECRET is not set: every webhook would be rejected")

    if not is_dev():
        missing = [name for name in ("HECTOR_REPO", "DISPATCH_TOKEN") if not os.environ.get(name)]
        if missing:
            raise SystemExit(f"{', '.join(missing)} not set: no fix could be started (or set ENV=dev)")

    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s",
                        handlers=[RichHandler(console=console, omit_repeated_times=False)])

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), log_config=None)
