# Problem 3: six ways to push crowded glasses apart.
#
# Tests run one folder at a time on purpose. Several solutions have a module
# of the same name — plan.py, run.py, train.py — and collecting them together
# would let one shadow another.

SOLUTIONS := 01-one-fixed-nudge 02-geometry-ranked 03-imitation-from-demonstrations \
             04-a-world-model 05-smolvla-as-it-downloads 06-smolvla-fine-tuned

.PHONY: help install test lint $(SOLUTIONS)

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
