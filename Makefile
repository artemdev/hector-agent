.PHONY: test evals

test:
	uv run pytest -v tests

evals:
	uv run pytest -v -m eval evals
