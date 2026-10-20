# Watchdog Agent

An AI agent that turns production errors from Sentry into pull requests. When Sentry reports a new issue, Watchdog clones the affected repository, lets a Claude agent reproduce the bug, write a regression test and fix it inside a locked-down Docker container, then pushes a branch, opens a PR and reports the status to Telegram.

It is for solo developers and small teams who want a first-draft fix waiting for review instead of a bare error alert. I use it on my own TypeScript app.

## How it works

```
Sentry ──webhook──▶ src/host/webhook.py ──repository_dispatch──▶ GitHub Actions (fix-issue.yml)
                                                                    │
                                                    src/host/fix_issue.py
                                     clone ─▶ agent in Docker ─▶ commit ─▶ push ─▶ PR ─▶ Telegram
```

- **Host** (plain Python) does everything that can be done deterministically: verifying the webhook signature, cloning, committing, pushing, opening the PR.
- **Agent** ([Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python)) only edits files. It runs in a container with no git credentials, guardrails that block git writes and `.env` reads, and a 30-minute timeout.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full code map.

## Built with

Python 3.12, [uv](https://docs.astral.sh/uv/), Claude Agent SDK, Starlette + Uvicorn (webhook), PyGithub, Docker, GitHub Actions, Langfuse (tracing), pytest.

## Running locally

Requirements: Python 3.12+, uv, Docker.

```sh
cp .env.example .env        # fill in GIT_REPO_NAME, GIT_AUTH_TOKEN and a Claude credential
uv sync
make test                   # unit tests, no API calls
make run CASE=2-type-error-cannot-read-undefined   # fix one sample Sentry issue end to end
make serve                  # receive Sentry webhooks at POST /sentry (ENV=dev fixes in-process)
```

`make run` uses the sample issues in [`evals/cases`](evals/cases) against the fixture app in [watchdog-fixtures](https://github.com/artemdev/watchdog-fixtures).

## Deploying

1. Host the webhook (`python -m src.host.webhook`) with `ENV=prod`, `SENTRY_CLIENT_SECRET`, `WATCHDOG_REPO` and `DISPATCH_TOKEN`.
2. In this repo's GitHub settings, add the secrets `GIT_AUTH_TOKEN`, `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and the variables `GIT_REPO_NAME`, `LANGFUSE_BASE_URL`.
3. In Sentry, create an internal integration with a webhook pointing at `https://<your-host>/sentry` and subscribe it to issue events.

## Testing

- `make test`: unit tests for the host, agent guardrails and harness.
- `make evals`: end-to-end tests of the agent's behaviour. Each case plants a bug in the fixture app, runs the real agent and checks the result on disk: the bug is fixed (by a hidden test), prompt injections in the payload are resisted, and noise is ignored. All payloads are synthetic. See [evals/README.md](evals/README.md).

## Roadmap

See [ROADMAP.md](ROADMAP.md).

## License

[MIT](LICENSE)
