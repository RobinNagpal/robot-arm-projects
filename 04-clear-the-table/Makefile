# Problem 4: the UR5e clears a table. MoveIt plans every motion, and a
# solution decides what to ask it for.
#
# Everything runs from problem 4's environment (`pixi run`), which starts MoveIt
# itself in the ROS environment kept in examiner/ros/. `make ros` makes that
# environment once; nothing here needs it to be activated by hand.

.DEFAULT_GOAL := help
FIRST ?= 10000
TABLES ?= 20
RUNS ?= 1

.PHONY: help install ros test lint runs box-data box-net collect imitation world-model reinforcement vla-data vla evaluate-geometry evaluate-geometry-ranked evaluate-imitation evaluate-world-model evaluate-reinforcement evaluate-vla

help: ## This list
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: ## Resolve the environment
	pixi install

ros: ## Make the ROS environment MoveIt runs in (once; a few gigabytes)
	cd examiner/ros && pixi install

test: ## The checks that need neither MoveIt nor the physics engine
	pixi run pytest -q tests

lint: ## Ruff over everything
	pixi run ruff check .

# ---------------------------------------------------------------- job 0: the boxes

box-data: ## Photograph 400 tables, twice each, from both viewing places, and write the answer keys
	pixi run python shared/seeing/build_box_data.py 0 400 shared/seeing/data/box-train.pkl
	pixi run python shared/seeing/build_box_data.py 600 100 shared/seeing/data/box-test.pkl

box-net: ## Train the box model and measure it on pictures it has not seen
	pixi run python shared/seeing/train_box_net.py shared/seeing/data/box-train.pkl shared/seeing/data/box-test.pkl 30

# ------------------------------------------------------- jobs 1 and 2: what to ask

# The solutions learn from four rounds of pushes, kept in shared/learning/data/. Round 1 is
# made again by `make collect`; rounds 2 to 4 were drawn partly from a trained
# world model, as docs/what-the-pushes-show.md says. Each target below writes
# the weights the results are measured with, under the same name.
PUSHES := shared/learning/data/pushes-round1.jsonl shared/learning/data/pushes-round2.jsonl shared/learning/data/pushes-round3.jsonl shared/learning/data/pushes-round4.jsonl

collect: ## Push at random with the arm: 640 tables, nine workers (round 1)
	pixi run python shared/learning/collect_pushes.py --first 1000 --tables 640 --out shared/learning/data/pushes-round1.jsonl --workers 9

imitation: ## Solution 3: copy the pushes that worked
	pixi run python 03-imitation/imitation.py $(PUSHES)

world-model: ## Solution 4: learn what a push does, five models
	pixi run python 04-world-model/world_model.py $(PUSHES) --epochs 16

reinforcement: ## Solution 5: learn by trying, a few thousand pushes
	pixi run python 05-reinforcement-learning/reinforcement.py train --iterations 25 --workers 8 --steps 20

vla-data: ## The pictures and answers SmolVLA is fitted on
	pixi run python 06-smolvla-fine-tuned/build_vla_data.py $(PUSHES) 06-smolvla-fine-tuned/data/vla-r4.pkl

vla: ## Solution 6: fit a small correction to SmolVLA
	pixi run python 06-smolvla-fine-tuned/vla.py --data 06-smolvla-fine-tuned/data/vla-r4.pkl --steps 600

# ----------------------------------------------------------------------- scoring

RECORDED := solution_1_geometry solution_2_geometry_ranked solution_3_imitation solution_3_imitation_with_check \
	solution_4_world_model solution_5_reinforcement solution_5_reinforcement_with_check \
	solution_6_smolvla solution_6_smolvla_with_check ceiling

runs: ## Every solution on 25 held-out tables, kept table by table in runs/
	pixi run python examiner/tools/record_runs.py arrangements
	for s in $(RECORDED); do pixi run python examiner/tools/record_runs.py solve $$s > examiner/logs/runs-$$s.log 2>&1 & done; wait
	pixi run python examiner/tools/record_runs.py summary

evaluate-geometry: ## Solution 1, the reference, on the held-out tables
	pixi run python examiner/tools/evaluate.py geometry --first $(FIRST) --tables $(TABLES) --runs $(RUNS)

evaluate-geometry-ranked: ## Solution 2
	pixi run python examiner/tools/evaluate.py geometry-ranked --first $(FIRST) --tables $(TABLES) --runs $(RUNS)

evaluate-imitation: ## Solution 3
	pixi run python examiner/tools/evaluate.py imitation --first $(FIRST) --tables $(TABLES) --runs $(RUNS)

evaluate-world-model: ## Solution 4
	pixi run python examiner/tools/evaluate.py world-model --first $(FIRST) --tables $(TABLES) --runs $(RUNS)

evaluate-reinforcement: ## Solution 5
	pixi run python examiner/tools/evaluate.py reinforcement --first $(FIRST) --tables $(TABLES) --runs $(RUNS)

evaluate-vla: ## Solution 6
	pixi run python examiner/tools/evaluate.py vla --first $(FIRST) --tables $(TABLES) --runs $(RUNS)
