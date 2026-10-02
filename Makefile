.PHONY: test evals image run

# RUN_AGENT_IN_CONTAINER=true|false comes from .env; override it per run: `make run RUN_AGENT_IN_CONTAINER=false`.
RUN_AGENT_IN_CONTAINER ?= $(shell sed -n 's/^RUN_AGENT_IN_CONTAINER=//p' .env 2>/dev/null)

image:
	docker build -q -f Dockerfile.agent -t watchdog-agent:dev .

run: $(if $(filter true,$(RUN_AGENT_IN_CONTAINER)),image)
	uv run python -m src

test:
	uv run pytest -v tests

evals: image  # the graders always run in the image
	uv run pytest -v -m eval evals
