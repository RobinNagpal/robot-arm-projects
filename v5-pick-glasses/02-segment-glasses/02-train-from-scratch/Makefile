# Problem 2 with a network written and trained here: no borrowed weights.

.DEFAULT_GOAL := help
SCENES ?= 200
HELD_OUT ?= 20

.PHONY: help setup train run crowded show test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z]+:.*##/ { printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	cd .. && pixi install

train: setup ## Draw SCENES training scenes and fit the models (TopNet takes minutes)
	cd .. && pixi run python 02-train-from-scratch/train.py --scenes $(SCENES)

run: setup ## Score it on the held-out spawned scenes; writes results.json
	cd .. && pixi run python 02-train-from-scratch/run.py --scenes $(HELD_OUT)

crowded: setup ## The same, on layouts where one glass really does hide another
	cd .. && pixi run python 02-train-from-scratch/run.py --scenes $(HELD_OUT) --crowded

show: setup ## Save pictures of what each model is taught and of what it answers (a few minutes)
	cd .. && pixi run python 02-train-from-scratch/show_top_net.py train --scenes $(SCENES)
	cd .. && pixi run python 02-train-from-scratch/show_top_net.py test --scenes $(HELD_OUT)
	cd .. && pixi run python 02-train-from-scratch/show_top_net.py test --scenes $(HELD_OUT) --crowded
	cd .. && pixi run python 02-train-from-scratch/show_ranker.py train --scenes $(SCENES)
	cd .. && pixi run python 02-train-from-scratch/show_ranker.py test
	cd .. && pixi run python 02-train-from-scratch/show_side_net.py train --scenes $(SCENES)
	cd .. && pixi run python 02-train-from-scratch/show_side_net.py test

test: setup ## The quick checks: no weights needed
	cd .. && pixi run pytest -q 02-train-from-scratch bench
