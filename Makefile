.PHONY: help setup ingest build models figures report test lint all clean-interim

PY := uv run python -m

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup:  ## Install the environment (uv)
	uv sync

ingest:  ## Ingest raw data: BTS noise (P03), Census, NYC 311 (P04-P05)
	$(PY) ne.ingest.bts_noise
	$(PY) ne.ingest.tiger
	$(PY) ne.ingest.acs
	$(PY) ne.ingest.nyc311

build:  ## Zonal stats and analysis tables (P06-P09, P12)
	$(PY) ne.build.zonal_stats
	@echo "TODO (P09, P12): analysis_table, nyc_panel"

models:  ## Disparity, spatial and complaint models (P10-P15)
	@echo "TODO (P10-P15): $(PY) ne.models.disparity / spatial_reg / complaints_nb / who_erf"

figures:  ## Make all charts (P10-P16)
	$(PY) ne.viz.qa
	@echo "TODO (P10-P16): $(PY) ne.viz.figures / maps"

report:  ## Render the Quarto report (P17)
	@echo "TODO (P17): quarto render report"

test:  ## Run tests
	uv run pytest -q

lint:  ## Lint and format check
	uv run ruff check src tests
	uv run ruff format --check src tests

all: ingest build models figures report  ## Full pipeline
