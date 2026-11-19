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
	$(PY) ne.build.analysis_table
	$(PY) ne.build.nyc_panel

models:  ## Disparity, spatial and complaint models (P10-P15)
	$(PY) ne.models.disparity
	$(PY) -W ignore ne.models.spatial_reg
	$(PY) -W ignore ne.models.complaints_nb
	$(PY) ne.models.health
	$(PY) -W ignore ne.models.robustness

figures:  ## Make all charts (P10-P16)
	$(PY) ne.viz.qa
	$(PY) ne.viz.figures
	$(PY) ne.viz.maps

report:  ## Render the Quarto report (P17)
	@echo "TODO (P17): quarto render report"

test:  ## Run tests
	uv run pytest -q

lint:  ## Lint and format check
	uv run ruff check src tests
	uv run ruff format --check src tests

all: ingest build models figures report  ## Full pipeline
