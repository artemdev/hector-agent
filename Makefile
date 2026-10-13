.PHONY: test evals image run

# `make run` fixes an eval case's Sentry event on the tag that has its bug; `main` already has the fix.
CASE ?= 2-type-error-cannot-read-undefined

image:
	docker build -q -f Dockerfile.agent -t watchdog-agent:dev .

run: image
	uv run --env-file .env python -m src.host evals/cases/$(CASE)/sentry.json --ref $(CASE)

test:
	uv run pytest -v tests

evals: image
	uv run --env-file .env pytest -v -m eval evals
