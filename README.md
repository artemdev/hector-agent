# Hector 💪

**Hector works 24/7, turning production errors into pull requests with a fix and keeping you updated on Telegram in real time.**

https://github.com/user-attachments/assets/b2420355-53ae-4e5e-86c0-35a9e6cf9949

## Why

Production errors happen faster than anyone can fix them, especially in vibe-coded and AI-assisted projects, and often at night when no one is watching.

## How it works

When your error tracker (only [Sentry](https://sentry.io) for now) reports a new error, Hector:

1. Gets the error from Sentry
2. Clones your repo
3. Lets an AI agent (Claude Agent SDK) find the bug, write a test for it and fix it
4. Opens a pull request for you to review
5. Sends you a Telegram notification at every step

See [ARCHITECTURE.md](ARCHITECTURE.md) for how it works inside.

## Key decisions

- **The AI only edits files. Plain code does the rest.** Cloning, committing, pushing and opening the PR are done by a Python script, not by the AI. This keeps runs predictable, and a prompt injection hidden in an error message can't push to `main`.
- **It never merges.** You review every PR like any other. Hector saves you the boring part, not the judgement.
- **Each fix runs in a locked Docker container on a fresh GitHub Actions runner.** Read-only filesystem, no git writes, no `.env` access, a 30-minute limit. Nothing persists between runs, and your GitHub, Telegram and app secrets never enter the container.
- **It's tested on behaviour, not on what the AI says.** Each test case plants a real bug and checks the result on disk with a hidden test the agent never sees, so it can't pass by editing or skipping tests.
- **It can decide not to act.** Errors that aren't your bug, such as noise from a browser extension, end with no change rather than a made-up fix.

Trade-offs: for now it supports only Node apps, with one repo per deployment.

## Results

Hector is tested end to end on 7 cases against a [sample app](https://github.com/artemdev/hector-fixtures). **7/7 cases pass.**

| Category  | What it checks                                                                    | Passing |
|-----------|-----------------------------------------------------------------------------------|---------|
| fix       | Fixes the bug without weakening tests, even when the cause isn't in the top frame | ✅ 4/4  |
| security  | Ignores prompt injections in the Sentry payload                                   | ✅ 2/2  |
| behaviour | Leaves the code alone when the error isn't a bug in your app                      | ✅ 1/1  |

See [evals/README.md](evals/README.md) for how the cases work.

## Try it

You need Python 3.12+, [uv](https://docs.astral.sh/uv/) and Docker.

```sh
cp .env.example .env    # add your GitHub token and Claude key
uv sync
make run                # fix a sample bug end to end
```

Other commands:

| Command      | What it does                         |
|--------------|--------------------------------------|
| `make test`  | Run unit tests (free, no AI calls)   |
| `make evals` | Run the agent on all sample bugs     |
| `make serve` | Start the webhook that Sentry calls  |

## Use it on your app

Hector is self-hosted: it runs on your own GitHub Actions and server.

1. Fork Hector and add your GitHub token, Claude key and app repo name to the fork's Actions settings.
2. Deploy the webhook (`make serve` with `ENV=prod`) on any server, such as Railway.
3. In Sentry, point a webhook at `https://<your-server>/sentry`.

See [SETUP.md](SETUP.md) for the step-by-step guide.

## Built with

Python, Claude Agent SDK, Docker, GitHub Actions, Sentry, Langfuse.

## What's next

See [ROADMAP.md](ROADMAP.md).

## License

[MIT](LICENSE)
