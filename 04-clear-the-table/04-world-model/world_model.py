"""Solution 4: learn what a push does, then search for a good one.

Imitation copies pushes. This solution learns something different: a stand-in for
the cell. Given a table and a push -- which glass, which way, how far, and the six
settings handed to MoveIt -- the model says whether MoveIt could plan it, whether a
glass would go over, where the pushed glass would end up, how much it would knock
the others about, and how long the arm would take. Then it chooses a push the way a
person would with a model of the cell: imagine many pushes, score what each would
leave, and make the best.

**Why this suits the two learned jobs.** Where a glass should go (job 1) and what
to tell MoveIt so that it does not tip (job 2) are one search here. The settings
are part of the push the search varies, and the model has learned from the cell
that a fast, high stroke tips glasses, so the search finds slow, low ones on its own.

**Five models, not one.** A single model is wrong in places and the search is
good at finding the places where it is wrong in its own favour: it picks the push
the model is most optimistic about, which is often the push it has seen least.
Five networks started from different weights agree where they have data and
disagree where they do not, and the search is penalised by how much they disagree.
"""

from __future__ import annotations

import math
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from examiner.motion.push_motions import GlassBox
from shared.learning import table_and_push_encoding
from shared.learning.learned_networks import WorldModelNetwork
from shared.turn_by_turn_loop import LOOK_ONLY_AS_NEEDED, RefusedGlasses, TableFinished, TurnByTurnSolution

WEIGHTS_FOLDER = Path(__file__).resolve().parent / "weights"
ENSEMBLE_SIZE = 5
MOVE_UNIT_METRES, TIME_UNIT_SECONDS = 0.05, 10.0  # scales that keep every target near one


def training_tensors(records: list[dict]):
    table_rows, table_masks, pushed_glasses, pushes, targets, feasible = [], [], [], [], [], []
    for record in records:
        rows_of_table, mask_of_table = table_and_push_encoding.encode_table(
            table_and_push_encoding.boxes_from_layout(record["before"])
        )
        outcome = table_and_push_encoding.push_outcome_from_record(record)
        pushed_glass = record["request"]["glass"]
        table_rows.append(rows_of_table)
        table_masks.append(mask_of_table)
        pushed_glasses.append(pushed_glass)
        pushes.append(
            table_and_push_encoding.encode_push(table_and_push_encoding.push_request_from_record(record))
        )
        # feasible, topple, along, across, disturbance, seconds, gain, room eased, success
        targets.append(
            [
                float(outcome["feasible"]),
                float(outcome["topple"]),
                outcome["moved"] / MOVE_UNIT_METRES,
                _sideways_drift(record) / MOVE_UNIT_METRES,
                outcome["disturbed"] / MOVE_UNIT_METRES,
                outcome["seconds"] / TIME_UNIT_SECONDS,
                float(np.clip(outcome["gain"], -2, 2)),
                float(np.clip(outcome["eased"], -40, 40)) / 20.0,
                float(outcome["feasible"] and not outcome["topple"] and outcome["gain"] >= 1),
            ]
        )
        feasible.append(outcome["feasible"])

    def as_tensor(values, dtype=torch.float32):
        return torch.tensor(np.stack(values) if isinstance(values[0], np.ndarray) else values, dtype=dtype)

    return (
        as_tensor(table_rows),
        as_tensor(table_masks, torch.bool),
        as_tensor(pushed_glasses, torch.long),
        as_tensor(pushes),
        as_tensor(targets),
        as_tensor(feasible, torch.bool),
    )


def _sideways_drift(record: dict) -> float:
    """Sideways drift of the pushed glass: positive to the left of the push."""
    if not record["feasible"]:
        return 0.0
    glass, request = record["request"]["glass"], record["request"]
    along_push = (math.cos(request["heading"]), math.sin(request["heading"]))
    moved = (
        record["after"][glass]["x"] - record["before"][glass]["x"],
        record["after"][glass]["y"] - record["before"][glass]["y"],
    )
    return -moved[0] * along_push[1] + moved[1] * along_push[0]


def world_model_loss(
    network: WorldModelNetwork, table_rows, table_masks, pushed_glasses, pushes, targets, feasible
):
    outputs = network(table_rows, table_masks, pushed_glasses, pushes)
    feasible_loss = nn.functional.binary_cross_entropy_with_logits(outputs[:, 0], targets[:, 0])
    # Whether a push works is learned from every push, because most are failures
    # and a model shown only the successes could not tell a good push from a bad one.
    success_loss = nn.functional.binary_cross_entropy_with_logits(outputs[:, 8], targets[:, 8])
    if feasible.any():
        topple_loss = nn.functional.binary_cross_entropy_with_logits(
            outputs[feasible, 1], targets[feasible, 1]
        )
        regression_loss = nn.functional.smooth_l1_loss(outputs[feasible][:, 2:8], targets[feasible][:, 2:8])
    else:
        topple_loss = regression_loss = outputs.sum() * 0
    total_loss = feasible_loss + topple_loss + regression_loss + success_loss
    return total_loss, (float(feasible_loss), float(topple_loss), float(regression_loss), float(success_loss))


def train_world_models(
    records: list[dict],
    epochs: int = 150,
    seed: int = 0,
    log=lambda *loss_parts: print(*loss_parts, flush=True),
) -> list[WorldModelNetwork]:
    tensors = training_tensors(records)
    record_count = len(records)
    training_count = int(0.9 * record_count)
    order = np.random.default_rng(seed).permutation(record_count)
    training_rows, held_out_rows = order[:training_count], order[training_count:]
    networks = []
    for model_index in range(ENSEMBLE_SIZE):
        torch.manual_seed(seed * 100 + model_index)
        network = WorldModelNetwork()
        optimiser = torch.optim.AdamW(network.parameters(), 1e-3, weight_decay=1e-4)
        rng = np.random.default_rng(seed * 100 + model_index)
        started = time.perf_counter()
        for _ in range(epochs):
            # Each model sees a different bootstrap of the data, so they differ where data is thin.
            bootstrap = rng.choice(training_rows, len(training_rows))
            for batch_start in range(0, len(bootstrap), 128):
                batch_rows = bootstrap[batch_start : batch_start + 128]
                batch_tensors = [tensor[batch_rows] for tensor in tensors]
                loss, _ = world_model_loss(network, *batch_tensors)
                optimiser.zero_grad()
                loss.backward()
                optimiser.step()
        network.eval()
        with torch.no_grad():
            held_out_loss, loss_parts = world_model_loss(
                network, *[tensor[held_out_rows] for tensor in tensors]
            )
        if log:
            log(
                f"  model {model_index + 1}/{ENSEMBLE_SIZE}: held-out loss {float(held_out_loss):.3f} "
                f"(feasible {loss_parts[0]:.3f}, "
                f"topple {loss_parts[1]:.3f}, move {loss_parts[2]:.3f}, works {loss_parts[3]:.3f}), "
                f"{time.perf_counter() - started:.0f} s"
            )
        networks.append(network)
    return networks


class WorldModelSolution(TurnByTurnSolution):
    name = "world model (imagines pushes, makes the best)"
    looking_mode = LOOK_ONLY_AS_NEEDED  # it reads the boxes, so one picture that shows every glass is enough

    # What a topple costs, how far the five models' disagreement is distrusted, and what a
    # second of arm time costs, all in units of "probability that the push works". Below
    # LEAST_WORTHWHILE_SCORE the table is left as it is. A push MoveIt refuses costs the arm nothing, so
    # a push that is only possible one time in five is still worth asking for if it would
    # be worth making. Set by looking at the pushes the models liked on tables below the
    # held-out line, and nowhere else.
    TOPPLE_COST, DISAGREEMENT_COST, ARM_SECOND_COST = 1.0, 0.5, 0.002
    LEAST_WORTHWHILE_SCORE = 0.1
    # How many pushes the search imagines: first drawn the way round two drew its informed
    # pushes, then the best few shaken a little, twice.
    PUSHES_IMAGINED, BEST_PUSHES_KEPT, NUDGES_PER_KEPT_PUSH, REFINEMENT_ROUNDS = 320, 24, 10, 2

    def __init__(self, weights: Path | None = None, seed: int = 0) -> None:
        saved_networks = torch.load(weights or WEIGHTS_FOLDER / "world-models-v3.pt", weights_only=True)
        self.world_model_networks = []
        for saved in saved_networks:
            network = WorldModelNetwork()
            network.load_state_dict(saved)
            self.world_model_networks.append(network.eval())
        self.seed = seed
        self.rng = random.Random(seed)

    def start_new_table(self) -> None:
        # The search draws its pushes at random. It is given the same draw at the start of
        # every table, so that a table gets the same answers every time it is run.
        self.rng = random.Random(self.seed)
        self.refused_glasses = RefusedGlasses()
        self.last_requested_glass = None

    @torch.no_grad()
    def predict_outcomes(self, boxes: list[GlassBox], pushed_glasses: np.ndarray, pushes: np.ndarray):
        rows, mask = table_and_push_encoding.encode_table(boxes)
        push_count = len(pushed_glasses)
        rows_repeated = torch.tensor(rows)[None].expand(push_count, -1, -1)
        mask_repeated = torch.tensor(mask)[None].expand(push_count, -1)
        outputs = torch.stack(
            [
                network(
                    rows_repeated,
                    mask_repeated,
                    torch.tensor(pushed_glasses),
                    torch.tensor(pushes, dtype=torch.float32),
                )
                for network in self.world_model_networks
            ]
        )
        return outputs

    def score_pushes(self, boxes: list[GlassBox], pushed_glasses: np.ndarray, pushes: np.ndarray):
        """How good each imagined push is, and the probabilities it was built from.

        A push is worth the chance that it works -- MoveIt plans it, no glass goes over and
        a glass is given room -- less the chance that it plans and tips a glass, less a
        charge for how far the five models disagree about it, less a charge for arm time.
        """
        outputs = self.predict_outcomes(boxes, pushed_glasses, pushes)
        works_chance = torch.sigmoid(outputs[:, :, 8])
        feasible_chance = torch.sigmoid(outputs[:, :, 0]).mean(0).numpy()
        topple_chance = torch.sigmoid(outputs[:, :, 1]).mean(0).numpy()
        arm_seconds = outputs.mean(0)[:, 5].numpy() * TIME_UNIT_SECONDS
        scores = (
            works_chance.mean(0).numpy()
            - self.TOPPLE_COST * feasible_chance * topple_chance
            - self.DISAGREEMENT_COST * works_chance.std(0).numpy()
            - self.ARM_SECOND_COST * feasible_chance * arm_seconds
        )
        return scores, feasible_chance, topple_chance

    def candidate_pushes(self, boxes: list[GlassBox], glasses_allowed: list[int]) -> list:
        """Pushes worth imagining: each would, if it went as asked, leave its glass with room.

        These are drawn by ``collect_training_pushes.push_that_would_free_a_glass``, which uses
        problem 3's own two tests -- the hand fits between the glasses, and the glass ends with room. Nothing
        here says whether the arm can make the push, or whether the glass would tip: the
        models are asked that. If the geometry finds nothing, nothing is imagined.
        """
        from shared.learning import collect_training_pushes

        imagined = []
        for _ in range(self.PUSHES_IMAGINED * 3):
            request = collect_training_pushes.push_that_would_free_a_glass(self.rng, boxes, tries=40)
            if request is not None and request.glass in glasses_allowed:
                imagined.append(request)
            if len(imagined) >= self.PUSHES_IMAGINED:
                break
        return imagined

    def nudged_push(self, request, boxes: list[GlassBox]):
        """The same push, a little different: the direction, the distance and every setting nudged."""
        numbers = table_and_push_encoding.encode_push(request).copy()
        angle = math.atan2(numbers[1], numbers[0]) + self.rng.gauss(0.0, 0.12)
        numbers[0], numbers[1] = math.cos(angle), math.sin(angle)
        numbers[2:] = np.clip(
            numbers[2:] + np.array([self.rng.gauss(0.0, 0.1) for _ in numbers[2:]]), 0.0, 1.0
        )
        return table_and_push_encoding.decode_push(request.glass, numbers)

    def search_for_best_push(self, boxes: list[GlassBox], glasses_allowed: list[int]):
        """Imagine a pool of pushes, keep the best few, shake them, and repeat.

        Returns (score, glass, push numbers) of the best push imagined, or a score of minus
        infinity when the geometry offers nothing to imagine.
        """
        imagined = self.candidate_pushes(boxes, glasses_allowed)
        best_so_far = (-math.inf, 0, np.zeros(table_and_push_encoding.NUMBERS_PER_PUSH, dtype=np.float32))
        for _ in range(self.REFINEMENT_ROUNDS + 1):
            if not imagined:
                break
            pushed_glasses = np.array([rows_repeated.glass for rows_repeated in imagined])
            pushes = np.stack(
                [table_and_push_encoding.encode_push(rows_repeated) for rows_repeated in imagined]
            )
            scores, _, _ = self.score_pushes(boxes, pushed_glasses, pushes)
            best_first = np.argsort(-scores)
            if scores[best_first[0]] > best_so_far[0]:
                best_so_far = (
                    float(scores[best_first[0]]),
                    int(pushed_glasses[best_first[0]]),
                    pushes[best_first[0]].copy(),
                )
            kept = [imagined[i] for i in best_first[: self.BEST_PUSHES_KEPT]]
            imagined = []
            for request in kept:
                for _ in range(self.NUDGES_PER_KEPT_PUSH):
                    nudged = self.nudged_push(request, boxes)
                    if table_and_push_encoding.hand_fits_along_push(
                        boxes, nudged.glass, nudged.heading, nudged.travel
                    ):
                        imagined.append(nudged)
        return best_so_far

    def decide_turn(self, observation):
        boxes = list(observation.boxes)
        if not boxes:
            return TableFinished("no glass in view")
        if observation.last_push_refusal_reason and self.last_requested_glass is not None:
            self.refused_glasses.remember(boxes, self.last_requested_glass)
        if table_and_push_encoding.count_pickable_boxes(boxes) == len(boxes):
            return TableFinished("every glass has room")
        refused_indices = self.refused_glasses.indices_in_look(boxes)
        glasses_allowed = [
            k
            for k in range(len(boxes))
            if k not in refused_indices and k < table_and_push_encoding.GLASS_SLOTS
        ]
        if not glasses_allowed:
            return TableFinished("nothing left that can be pushed")
        best_so_far = self.search_for_best_push(boxes, glasses_allowed)
        if best_so_far[0] <= self.LEAST_WORTHWHILE_SCORE:
            return TableFinished("no push the model expects to work")
        self.last_requested_glass = best_so_far[1]
        return table_and_push_encoding.decode_push(best_so_far[1], best_so_far[2])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("records", nargs="+")
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--tag", default="world-models-v3")
    arguments = parser.parse_args()
    records = table_and_push_encoding.load_push_records(*arguments.records)
    print(f"{len(records)} pushes")
    networks = train_world_models(records, arguments.epochs)
    WEIGHTS_FOLDER.mkdir(exist_ok=True)
    torch.save([network.state_dict() for network in networks], WEIGHTS_FOLDER / f"{arguments.tag}.pt")
