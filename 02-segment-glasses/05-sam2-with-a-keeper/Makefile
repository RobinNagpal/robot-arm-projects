# Problem 2 with borrowed weights: SAM 2 proposes, a small fitted keeper decides.

.DEFAULT_GOAL := help
RUNG ?= sam2
SCENES ?= 0

.PHONY: help setup fetch train run crowded show test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z]+:.*##/ { printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	cd .. && pixi install

fetch: setup ## Download the borrowed weights into weights/ (SAM 2 is 320 MB)
	cd .. && pixi run python 05-sam2-with-a-keeper/weights.py

train: setup ## Fit the keeper, which needs SAM 2 run over the training scenes (minutes)
	cd .. && pixi run python 05-sam2-with-a-keeper/train.py --solution $(RUNG) --scenes $(SCENES)

run: setup ## Score a rung on the held-out spawned scenes; writes results-$(RUNG).json
	cd .. && pixi run python 05-sam2-with-a-keeper/run.py --solution $(RUNG) --scenes $(SCENES)

crowded: setup ## The same, on layouts where one glass really does hide another
	cd .. && pixi run python 05-sam2-with-a-keeper/run.py --solution $(RUNG) --scenes $(SCENES) --crowded

show: setup ## Print the keeper's eight measurements beside its answer, over one scene
	cd .. && pixi run python 05-sam2-with-a-keeper/show_keeper.py

test: setup ## The quick checks: no weights, no network
	cd .. && pixi run pytest -q 05-sam2-with-a-keeper bench
