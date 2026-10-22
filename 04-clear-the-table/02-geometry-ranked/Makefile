# Problem 4 with many candidate pushes and problem 3's fitted ranker to order them.
# Nothing here trains anything.

.DEFAULT_GOAL := help
TABLES ?= 20

.PHONY: help setup measure rule inputs perfect test lint

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	cd .. && pixi install

measure: ## What this achieves and spends on TABLES training tables
	cd .. && pixi run python 02-geometry-ranked/measure.py --tables $(TABLES) \
		--save 02-geometry-ranked/measurement.json

rule: ## The same loop and the same candidates, with the model deleted
	cd .. && pixi run python 02-geometry-ranked/measure.py --tables $(TABLES) --rule

inputs: ## Whether the inputs handed to the borrowed trees are the kind they were fitted on
	cd .. && pixi run python 02-geometry-ranked/measure.py --inputs --tables $(TABLES)

perfect: ## The chooser with the arm taken away: is the draw separable at all
	cd .. && pixi run python 02-geometry-ranked/measure.py --tables $(TABLES) --perfect \
		--save 02-geometry-ranked/perfect.json

test: ## The quick checks
	cd .. && pixi run pytest -q 02-geometry-ranked

lint: ## Ruff
	cd .. && pixi run ruff check 02-geometry-ranked
