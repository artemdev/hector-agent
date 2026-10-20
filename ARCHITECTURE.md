This document describes the high-level architecture of Hector, an AI coding agent that fixes production errors reported by Sentry.

## Bird's-eye view

Input data comes from Sentry as issues that trigger the agent via a webhook.

The host runs in the cloud or on GitHub Actions. When an issue is received, the agent produces a fix and then creates a pull request.

There are two main parts: the host (a Python script) and the AI agent (built with the Claude Agent SDK). The host runs the AI agent and handles everything that can be done programmatically, such as fetching the GitHub repository, committing, pushing and creating the PR. The agent receives only the Sentry payload and the repository files, and its only job is to produce the code fix. This separation keeps the results safe and predictable, because every action that can be done programmatically is done by the host.

## End-to-end tests

The agent is tested end to end on a small set of synthetic Sentry issues, each planted in a fixture app. Each case runs the real agent in its container against a mocked repository with a known bug, then grades the result from what is on disk, not from what the agent says it did.

Cases fall into three categories:

- **fix**: the agent must fix a real bug. A hidden test, which the agent never sees, verifies the fix.
- **security**: the agent must resist an attack, such as a prompt injection in the Sentry payload.
- **behaviour**: the agent must not act, for example on noise from a browser extension.

Checks are deterministic where possible (no commits, no git writes, no network calls, tests not weakened, test suite passes). An LLM judge reviews what those checks can't cover, such as prompt injection and secret handling.

See [evals/README.md](evals/README.md) for the case format and how to run these tests.

## Code Map

### Host

- `src/host/webhook.py`: the entry point in production. `POST /sentry` checks Sentry's `Sentry-Hook-Signature` (HMAC-SHA256 of the body with `SENTRY_CLIENT_SECRET`, 401 if wrong), acknowledges every event but a newly created issue with 200, and for a new issue starts a fix and answers 202. With `ENV=prod` it starts the fix by sending a `repository_dispatch` to `HECTOR_REPO`. It answers 502 if that fails, so Sentry retries. Its only secrets are `SENTRY_CLIENT_SECRET` and `DISPATCH_TOKEN`. With `ENV=dev` it runs `fix_issue` in its own process as a background task. `make serve` runs it (`ENV=dev` by default).
- `.github/workflows/fix-issue.yml`: runs `fix_issue` for one dispatched event on a fresh GitHub runner, which has Docker for the agent container. The git token, the Claude credentials and the Telegram and Langfuse keys are secrets of this repo. The webhook never holds them. It allows one run per issue at a time.
- `src/host/fix_issue.py`: one issue end to end: clone, run the agent in its container, commit, push, open the PR, report to Telegram. `make run` and the workflow call it directly on an event file.

### Agent

Run in isolated docker container (production)

- **Isolation**: Runs in sandbox and docker container to insure that it won't do harmful actions to the environment.
- **Least privilage**: have access only to mandatory tools: read/write workdir, deny reading/writing git folder or .env variables

### Host environment

Running all github actions (pulling, pushing, commiting andPR creation)

### Observability

### Deployment
