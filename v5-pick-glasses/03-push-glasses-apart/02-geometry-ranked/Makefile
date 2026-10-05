# Solution 2: the geometry enumerates, a fitted ranker orders. No ROS, no Gazebo,
# no accelerator.

.DEFAULT_GOAL := help
TABLES ?= 200
FILM ?= 3

.PHONY: help setup spread train run rule demos film test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	pixi install

spread: setup ## Measure what differs inside a candidate group, before trusting any ranker
	pixi run python spread.py

train: setup ## Label candidates on TABLES training tables and fit the trees (about 5 minutes)
	pixi run python train.py --tables $(TABLES)

run: setup ## Clear the 50 held-out tables with the ranker and score it
	pixi run python run.py

rule: setup ## The same run with the model deleted, which is the comparison that matters
	pixi run python run.py --rule

demos: setup ## Write demonstrations for solutions 3 and 6 into demonstrations/
	pixi run python demos.py --tables $(TABLES)

film: setup ## Film the first FILM held-out tables into videos/
	pixi run python run.py --tables $(FILM) --film $(FILM)

test: setup ## The quick checks; no trained model needed
	pixi run pytest -q . ../bench
