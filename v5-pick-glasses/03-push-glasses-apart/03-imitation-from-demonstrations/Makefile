# Solution 3: imitation from demonstrations. The problem's one environment.

.DEFAULT_GOAL := help
TABLES ?= 5200
SEEDS ?= 1
SEED ?= 0
STEPS ?= 10000
RUNG ?= act
FILM ?= 3

.PHONY: help setup teacher collect train run film test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	pixi install

teacher: setup ## Fit solution 2, which is what the demonstrations are copied from
	pixi run python ../02-geometry-ranked/train.py

collect: setup ## Run the teacher on TABLES training tables and keep the pushes that worked
	pixi run python collect.py --tables $(TABLES)

train: setup ## Fit SEEDS copies of RUNG, starting at seed SEED. Run it once per seed: each takes about an hour
	pixi run python -u train.py --rung $(RUNG) --seeds $(SEEDS) --first-seed $(SEED) --steps $(STEPS)

run: setup ## Clear the 50 held-out tables with every fitted seed, and score it
	pixi run python run.py --rung $(RUNG)

film: setup ## Film the first FILM held-out tables into videos/
	pixi run python run.py --rung $(RUNG) --tables $(FILM) --film $(FILM)

test: setup ## The quick checks: no fitted policy, no download
	pixi run pytest -q .
