# Roadmap

## Now
- [ ] Deploy the webhook to Railway and run fixes on GitHub Actions in production
- [ ] Simplify the hardest-to-read functions in the host and harness
- [ ] Group reused helpers into well-named modules and remove unused logic

## Next
- [ ] Deduplicate issues across webhook retries and reopenings (store issue → PR state in Postgres)
- [ ] Update the existing PR when an issue recurs instead of skipping it
- [ ] More end-to-end cases: async errors, frontend (React) stack traces, errors with no stack trace
- [ ] Report edit distance to the reference fix next to each end-to-end case result
- [ ] Decide when not to act: confidence threshold and a "needs human" Telegram message

## Later
- [ ] Support several target repositories from one deployment
- [ ] Monorepo support: pick the package and test command from the stack trace
- [ ] Cost and duration per fix in the PR description (from Langfuse)
- [ ] Docs: Sentry integration setup guide with screenshots
