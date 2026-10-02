# The learned version of problem 4. Its own environment; no ROS, no Gazebo.

.DEFAULT_GOAL := help
TABLES ?= 200
COUNT ?= 20

.PHONY: help setup train collect train-push run trace explain show test

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ { printf "  \033[36m%-11s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## Install the environment
	pixi install

train: setup ## Draw TABLES tables and train TopNet, Ranker, SideNet and GripNet (about 3 minutes)
	pixi run python train.py --tables $(TABLES)

collect: setup ## Push glasses about on 9000 mixed tables in MuJoCo (about 10 minutes)
	pixi run python collect.py

train-push: setup ## Train the five copies of the push model on the collected pushes (a few minutes)
	pixi run python train_push.py

run: setup ## Clear the 50 held-out tables and score them; writes results.json
	pixi run python run.py

trace: setup ## Clear the first 3 held-out tables, writing every step to saved/runs/, then draw them
	pixi run python run.py --tables 3 --trace --show
	pixi run python show.py run

explain: setup ## Four held-out tables explained step by step, into saved/workflow-explained/
	pixi run python explain.py

show: setup ## Save pictures and JSON of what every model is taught and answers, into saved/
	pixi run python show.py top train --count $(COUNT)
	pixi run python show.py top test --count $(COUNT)
	pixi run python show.py ranker train --count $(COUNT)
	pixi run python show.py ranker test --count $(COUNT)
	pixi run python show.py side train --count $(COUNT)
	pixi run python show.py side test --count $(COUNT)
	pixi run python show.py grip train --count $(COUNT)
	pixi run python show.py grip test --count $(COUNT)
	pixi run python show.py push train --count $(COUNT)
	pixi run python show.py push test --count $(COUNT)

test: setup ## The quick checks
	pixi run pytest -q test_learned.py
