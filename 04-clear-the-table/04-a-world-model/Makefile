# Problem 4, learned: a model of what a push does, and a search over pushes.
#
# Run from this folder. The environment belongs to 04-clear-the-table above it,
# so every line goes through its pixi.
.DEFAULT_GOAL := help

PROBLEM := ..
HERE := 04-a-world-model
TABLES ?= 600
PIXI = cd $(PROBLEM) && pixi run

.PHONY: help collect collect-more collect-planned collect-doubted collect-check check-planned train toppled measure measure-predicting reference select judge test lint

help: ## This list
	@grep -hE '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | sort

collect: ## Round 1: pushes drawn at random on TABLES training tables (about 5 minutes)
	$(PIXI) python $(HERE)/collect.py --tables $(TABLES) --save $(HERE)/training.json

collect-more: ## Round 1 again, on the tables after it: the plainest kind of more data
	$(PIXI) python $(HERE)/collect.py --more --tables 1200 --save $(HERE)/training.json

collect-planned: ## Round 2: the search's own pushes, which needs a trained model (about 15 minutes)
	$(PIXI) python $(HERE)/collect.py --planned --tables 300 --save $(HERE)/training.json

collect-doubted: ## Round 3: the pushes the copies disagree about, which needs a trained model
	$(PIXI) python $(HERE)/collect.py --doubted --tables 300 --save $(HERE)/training.json

train: ## Fit the copies of the model on every round collected (about 2 minutes)
	$(PIXI) python $(HERE)/train.py --save $(HERE)/training.json

collect-check: ## A planned round kept out of the fit, for reading the topple head on the search's own pushes
	$(PIXI) python $(HERE)/collect.py --planned-check --tables 150

check-planned: ## Read the fitted copies on that set, which is where the broken glasses are explained
	$(PIXI) python $(HERE)/train.py --check $(HERE)/data/validation_planned.npz

toppled: ## For every table a glass went over on, whether it was the pushed glass or a neighbour
	$(PIXI) python $(HERE)/measure.py --toppled --first 5300 --tables 300

measure: ## The twenty tables the geometry reference was calibrated on
	$(PIXI) python $(HERE)/measure.py --save $(HERE)/measurement.json

measure-predicting: ## The same twenty, with the model believed instead of looking between pushes
	$(PIXI) python $(HERE)/measure.py --predicting --save $(HERE)/measurement-predicting.json

reference: ## The geometry reference's own numbers on the same twenty, to sit beside
	$(PIXI) python 01-one-fixed-nudge/calibrate.py --tables 20 --save $(HERE)/reference.json

select: ## A clocked queue of fifty tables below the held-out line, for choosing on
	$(PIXI) python $(HERE)/measure.py --select 500

judge: ## The held-out queue, once, through the examiner's own judging
	$(PIXI) python $(HERE)/measure.py --judge

test: ## The checks, none of which needs a trained model
	$(PIXI) pytest -q $(HERE)

lint: ## Ruff over this folder
	$(PIXI) ruff check $(HERE)
