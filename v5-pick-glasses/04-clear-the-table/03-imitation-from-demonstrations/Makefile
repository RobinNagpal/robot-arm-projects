# Problem 4 by copying the ranked geometry: a small model with action chunking,
# fitted here from nothing on ../demonstrations.

.DEFAULT_GOAL := help
TABLES ?= 20
SEEDS ?= 3
STEPS ?= 8000
# How many looking frames the policy's fit reads. The set holds far more than a
# fit can use, and loading.load says what the cap is for.
LOOKS ?= 8000

.PHONY: help setup collect train train-gate train-policy teacher measure judge test lint

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	cd .. && pixi install

collect: ## Run the teacher over the training tables and write ../demonstrations
	cd .. && pixi run python -u 03-imitation-from-demonstrations/collect.py
	cd .. && pixi run python -u 03-imitation-from-demonstrations/collect.py --held-back

train: ## Fit SEEDS seeds on the collected demonstrations
	cd .. && pixi run python -u 03-imitation-from-demonstrations/train.py \
		--seeds $(SEEDS) --steps $(STEPS)

train-gate: ## Fit SEEDS gates alone, on the mixture as the teacher gave it
	cd .. && pixi run python -u 03-imitation-from-demonstrations/train.py \
		--seeds $(SEEDS) --gate-only

train-policy: ## Fit SEEDS policies alone, reading at most LOOKS looking frames
	cd .. && pixi run python -u 03-imitation-from-demonstrations/train.py \
		--seeds $(SEEDS) --steps $(STEPS) --policy-only --looks $(LOOKS)

judge: ## The held-out queue, walked once a fit through bench/judging.py
	cd .. && pixi run python -u 03-imitation-from-demonstrations/run.py --judge

teacher: ## How long the teacher goes without touching a glass
	cd .. && pixi run python -u 03-imitation-from-demonstrations/teacher.py

measure: ## What every fitted seed achieves on TABLES training tables
	cd .. && pixi run python -u 03-imitation-from-demonstrations/run.py --tables $(TABLES) \
		--save 03-imitation-from-demonstrations/measurement.json

test: ## The quick checks
	cd .. && pixi run pytest -q 03-imitation-from-demonstrations

lint: ## Ruff
	cd .. && pixi run ruff check 03-imitation-from-demonstrations
