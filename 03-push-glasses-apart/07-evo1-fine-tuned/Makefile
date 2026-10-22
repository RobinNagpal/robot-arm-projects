# Solution 7: Evo-1, a newer and larger borrowed model, fitted on the same
# demonstrations as solution 6 so that the model is the only difference.

.DEFAULT_GOAL := help
STEPS ?= 1000
BATCH ?= 4
SEED ?= 0
INTO ?= fitted
FILM ?= 3

.PHONY: help setup train run film test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	pixi install

train: setup ## Fit the action half (needs solution 6's demonstrations; downloads the backbone once)
	pixi run python train.py --steps $(STEPS) --batch $(BATCH) --seed $(SEED) --into $(INTO)

run: setup ## Clear the 50 held-out tables, 3 evaluation runs, and score it
	pixi run python run.py

film: setup ## Film the first FILM held-out tables into videos/
	pixi run python run.py --tables $(FILM) --runs 1 --film $(FILM)

test: setup ## The checks that need no fit and no download
	pixi run pytest -q . ../bench
