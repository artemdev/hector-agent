# Hector 💪

**Hector works 24/7, turning new Sentry issues into pull requests with a fix.**

https://github.com/user-attachments/assets/b2420355-53ae-4e5e-86c0-35a9e6cf9949

**See a real PR Hector opened:** [fix: TypeError: Cannot read properties of undefined (reading 'trim')](https://github.com/artemdev/hector-fixtures/pull/10). It finds the root cause, fixes it, and adds a test that failed before the fix.

When Sentry reports a new error, Hector:

1. Gets the error from Sentry
2. Clones your repo
3. Lets a Claude Code AI agent find the bug, write a test for it and fix it
4. Opens a pull request for you to review
5. Sends you a Telegram notification at every step

You stay in control: it never merges anything. You review the PR like any other.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how it works inside.

## Is it safe?

- The AI only edits files. It can't push, commit or read your secrets.
- It runs inside a locked Docker container and stops after 30 minutes.
- Pushing and opening the PR is done by plain code, not by the AI.

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

The sample bugs live in [hector-fixtures](https://github.com/artemdev/hector-fixtures).

## Use it on your app

1. Fork Hector and add your GitHub token, Claude key and app repo name to the fork's Actions settings.
2. Deploy the webhook (`make serve` with `ENV=prod`) on any server.
3. In Sentry, point a webhook at `https://<your-server>/sentry`.

Works with Node apps for now. See [SETUP.md](SETUP.md) for the step-by-step guide.

## Built with

Python, Claude Agent SDK, Docker, GitHub Actions, Sentry, Langfuse.

## More

- [Set it up on your app](SETUP.md)
- [How it works inside](ARCHITECTURE.md)
- [Sample bugs and tests](evals/README.md)
- [What's next](ROADMAP.md)

## License

[MIT](LICENSE)
