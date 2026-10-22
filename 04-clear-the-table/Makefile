# Problem 4: the arm carries its own camera, and the table is marked when the
# solution says it is done.
#
# Tests run one folder at a time on purpose. The bench and the solutions have
# modules of the same name — run.py, plan.py, scoring.py — and collecting them
# together would let one shadow another.
SOLUTIONS := 01-one-fixed-nudge 02-geometry-ranked 03-imitation-from-demonstrations \
             04-a-world-model 06-smolvla-fine-tuned

# Where the films go.
FILMS := videos

.PHONY: help install test lint films $(SOLUTIONS)

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

# One table, all six solutions, and the files the pages link to. The table and
# the reason it was chosen are in results/films.py, because that script is the
# one place all six solutions meet. Each one is filmed in a process of its own:
# several of them load their borrowed files under the same plain names, so two
# in one process would fight over them.
films: install ## Film all six solutions on the one comparison table
	pixi run python results/films.py --all
	@echo "six films in $(FILMS)"
