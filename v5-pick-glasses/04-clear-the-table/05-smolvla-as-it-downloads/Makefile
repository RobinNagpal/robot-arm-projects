# Solution 5: SmolVLA exactly as it downloads. Nothing is trained, so there is
# no collect and no train target. The weights arrive on the first run.

.DEFAULT_GOAL := help
TABLES ?= 20
RUNS ?= 3

.PHONY: help setup measure pinned test lint

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	cd .. && pixi install

measure: ## What it achieves and spends on TABLES tables, RUNS times over
	cd .. && pixi run python 05-smolvla-as-it-downloads/measure.py \
		--tables $(TABLES) --runs $(RUNS) --show \
		--save 05-smolvla-as-it-downloads/measurement.json

pinned: ## The same, with problem 3's parked jaw pose as the state; tells the picture from the state
	cd .. && pixi run python 05-smolvla-as-it-downloads/measure.py \
		--tables $(TABLES) --runs 1 --pinned \
		--save 05-smolvla-as-it-downloads/pinned.json

test: ## The quick checks. No download, no accelerator.
	cd .. && pixi run pytest -q 05-smolvla-as-it-downloads

lint: ## Ruff
	cd .. && pixi run ruff check 05-smolvla-as-it-downloads
