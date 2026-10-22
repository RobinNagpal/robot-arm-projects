# learn-pick-place — one entry point for everything.
#
# Run `make` on its own to see what is available.

SHELL := /bin/bash
.DEFAULT_GOAL := help

EPISODES ?= 200
DATA     ?= data/pick-place
NAME     ?= act
STEPS    ?= 20000
BATCH    ?= 64
CHUNK    ?= 20
ACTION_STEPS ?= 10
LR       ?= 1e-4
EVAL_EPISODES ?= 50
VIDEOS   ?= 3
# The best checkpoint of the current run (run 3); the last one scored lower.
# See docs/results.md.
POLICY   ?= outputs/$(NAME)/checkpoints/015000/pretrained_model
SEEDS    ?= 0 1 2
RUN      ?= 1
DRIVER   ?= policy
GUI      ?= 1

# MuJoCo Menagerie, pinned: the UR5e arm and the Robotiq 2F-85 gripper.
MENAGERIE_URL    := https://github.com/google-deepmind/mujoco_menagerie
MENAGERIE_COMMIT := 8161bba264d7fa7c99ca301e91e7fb44737676ad
MENAGERIE_DIR    := assets/menagerie

# -u so progress and any error show as they happen, not when the run ends.
py = pixi run python -u -m

.PHONY: help setup assets view record train resume evaluate gazebo gazebo-all test lint clean-data clean-runs doctor

help: ## Show this help
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} \
		/^##@/ { printf "\n  \033[1m%s\033[0m\n", substr($$0, 5) } \
		/^[a-zA-Z_.-]+:.*?##/ { printf "    \033[36m%-11s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@echo "  Settings: EPISODES=$(EPISODES) DATA=$(DATA) NAME=$(NAME) STEPS=$(STEPS) BATCH=$(BATCH)"
	@echo "            CHUNK=$(CHUNK) ACTION_STEPS=$(ACTION_STEPS) LR=$(LR) EVAL_EPISODES=$(EVAL_EPISODES)"
	@echo "            POLICY=$(POLICY)"
	@echo "  Gazebo:   RUN=$(RUN) (1 to 10) DRIVER=$(DRIVER) (policy or expert) GUI=$(GUI) (1 window, 0 none)"
	@echo "  For example: make record EPISODES=500"
	@echo ""

##@ Demonstrations

view: setup ## Film the scripted expert and draw what the camera found, into figures/expert/
	$(py) pick_place.view --seeds $(SEEDS) --out figures/expert

record: setup ## Record EPISODES good expert demonstrations as a LeRobot dataset in DATA
	$(py) pick_place.record --episodes $(EPISODES) --out $(DATA)

##@ Policy

train: setup ## Train ACT on DATA into outputs/NAME/
	rm -rf outputs/$(NAME)
	pixi run lerobot-train \
		--dataset.repo_id=local/pick-place --dataset.root=$(DATA) \
		--policy.type=act --policy.device=$$(pixi run python -c "import torch; print('mps' if torch.backends.mps.is_available() else 'cuda' if torch.cuda.is_available() else 'cpu')" 2>/dev/null) \
		--policy.push_to_hub=false \
		--policy.chunk_size=$(CHUNK) --policy.n_action_steps=$(ACTION_STEPS) --policy.optimizer_lr=$(LR) \
		--output_dir=outputs/$(NAME) --job_name=$(NAME) \
		--steps=$(STEPS) --batch_size=$(BATCH) --log_freq=500 --save_freq=5000 \
		--wandb.enable=false --num_workers=2

resume: setup ## Carry on a stopped training run
	pixi run lerobot-train --config_path=outputs/$(NAME)/checkpoints/last/pretrained_model/train_config.json --resume=true

evaluate: setup ## Run POLICY on EVAL_EPISODES unseen episodes next to the expert; film the first VIDEOS
	$(py) pick_place.evaluate --policy $(POLICY) --episodes $(EVAL_EPISODES) --videos $(VIDEOS) \
		--video-dir figures/evaluate/$(NAME)

##@ Gazebo

gazebo: setup ## Run POLICY in Gazebo on one of 10 fixed runs, in Gazebo's window: make gazebo RUN=3
	$(py) pick_place.gazebo.run --run $(RUN) --driver $(DRIVER) --policy $(POLICY) $(if $(filter 1,$(GUI)),--gui,)

gazebo-all: setup ## Run POLICY on all 10 Gazebo runs, no window, and print a table of outcomes
	$(py) pick_place.gazebo.run --run all --driver $(DRIVER) --policy $(POLICY)

##@ Project

setup: assets ## Install the environment and download the robot models
	@pixi install

assets: $(MENAGERIE_DIR)/.done ## Download the arm and gripper models, pinned

$(MENAGERIE_DIR)/.done:
	rm -rf $(MENAGERIE_DIR)
	git clone --quiet --filter=blob:none --no-checkout $(MENAGERIE_URL) $(MENAGERIE_DIR)
	cd $(MENAGERIE_DIR) && git sparse-checkout set universal_robots_ur5e robotiq_2f85 \
		&& git checkout --quiet $(MENAGERIE_COMMIT)
	touch $@

test: setup ## Run the tests
	pixi run pytest -q

lint: setup ## Check code style
	pixi run ruff check pick_place tests
	pixi run ruff format --check pick_place tests

clean-data: ## Delete the recorded demonstrations and the Gazebo worlds
	rm -rf $(DATA) data/gazebo

clean-runs: ## Delete every training run and its model
	rm -rf outputs

doctor: ## Print versions of everything that matters
	@printf "%-10s %s\n" "pixi" "$$(pixi --version 2>&1)"
	@pixi run python -c "import sys, mujoco, torch, lerobot; \
		print(f'{\"python\":<10} {sys.version.split()[0]}'); \
		print(f'{\"MuJoCo\":<10} {mujoco.__version__}'); \
		print(f'{\"PyTorch\":<10} {torch.__version__}, Apple GPU: {torch.backends.mps.is_available()}'); \
		print(f'{\"LeRobot\":<10} {lerobot.__version__}')" 2>/dev/null
