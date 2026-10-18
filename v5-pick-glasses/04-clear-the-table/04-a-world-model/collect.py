"""Push glasses about on training tables, and write down what the camera saw happen.

    pixi run python collect.py                   # round 1: pushes drawn at random
    pixi run python collect.py --planned         # round 2: the search's own pushes

**Collecting costs arm time here, and that is the difference from problem 3.**
There, one call handed over the whole table for nothing, so fifteen thousand
pushes cost nothing but laptop minutes. Here the arm has to drive round the
table and look before it knows where anything is, and it has to look again to
find out what its push did. So a push costs seconds of simulated arm motion,
the same seconds a run is marked on, and the collection is counted in hundreds
of tables rather than thousands. ``--save`` writes down what it cost.

**Every push is made by the real loop, through the real cell.** The collector
is a ``Solution`` and ``open_run.clear_table`` runs it, so a collected push is
one the cell would really have carried out: it went through the tipping
interlock, it was charged for, and the look after it reached only as far as the
camera does. A collector that drove the bench directly would fill the model
with pushes the runner would never let it make.

The one thing that is not read from the camera is whether a glass went over. A
topple ends the table, so the runner's own ending says that one happened; the
camera cannot be trusted with it, because the glass that went over may have
gone over outside the picture, and a push wrongly labelled safe is the single
mistake this whole solution rests on.

**There are two rounds, as there are in problem 3.** The first pushes at
random, which is the only way to see what a push does when nobody is choosing
them for their outcome. The second lets the search choose, using the model
trained on the first round: the search asks about thousands of pushes and finds
the few the model is wrong about in its own favour, and making exactly those
and writing down what really happened is what closes those holes.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path

import encoding
import numpy as np
import search
from borrowed import DATA, nudge

import tables
from contract import GLASS_OVER, Answer, Done, Look
from open_run import OpenCell, clear_table
from partners import Bench, Seen
from wrist import WRIST_VIEW_SIZE, in_picture

import plan

# Arm seconds a collecting table is given. Far more than it can spend, because
# what stops a collecting table is running out of pushes worth making rather
# than running out of clock; the arm seconds are added up afterwards and
# reported rather than rationed.
ROOM_TO_WORK = 100_000.0

# How many pushes to make on one table before moving on. The table's own state
# after one push is the start of the next, so a table's build and its first
# sweep are paid once for several examples -- which is the only reason
# collecting is affordable at all. A glass going over ends the table early.
PUSHES_PER_TABLE = 6

# Where the training tables, the tuning tables and the validation tables sit.
# All below TEST_SEEDS, and all clear of the twenty the README reports.
TRAIN_SEEDS = 1000
# More of round 1, on tables past the band round 1 itself used. A second batch
# of pushes drawn the same way is the plainest kind of "more data" there is, and
# it is the one to measure before any cleverer choice of push: it cannot shift
# the mixture the model is fitted on, because it is drawn from the same one.
MORE_SEEDS = 2200
PLANNED_SEEDS = 4000
DOUBTED_SEEDS = 5000
VALIDATION_SEEDS = 9000

# How often a random push goes to a glass that has no room, and how often it
# heads roughly away from that glass's nearest neighbour, which is the kind of
# push the search will ask about most. The rest are uniform, so the model also
# sees pushes into things.
CROWDED_SHARE = 0.7
AWAY_SHARE = 0.5
AWAY_SPREAD = math.radians(50)

# Round 2: how often the search's choice is swapped for a random push, so that
# the model keeps seeing pushes the search would not make.
EXPLORE = 0.25

# Round 3: how many candidate pushes to draw on one table before asking the
# copies which of them they disagree about most. Forty is enough that the most
# doubted of them is well clear of the middle of the draw, and small enough that
# asking about all of them costs less than making one push.
CANDIDATES = 40


@dataclass
class Example:
    """One push, waiting to be told what it did."""

    inputs: np.ndarray
    before: list[Seen]  # the table as it was believed when the push was answered
    target: Seen
    heading: float
    outputs: np.ndarray | None = None
    mask: np.ndarray | None = None


class Blind:
    """A camera that renders nothing, for a run where nobody looks at the picture.

    Which glasses a look catches is decided by ``wrist.in_picture``, which is
    geometry and costs nothing; the rendered picture beside it is for solutions
    that work from pixels. This one does not, so collecting renders no frames
    and runs about a third faster -- and the glasses it sees, the physics it
    pushes and the arm seconds it is charged are identical. Checked:
    ``test_world_model.py`` runs one table both ways and compares.
    """

    def view(self, jaw) -> np.ndarray:
        return np.zeros(WRIST_VIEW_SIZE, dtype=np.uint8)


def blind_cell(seed: int) -> OpenCell:
    """The cell for one collecting table: the draw, the physics, and no renderer."""
    return OpenCell(Bench(seed, glasses=tables.table(seed)), Blind(), in_picture)


class Collector(nudge.OneFixedNudge):
    """The geometry reference's loop with its chooser replaced by a dice roll.

    Everything about seeing is the reference's and is left alone: the sweep
    round the ring at the start, the belief merged across looks, the free frames
    taken from where the jaw stands to beat the measurement error down, and the
    rule that a glass which has just been pushed is forgotten before it is
    measured again. That machinery is exactly what makes a label trustworthy,
    so a collector that wrote its own would be collecting labels of its own.

    What is taken out is the ranging push and the test push. Those are the
    reference's way of finding out, with the arm, how far away a glass is and
    whether it slides -- and they are what this solution is trying to replace
    with a model, so a training set made with them would not contain the thing
    the model has to learn.
    """

    name = "collecting"

    def __init__(self, rng: random.Random, allowed: int = PUSHES_PER_TABLE) -> None:
        super().__init__()
        self.rng = rng
        # Not ``self.pushes``: the reference keeps its own running count of
        # pushes answered under that name, and a collector that overwrote it
        # with a limit would be comparing a counter against a counter. It did,
        # and the tables that did not topple ran for hundreds of pushes.
        self.allowed = allowed
        self.examples: list[Example] = []

    def begin(self, seed: int) -> None:
        super().begin(seed)
        self.made = 0
        self.examples = []

    def _decide(self, look: Look) -> Answer:
        """A push drawn at random, or the end of the table."""
        glasses = [glass for glass in self.table.glasses() if glass.standing]
        if self.made >= self.allowed or len(glasses) < 2:
            return Done("collected what this table had to give")
        drawn = self._draw(glasses)
        if drawn is None:
            return Done("nowhere on the map to push anything on this table")
        target, heading, offset, travel, reach = drawn
        return self._answer_with(look, target, heading, offset, travel, reach)

    def _draw(self, glasses: list[Seen]) -> tuple | None:
        """One push at random, or None when every try of it was off the map."""
        for _try in range(20):
            crowded = [glass for glass in glasses if not plan.room(glass, glasses, nudge.ROOM_MARGIN)]
            pool = crowded if crowded and self.rng.random() < CROWDED_SHARE else glasses
            target = self.rng.choice(pool)
            others = encoding.others_of(glasses, target)
            if others and self.rng.random() < AWAY_SHARE:
                near = others[0]
                heading = math.atan2(target.y - near.y, target.x - near.x) + self.rng.gauss(0.0, AWAY_SPREAD)
            else:
                heading = self.rng.uniform(-math.pi, math.pi)
            low, high = search.bounds(target)
            offset = self.rng.uniform(low[1], high[1])
            travel = self.rng.uniform(low[2], high[2])
            # The whole range, so that the model sees pushes that reach the
            # glass and pushes that stop short of it. That range is the only
            # thing in the training set that can teach it where contact is.
            reach = self.rng.uniform(low[3], high[3])
            if self._on_the_map(target, heading, offset, travel, reach):
                return target, heading, offset, travel, reach
        return None

    def _on_the_map(self, target: Seen, heading, offset, travel, reach) -> bool:
        """Whether the arm could hold the jaw at both ends of this push.

        The map is checked and only the map, because a push off the table or
        out of the arm's reach is one the bench refuses outright, and a refusal
        teaches the model nothing: the arm never moved.
        """
        draws = np.array([[heading, offset, travel, reach]])
        along, left = encoding.frame(draws[:, 0])
        middle = np.array([target.x, target.y])
        start = middle - (target.widest / 2 + plan.APPROACH_GAP) * along + offset * left
        end = start + (reach + travel) * along
        return bool(search.in_reach(start).all() and search.in_reach(end).all())

    def _answer_with(self, look: Look, target: Seen, heading, offset, travel, reach) -> Answer:
        """Answer with this push, and keep the table as it was so the push can be read later."""
        glasses = [glass for glass in self.table.glasses() if glass.standing]
        along = np.array([math.cos(heading), math.sin(heading)])
        aim = tuple(np.array([target.x, target.y]) + travel * along)
        push = encoding.push_of(target, heading, offset, travel, aim)
        self.examples.append(
            Example(
                inputs=encoding.encode(glasses, target, heading, offset, travel, reach)[0],
                before=glasses,
                target=target,
                heading=float(heading),
            )
        )
        self.made += 1
        # The reference's ``_make`` reads the reach for a glass out of here, so
        # this is how a chosen reach is handed to it.
        self.reach_for[push.glass] = reach
        return self._make(look, push, nudge.PUSHING)

    def _read_the_push(self, look: Look) -> Answer | None:
        """The reference's reading of the last push, and then the label it produced."""
        made = self.pushed
        waiting = super()._read_the_push(look)
        if waiting is not None:
            return waiting
        example = self.examples[-1] if self.examples else None
        if example is not None and made is not None and example.outputs is None:
            # Only the glasses the camera found again carry a label. ``after``
            # is the belief as it stands now, which for the pushed glass was
            # forgotten before the push and so holds nothing older than it.
            after = {glass.id: glass for glass in self.table.glasses()}
            example.outputs, example.mask = encoding.outcome(
                example.before, after, example.target, example.heading, toppled=False
            )
        return None


def table(
    seed: int, model=None, explore: float = EXPLORE, doubting: bool = False
) -> tuple[list[Example], float, int]:
    """Every push made on one table: the examples, the arm seconds, and the glasses toppled.

    With a ``model``, the search chooses most of the pushes, which is round 2;
    with ``doubting`` as well, the copies' own disagreement chooses them, which
    is round 3.
    """
    rng = random.Random(f"collect:{seed}")
    if model is None:
        collector: Collector = Collector(rng)
    elif doubting:
        collector = Doubted(rng, model, explore)
    else:
        collector = Planner(rng, model, explore)
    result = clear_table(collector, seed, ROOM_TO_WORK, cell=blind_cell(seed))
    examples = [example for example in collector.examples if example.outputs is not None]
    if result.ended_by == GLASS_OVER and collector.examples and collector.examples[-1].outputs is None:
        # The push that ended the table is the one that put a glass over. It
        # was never looked at, so it has no movement to learn from, but the one
        # label that matters is known for certain.
        last = collector.examples[-1]
        last.outputs = np.zeros(encoding.OUTPUTS, dtype=np.float32)
        last.mask = np.zeros(encoding.OUTPUTS, dtype=np.float32)
        last.outputs[encoding.TOPPLED] = 1.0
        last.mask[encoding.TOPPLED] = 1.0
        examples.append(last)
    return examples, result.arm_seconds, result.toppled


class Planner(Collector):
    """Round 2: the search chooses the push, with a share still drawn at random."""

    name = "collecting, planned"

    def __init__(self, rng: random.Random, model, explore: float = EXPLORE) -> None:
        super().__init__(rng)
        self.model = model
        self.explore = explore
        self.generator = np.random.default_rng(rng.randrange(1 << 30))

    def _decide(self, look: Look) -> Answer:
        glasses = [glass for glass in self.table.glasses() if glass.standing]
        if self.made >= self.allowed or len(glasses) < 2:
            return Done("collected what this table had to give")
        if self.rng.random() >= self.explore:
            choices = [
                verdict.choice
                for verdict in (
                    search.best_push(self.model, glasses, glass, self.generator) for glass in glasses
                )
                if verdict.choice is not None
            ]
            if choices:
                best = min(choices, key=lambda choice: choice.cost)
                target = next(glass for glass in glasses if glass.id == best.target)
                return self._answer_with(
                    look, target, best.heading, best.offset, best.travel, best.reach
                )
        return super()._decide(look)


class Doubted(Collector):
    """Round 3: of many candidate pushes, the one the copies disagree about most.

    **Why this round exists.** The search was made pessimistic, because a search
    that maximises over an uncertain prediction lands where the model is most
    wrongly optimistic, and that cured almost all of this solution's broken
    glasses. Pessimism has a price, and the price is opportunities: a push the
    three copies disagree about is now a push the search turns down, whether or
    not it was a good one. The way to get those pushes back is not to make the
    search braver, because that is the change that broke the glasses. It is to
    make the copies agree, and copies only agree where they have seen something.
    So this round goes looking for the pushes they disagree about and writes down
    what really happens.

    **How it differs from round 2.** Round 2 lets the search choose, so it finds
    the pushes the model *likes* most, which are the ones it is optimistically
    wrong about. This round ignores what the copies expect to happen and looks
    only at how far apart they are, so it finds the pushes the model knows
    nothing about -- which is a different set, and the one pessimism is paid for.
    """

    name = "collecting, doubted"

    def __init__(
        self, rng: random.Random, model, explore: float = EXPLORE, candidates: int = CANDIDATES
    ) -> None:
        super().__init__(rng)
        self.model = model
        self.explore = explore
        self.candidates = candidates

    def _decide(self, look: Look) -> Answer:
        glasses = [glass for glass in self.table.glasses() if glass.standing]
        if self.made >= self.allowed or len(glasses) < 2:
            return Done("collected what this table had to give")
        if self.rng.random() >= self.explore:
            drawn = [self._draw(glasses) for _ in range(self.candidates)]
            drawn = [one for one in drawn if one is not None]
            if drawn:
                return self._answer_with(look, *most_doubted(self.model, glasses, drawn))
        # A share is still drawn at random and taken as it comes, for round 2's
        # reason: a set made only of what the model doubts is a set the model's
        # own weaknesses chose, and the ordinary pushes have to stay in it.
        return super()._decide(look)


def disagreement(model, glasses: list[Seen], drawn: list[tuple]) -> np.ndarray:
    """How far apart the copies are about each of these candidate pushes.

    One call to the copies for each candidate, because the candidates are at
    different glasses and the encoding is written for a stack of pushes at one
    glass. ``search.disagreement`` is the arithmetic, so that the round that
    collects these pushes and the solution that tests a glass before making one
    cannot disagree about what a doubt is.
    """
    return np.concatenate([search.disagreement(model, glasses, *one) for one in drawn])


def most_doubted(model, glasses: list[Seen], drawn: list[tuple]) -> tuple:
    """The one of these pushes the copies disagree about most."""
    return drawn[int(np.argmax(disagreement(model, glasses, drawn)))]


def collect(seeds: list[int], save: Path, model=None, doubting: bool = False) -> dict:
    """Walk the tables, gather the pushes, and say what the arm spent doing it."""
    started = time.perf_counter()
    rows, arm, toppled = [], 0.0, 0
    for seed in seeds:
        examples, seconds, over = table(seed, model, doubting=doubting)
        rows += examples
        arm += seconds
        toppled += over
    inputs = np.stack([row.inputs for row in rows])
    outputs = np.stack([row.outputs for row in rows])
    mask = np.stack([row.mask for row in rows])
    save.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(save, inputs=inputs, outputs=outputs, mask=mask)
    cost = {
        "tables": len(seeds),
        "pushes": len(rows),
        "toppled": toppled,
        "arm_seconds": round(arm, 1),
        "arm_minutes": round(arm / 60.0, 1),
        "laptop_seconds": round(time.perf_counter() - started, 1),
        "share_that_toppled": round(float(outputs[:, encoding.TOPPLED].mean()), 3),
        "labels_measured": round(float(mask.mean()), 3),
    }
    print(
        f"{cost['tables']} tables, {cost['pushes']} pushes in {cost['laptop_seconds']:.0f}s of laptop "
        f"time and {cost['arm_minutes']} arm minutes: {100 * cost['share_that_toppled']:.0f}% toppled "
        f"something -> {save.name}"
    )
    return cost


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=400)
    parser.add_argument("--validation", type=int, default=80)
    parser.add_argument("--planned", action="store_true", help="round 2: the search chooses the pushes")
    parser.add_argument(
        "--doubted", action="store_true", help="round 3: the pushes the copies disagree about"
    )
    parser.add_argument(
        "--more", action="store_true", help="another batch of round 1's random pushes, on later tables"
    )
    parser.add_argument("--save", type=str, default="", help="write what collecting cost to this file")
    arguments = parser.parse_args()

    if arguments.more:
        seeds = range(MORE_SEEDS, MORE_SEEDS + arguments.tables)
        if seeds[-1] >= PLANNED_SEEDS:
            raise SystemExit(f"this would reach round 2's tables, which start at {PLANNED_SEEDS}")
        cost = {"round_1_more": collect(list(seeds), DATA / "train_more.npz")}
    elif arguments.doubted:
        import push_model
        from borrowed import WEIGHTS

        seeds = range(DOUBTED_SEEDS, DOUBTED_SEEDS + arguments.tables)
        if seeds[-1] >= VALIDATION_SEEDS:
            raise SystemExit(f"round 3 would reach the validation tables, which start at {VALIDATION_SEEDS}")
        model = push_model.Ensemble.load(WEIGHTS)
        # Deliberately not ``train_doubted.npz``: ``train.py`` reads every
        # ``train*.npz`` in the folder, and this round was measured and not
        # kept, so a name outside that glob is what stops it from being fitted
        # on by accident. ``train.py --doubted`` is how to fit on it again.
        cost = {"doubted": collect(list(seeds), DATA / "doubted.npz", model, doubting=True)}
    elif arguments.planned:
        import push_model
        from borrowed import WEIGHTS

        seeds = range(PLANNED_SEEDS, PLANNED_SEEDS + arguments.tables)
        if seeds[-1] >= VALIDATION_SEEDS:
            raise SystemExit(f"round 2 would reach the validation tables, which start at {VALIDATION_SEEDS}")
        model = push_model.Ensemble.load(WEIGHTS)
        cost = {"planned": collect(list(seeds), DATA / "train_planned.npz", model)}
    else:
        if TRAIN_SEEDS + arguments.tables > PLANNED_SEEDS:
            raise SystemExit(f"round 1 would reach round 2's tables, which start at {PLANNED_SEEDS}")
        cost = {
            "round_1": collect(list(range(TRAIN_SEEDS, TRAIN_SEEDS + arguments.tables)), DATA / "train.npz"),
            "validation": collect(
                list(range(VALIDATION_SEEDS, VALIDATION_SEEDS + arguments.validation)),
                DATA / "validation.npz",
            ),
        }
    if arguments.save:
        where = Path(arguments.save)
        held = json.loads(where.read_text()) if where.exists() else {}
        held.update(cost)
        where.write_text(json.dumps(held, indent=2) + "\n")
        print(f"what it cost is in {where}")


if __name__ == "__main__":
    main()
