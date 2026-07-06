.PHONY: setup mock test lint run report study clean

setup:
	uv sync --extra dev

mock:
	uv run python -m agentic_bias_lens --dry-run

test:
	uv run pytest -q

lint:
	uv run ruff check .

run:
	uv run python -m agentic_bias_lens

report:
	uv run python -m agentic_bias_lens --report-only

study:
	pwsh scripts/run-study.ps1

clean:
	rm -rf runs/ cache/ .pytest_cache/ .ruff_cache/
