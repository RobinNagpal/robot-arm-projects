# Problem 4, learned: a model of what a push does, and a search over pushes.
#
# Run from this folder. The environment belongs to 04-clear-the-table above it,
# so every line goes through its pixi.
.DEFAULT_GOAL := help

PROBLEM := ..
HERE := 04-a-world-model
TABLES ?= 600
PIXI = cd $(PROBLEM) && pixi run

.PHONY: help collect collect-planned train measure measure-predicting reference judge test lint

help: ## This list
	@grep -hE '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | sort

collect: ## Round 1: pushes drawn at random on TABLES training tables (about 12 minutes)
	$(PIXI) python $(HERE)/collect.py --tables $(TABLES) --save $(HERE)/training.json

collect-planned: ## Round 2: the search's own pushes, which needs a trained model (about 15 minutes)
	$(PIXI) python $(HERE)/collect.py --planned --tables 300 --save $(HERE)/training.json

train: ## Fit the copies of the model on every round collected (about 2 minutes)
	$(PIXI) python $(HERE)/train.py --save $(HERE)/training.json

measure: ## The twenty tables the geometry reference was calibrated on
	$(PIXI) python $(HERE)/measure.py --save $(HERE)/measurement.json

measure-predicting: ## The same twenty, with the model believed instead of looking between pushes
	$(PIXI) python $(HERE)/measure.py --predicting --save $(HERE)/measurement-predicting.json

reference: ## The geometry reference's own numbers on the same twenty, to sit beside
	$(PIXI) python 01-one-fixed-nudge/calibrate.py --tables 20 --save $(HERE)/reference.json

judge: ## The held-out queue, once, through the bench's own judging
	$(PIXI) python $(HERE)/measure.py --judge

test: ## The checks, none of which needs a trained model
	$(PIXI) pytest -q $(HERE)

lint: ## Ruff over this folder
	$(PIXI) ruff check $(HERE)
