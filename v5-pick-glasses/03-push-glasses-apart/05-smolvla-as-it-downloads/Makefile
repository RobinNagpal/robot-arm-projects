# Solution 5: SmolVLA exactly as it downloads. Nothing is trained, so there is
# no collect and no train target. The weights arrive on the first run.

.DEFAULT_GOAL := help
TABLES ?= 50
RUNS ?= 3
FILM ?= 3

.PHONY: help setup run film sensitivity test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	pixi install

run: setup ## The three evaluation runs over the 50 held-out tables (about an hour on a laptop)
	pixi run python run.py --runs $(RUNS) --tables $(TABLES)

film: setup ## Film the first FILM held-out tables into videos/
	pixi run python run.py --runs 1 --tables $(FILM) --film $(FILM)

sensitivity: setup ## The same, with the one undetermined slot of the join turned over
	pixi run python run.py --runs 1 --tables $(TABLES) --upside-down

test: setup ## The quick checks. No download, no accelerator.
	pixi run pytest -q . ../bench
