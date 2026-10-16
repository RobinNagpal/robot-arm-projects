# Problem 4 by copying the ranked geometry: a small model with action chunking,
# fitted here from nothing on ../demonstrations.

.DEFAULT_GOAL := help
TABLES ?= 20
SEEDS ?= 3
STEPS ?= 8000

.PHONY: help setup collect train teacher measure judge test lint

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
