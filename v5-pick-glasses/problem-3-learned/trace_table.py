"""Clear one table, and write down everything the arm saw, asked and did.

For reading, not for scoring. It runs the same plan.clear as run.py on the
same table, so the pushes are the ones in results.json, and beside each it
writes what went into the model, what came out, and what then really happened.

    pixi run python trace_table.py                 # table 10000, the first held-out one
    pixi run python trace_table.py --table 10003

Writes traces/table-<seed>/trace.json, video.mp4 and a picture for each step,
named by the step's number. A push gets three: what the model expects, the jaw
at the end of the push, and what the next look found. Lengths in the file are
millimetres and angles are degrees, except the ``row`` lists, which are the
numbers exactly as the model takes them and gives them.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np
import torch
from bench import GLASS_ZONE, GRIP_ROOM, KINDS, TEST_SEEDS, Felt, Push, Seen, has_room
from film import FPS, TAKE_MOVES, FilmedBench
from work_cell.arm.dimensions import COMFORTABLE_REACH
from work_cell.table.layout import ROBOT_BASE

import features
import picture
import plan
from model import Ensemble, sigmoid
from scoring import Scorecard
from train import WEIGHTS

TRACES = Path(__file__).parent / "traces"

INPUT_NAMES = (
    [f"kind is {kind}" for kind in KINDS]
    + [
        "pushed glass: height",
        "pushed glass: widest",
        "pushed glass: foot",
        "push: offset across",
        "push: travel",
    ]
    + [
        f"other {slot + 1}: {what}"
        for slot in range(features.OTHERS)
        for what in ("along", "across", "widest", "height", "there")
    ]
)
OUTPUT_NAMES = (
    ["pushed glass moves: along", "pushed glass moves: across"]
    + [f"other {slot + 1} moves: {way}" for slot in range(features.OTHERS) for way in ("along", "across")]
    + ["something topples (logit)", "jaw blocked on the way down (logit)"]
)


def mm(value) -> float | list:
    """Metres to millimetres, to a tenth."""
    return np.round(1000 * np.asarray(value, dtype=float), 1).tolist()


def rounded(row) -> list:
    """A row of the model's own numbers, to four places."""
    return np.round(np.asarray(row, dtype=float), 4).tolist()


def compact(text: str) -> str:
    """Put each list of numbers on one line, so a row reads as a row."""
    return re.sub(
        r"\[[-\d.,e\s]+\]",
        lambda found: " ".join(found.group().split()).replace("[ ", "[").replace(" ]", "]"),
        text,
    )


def _glass(s: Seen, seen: list[Seen]) -> dict:
    others = [(o.x, o.y, o.widest) for o in seen if o.id != s.id]
    return {
        "id": s.id,
        "x": mm(s.x),
        "y": mm(s.y),
        "height": mm(s.height),
        "widest": mm(s.widest),
        "foot": mm(s.foot),
        "standing": s.standing,
        "has_room": has_room(s.x, s.y, others, margin=plan.TAKE_MARGIN),
    }


def _crowding(seen: list[Seen]) -> float:
    if not seen:
        return 0.0
    return mm(plan.shortfall(np.array([[s.x, s.y] for s in seen]), np.array([s.widest for s in seen])))


def _moves(row: np.ndarray, slots: list[Seen]) -> list[dict]:
    """The movement part of an output row, one entry per glass, in the push's frame."""
    return [
        {
            "glass": glass.id,
            "along": mm(row[2 * slot] * features.MOVE_SCALE),
            "across": mm(row[2 * slot + 1] * features.MOVE_SCALE),
        }
        for slot, glass in enumerate(slots)
    ]


class TracedBench(FilmedBench):
    """A filmed bench that also writes each look, take and push into ``trace``."""

    def __init__(self, seed: int, model: Ensemble, kind: str, folder: Path) -> None:
        self.trace: list[dict] = []
        self.ensemble, self.kind, self.folder = model, kind, folder
        self.seen: list[Seen] = []
        # The last look's readings, less the glasses taken since.
        self.readings: list[dict] = []
        self.pushing: np.ndarray | None = None
        self.asked: dict[int, plan.Verdict] = {}
        self.planning: dict | None = None
        self.waiting: tuple[dict, Seen, Push, Felt] | None = None
        super().__init__(seed, "learned")

    def _add(self, step: dict) -> dict:
        step = {"number": len(self.trace) + 1, **step, "video_seconds": round(len(self.frames) / FPS, 2)}
        self.trace.append(step)
        return step

    def _view(self) -> np.ndarray:
        """The table as the film sees it now, with nothing written on it."""
        self.renderer.update_scene(self.data, self.camera)
        return self.renderer.render()[:, :, ::-1].copy()

    def _picture(
        self, step: dict, name: str, scene: np.ndarray, drawing: np.ndarray, title: str, lines: list
    ) -> None:
        file = f"step-{step['number']:02d}-{name}.png"
        cv2.imwrite(
            str(self.folder / file), picture.picture(scene, drawing, f"Step {step['number']}: {title}", lines)
        )
        step.setdefault("pictures", []).append(file)

    def look(self) -> list[Seen]:
        seen = super().look()
        if self.waiting is not None:
            self._happened(seen)
        self.seen, self.asked, self.planning = seen, {}, None
        step = self._add(
            {"step": "look", "glasses": [_glass(s, seen) for s in seen], "room_missing": _crowding(seen)}
        )
        self.readings = step["glasses"]
        roomy = sum(g["has_room"] for g in self.readings)
        if not seen:
            lines = ["The table is empty."]
        elif roomy:
            lines = [
                f"The camera reads {len(seen)} glasses: {roomy} with room for the gripper, "
                f"{len(seen) - roomy} crowded.",
                "The ones with room are taken first. The model is not used for that.",
            ]
        else:
            lines = [
                f"The camera reads {len(seen)} glasses, and none has room for the gripper.",
                f"Room missing on the whole table: {step['room_missing']} mm. A push has to be found.",
            ]
        self._picture(step, "look", self._view(), picture.above(self.readings, rings=True), "look", lines)
        return seen

    def take(self, glass: int) -> None:
        step = self._add({"step": "take", "glass": glass})
        drawing = picture.above(self.readings, taking=glass)
        first = len(self.frames)
        super().take(glass)
        # The film's own frame from while the glass is being lifted.
        lifted = self.frames[first + round(0.6 * sum(TAKE_MOVES.values()) * FPS)]
        lines = [
            f"Glass {glass} has room, so the arm picks it up and racks it.",
            "The model is not used for this.",
        ]
        self._picture(step, "take", lifted, drawing, f"take glass {glass}", lines)
        self.readings = [g for g in self.readings if g["id"] != glass]

    def _back_off(self, at: np.ndarray, u: np.ndarray) -> None:
        self.pushing = self._view()
        super()._back_off(at, u)

    def search_picture(self, chosen: int | None) -> None:
        """Every glass has been searched: draw the best push found for each."""
        step = self.planning
        if step is None or "pictures" in step:
            return
        reading = {g["id"]: g for g in self.readings}
        found = [row for row in step["per_glass"] if row["best"] is not None]
        asked = sum(row["pushes_asked_about"] for row in step["per_glass"])
        lines = [f"No glass has room. The search asked the model what {asked} different pushes would do."]
        for row in step["per_glass"]:
            best = row["best"]
            lines.append(
                f"  glass {row['glass']}: no push. {row['no_push_because']}"
                if best is None
                else f"  glass {row['glass']}: best push costs {best['cost']} "
                f"(heading {best['heading']} deg, {best['travel']} mm)"
            )
        lines.append(
            f"The table is missing {step['room_missing_now']} mm of room. No push is expected to win back "
            f"{mm(plan.WORTH_IT)} mm of it, so the glasses left are refused."
            if chosen is None
            else f"Cost is the room still missing afterwards. Lowest wins: push glass {chosen}."
        )
        drawing = picture.above(
            self.readings,
            rings=True,
            pushes=[
                (reading[row["glass"]], row["best"]["lands_at"], row["glass"] == chosen) for row in found
            ],
        )
        self._picture(step, "search", self._view(), drawing, "search", lines)

    def verdict(self, target: Seen, verdict: plan.Verdict, tried: dict) -> None:
        """One glass's search is over: what it tried, and the best it found."""
        if self.planning is None:
            self.planning = self._add(
                {"step": "search", "room_missing_now": _crowding(self.seen), "per_glass": []}
            )
        self.asked[target.id] = verdict
        choice = verdict.choice
        self.planning["per_glass"].append(
            {
                "glass": target.id,
                "pushes_asked_about": tried["asked"],
                "dropped_might_topple": tried["topple"],
                "dropped_off_the_map": tried["map"],
                "dropped_model_unsure": tried["unsure"],
                "best": None
                if choice is None
                else {
                    "heading": round(math.degrees(choice.heading), 1),
                    "offset": mm(choice.offset),
                    "travel": mm(choice.travel),
                    "lands_at": mm(choice.aim),
                    "cost": mm(choice.cost),
                },
                "no_push_because": verdict.reason,
            }  # fmt: skip
        )

    def push(self, push: Push):
        choice = self.asked[push.glass].choice
        target = next(s for s in self.seen if s.id == push.glass)
        slots = [target, *features.others_of(self.seen, target)]
        row = features.encode(self.seen, target, self.kind, choice.heading, choice.offset, choice.travel)
        out = self.ensemble.predict(row)[:, 0]
        mean = out.mean(0)
        step = self._add(
            {
                "step": "push",
                "push_number": len(self.records) + 1,
                "glass": push.glass,
                "push": {
                    "heading": round(math.degrees(push.heading), 1),
                    "offset": mm(choice.offset),
                    "travel": mm(push.travel),
                    "jaw_comes_down_at": mm(push.start),
                    "feels_forward_up_to": mm(push.reach),
                },
                "model_input": {
                    "row": rounded(row[0]),
                    "pushed_glass": {
                        "height": mm(target.height),
                        "widest": mm(target.widest),
                        "foot": mm(target.foot),
                    },
                    "others_in_push_frame": [
                        {
                            "glass": other.id,
                            "along": mm(row[0, base] * features.PLACE_SCALE),
                            "across": mm(row[0, base + 1] * features.PLACE_SCALE),
                            "widest": mm(other.widest),
                            "height": mm(other.height),
                        }
                        for slot, other in enumerate(slots[1:])
                        for base in [len(KINDS) + 5 + 5 * slot]
                    ],
                },
                "model_output": {
                    "rows_per_copy": rounded(out),
                    "moves": _moves(mean, slots),
                    "topple_chance_per_copy": rounded(sigmoid(out[:, features.TOPPLED])),
                    "blocked_chance": round(float(sigmoid(out[:, features.BLOCKED]).mean()), 4),
                    "pushed_glass_lands_at": mm(choice.aim),
                    "room_missing_expected_after": mm(choice.cost - plan.TRAVEL_COST * choice.travel),
                },
            }
        )
        self.search_picture(push.glass)
        said, asked = step["model_output"], step["push"]
        reading = next(g for g in self.readings if g["id"] == push.glass)
        drawing = picture.above(
            self.readings,
            pushes=[(reading, said["pushed_glass_lands_at"], True)],
            jaw=(asked["jaw_comes_down_at"], asked["heading"]),
        )
        lines = [
            f"The push: heading {asked['heading']} deg, {asked['travel']} mm, "
            f"the jaw meeting the glass {asked['offset']} mm left of its middle.",
            f"The model says: glass {push.glass} moves {said['moves'][0]['along']} mm, "
            f"topple chance {max(said['topple_chance_per_copy']):.2%}, "
            f"blocked chance {said['blocked_chance']:.2%}.",
            f"Room missing on the table: {_crowding(self.seen)} mm now, "
            f"{said['room_missing_expected_after']} mm expected after.",
        ]
        self._picture(
            step,
            "push-1-expected",
            self._view(),
            drawing,
            f"push glass {push.glass}, as the model expects",
            lines,
        )

        self.pushing = None
        felt = super().push(push)
        step["jaw_felt"] = {
            "blocked_on_the_way_down": felt.blocked,
            "touched_after": None if felt.touched is None else mm(felt.touched),
            "pushed": mm(felt.pushed),
            "jammed": felt.jammed,
            "peak_force_newtons": round(felt.peak, 2),
        }
        if self.pushing is not None:
            lines = [
                "The jaw never touched the glass."
                if felt.touched is None
                else f"The jaw touched the glass after feeling forward {mm(felt.touched)} mm, "
                f"then pushed {mm(felt.pushed)} mm{', and jammed' if felt.jammed else ''}.",
                f"Most force felt: {felt.peak:.2f} N.",
            ]
            self._picture(step, "push-2-pushing", self.pushing, drawing, "the arm makes the push", lines)
        self.waiting = (step, target, push, felt)
        return felt

    def _happened(self, after: list[Seen]) -> None:
        """The look after a push: the same row a training example is labelled with."""
        step, target, push, felt = self.waiting
        self.waiting = None
        slots = [target, *features.others_of(self.seen, target)]
        row = features.outcome(self.seen, after, target, push.heading, felt.blocked)
        landed = next(s for s in after if s.id == target.id)
        step["what_happened"] = {
            "row": rounded(row),
            "moves": _moves(row, slots),
            "toppled": bool(row[features.TOPPLED]),
            "pushed_glass_landed_at": mm([landed.x, landed.y]),
            "landing_error": mm(math.dist((landed.x, landed.y), push.aim)),
        }
        real, said = step["what_happened"], step["model_output"]
        was = next(g for g in self.readings if g["id"] == target.id)
        now = [_glass(s, after) for s in after]
        drawing = picture.above(now, pushes=[(was, said["pushed_glass_lands_at"], True)], was=was, rings=True)
        lines = [
            "The jaw was blocked on the way down, so nothing was pushed."
            if felt.blocked
            else f"Glass {target.id} moved {real['moves'][0]['along']} mm. "
            f"The model said {said['moves'][0]['along']} mm.",
            f"It stands {real['landing_error']} mm from where the model aimed it (the dashed circle). "
            f"Toppled: {'yes' if real['toppled'] else 'no'}.",
            "The readings before, the push, and the readings after are what one training example holds.",
        ]
        self._picture(step, "push-3-happened", self._view(), drawing, "what really happened", lines)


def trace(seed: int) -> Path:
    kind = KINDS[seed % len(KINDS)]
    model = Ensemble.load(WEIGHTS)
    folder = TRACES / f"table-{seed}"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("step-*.png"):
        old.unlink()
    bench = TracedBench(seed, model, kind, folder)

    # plan.py is left as it is, so the traced run is the scored run. Its two
    # search functions are wrapped only to be listened to.
    best_push, score = plan.best_push, plan.score
    tried: dict = {}

    def listening_score(model, seen, target, *arguments):
        cost, landing, dropped = score(model, seen, target, *arguments)
        tried["asked"] += len(cost)
        for reason, count in dropped.items():
            tried[reason] += count
        return cost, landing, dropped

    def listening_best_push(model, seen, target, kind, rng):
        tried.update(asked=0, topple=0, map=0, unsure=0)
        verdict = best_push(model, seen, target, kind, rng)
        bench.verdict(target, verdict, tried)
        return verdict

    plan.best_push, plan.score = listening_best_push, listening_score
    try:
        refused = plan.clear(bench, model, kind, np.random.default_rng(seed))
    finally:
        plan.best_push, plan.score = best_push, score

    bench.search_picture(None)
    outcome = Scorecard().scene(bench, refused)
    racked = sum(bench.taken.values())
    step = bench._add(
        {
            "step": "end",
            "outcome": outcome,
            "racked": racked,
            "refused": {str(k): v for k, v in refused.items()},
        }
    )
    lines = [
        f"Racked {racked} of {len(bench.glasses)} glasses in {len(bench.records)} pushes. "
        f"Refused {len(refused)}."
    ]
    lines += [f"  glass {glass}: {why}" for glass, why in refused.items()]
    bench._picture(step, "end", bench._view(), picture.above(bench.readings, rings=True), outcome, lines)

    bench.save(folder / "video.mp4", f"{outcome}: racked {racked}, refused {len(refused)}")
    document = {
        "table": seed,
        "kind": kind,
        "units": "millimetres and degrees; 'row' lists are the model's own scaled numbers",
        "map": {
            "glass_zone_x_min_x_max_y_min_y_max": mm(GLASS_ZONE),
            "arm_base": mm(ROBOT_BASE[:2]),
            "arm_reach_least_most": mm(COMFORTABLE_REACH),
            "grip_room": mm(GRIP_ROOM),
        },
        "model": {
            "copies": len(model.nets),
            "input_names": INPUT_NAMES,
            "input_scale": "places and sizes are divided by 100 mm, the push's travel by 50 mm",
            "output_names": OUTPUT_NAMES,
            "output_scale": "movements are divided by 50 mm",
        },
        "steps": bench.trace,
    }
    (folder / "trace.json").write_text(compact(json.dumps(document, indent=1)))
    return folder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=int, default=TEST_SEEDS, help="the table's seed")
    arguments = parser.parse_args()
    torch.set_num_threads(4)
    folder = trace(arguments.table)
    steps = json.loads((folder / "trace.json").read_text())["steps"]
    pictures = sum(len(step.get("pictures", [])) for step in steps)
    print(
        f"{len(steps)} steps, ending {steps[-1]['outcome']} -> {folder}/: "
        f"trace.json, video.mp4, {pictures} pictures"
    )


if __name__ == "__main__":
    main()
