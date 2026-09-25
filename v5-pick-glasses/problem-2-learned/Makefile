# The learned version of problem 2. Its own environment; no ROS, no Gazebo.

.DEFAULT_GOAL := help
SCENES ?= 200

.PHONY: help setup train run test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z]+:.*##/ { printf "  \033[36m%-6s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	pixi install

train: setup ## Draw SCENES scenes and train the three models (about a minute)
	pixi run python train.py --scenes $(SCENES)

run: setup ## Run the pipeline on the 50 held-out scenes and score it
	pixi run python run.py

test: setup ## The quick checks
	pixi run pytest -q . ../problem-2-sim
