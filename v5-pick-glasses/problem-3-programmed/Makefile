# Problem 3 by geometry alone. Its own environment; no ROS, no Gazebo, no training.

.DEFAULT_GOAL := help
FILM ?= 3

.PHONY: help setup run film test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	pixi install

run: setup ## Clear the 50 held-out tables and score it
	pixi run python run.py

film: setup ## Film the first FILM held-out tables into videos/
	pixi run python run.py --scenes $(FILM) --film $(FILM)

test: setup ## The quick checks
	pixi run pytest -q . ../problem-3-sim
