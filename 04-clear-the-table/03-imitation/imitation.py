"""Solution 3: copy the pushes that worked.

The model reads the boxes the box model found and answers, in one go, with which
glass to push, which way, how far, and the six settings to hand MoveIt. It is not
told how to choose them. It is shown pushes that were made in the cell and worked,
and trained to answer the same way.

**Who the teacher is.** There is no hand-written teacher here. The pushes were
made at random, the cell scored each one, and the ones kept as demonstrations are
the ones that MoveIt could plan, that did not tip a glass, and that left the table
with more room than it had. The simulator is the expert: a demonstration is a push
it approved. This is the cheapest honest teacher, and its weakness is plain: it
can only show pushes that a random draw happened to find.

**What "finished" is taught from.** A table with every glass already pickable is
shown with the answer "finished", because the same network has to know when to
stop, and a network that only ever saw pushes would never say so.

Training is a plain supervised loss: a cross entropy on which glass (or
finished), and a squared error on the push, taken only at the glass that was
chosen. The glasses are shuffled every time they are used, so the network cannot
learn that "slot 0" means anything.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import torch
from geometry_reference import SAFE_SETTINGS  # noqa: F401
from torch import nn

from shared.learning import table_and_push_encoding
from shared.learning.learned_networks import PushPolicyNetwork
from shared.turn_by_turn_loop import LOOK_ONLY_AS_NEEDED, RefusedGlasses, TableFinished, TurnByTurnSolution

WEIGHTS_FOLDER = Path(__file__).resolve().parent / "weights"


def demonstrations_from_pushes(records: list[dict], least_gain_mm: float = 4.0) -> tuple[list, int]:
    """(rows, mask, glass, action) for every push worth copying, and how many finished-tables there were."""
    demonstrations, finished_tables = [], 0
    for record in records:
        before = table_and_push_encoding.boxes_from_layout(record["before"])
        rows, mask = table_and_push_encoding.encode_table(before)
        if all(glass["pickable"] for glass in record["before"]):
            demonstrations.append(
                (
                    rows,
                    mask,
                    table_and_push_encoding.GLASS_SLOTS,
                    np.zeros(table_and_push_encoding.NUMBERS_PER_PUSH, np.float32),
                )
            )  # the table is finished
            finished_tables += 1
            continue
        outcome = table_and_push_encoding.push_outcome_from_record(record)
        if not outcome["feasible"] or outcome["topple"]:
            continue
        # Worth copying: it freed a glass, or took real room off the table
        # without disturbing anything else much.
        if outcome["gain"] >= 1 or (
            outcome["eased"] >= least_gain_mm and outcome["disturbed"] < 0.01 and outcome["moved"] > 0.01
        ):
            demonstrations.append(
                (
                    rows,
                    mask,
                    record["request"]["glass"],
                    table_and_push_encoding.encode_push(
                        table_and_push_encoding.push_request_from_record(record)
                    ),
                )
            )
    return demonstrations, finished_tables


def demonstrations_from_ceiling_lessons(lessons: list[dict]) -> tuple[list, int]:
    """(rows, mask, glass, action) for every turn of the ceiling's lessons, and how many said "finished".

    A push the search made is copied unless it tipped a glass after all, which the
    search's tries can miss, because a try and the real push are not quite the same
    motion. A turn on which the search stopped is copied as "finished", and that
    includes tables that still had glasses short of room: the search tried thirty
    pushes there and none was worth making.
    """
    demonstrations, finished_lessons = [], 0
    for lesson in lessons:
        table_rows, mask = table_and_push_encoding.encode_table(
            table_and_push_encoding.boxes_from_layout(lesson["before"])
        )
        if lesson["request"] is None:
            demonstrations.append(
                (
                    table_rows,
                    mask,
                    table_and_push_encoding.GLASS_SLOTS,
                    np.zeros(table_and_push_encoding.NUMBERS_PER_PUSH, np.float32),
                )
            )
            finished_lessons += 1
        elif not lesson.get("toppled") and lesson["request"]["glass"] < table_and_push_encoding.GLASS_SLOTS:
            demonstrations.append(
                (
                    table_rows,
                    mask,
                    lesson["request"]["glass"],
                    table_and_push_encoding.encode_push(
                        table_and_push_encoding.push_request_from_record(lesson)
                    ),
                )
            )
    return demonstrations, finished_lessons


def train_push_policy_by_imitation(
    demonstrations: list, epochs: int = 300, seed: int = 0, log=lambda *parts: print(*parts, flush=True)
) -> PushPolicyNetwork:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = PushPolicyNetwork()
    optimiser = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-4)
    rows = torch.tensor(np.stack([demonstration[0] for demonstration in demonstrations]))
    mask = torch.tensor(np.stack([demonstration[1] for demonstration in demonstrations]))
    glass = torch.tensor([demonstration[2] for demonstration in demonstrations])
    action = torch.tensor(np.stack([demonstration[3] for demonstration in demonstrations]))
    count = len(demonstrations)
    started = time.perf_counter()
    for epoch in range(epochs):
        order = rng.permutation(count)
        summed_loss = 0.0
        for batch_start in range(0, count, 64):
            batch = order[batch_start : batch_start + 64]
            batch_rows, batch_mask, batch_glass, batch_action = (
                rows[batch].clone(),
                mask[batch].clone(),
                glass[batch].clone(),
                action[batch],
            )
            # Shuffle the glasses, and the answer with them.
            for row_in_batch in range(len(batch)):
                shuffle = torch.randperm(table_and_push_encoding.GLASS_SLOTS)
                unshuffle = torch.argsort(shuffle)
                batch_rows[row_in_batch], batch_mask[row_in_batch] = (
                    batch_rows[row_in_batch][shuffle],
                    batch_mask[row_in_batch][shuffle],
                )
                if batch_glass[row_in_batch] < table_and_push_encoding.GLASS_SLOTS:
                    batch_glass[row_in_batch] = unshuffle[batch_glass[row_in_batch]]
            logits, pushes, _ = net(batch_rows, batch_mask)
            choice = nn.functional.cross_entropy(logits, batch_glass)
            real = batch_glass < table_and_push_encoding.GLASS_SLOTS
            chosen = pushes[
                torch.arange(len(batch)), batch_glass.clamp(max=table_and_push_encoding.GLASS_SLOTS - 1)
            ]
            fit = ((chosen - batch_action) ** 2).mean(1)
            fit = (fit * real).sum() / real.sum().clamp(min=1)
            loss = choice + 2.0 * fit
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            summed_loss += float(loss) * len(batch)
        if log and (epoch % 50 == 49 or epoch == epochs - 1):
            log(
                f"  epoch {epoch + 1}/{epochs}: loss {summed_loss / count:.3f}, "
                f"{time.perf_counter() - started:.0f} s"
            )
    return net.eval()


class ImitationSolution(TurnByTurnSolution):
    name = "imitation (copies the pushes that worked)"
    looking_mode = LOOK_ONLY_AS_NEEDED  # it reads the boxes, so one picture that shows every glass is enough

    def __init__(self, weights: Path | None = None) -> None:
        self.policy_network = PushPolicyNetwork()
        self.policy_network.load_state_dict(
            torch.load(weights or WEIGHTS_FOLDER / "imitation-r4.pt", weights_only=True)
        )
        self.policy_network.eval()
        self.refused_glasses = RefusedGlasses()
        self.last_requested_glass: int | None = None

    def start_new_table(self) -> None:
        self.refused_glasses = RefusedGlasses()
        self.last_requested_glass = None

    @torch.no_grad()
    def decide_turn(self, observation):
        boxes = list(observation.boxes)
        if not boxes:
            return TableFinished("no glass in view")
        if observation.last_push_refusal_reason and self.last_requested_glass is not None:
            self.refused_glasses.remember(boxes, self.last_requested_glass)
        rows, mask = table_and_push_encoding.encode_table(boxes)
        scores_for_each_choice, push_for_each_glass, _ = self.policy_network(
            torch.tensor(rows)[None], torch.tensor(mask)[None]
        )
        allowed_scores = scores_for_each_choice[0].clone()
        for refused_index in self.refused_glasses.indices_in_look(boxes):
            if refused_index < table_and_push_encoding.GLASS_SLOTS:
                allowed_scores[refused_index] = -1e9
        chosen = int(allowed_scores.argmax())
        if chosen == table_and_push_encoding.GLASS_SLOTS or table_and_push_encoding.count_pickable_boxes(
            boxes
        ) == len(boxes):
            return TableFinished(
                "every glass has room"
                if table_and_push_encoding.count_pickable_boxes(boxes) == len(boxes)
                else "the model says the table is finished"
            )
        self.last_requested_glass = chosen
        return table_and_push_encoding.decode_push(chosen, push_for_each_glass[0, chosen].numpy())


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("records", nargs="*")
    parser.add_argument("--lessons", nargs="*", default=[], help="the ceiling's lessons")
    parser.add_argument("--repeat", type=int, default=1, help="how many times each lesson is shown per pass")
    parser.add_argument(
        "--stop-repeat", type=int, help="the same for lessons that say 'finished' (default: --repeat)"
    )
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--tag", default="imitation-r4")
    arguments = parser.parse_args()
    records = table_and_push_encoding.load_push_records(*arguments.records)
    demonstrations, finished = demonstrations_from_pushes(records) if records else ([], 0)
    print(f"{len(records)} pushes -> {len(demonstrations)} demonstrations ({finished} of them 'finished')")
    lessons, finished_lessons = (
        demonstrations_from_ceiling_lessons(table_and_push_encoding.load_push_records(*arguments.lessons))
        if arguments.lessons
        else ([], 0)
    )
    print(
        f"{len(lessons)} lessons from the search ({finished_lessons} of them 'finished'), "
        f"each shown {arguments.repeat} times"
    )
    # Most lessons say "finished", so shown as often as the pushes they teach the policy to stop everywhere.
    stop_repeat = arguments.repeat if arguments.stop_repeat is None else arguments.stop_repeat
    demonstrations += [
        demonstration for demonstration in lessons if demonstration[2] != table_and_push_encoding.GLASS_SLOTS
    ] * arguments.repeat + [
        demonstration for demonstration in lessons if demonstration[2] == table_and_push_encoding.GLASS_SLOTS
    ] * stop_repeat
    network = train_push_policy_by_imitation(demonstrations, arguments.epochs)
    WEIGHTS_FOLDER.mkdir(exist_ok=True)
    torch.save(network.state_dict(), WEIGHTS_FOLDER / f"{arguments.tag}.pt")
    (Path(__file__).resolve().parent / "results").mkdir(exist_ok=True)
    (Path(__file__).resolve().parent / "results" / f"{arguments.tag}-training.json").write_text(
        json.dumps(
            {
                "pushes": len(records),
                "demonstrations": len(demonstrations),
                "finished": finished,
                "lessons": len(lessons),
                "lessons_finished": finished_lessons,
                "repeat": arguments.repeat,
                "stop_repeat": stop_repeat,
                "epochs": arguments.epochs,
            },
            indent=1,
        )
    )
