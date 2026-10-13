# Problem 3: six ways to push crowded glasses apart.
#
# Tests run one folder at a time on purpose. Several solutions have a module
# of the same name — plan.py, run.py, train.py — and collecting them together
# would let one shadow another.

SOLUTIONS := 01-one-fixed-nudge 02-geometry-ranked 03-imitation-from-demonstrations \
             04-a-world-model 05-smolvla-as-it-downloads 06-smolvla-fine-tuned

# The one held-out table every solution is filmed on. It was chosen by a rule
# applied afterwards rather than by eye: every solution has to reach its own
# commonest outcome there and rack at least one glass, and exactly one table of
# the fifty does both. The documents say so, so it is written here once rather
# than typed into six commands.
FILM_TABLE := 10025
FILMS := ../videos/03-push-glasses-apart

.PHONY: help install test lint comparison-films $(SOLUTIONS)

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

# Each solution's own `make film` films whichever tables it is pointed at, for
# looking at while working on it. This one is different: one table, all six
# solutions, and the files the documents link to.
comparison-films: install ## Film FILM_TABLE with all six, for the comparison page
	@mkdir -p $(FILMS)
	cd 01-one-fixed-nudge && pixi run python run.py --first $(FILM_TABLE) --scenes 1 --film 1
	cp 01-one-fixed-nudge/videos/table-$(FILM_TABLE).mp4 $(FILMS)/01-one-fixed-nudge.mp4
	cd 02-geometry-ranked && pixi run python run.py --first $(FILM_TABLE) --tables 1 --film 1
	cp 02-geometry-ranked/videos/table-$(FILM_TABLE).mp4 $(FILMS)/02-geometry-ranked.mp4
	cd 03-imitation-from-demonstrations && \
	  pixi run python run.py --first $(FILM_TABLE) --tables 1 --film 1 --seeds 0
	cp 03-imitation-from-demonstrations/videos/act-0-table-$(FILM_TABLE).mp4 \
	   $(FILMS)/03-imitation-from-demonstrations.mp4
	cd 04-a-world-model && pixi run python run.py --first $(FILM_TABLE) --tables 1 --film 1
	cp 04-a-world-model/videos/table-$(FILM_TABLE).mp4 $(FILMS)/04-a-world-model.mp4
	cd 05-smolvla-as-it-downloads && \
	  pixi run python run.py --first $(FILM_TABLE) --tables 1 --runs 1 --film 1
	cp 05-smolvla-as-it-downloads/videos/table-$(FILM_TABLE).mp4 \
	   $(FILMS)/05-smolvla-as-it-downloads.mp4
	cd 06-smolvla-fine-tuned && \
	  pixi run python run.py --first $(FILM_TABLE) --tables 1 --runs 1 --film 1
	cp 06-smolvla-fine-tuned/videos/table-$(FILM_TABLE).mp4 $(FILMS)/06-smolvla-fine-tuned.mp4
	@echo "six films in $(FILMS)"
