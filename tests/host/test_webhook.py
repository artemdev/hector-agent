import hmac
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from src.host import webhook

SECRET = "test-secret"
NEW_ISSUE = json.loads(Path("evals/cases/2-type-error-cannot-read-undefined/sentry.json").read_text())


def sign(body: bytes, secret: str = SECRET) -> dict[str, str]:
    """The header Sentry sends with `body`."""
    return {"Sentry-Hook-Signature": hmac.new(secret.encode(), body, "sha256").hexdigest()}


@pytest.fixture
def agent_runs(monkeypatch) -> list[tuple[dict, str | None]]:
    """Each `(event, ref)` the webhook started `fix_issue` with in dev, instead of fixing anything."""
    runs = []

    async def fix_issue(event, ref):
        runs.append((event, ref))

    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("SENTRY_CLIENT_SECRET", SECRET)
    monkeypatch.setattr(webhook, "fix_issue", fix_issue)
    return runs


@pytest.fixture
def dispatches(monkeypatch, agent_runs) -> list[dict]:
    """Each event the webhook dispatched to the fix workflow in prod, instead of calling GitHub."""
    events = []

    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setattr(webhook, "dispatch", events.append)
    return events


@pytest.fixture
def client(agent_runs):
    return TestClient(webhook.app)


def test_rejects_a_wrong_signature(client, agent_runs):
    body = json.dumps(NEW_ISSUE).encode()

    response = client.post("/sentry", content=body, headers=sign(body, secret="wrong-secret"))

    assert response.status_code == 401
    assert agent_runs == []


def test_ignores_a_resolved_issue(client, agent_runs):
    body = json.dumps(NEW_ISSUE | {"action": "resolved"}).encode()

    response = client.post("/sentry", content=body, headers=sign(body))

    assert response.status_code == 200
    assert agent_runs == []


def test_ignores_a_created_comment(client, agent_runs):
    body = json.dumps({"action": "created", "data": {"comment": {"text": "looks like a bug"}}}).encode()

    response = client.post("/sentry", content=body, headers=sign(body))

    assert response.status_code == 200
    assert agent_runs == []


def test_fixes_a_new_issue(client, agent_runs):
    body = json.dumps(NEW_ISSUE).encode()

    response = client.post("/sentry", content=body, headers=sign(body))

    assert response.status_code == 202
    assert agent_runs == [(NEW_ISSUE, None)]


def test_dispatches_a_new_issue_in_prod(client, dispatches, agent_runs):
    body = json.dumps(NEW_ISSUE).encode()

    response = client.post("/sentry", content=body, headers=sign(body))

    assert response.status_code == 202
    assert dispatches == [NEW_ISSUE]
    assert agent_runs == []


def test_fails_when_the_dispatch_fails_so_sentry_retries(client, monkeypatch):
    def dispatch(event):
        raise OSError("github is down")

    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setattr(webhook, "dispatch", dispatch)
    body = json.dumps(NEW_ISSUE).encode()

    response = client.post("/sentry", content=body, headers=sign(body))

    assert response.status_code == 502


def test_does_not_dispatch_an_ignored_event_in_prod(client, dispatches):
    body = json.dumps(NEW_ISSUE | {"action": "resolved"}).encode()

    response = client.post("/sentry", content=body, headers=sign(body))

    assert response.status_code == 200
    assert dispatches == []
