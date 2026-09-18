# classification-shapes — one entry point for everything.
#
# Run `make` on its own to see what is available.

SHELL := /bin/bash
.DEFAULT_GOAL := help

TRAIN  ?= 6000
VAL    ?= 1000
TEST   ?= 1000
UNSEEN ?= 1000
SEED   ?= 1
DATA   ?= data/shapes
PICTURES ?= 250
EPOCHS ?= 100
BATCH  ?= 8
NAME   ?= shapes
WEIGHTS ?= runs/$(NAME)/weights/best.pt
COM_DATA  ?= data/center-of-mass
COM_TRAIN ?= 250
COM_VAL   ?= 50
COM_TEST  ?= 100
COM_NAME  ?= com
COM_MODEL ?= yolo26s-pose.pt
COM_EPOCHS ?= 150
COM_WEIGHTS ?= runs/$(COM_NAME)/weights/best.pt

# -u so progress and any error show as they happen, not when the run ends.
py = pixi run python -u -m

.PHONY: help setup data split preview stats train resume evaluate clean-runs com-data com-preview com-stats \
	com-train com-resume com-evaluate com-predict \
	test lint clean-data doctor

help: ## Show this help
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} \
		/^##@/ { printf "\n  \033[1m%s\033[0m\n", substr($$0, 5) } \
		/^[a-zA-Z_.-]+:.*?##/ { printf "    \033[36m%-11s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@echo "  Settings: TRAIN=$(TRAIN) VAL=$(VAL) TEST=$(TEST) UNSEEN=$(UNSEEN) SEED=$(SEED) DATA=$(DATA)"
	@echo "  Training: PICTURES=$(PICTURES) EPOCHS=$(EPOCHS) BATCH=$(BATCH) NAME=$(NAME) WEIGHTS=$(WEIGHTS)"
	@echo "  Center of mass: COM_TRAIN=$(COM_TRAIN) COM_VAL=$(COM_VAL) COM_TEST=$(COM_TEST) COM_DATA=$(COM_DATA)"
	@echo "                  COM_MODEL=$(COM_MODEL) COM_EPOCHS=$(COM_EPOCHS) COM_NAME=$(COM_NAME) COM_WEIGHTS=$(COM_WEIGHTS)"
	@echo "  For example: make data TRAIN=500 VAL=100 TEST=100 UNSEEN=100"
	@echo ""

##@ Dataset

data: setup ## Render every split: train, val, test and test-unseen
	$(py) synthetic.generate --split train       --count $(TRAIN)  --seed $(SEED) --out $(DATA)
	$(py) synthetic.generate --split val         --count $(VAL)    --seed $(SEED) --out $(DATA)
	$(py) synthetic.generate --split test        --count $(TEST)   --seed $(SEED) --out $(DATA)
	$(py) synthetic.generate --split test-unseen --count $(UNSEEN) --seed $(SEED) --out $(DATA)
	$(py) synthetic.stats --data $(DATA)

split: setup ## Render one split: make split SPLIT=val COUNT=200
	$(py) synthetic.generate --split $(SPLIT) --count $(COUNT) --seed $(SEED) --out $(DATA)

preview: ## Draw the labels onto some pictures of each split, into figures/
	$(py) synthetic.preview --data $(DATA) --split train       --count 12 --columns 4 --output figures/train-samples.jpg
	$(py) synthetic.preview --data $(DATA) --split test-unseen --count 8  --columns 4 --output figures/unseen-samples.jpg

stats: ## Count the labelled blocks of each class in each split
	$(py) synthetic.stats --data $(DATA)

##@ Model

train: setup ## Train YOLO26s-seg into runs/NAME/, on PICTURES random train pictures (PICTURES=all for every one)
	$(py) training.train --data $(DATA) $(if $(filter all,$(PICTURES)),,--pictures $(PICTURES)) \
		--epochs $(EPOCHS) --batch $(BATCH) --name $(NAME)

resume: setup ## Carry on a stopped training run
	$(py) training.train --resume runs/$(NAME)/weights/last.pt

evaluate: setup ## Score WEIGHTS on test and test-unseen, side by side
	$(py) training.evaluate --weights $(WEIGHTS) --data $(DATA) --batch $(BATCH)

clean-runs: ## Delete every training run and its model
	rm -rf runs

##@ Center of mass

com-data: setup ## Render the centre-of-mass dataset: irregular shapes, camera straight down
	$(py) center_of_mass.generate --split train --count $(COM_TRAIN) --seed $(SEED) --out $(COM_DATA)
	$(py) center_of_mass.generate --split val   --count $(COM_VAL)   --seed $(SEED) --out $(COM_DATA)
	$(py) center_of_mass.generate --split test  --count $(COM_TEST)  --seed $(SEED) --out $(COM_DATA)
	$(py) center_of_mass.stats --data $(COM_DATA)

com-preview: ## Draw boxes and centre-of-mass points onto some train pictures, into figures/
	$(py) center_of_mass.preview --data $(COM_DATA) --split train --count 12 --columns 4 \
		--output figures/center-of-mass-samples.jpg

com-stats: ## Count blocks per class, and check the points against the masks
	$(py) center_of_mass.stats --data $(COM_DATA)

com-train: setup ## Train the centre-of-mass pose model into runs/COM_NAME/
	$(py) center_of_mass.train --data $(COM_DATA) --model $(COM_MODEL) --epochs $(COM_EPOCHS) \
		--batch $(BATCH) --name $(COM_NAME)

com-resume: setup ## Carry on a stopped centre-of-mass training run
	$(py) center_of_mass.train --resume runs/$(COM_NAME)/weights/last.pt

com-evaluate: setup ## Score COM_WEIGHTS on test: centre-of-mass error in pixels and mm, pictures drawn
	$(py) center_of_mass.evaluate --weights $(COM_WEIGHTS) --data $(COM_DATA)

com-predict: setup ## Draw COM_WEIGHTS' centres of mass on any pictures: make com-predict SOURCE=folder
	$(py) center_of_mass.predict --weights $(COM_WEIGHTS) --source $(SOURCE)

##@ Project

setup: ## Install the environment
	@pixi install

test: setup ## Run the tests (no simulator needed)
	pixi run pytest -q

lint: setup ## Check code style
	pixi run ruff check synthetic training center_of_mass tests
	pixi run ruff format --check synthetic training center_of_mass tests

clean-data: ## Delete every rendered picture and label
	rm -rf $(DATA)

doctor: ## Print versions of everything that matters
	@printf "%-10s %s\n" "pixi" "$$(pixi --version 2>&1)"
	@pixi run bash -c 'printf "%-10s %s\n" "python" "$$(python --version 2>&1)"; \
		printf "%-10s %s\n" "Gazebo" "$$(gz sim --versions 2>&1 | head -1)"; \
		printf "%-10s %s\n" "OpenCV" "$$(python -c "import cv2; print(cv2.__version__)")"'
