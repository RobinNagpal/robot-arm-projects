# Problem 2: six ways to turn the same pictures into the same masks.
#
# Tests run one folder at a time on purpose. Several solutions have a module
# of the same name — run.py, train.py — and collecting them together would
# let one shadow another.

SOLUTIONS := 01-rules-on-the-table 02-train-from-scratch 03-yolo-zero-shot \
             04-yolo-fine-tuned 05-sam2-with-a-keeper 06-rf-detr-fine-tuned

.PHONY: help install test lint floor by-kind $(SOLUTIONS)

help: ## This list
	@grep -hE '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | sort

install: ## Resolve the environment
	pixi install

test: install ## Every folder's tests, one folder at a time
	@for d in bench $(SOLUTIONS); do \
	  [ -d $$d ] || continue; \
	  echo "--- $$d"; pixi run pytest -q $$d || exit 1; \
	done

lint: install ## Ruff over everything
	pixi run ruff check .

floor: install ## The best any solution could do: the renderer's own masks
	pixi run python bench/floor.py

by-kind: install ## What a borrowed model outlines well, one kind at a time
	pixi run python bench/by_kind.py
