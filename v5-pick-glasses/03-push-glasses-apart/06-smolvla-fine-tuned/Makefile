# Solution 6: the same foundation model as solution 5, fine-tuned on this
# bench's own pushes with a low-rank correction.

.DEFAULT_GOAL := help
TABLES ?= 800
STEPS ?= 1000
BATCH ?= 4
SEED ?= 0
INTO ?= correction
FILM ?= 3

.PHONY: help setup demonstrations tuning train run film test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	pixi install

demonstrations: setup ## Run the teacher over TABLES training tables and write the demonstrations
	pixi run python demonstrations.py --tables $(TABLES)

tuning: setup ## The same on the tuning tables, which say when to stop training
	pixi run python demonstrations.py --check

train: setup ## Fit the correction (needs both demonstration sets; downloads the weights once)
	pixi run python train.py --steps $(STEPS) --batch $(BATCH) --seed $(SEED) --into $(INTO)

run: setup ## Clear the 50 held-out tables, 3 evaluation runs, and score it
	pixi run python run.py

film: setup ## Film the first FILM held-out tables into videos/
	pixi run python run.py --tables $(FILM) --runs 1 --film $(FILM)

test: setup ## The checks that need no correction and no download
	pixi run pytest -q . ../bench
