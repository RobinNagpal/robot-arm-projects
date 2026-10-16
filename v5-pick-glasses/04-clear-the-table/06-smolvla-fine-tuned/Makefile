# Solution 6: the borrowed model with a correction fitted on problem 4's own
# demonstrations. The demonstrations are collected once, into ../demonstrations,
# by solution 3's collector; nothing here collects anything.

.DEFAULT_GOAL := help
SEEDS ?= 3
STEPS ?= 1000
TABLES ?= 20
ROOM ?= 120
QUIET ?= 16

.PHONY: help setup train selection pair measure test lint

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	cd .. && pixi install

train: ## Fit SEEDS corrections on the collected demonstrations
	cd .. && pixi run python -u 06-smolvla-fine-tuned/train.py --seeds $(SEEDS) --steps $(STEPS)

selection: ## One walk of TABLES tables below the held-out line, at QUIET quiet answers
	cd .. && pixi run python -u 06-smolvla-fine-tuned/run.py --first 0 --tables $(TABLES) \
		--runs 1 --seeds 1 --room $(ROOM) --quiet-for $(QUIET) \
		--save selection-quiet-$(QUIET).json

pair: ## The fitted weights and the same weights untrained, on the tables below the held-out line
	cd .. && pixi run python -u 06-smolvla-fine-tuned/run.py --first 0 --tables $(TABLES) \
		--runs $(SEEDS) --room $(ROOM) --save pair-fitted.json
	cd .. && pixi run python -u 06-smolvla-fine-tuned/run.py --first 0 --tables $(TABLES) \
		--runs $(SEEDS) --room $(ROOM) --as-it-downloads --save pair-untrained.json

measure: ## The held-out queue, walked once by each fitted correction. Measured once.
	cd .. && pixi run python -u 06-smolvla-fine-tuned/run.py

test: ## The quick checks. No weights, no accelerator.
	cd .. && pixi run pytest -q 06-smolvla-fine-tuned

lint: ## Ruff
	cd .. && pixi run ruff check 06-smolvla-fine-tuned
