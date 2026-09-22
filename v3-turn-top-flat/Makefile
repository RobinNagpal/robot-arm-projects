# turn-top-flat — one entry point for everything.
#
# Run `make` on its own to see what is available.

SHELL := /bin/bash
.DEFAULT_GOAL := help

SEED    ?= 1
GUI     ?= true
RVIZ    ?= false
DENSITY ?=
LEG_DENSITY ?=
SIZE    ?= 1

# Run a command inside the pixi environment with the workspace overlay sourced.
ros = pixi run bash -c 'source install/setup.bash && $(1)'

# The room's settings, as launch arguments. A launch argument cannot be
# empty, so a density is only passed on when one is given.
room = seed:=$(SEED) size:=$(SIZE) gui:=$(GUI) rviz:=$(RVIZ) $(if $(DENSITY),top_density:=$(DENSITY)) \
	$(if $(LEG_DENSITY),leg_density:=$(LEG_DENSITY))

# Start the cell and run the task, turning the top flat the way $(1) says.
turn = $(call ros,ros2 launch turn_top_flat run.launch.py turn:=$(1) $(room))

.PHONY: help setup build wrist whole-arm tilt cell test lint clean doctor

help: ## Show this help
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} \
		/^##@/ { printf "\n  \033[1m%s\033[0m\n", substr($$0, 5) } \
		/^[a-zA-Z_.-]+:.*?##/ { printf "    \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@echo "  Settings: SEED=$(SEED) SIZE=$(SIZE) GUI=$(GUI) RVIZ=$(RVIZ) DENSITY=$(if $(DENSITY),$(DENSITY),400) LEG_DENSITY=$(if $(LEG_DENSITY),$(LEG_DENSITY),500)"
	@echo "  For example: make wrist SEED=7"
	@echo "               make whole-arm DENSITY=1500   (a heavier top, in kg/m^3)"
	@echo "               make tilt DENSITY=3000"
	@echo "               make tilt LEG_DENSITY=200     (lighter legs, in kg/m^3)"
	@echo "               make tilt SIZE=2              (top and legs twice as big)"
	@echo ""

##@ Turning the top flat

wrist: build ## Lift the top out and turn it flat with wrist 1 alone
	$(call turn,wrist)

whole-arm: build ## Lift the top out and turn it flat with the whole arm, about its gripped edge
	$(call turn,whole_arm)

tilt: build ## Lift the top out, rest it on the far legs, and tilt it down onto all four
	$(call turn,tilt)

cell: build ## Start the cell but leave the arm alone, for poking at by hand
	$(call ros,ros2 launch turn_top_flat run.launch.py task:=false $(room))

##@ Project

setup: ## Install the environment (the first run downloads a few gigabytes)
	pixi install

build: setup ## Build the workspace
	@pixi run colcon build --symlink-install

test: build ## Run the tests
	$(call ros,pytest src/turn_top_flat/test -q)

lint: setup ## Check code style
	pixi run ruff check src/
	pixi run ruff format --check src/

clean: ## Remove build/, install/ and log/
	pixi run clean

doctor: ## Print versions of everything that matters
	@printf "%-14s %s\n" "pixi" "$$(pixi --version 2>&1)"
	@pixi run bash -c 'printf "%-14s %s\n" "python" "$$(python --version 2>&1)"; \
		printf "%-14s %s\n" "ROS distro" "$$ROS_DISTRO"; \
		printf "%-14s %s\n" "Gazebo" "$$(gz sim --versions 2>&1 | head -1)"'
