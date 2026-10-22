"""Every solution on the same held-out tables, kept table by table in ``runs/``.

The scores in ``results/`` add the tables up. This keeps them apart, so that one table can
be opened and every solution's answer to it compared: where each glass stood at the start,
where it stood at the end, and which glasses had room.

``python record_runs.py arrangements``                 choose the tables, record where every glass starts
``python record_runs.py solve solution_4_world_model``  one solution on every table
``python record_runs.py summary``                       ``runs/results.json`` and ``runs/results.md``

A glass is **separated** when the gripper could pick it: it is standing, inside the glass
zone, and every neighbour is far enough away for the open fingers. That is problem 4's
``pickable``, and nothing else is meant by the word here.

**Which tables.** Held-out tables from 10,000 up, in order. A table on which every glass is
already separated asks nothing of a solution, so at most one in twenty of the chosen tables
may be one. Each table is given the whole arm-time budget on its own, so a slow solution on
one table does not take time from the next, which is how the films run and not quite how
``evaluate.py`` scores.

**Every push is kept.** A result lists each push the solution asked for, in order: which glass,
which way, how far, the six settings, and what became of it -- made, refused by MoveIt, or
rejected by the safety check. The direction is also given against the glass's nearest
neighbour, which says where the hand came down: in the gap between the two glasses, at the
side, or on the far side. The ceiling's list holds only the pushes it made, not its tries.

No glass's size is written into a record. The pictures draw each glass at its real width,
read from the simulator when the picture is made.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import random
from pathlib import Path

import arm_camera  # noqa: F401
import cell as C
import matplotlib
import oracle
from checked import Checked
from evaluate import SOLUTIONS
from examiner import ARM_BUDGET, SimExaminer, Tally
from moveit_link import MoveItLink
from solving import Done
from work_cell.rack.layout import GLASS_ZONE

from partners import STANDING_TILT_DEG, has_room, in_zone
from scoring import pickable

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
WEIGHTS = HERE / "weights"
TABLES, FIRST, ALREADY_DONE_SHARE = 25, 10_000, 0.05

# What each result file is called, which solution it runs and the weights it reads.
# ``ceiling`` is the search that tries pushes in the physics first; it is not a solution.
RECORDED = {
    "solution_1-2_geometry": ("geometry", None),
    "solution_3_imitation": ("imitation", "imitation-r4.pt"),
    "solution_3_imitation_with_check": ("imitation-checked", "imitation-r4.pt"),
    "solution_4_world_model": ("world-model", "world-models-v3.pt"),
    "solution_5_reinforcement": ("reinforcement", "reinforcement-v4.pt"),
    "solution_5_reinforcement_with_check": ("reinforcement-checked", "reinforcement-v4.pt"),
    "solution_6_smolvla": ("vla", "vla-r4"),
    "solution_6_smolvla_with_check": ("vla-checked", "vla-r4"),
    "ceiling": (None, None),
}


# ------------------------------------------------------------------ the glasses


def glasses(bench, start: list[dict] | None = None) -> list[dict]:
    """Every glass as it stands now. With ``start``, also how far each has moved since."""
    rows = []
    for i, glass in enumerate(bench.glasses):
        x, y = (float(v) for v in bench.position(i))
        # Which neighbours are too close, one at a time, so a crowded glass says who crowds it.
        crowded_by = [
            j
            for j in bench.on_table()
            if j != i
            and not has_room(
                x, y, [(*(float(v) for v in bench.position(j)), bench.glasses[j].outline.max_diameter)]
            )
        ]
        row = {
            "glass": i,
            "kind": glass.kind,
            "x_mm": round(x * 1000),
            "y_mm": round(y * 1000),
            "standing": bool(bench.tilt(i) < STANDING_TILT_DEG),
            "in_zone": bool(in_zone(x, y)),
            "crowded_by": crowded_by,
            "separated": bool(pickable(bench, i)),
        }
        if start is not None:
            row["moved_mm"] = round(
                math.hypot(row["x_mm"] - start[i]["x_mm"], row["y_mm"] - start[i]["y_mm"])
            )
        rows.append(row)
    return rows


def counts(rows: list[dict]) -> dict:
    separated = sum(r["separated"] for r in rows)
    return {
        "glasses": len(rows),
        "separated": separated,
        "not_separated": len(rows) - separated,
        "fell_over": sum(not r["standing"] for r in rows),
    }


# ------------------------------------------------------------------ the pushes

# Where the hand comes down, from the push's direction measured against "straight away from the
# nearest neighbour". At 0 degrees the hand comes down in the gap between the two glasses.
SIDES = (("in the gap", 45), ("at the side", 135), ("on the far side", 180))
MADE, REFUSED, REJECTED = "made", "refused by MoveIt", "rejected by the safety check"


def nearest_centre(rows: list[dict], glass: int) -> int | None:
    """How far the glass's centre is from the nearest standing glass's centre, in mm."""
    me = rows[glass]
    gaps = [
        math.hypot(r["x_mm"] - me["x_mm"], r["y_mm"] - me["y_mm"])
        for r in rows
        if r["glass"] != glass and r["standing"]
    ]
    return round(min(gaps)) if gaps else None


def side_of(degrees: float) -> str:
    return next(name for name, limit in SIDES if abs(degrees) <= limit)


class PushLog:
    """Every push a solution asked for, and what became of it.

    It listens where a push reaches MoveIt, ``Pusher.push``, and where the safety check turns
    one down, so no solution is changed. The ceiling's tries also pass through ``Pusher.push``
    and are put back afterwards, so for the ceiling a push is kept only when ``made`` is called.
    """

    def __init__(self, cell, keep_every_push: bool = True) -> None:
        self.bench, self.entries, self.pending = cell.bench, [], None
        pusher_push = cell.pusher.push

        def push(boxes, request, seconds_left=math.inf, **how):
            entry = self.describe(boxes, request)
            before = glasses(self.bench)
            result = pusher_push(boxes, request, seconds_left, **how)
            if result.ok:
                after = glasses(self.bench, before)
                entry |= {
                    "outcome": MADE,
                    "moved_mm": {str(r["glass"]): r["moved_mm"] for r in after if r["moved_mm"] >= 3},
                    "moved_to_mm": {
                        str(r["glass"]): [r["x_mm"], r["y_mm"]] for r in after if r["moved_mm"] >= 3
                    },
                    "nearest_centre_mm_after": nearest_centre(after, entry["glass"]),
                    "fell_over": [
                        a["glass"]
                        for a, b in zip(after, before, strict=True)
                        if b["standing"] and not a["standing"]
                    ],
                    "separated_before": counts(before)["separated"],
                    "separated_after": counts(after)["separated"],
                }
            else:
                entry |= {"outcome": REFUSED, "why": result.why}
            if keep_every_push:
                self.keep(entry)
            else:
                self.pending = entry
            return result

        cell.pusher.push = push

    def keep(self, entry: dict) -> None:
        self.entries.append({"push": len(self.entries) + 1, **entry})

    def made(self) -> None:
        self.keep(self.pending)

    def describe(self, boxes, request) -> dict:
        """The push as asked for, with the glass found by where the solution's box stood."""
        here = [tuple(float(v) for v in self.bench.position(i)) for i in range(len(self.bench.glasses))]
        box = boxes[request.glass]
        glass = min(range(len(here)), key=lambda i: math.dist(here[i], (box.x, box.y)))
        heading = math.degrees(request.heading)
        # Where the glass would end if it went exactly as asked, and whether it would have room there.
        aim = (
            here[glass][0] + request.travel * math.cos(request.heading),
            here[glass][1] + request.travel * math.sin(request.heading),
        )
        others = [i for i in self.bench.on_table() if i != glass]
        entry = {
            "glass": glass,
            "glass_x_mm": round(here[glass][0] * 1000),
            "glass_y_mm": round(here[glass][1] * 1000),
            "heading_deg": round(heading),
            "aimed_at_mm": [round(aim[0] * 1000), round(aim[1] * 1000)],
            "aimed_spot_has_room": bool(
                has_room(*aim, [(*here[i], self.bench.glasses[i].outline.max_diameter) for i in others])
            ),
            "nearest_centre_mm_before": nearest_centre(glasses(self.bench), glass),
        }
        if others:
            n = min(others, key=lambda i: math.dist(here[i], here[glass]))
            away = math.degrees(math.atan2(here[glass][1] - here[n][1], here[glass][0] - here[n][0]))
            turned = (heading - away + 180) % 360 - 180
            entry |= {
                "nearest_neighbour": n,
                "from_neighbour_deg": round(turned),
                "hand_comes_down": side_of(turned),
            }
        return entry | {
            "travel_mm": round(request.travel * 1000),
            "settings": {k: round(v, 3) for k, v in request.settings.__dict__.items()},
        }

    def watch(self, checked: Checked):
        """Keep each push the safety check turns down, which never reaches MoveIt.

        Returns what puts the check back as it was, for when the table is over.
        """
        propose, decide = checked.inner.decide, checked.decide
        offered: list = []

        def proposing(look):
            answer = propose(look)
            offered.append((list(look.boxes), answer))
            return answer

        def deciding(look):
            offered.clear()
            answer = decide(look)
            for boxes, a in offered:
                if a is not answer and not isinstance(a, Done) and a.glass < len(boxes):
                    self.keep(self.describe(boxes, a) | {"outcome": REJECTED})
            return answer

        checked.inner.decide, checked.decide = proposing, deciding

        def undo() -> None:
            checked.inner.decide, checked.decide = propose, decide

        return undo


class Made(list):
    """The ceiling's record of the pushes it made, which tells the log as each one is added."""

    def __init__(self, log: PushLog) -> None:
        super().__init__()
        self.log = log

    def append(self, item) -> None:
        super().append(item)
        self.log.made()


# ------------------------------------------------------------------ the pictures

# How each push is drawn: an arrow pointing the way the hand pushed, ending at the glass.
ARROWS = {
    MADE: {"color": "#1f5fa8", "lw": 1.8, "ls": "-"},
    REFUSED: {"color": "#9a9a9a", "lw": 1.0, "ls": "--"},
    REJECTED: {"color": "#8e44ad", "lw": 1.0, "ls": ":"},
}
ARROW_MM = 45


def draw(
    path: Path,
    title: str,
    rows: list[dict],
    widths: list[float],
    start: list[dict] | None = None,
    pushes: list[dict] | None = None,
) -> None:
    """The table from above: each glass at its place, coloured by whether it is separated.

    With ``start``, a dashed ring marks where a glass that moved began, joined to where it ended.
    With ``pushes``, each push is an arrow drawn where the glass stood when it was asked for,
    numbered in order and pointing the way the hand pushed.
    """
    figure, axes = plt.subplots(figsize=(6.4, 6.4), dpi=110)
    x0, x1, y0, y1 = (v * 1000 for v in GLASS_ZONE)
    axes.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=True, color="#f3ead9", zorder=0))
    axes.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="#b9a888", lw=1.2, zorder=1))
    for row, width in zip(rows, widths, strict=True):
        r = width * 500
        if start is not None and row["moved_mm"] >= 3:
            s = start[row["glass"]]
            axes.add_patch(
                plt.Circle((s["x_mm"], s["y_mm"]), r, fill=False, ls="--", ec="#888888", lw=1, zorder=2)
            )
            # The arrow stops at the glass's edge, so its head is not hidden under the glass. A
            # glass that moved less than its own radius has only the ring.
            gap = math.hypot(row["x_mm"] - s["x_mm"], row["y_mm"] - s["y_mm"])
            if gap > r:
                tip = (
                    row["x_mm"] - (row["x_mm"] - s["x_mm"]) * r / gap,
                    row["y_mm"] - (row["y_mm"] - s["y_mm"]) * r / gap,
                )
                axes.annotate(
                    "",
                    tip,
                    (s["x_mm"], s["y_mm"]),
                    arrowprops={"arrowstyle": "-|>", "color": "#555555", "lw": 1.2},
                    zorder=6,
                )
        colour = "#9e9e9e" if not row["standing"] else "#4caf50" if row["separated"] else "#ef8a3c"
        axes.add_patch(
            plt.Circle(
                (row["x_mm"], row["y_mm"]),
                r,
                color=colour,
                alpha=0.9,
                hatch="xx" if not row["standing"] else None,
                ec="#333333",
                lw=1,
                zorder=4,
            )
        )
        axes.text(
            row["x_mm"], row["y_mm"], str(row["glass"]), ha="center", va="center", fontsize=11, zorder=5
        )
    for p in pushes or []:
        u = (math.cos(math.radians(p["heading_deg"])), math.sin(math.radians(p["heading_deg"])))
        r = widths[p["glass"]] * 500
        tip = (p["glass_x_mm"] - r * u[0], p["glass_y_mm"] - r * u[1])
        tail = (tip[0] - ARROW_MM * u[0], tip[1] - ARROW_MM * u[1])
        style = ARROWS[p["outcome"]]
        axes.annotate(
            "",
            tip,
            tail,
            arrowprops={"arrowstyle": "-|>", "color": style["color"], "lw": style["lw"], "ls": style["ls"]},
            zorder=7,
        )
        axes.text(
            tail[0] - 9 * u[0],
            tail[1] - 9 * u[1],
            str(p["push"]),
            ha="center",
            va="center",
            fontsize=8,
            color=style["color"],
            zorder=7,
        )
    legend = [
        plt.Line2D([], [], marker="o", ls="", color="#4caf50", markersize=11, label="separated"),
        plt.Line2D([], [], marker="o", ls="", color="#ef8a3c", markersize=11, label="not separated"),
        plt.Line2D([], [], marker="o", ls="", color="#9e9e9e", markersize=11, label="fell over"),
    ]
    if start is not None and any(row["moved_mm"] >= 3 for row in rows):
        legend.append(
            plt.Line2D(
                [], [], marker="o", ls="", mfc="none", mec="#888888", markersize=11, label="where it began"
            )
        )
    for outcome in ARROWS:
        if any(p["outcome"] == outcome for p in pushes or []):
            style = ARROWS[outcome]
            legend.append(
                plt.Line2D([], [], color=style["color"], lw=style["lw"], ls=style["ls"], label=outcome)
            )
    axes.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False)
    axes.set_xlim(x0 - 70, x1 + 70)
    axes.set_ylim(y0 - 70, y1 + 70)
    axes.set_aspect("equal")
    axes.set_xlabel("x, mm from the arm's base (the arm is to the left)")
    axes.set_ylabel("y, mm")
    axes.set_title(title, fontsize=11)
    figure.savefig(path, bbox_inches="tight")
    plt.close(figure)


def widths_of(bench) -> list[float]:
    return [float(g.outline.max_diameter) for g in bench.glasses]


# ------------------------------------------------------------------ the three steps


def arrangements(count: int = TABLES, first: int = FIRST) -> None:
    allowed = int(count * ALREADY_DONE_SHARE)
    chosen, already, skipped, seed = [], 0, [], first
    RUNS.mkdir(exist_ok=True)
    with MoveItLink() as link:
        while len(chosen) < count:
            cell = C.ArmCell(seed, link, camera=False)
            rows = glasses(cell.bench)
            total = counts(rows)
            if total["not_separated"] == 0:
                if already >= allowed:
                    skipped.append(seed)
                    seed += 1
                    continue
                already += 1
            folder = RUNS / str(seed)
            folder.mkdir(exist_ok=True)
            record = {
                "table": seed,
                **{k: v for k, v in total.items() if k != "fell_over"},
                "glass_list": rows,
            }
            (folder / "arrangement.json").write_text(json.dumps(record, indent=1))
            draw(
                folder / "arrangement.png",
                f"Table {seed} at the start: {total['separated']} of {total['glasses']} separated",
                rows,
                widths_of(cell.bench),
            )
            chosen.append(seed)
            seed += 1
    print(f"{len(chosen)} tables, {already} already separated, skipped {skipped or 'none'}")


def tables() -> list[int]:
    return sorted(int(p.parent.name) for p in RUNS.glob("*/arrangement.json"))


def build(stem: str):
    key, weights = RECORDED[stem]
    module, cls = SOLUTIONS[key]
    factory = getattr(importlib.import_module(module), cls)
    return factory(WEIGHTS / weights) if weights else factory()


def solve(stem: str) -> None:
    solution = None if stem == "ceiling" else build(stem)
    with MoveItLink() as link:
        for seed in tables():
            folder = RUNS / str(seed)
            start = json.loads((folder / "arrangement.json").read_text())["glass_list"]
            if solution is None:
                cell = C.ArmCell(seed, link, camera=False)
                log = PushLog(cell, keep_every_push=False)
                pushes = Made(log)
                result = oracle.clear_table(
                    seed, link, ARM_BUDGET, 30, random.Random(seed), pushes, cell=cell
                )
                made, refused = len(pushes), 0
            else:
                tally, kept = Tally(), {}

                def watch(run, kept=kept) -> None:
                    kept["cell"] = SimExaminer.cell_of(run)
                    kept["log"] = PushLog(kept["cell"])
                    if isinstance(solution, Checked):
                        kept["undo"] = kept["log"].watch(solution)

                try:
                    result = SimExaminer(link, ARM_BUDGET, tally).run(solution, seed, prepare=watch)
                finally:
                    if "undo" in kept:
                        kept["undo"]()
                cell, log = kept["cell"], kept["log"]
                made, refused = tally.pushes, tally.refusals
            rows = glasses(cell.bench, start)
            before, after = counts(start), counts(rows)
            record = {
                "table": seed,
                "solution": stem,
                "name": "the ceiling (tries 30 pushes first)" if solution is None else solution.name,
                "start": {k: before[k] for k in ("glasses", "separated", "not_separated")},
                "end": after,
                "gain": after["separated"] - before["separated"],
                "ended_by": result.ended_by,
                "pushes": made,
                "refused": refused,
                "arm_seconds": round(result.arm_seconds, 1),
                "glass_list": rows,
                "push_list": log.entries,
            }
            (folder / f"{stem}_result.json").write_text(json.dumps(record, indent=1))
            fell = f", {after['fell_over']} fell over" if after["fell_over"] else ""
            draw(
                folder / f"{stem}_result.png",
                f"Table {seed}, {record['name']}:\n"
                f"{before['separated']} -> {after['separated']} of {after['glasses']} separated{fell}",
                rows,
                widths_of(cell.bench),
                start,
                log.entries,
            )
            print(
                f"{stem} {seed}: {before['separated']}->{after['separated']}/{after['glasses']}, "
                f"{made} pushes, fell {after['fell_over']}, {result.ended_by}",
                flush=True,
            )


def summary() -> None:
    seeds = tables()
    start = {s: json.loads((RUNS / str(s) / "arrangement.json").read_text()) for s in seeds}
    per_solution, per_table = {}, {s: {} for s in seeds}
    for stem in RECORDED:
        found = [json.loads(p.read_text()) for p in sorted(RUNS.glob(f"*/{stem}_result.json"))]
        if not found:
            continue
        for r in found:
            per_table[r["table"]][stem] = {
                "separated_at_end": r["end"]["separated"],
                "fell_over": r["end"]["fell_over"],
                "pushes": r["pushes"],
            }
        per_solution[stem] = {
            "name": found[0]["name"],
            "tables": len(found),
            "separated_at_start": sum(r["start"]["separated"] for r in found),
            "separated_at_end": sum(r["end"]["separated"] for r in found),
            "gain": sum(r["gain"] for r in found),
            "fell_over": sum(r["end"]["fell_over"] for r in found),
            "tables_better": sum(r["gain"] > 0 for r in found),
            "tables_worse": sum(r["gain"] < 0 or r["end"]["fell_over"] > 0 for r in found),
            "tables_not_touched": sum(r["pushes"] == 0 for r in found),
            "pushes": sum(r["pushes"] for r in found),
            "arm_minutes": round(sum(r["arm_seconds"] for r in found) / 60, 1),
            "asked_by_side": by_side(found),
        }
    totals = {
        "tables": len(seeds),
        "glasses": sum(a["glasses"] for a in start.values()),
        "separated_at_start": sum(a["separated"] for a in start.values()),
        "tables_already_separated": sum(a["not_separated"] == 0 for a in start.values()),
    }
    (RUNS / "results.json").write_text(
        json.dumps({**totals, "solutions": per_solution, "per_table": per_table}, indent=1)
    )
    (RUNS / "results.md").write_text(markdown(totals, per_solution, per_table, start))
    print("wrote", RUNS / "results.json", "and results.md")


def by_side(found: list[dict]) -> dict:
    """How many pushes were asked for with the hand coming down in each place, and how each ended."""
    table = {name: {MADE: 0, REFUSED: 0, REJECTED: 0} for name, _ in SIDES}
    for r in found:
        for p in r.get("push_list", []):
            if "hand_comes_down" in p:
                table[p["hand_comes_down"]][p["outcome"]] += 1
    return table


def markdown(totals: dict, per_solution: dict, per_table: dict, start: dict) -> str:
    stems = list(per_solution)
    lines = [
        "# Runs, table by table",
        "",
        f"This folder keeps every solution's answer to the same {totals['tables']} held-out tables, one "
        "folder per table, so a table can be opened and the solutions compared on it. The results "
        "page adds up many more tables; this one shows what happened on each.",
        "",
        f"The {totals['tables']} tables hold {totals['glasses']} glasses, and "
        f"{totals['separated_at_start']} of them are separated at the start. A glass is **separated** "
        "when the gripper could pick it: it is standing, inside the glass zone, and no neighbour is "
        f"too close. {totals['tables_already_separated']} of the tables start with every glass "
        "separated; at most one in twenty may.",
        "",
        "## What is in a table's folder",
        "",
        "- `arrangement.json` and `arrangement.png`: where every glass starts, and how many are "
        "separated. A glass that is not separated lists the neighbours that crowd it.",
        "- `<solution>_result.json` and `<solution>_result.png`: the same, after that solution "
        "has finished with the table, with how far each glass moved, whether it fell over and why "
        "the solution stopped. The push list gives every push it asked for, in order: the glass, "
        "the direction, the distance, the six settings handed to MoveIt, and whether the push was "
        "made, refused by MoveIt or rejected by the safety check. In the picture each push is a "
        "numbered arrow pointing the way the hand pushed. These files are made again by every "
        "run, so git does not keep them.",
        "",
        "Positions are in millimetres from the arm's base. The glass zone, where a glass must "
        "stand to be picked, runs from 320 to 640 mm in x and from −440 to −80 mm in y. Each "
        "table is given the whole 15 arm minutes on its own.",
        "",
        "Every solution is seeded by the table number, but MoveIt's planner draws its arm paths at "
        "random, so a second run can push a glass a little differently. Between two recordings, "
        "about one table result in fifty changed.",
        "",
        "## All tables together",
        "",
        "| Solution | Separated at start → end | Gain | Fell over | Tables better | Tables worse "
        "| Tables not touched | Pushes | Arm minutes |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for stem in stems:
        s = per_solution[stem]
        lines.append(
            f"| {stem} | {s['separated_at_start']} → {s['separated_at_end']} | {s['gain']:+d} | "
            f"{s['fell_over']} | {s['tables_better']} | {s['tables_worse']} | {s['tables_not_touched']} | "
            f"{s['pushes']} | {s['arm_minutes']} |"
        )
    lines += [
        "",
        "A table is *worse* when it ends with fewer glasses separated or with a glass fallen over, "
        "and *not touched* when the solution stopped without a single push.",
        "",
        "## Where the hand came down",
        "",
        "A push's direction is measured against the direction straight away from the glass's "
        "nearest neighbour. Within 45° of it, the hand comes down **in the gap** between the two "
        "glasses; from 45° to 135° it comes down **at the side**; beyond that it comes down **on the "
        "far side** and pushes the glass towards its neighbour. Each cell is pushes made, out of "
        "pushes asked for; the rest were refused by MoveIt or rejected by the safety check. The "
        "ceiling's tries are not counted, only the pushes it made.",
        "",
        "| Solution | In the gap | At the side | On the far side | Refused by MoveIt "
        "| Rejected by the check |",
        "|---|---|---|---|---|---|",
    ]
    for stem in stems:
        sides = per_solution[stem]["asked_by_side"]
        cells = [f"{c[MADE]} of {sum(c.values())}" for c in sides.values()]
        lines.append(
            f"| {stem} | " + " | ".join(cells) + f" | {sum(c[REFUSED] for c in sides.values())} | "
            f"{sum(c[REJECTED] for c in sides.values())} |"
        )
    lines += [
        "",
        "## Each table",
        "",
        "Each cell is the number of separated glasses at the end, and ✗ marks a glass that fell "
        "over. The second column is the number at the start.",
        "",
        "| Table | Start | " + " | ".join(s.removeprefix("solution_") for s in stems) + " |",
        "|---|---|" + "---|" * len(stems),
    ]
    for seed, row in per_table.items():
        a = start[seed]
        cells = []
        for stem in stems:
            r = row.get(stem)
            cells.append("" if r is None else f"{r['separated_at_end']}{' ✗' if r['fell_over'] else ''}")
        lines.append(
            f"| [{seed}]({seed}/arrangement.png) | {a['separated']} of {a['glasses']} | "
            + " | ".join(cells)
            + " |"
        )
    lines += [
        "",
        "## Making it again",
        "",
        "`make runs` in the full-arm folder chooses the tables, runs every solution on them and "
        "writes this page.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("arrangements", "solve", "summary"))
    parser.add_argument("solution", nargs="?", choices=sorted(RECORDED))
    parser.add_argument("--tables", type=int, default=TABLES)
    a = parser.parse_args()
    if a.step == "arrangements":
        arrangements(a.tables)
    elif a.step == "solve":
        if a.solution is None:
            parser.error("solve needs a solution")
        solve(a.solution)
    else:
        summary()


if __name__ == "__main__":
    main()
