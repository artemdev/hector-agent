# Evals

End-to-end evaluation of the agent. Each case runs the real agent in Docker on a real bug and grades the result. Evals call the Claude API and cost money, so plain `pytest` skips them.

## Running

Requires Docker and these variables in `.env`: `GIT_AUTH_TOKEN`, `GIT_REPO_NAME`, and the agent's API keys.

```sh
make evals                       # all cases
uv run --env-file .env pytest -v -m eval -m security evals   # one category
make run CASE=2-type-error-cannot-read-undefined             # run the agent on one case without grading
```

## How a case runs

1. Clone the fixture repo at the case's `buggy_tag` and install npm dependencies.
2. Run the agent in its container with the case's `sentry.json`.
3. Run every check against the working tree the agent left behind.

All checks for a case share one agent run.

## Case format

Each case is a folder in `evals/cases/<id>/` with two files:
- `sentry.json`: the Sentry webhook payload the agent receives
- `case.yaml`: metadata and grading rules
