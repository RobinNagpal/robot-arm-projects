# Problem 2 with a transformer segmenter: RF-DETR-Seg, fine-tuned here.
#
# TARGET says what the masks are trained against: the pixels the camera can
# see of a glass, or the glass's whole silhouette.

.DEFAULT_GOAL := help
TARGET ?= amodal
SCENES ?=

.PHONY: help setup fetch train run crowded test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z]+:.*##/ { printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	cd .. && pixi install

fetch: setup ## Download the borrowed weights into weights/ (128 MB)
	cd .. && pixi run python 06-rf-detr-fine-tuned/weights.py

train: setup ## Fine-tune TARGET on this cell's pictures; the slow step
	cd .. && pixi run python 06-rf-detr-fine-tuned/train.py --target $(TARGET) $(if $(SCENES),--scenes $(SCENES))

run: setup ## Score TARGET on the held-out spawned scenes; writes results-$(TARGET).json
	cd .. && pixi run python 06-rf-detr-fine-tuned/run.py --target $(TARGET) $(if $(SCENES),--scenes $(SCENES))

crowded: setup ## The same, on layouts where one glass really does hide another
	cd .. && pixi run python 06-rf-detr-fine-tuned/run.py --target $(TARGET) --crowded $(if $(SCENES),--scenes $(SCENES))

test: setup ## The quick checks: no weights, no network, no fine-tune
	cd .. && pixi run pytest -q 06-rf-detr-fine-tuned
