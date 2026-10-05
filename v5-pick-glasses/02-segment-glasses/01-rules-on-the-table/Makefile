# Problem 2 by geometry alone: no model, no weights, no training.

.DEFAULT_GOAL := help
SCENES ?= 20

.PHONY: help setup run crowded test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z]+:.*##/ { printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	cd .. && pixi install

run: setup ## Score it on the held-out spawned scenes; writes results.json
	cd .. && pixi run python 01-rules-on-the-table/run.py --scenes $(SCENES)

crowded: setup ## The same, on layouts where one glass really does hide another
	cd .. && pixi run python 01-rules-on-the-table/run.py --scenes $(SCENES) --crowded

test: setup ## The quick checks
	cd .. && pixi run pytest -q 01-rules-on-the-table bench
