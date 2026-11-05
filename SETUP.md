# Set up Hector on your app

Once it's set up, every new Sentry issue in your app becomes a pull request with a fix.

It takes about 15 minutes, in three places: a fork of Hector on GitHub, a small server for the webhook, and Sentry.

```
Sentry ──new issue──▶ webhook (your server) ──triggers──▶ GitHub Action (your Hector fork) ──PR──▶ your app repo
```

> **Your app must be a Node project for now.** Hector installs dependencies from `package.json` with npm, yarn or pnpm, so the agent can run your tests.

## 1. Fork Hector

Fork this repo. The fix runs as a GitHub Action in **your fork**. It clones your app, then opens the PR in your app's repo.

## 2. Create the tokens

| Token | Where to get it | Access it needs |
|---|---|---|
| App token | GitHub → Settings → Developer settings → Fine-grained tokens | Your **app repo**: Contents and Pull requests, read and write |
| Dispatch token | Same place | Your **Hector fork**: Contents, read and write (lets the webhook start the Action) |
| Claude key | [console.anthropic.com](https://console.anthropic.com), or `claude setup-token` for a Claude subscription | — |

## 3. Add them to your fork

In your fork: **Settings → Secrets and variables → Actions**.

**Secrets**

| Name | Value | Required |
|---|---|---|
| `GIT_AUTH_TOKEN` | The app token | yes |
| `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` | The Claude key | yes |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Your bot and chat, for status messages (comma-separate several chats) | no |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Your Langfuse keys, for traces | no |

**Variables**

| Name | Value | Required |
|---|---|---|
| `GIT_REPO_NAME` | Your app repo, e.g. `acme/shop` | yes |
| `GIT_REF` | The branch to fix; unset means the default branch | no |
| `GIT_ROOT_PATH` | The package folder in a monorepo, e.g. `apps/web`; unset means the repo root | no |
| `LANGFUSE_BASE_URL` | Your Langfuse URL | no |

## 4. Create a Sentry integration

In Sentry: **Settings → Developer Settings → Custom Integrations → Create New Integration → Internal Integration**.

- **Webhook URL**: `https://<your-server>/sentry`. If your server isn't up yet, add the URL after step 5.
- **Alert Rule Action**: off. **Webhooks**: turn on **issue**.
- **Permissions**: Issue & Event, read.
- Save, then copy the **Client Secret**.

## 5. Deploy the webhook

Run `make serve` on any host that can receive HTTPS, such as Railway, Fly.io or a small VM, with these environment variables:

| Name | Value |
|---|---|
| `ENV` | `prod` |
| `SENTRY_CLIENT_SECRET` | The client secret from step 4 |
| `HECTOR_REPO` | Your fork, e.g. `acme/hector` |
| `DISPATCH_TOKEN` | The dispatch token |
| `PORT` | Optional, defaults to `8000` |

The webhook holds only these values. Your GitHub and Claude keys stay in GitHub Actions secrets.

## 6. Check it works

Trigger an error in your app. Within a minute, a **fix-issue** run should appear in your fork's **Actions** tab. When it finishes, the PR shows up in your app repo (and in Telegram, if you set it up).

If nothing happens:

- **No run in Actions**: check the webhook logs. `401` means `SENTRY_CLIENT_SECRET` is wrong. `502` means `HECTOR_REPO` or `DISPATCH_TOKEN` is wrong.
- **The run fails at clone or PR**: check `GIT_REPO_NAME` and the app token's access.
- **No PR, but the run passed**: the agent decided not to change anything, for example because the error came from a browser extension. The run log says why.
