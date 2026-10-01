# Problem 2 with borrowed weights. Its own environment; no ROS, no Gazebo.

.DEFAULT_GOAL := help
TEST_SCENES ?= 20
SOLUTIONS := sam maskrcnn amodal

.PHONY: help install setup train test test-crowded train-all test-all check solution

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-13s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: ## Install the environment, without fetching any weights
	pixi install

setup: install ## Install the environment and fetch the borrowed weights (once; the long step)
	pixi run python weights.py

# Both train and test need SOLUTION, and a mistyped name should stop here
# rather than after several minutes of loading a model.
solution:
	@if [ -z "$(SOLUTION)" ]; then \
		echo "SOLUTION is missing. Say which solution to work on, one of: $(SOLUTIONS)"; \
		echo "  e.g. make train SOLUTION=sam, then make test SOLUTION=sam"; \
		exit 2; \
	fi
	@case " $(SOLUTIONS) " in \
		*" $(SOLUTION) "*) ;; \
		*) echo "SOLUTION=$(SOLUTION) is not a solution here. Use one of: $(SOLUTIONS)"; exit 2 ;; \
	esac

# SCENES is left unset on purpose: each solution has its own default, because
# running SAM over a picture costs far more than one training step.
train: solution install ## Fit what SOLUTION fits (slow); SCENES=n to use more scenes
	pixi run python train.py --solution $(SOLUTION) $(if $(SCENES),--scenes $(SCENES),)

test: solution install ## Run SOLUTION on TEST_SCENES held-out spawned scenes and score it
	pixi run python run.py --solution $(SOLUTION) --scenes $(TEST_SCENES)

test-crowded: solution install ## The same on crowded layouts, where one glass really hides another
	pixi run python run.py --solution $(SOLUTION) --scenes $(TEST_SCENES) --crowded

train-all: ## Train all three, one after the other (very slow)
	@for s in $(SOLUTIONS); do $(MAKE) train SOLUTION=$$s || exit 1; done

test-all: ## Test all three, one after the other
	@for s in $(SOLUTIONS); do $(MAKE) test SOLUTION=$$s || exit 1; done

check: install ## The quick checks, which need no weights
	pixi run pytest -q . ../problem-2-sim
