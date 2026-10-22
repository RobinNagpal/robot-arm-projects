# Problem 4 by geometry alone. No training, and nothing learned.

.DEFAULT_GOAL := help
TABLES ?= 20

.PHONY: help setup calibrate test lint

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	cd .. && pixi install

calibrate: ## Measure the arm time this needs, on TABLES training tables
	cd .. && pixi run python 01-one-fixed-nudge/calibrate.py --tables $(TABLES) \
		--save 01-one-fixed-nudge/calibration.json

test: ## The quick checks
	cd .. && pixi run pytest -q 01-one-fixed-nudge

lint: ## Ruff
	cd .. && pixi run ruff check 01-one-fixed-nudge
