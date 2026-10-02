.PHONY: test evals image run

image:
	docker build -q -f Dockerfile.agent -t watchdog-agent:dev .

run: image
	uv run python -m src

test:
	uv run pytest -v tests

evals: image
	uv run pytest -v -m eval evals
