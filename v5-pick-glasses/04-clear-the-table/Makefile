# Problem 4: the arm carries its own camera, and the table is marked when the
# solution says it is done.
#
# Tests run one folder at a time on purpose. The bench and the solutions have
# modules of the same name — run.py, plan.py, scoring.py — and collecting them
# together would let one shadow another.

SOLUTIONS := 01-one-fixed-nudge

# Problem 3's folder, for two reasons. Its bench is what this problem borrows
# rather than copies, and its environment already holds everything problem 4
# needs, which is what `test-in-problem-3` below is for.
PUSHING := ../03-push-glasses-apart

.PHONY: help install test lint test-in-problem-3 $(SOLUTIONS)

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

# The same test files, run in problem 3's environment, for a machine where this
# folder's own environment is not resolved yet. The three paths are the ones
# `pixi.toml` sets here: the project's modules, this problem's bench, and
# problem 3's bench, which this problem borrows from.
test-in-problem-3: ## The same tests in problem 3's environment, before this one is resolved
	@here=$$PWD; for d in bench $(SOLUTIONS); do \
	  [ -d $$d ] || continue; \
	  echo "--- $$d"; \
	  ( cd $(PUSHING) && \
	    PYTHONPATH="$$PWD/../src/work_cell:$$here/bench:$$PWD/bench" \
	    pixi run pytest -q $$here/$$d ) || exit 1; \
	done
