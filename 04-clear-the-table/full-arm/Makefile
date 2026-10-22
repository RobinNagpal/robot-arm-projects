# The whole-arm cell: MoveIt plans, a learned model says what to ask for.
#
# Everything runs from problem 4's environment (`pixi run`), which starts MoveIt
# itself in the ROS environment kept in ros/. `make ros` makes that environment
# once; nothing here needs it to be activated by hand.

.DEFAULT_GOAL := help
FIRST ?= 10000
TABLES ?= 20
RUNS ?= 1

.PHONY: help ros test lint runs box-data box-net collect imitation world-model reinforcement vla-data vla evaluate-geometry evaluate-imitation evaluate-world-model evaluate-reinforcement evaluate-vla

help: ## This list
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

ros: ## Make the ROS environment MoveIt runs in (once; a few gigabytes)
	cd ros && pixi install

test: ## The checks that need neither MoveIt nor the physics engine
	cd .. && pixi run pytest -q full-arm

lint: ## Ruff
	cd .. && pixi run ruff check full-arm

# ---------------------------------------------------------------- job 0: the boxes

box-data: ## Photograph 400 tables, twice each, from both viewing places, and write the answer keys
	cd .. && pixi run python full-arm/build_box_data.py 0 400 full-arm/data/box-train.pkl
	cd .. && pixi run python full-arm/build_box_data.py 600 100 full-arm/data/box-test.pkl

box-net: ## Train the box model and measure it on pictures it has not seen
	cd .. && pixi run python full-arm/train_box_net.py full-arm/data/box-train.pkl full-arm/data/box-test.pkl 30

# ------------------------------------------------------- jobs 1 and 2: what to ask

collect: ## Push at random with the arm: 640 tables, nine workers
	cd .. && pixi run python full-arm/collect_pushes.py --first 1000 --tables 640 --out full-arm/data/pushes-round1.jsonl --workers 9

imitation: ## Solution 3: copy the pushes that worked
	cd .. && pixi run python full-arm/imitation.py full-arm/data/pushes-round1.jsonl

world-model: ## Solution 4: learn what a push does, five models
	cd .. && pixi run python full-arm/world_model.py full-arm/data/pushes-round1.jsonl --epochs 16

reinforcement: ## Solution 5: learn by trying, a few thousand pushes
	cd .. && pixi run python full-arm/reinforcement.py train --iterations 25 --workers 8 --steps 20

vla-data: ## The pictures and answers SmolVLA is fitted on
	cd .. && pixi run python full-arm/build_vla_data.py full-arm/data/pushes-round1.jsonl full-arm/data/vla-round1.pkl

vla: ## Solution 6: fit a small correction to SmolVLA
	cd .. && pixi run python full-arm/vla.py --data full-arm/data/vla-round1.pkl --steps 300 --tag vla-round1

# ----------------------------------------------------------------------- scoring

RECORDED := solution_1-2_geometry solution_3_imitation solution_3_imitation_with_check \
	solution_4_world_model solution_5_reinforcement solution_5_reinforcement_with_check \
	solution_6_smolvla solution_6_smolvla_with_check ceiling

runs: ## Every solution on 25 held-out tables, kept table by table in runs/
	cd .. && pixi run python full-arm/record_runs.py arrangements
	cd .. && for s in $(RECORDED); do pixi run python full-arm/record_runs.py solve $$s > full-arm/logs/runs-$$s.log 2>&1 & done; wait
	cd .. && pixi run python full-arm/record_runs.py summary

evaluate-geometry: ## The reference, on the held-out tables
	cd .. && pixi run python full-arm/evaluate.py geometry --first $(FIRST) --tables $(TABLES) --runs $(RUNS)

evaluate-imitation: ## Solution 3
	cd .. && pixi run python full-arm/evaluate.py imitation --first $(FIRST) --tables $(TABLES) --runs $(RUNS)

evaluate-world-model: ## Solution 4
	cd .. && pixi run python full-arm/evaluate.py world-model --first $(FIRST) --tables $(TABLES) --runs $(RUNS)

evaluate-reinforcement: ## Solution 5
	cd .. && pixi run python full-arm/evaluate.py reinforcement --first $(FIRST) --tables $(TABLES) --runs $(RUNS)

evaluate-vla: ## Solution 6
	cd .. && pixi run python full-arm/evaluate.py vla --weights full-arm/weights/vla-round1 --first $(FIRST) --tables $(TABLES) --runs $(RUNS)
