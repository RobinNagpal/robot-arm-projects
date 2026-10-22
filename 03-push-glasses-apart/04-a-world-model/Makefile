# The learned version of problem 3. Its own environment; no ROS, no Gazebo.

.DEFAULT_GOAL := help
TABLES ?= 4000
FILM ?= 3
TABLE ?= 10000

.PHONY: help setup collect collect-planned train run film trace examples test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	pixi install

collect: setup ## Round 1: random pushes on TABLES training tables (about 5 minutes)
	pixi run python collect.py --tables $(TABLES)

collect-planned: setup ## Round 2: the planner's own pushes on 5000 new tables (about 20 minutes; needs a trained model)
	pixi run python collect.py --planned --tables 5000

train: setup ## Train the five copies of the forward model on every round collected (about 5 minutes)
	pixi run python train.py

run: setup ## Clear the 50 held-out tables and score it
	pixi run python run.py

film: setup ## Film the first FILM held-out tables into videos/
	pixi run python run.py --tables $(FILM) --film $(FILM)

trace: setup ## Write down and draw every step of table TABLE: what the model was given, what it said, what happened
	pixi run python trace_table.py --table $(TABLE)

examples: setup ## Write the first 20 collected pushes out as JSON, to see what the model is trained on
	pixi run python examples.py

test: setup ## The quick checks
	pixi run pytest -q . ../bench
