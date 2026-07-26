# EMKA — Expeditionary Medical Knowledge Assistant
# All targets run fully offline except `setup` and `models` (provisioning-time only).

.PHONY: setup models ingest index serve web eval smoke test lint

## Provisioning (network allowed — run once before the device goes dark)

setup:            ## Create the Python env and install all dependencies
	uv sync --all-groups
	@if [ -d web ] && [ -f web/package.json ]; then cd web && npm ci; fi

models:           ## Download/stage model weights into models/ (see models/README.md)
	uv run python scripts/fetch_models.py

## Runtime (fully offline)

ingest:           ## Run the manifest-driven ingest queue over corpus/
	uv run python -m ingest.run

index:            ## Build/rebuild retrieval indexes (dense + keyword) from ingested chunks
	uv run python -m retrieval.build_index

serve:            ## Start the FastAPI service (localhost / isolated LAN only)
	uv run uvicorn api.main:app --host 127.0.0.1 --port 8000

web:              ## Start the web front end dev server
	cd web && npm run dev

eval:             ## Run the gold-standard eval harness; non-zero exit on threshold breach
	uv run python -m eval.run

smoke:            ## Verify offline inference: chat model, embeddings, reranker
	uv run python scripts/smoke.py

## Dev hygiene

test:             ## Run the test suite
	uv run pytest

lint:             ## Ruff check + format check
	uv run ruff check .
	uv run ruff format --check .
