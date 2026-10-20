.PHONY: test evals image run serve

# `make run` fixes an eval case's Sentry event on the tag that has its bug; `main` already has the fix.
CASE ?= 2-type-error-cannot-read-undefined

image:
	docker build -q -f Dockerfile.agent -t watchdog-agent:dev .

run: image
	uv run --env-file .env python -m src.host evals/cases/$(CASE)/sentry.json --ref $(CASE)

# `make serve` receives Sentry's webhooks at POST /sentry. ENV=dev fixes each new issue in this process, like
# `make run`; ENV=prod hands it to the fix-issue GitHub workflow (.github/workflows/fix-issue.yml).
ENV ?= dev

serve: $(if $(filter dev,$(ENV)),image)
	ENV=$(ENV) uv run --env-file .env python -m src.host.webhook

test:
	uv run pytest -v tests

evals: image
	uv run --env-file .env pytest -v -m eval evals
