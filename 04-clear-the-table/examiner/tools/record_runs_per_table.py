"""Every solution on the same held-out tables, kept table by table in ``runs/``.

The scores in ``results/`` add the tables up. This keeps them apart, so that one table can
be opened and every solution's answer to it compared: where each glass stood at the start,
where it stood at the end, and which glasses had room.

``python record_runs_per_table.py arrangements``     choose the tables, record where every glass starts
``python record_runs_per_table.py solve SOLUTION``   one solution on every table
``python record_runs_per_table.py summary``          ``runs/results.json`` and ``runs/results.md``

A glass is **separated** when the gripper could pick it: it is standing, inside the glass
zone, and every neighbour is far enough away for the open fingers. That is problem 4's
``glass_is_pickable``, and nothing else is meant by the word here.

**Which tables.** Held-out tables from 10,000 up, in order. A table on which every glass is
already separated asks nothing of a solution, so at most one in twenty of the chosen tables
may be one. Each table is given the whole arm-time budget on its own, so a slow solution on
one table does not take time from the next, which is how the films run and not quite how
``evaluate_solution.py`` scores.

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
import json
import math
import random
from pathlib import Path

import matplotlib
from safety_check import SafetyCheckedSolution
from work_cell.rack.layout import GLASS_ZONE

from examiner.examining import one_table_cell
from examiner.examining.solution_catalogue import SolutionChoice
from examiner.examining.table_examiner import ARM_SECONDS_FOR_TABLE_LIST, ArmActivityCounts, SimulatedExaminer
from examiner.examining.table_scoring import glass_is_pickable
from examiner.motion.moveit_connection import MoveItConnection
from examiner.motion.push_motions import PushWatcher
from examiner.simulation.taken_from_problem_3 import STANDING_TILT_DEG, has_room, in_zone
from examiner.tools import ceiling_search

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

THIS_FOLDER = Path(__file__).resolve().parent
# The examiner's folder, which keeps the runs, and the problem's, which keeps the solutions.
EXAMINER_FOLDER = THIS_FOLDER.parent
RUNS = EXAMINER_FOLDER / "runs"
PROBLEM = EXAMINER_FOLDER.parent
TABLES, FIRST, ALREADY_DONE_SHARE = 25, 10_000, 0.05

# What each result file is called, which solution it runs and the weights it reads, which
# are kept in that solution's own folder. ``ceiling`` is the search that tries pushes in the
# physics first; it is not a solution.
IMITATION = PROBLEM / "03-imitation" / "weights" / "imitation-r4.pt"
REINFORCEMENT = PROBLEM / "05-reinforcement-learning" / "weights" / "reinforcement-v4.pt"
SMOLVLA = PROBLEM / "06-smolvla-fine-tuned" / "weights" / "vla-r4"
RECORDED = {
    "solution_1_geometry": ("geometry", None),
    "solution_2_geometry_ranked": ("geometry-ranked", None),
    "solution_3_imitation": ("imitation", IMITATION),
    "solution_3_imitation_with_check": ("imitation-checked", IMITATION),
    "solution_4_world_model": ("world-model", PROBLEM / "04-world-model" / "weights" / "world-models-v3.pt"),
    "solution_5_reinforcement": ("reinforcement", REINFORCEMENT),
    "solution_5_reinforcement_with_check": ("reinforcement-checked", REINFORCEMENT),
    "solution_6_smolvla": ("vla", SMOLVLA),
    "solution_6_smolvla_with_check": ("vla-checked", SMOLVLA),
    "ceiling": (None, None),
}


# ------------------------------------------------------------------ the glasses


def glass_rows(simulator, rows_at_start: list[dict] | None = None) -> list[dict]:
    """Every glass as it stands now. With ``rows_at_start``, also how far each has moved since."""
    rows = []
    for i, glass in enumerate(simulator.glasses):
        x, y = (float(value) for value in simulator.position(i))
        # Which neighbours are too close, one at a time, so a crowded glass says who crowds it.
        crowded_by = [
            other
            for other in simulator.on_table()
            if other != i
            and not has_room(
                x,
                y,
                [
                    (
                        *(float(value) for value in simulator.position(other)),
                        simulator.glasses[other].outline.max_diameter,
                    )
                ],
            )
        ]
        row = {
            "glass": i,
            "kind": glass.kind,
            "x_mm": round(x * 1000),
            "y_mm": round(y * 1000),
            "standing": bool(simulator.tilt(i) < STANDING_TILT_DEG),
            "in_zone": bool(in_zone(x, y)),
            "crowded_by": crowded_by,
            "separated": bool(glass_is_pickable(simulator, i)),
        }
        if rows_at_start is not None:
            row["moved_mm"] = round(
                math.hypot(row["x_mm"] - rows_at_start[i]["x_mm"], row["y_mm"] - rows_at_start[i]["y_mm"])
            )
        rows.append(row)
    return rows


def separated_counts(glass_rows: list[dict]) -> dict:
    separated = sum(r["separated"] for r in glass_rows)
    return {
        "glasses": len(glass_rows),
        "separated": separated,
        "not_separated": len(glass_rows) - separated,
        "fell_over": sum(not r["standing"] for r in glass_rows),
    }


# ------------------------------------------------------------------ the pushes

# Where the hand comes down, from the push's direction measured against "straight away from the
# nearest neighbour". At 0 degrees the hand comes down in the gap between the two glasses.
HAND_SIDES = (("in the gap", 45), ("at the side", 135), ("on the far side", 180))
MADE, REFUSED, REJECTED = "made", "refused by MoveIt", "rejected by the safety check"


def nearest_centre_distance_mm(glass_rows: list[dict], glass: int) -> int | None:
    """How far the glass's centre is from the nearest standing glass's centre, in mm."""
    this_glass = glass_rows[glass]
    distances = [
        math.hypot(row["x_mm"] - this_glass["x_mm"], row["y_mm"] - this_glass["y_mm"])
        for row in glass_rows
        if row["glass"] != glass and row["standing"]
    ]
    return round(min(distances)) if distances else None


def where_the_hand_comes_down(degrees: float) -> str:
    return next(name for name, limit in HAND_SIDES if abs(degrees) <= limit)


class PushRecorder(PushWatcher):
    """Every push a solution asked for, and what became of it.

    It is a ``PushWatcher``, so the pusher tells it about every push that reaches MoveIt. A push
    the safety check turns down never reaches MoveIt, so when the solution is wrapped in the
    check, the recorder also reads the check's own list of the pushes it turned down. It reads
    that list each time a push starts and once more when the table is over, so the entries stay
    in the order the solution asked for them. No solution is changed by being recorded.

    The ceiling's tries also pass through the pusher, and are put back afterwards, so the
    ceiling lets the recorder watch only the pushes it really makes.
    """

    def __init__(self, cell, safety_check: SafetyCheckedSolution | None = None) -> None:
        self.simulator, self.entries = cell.simulator, []
        self.safety_check = safety_check
        self.turned_down_pushes_kept = 0
        self.entry_of_push_under_way: dict = {}
        self.glass_rows_before_push: list[dict] = []

    def push_starting(self, boxes, request) -> None:
        self.keep_pushes_turned_down_by_safety_check()
        self.entry_of_push_under_way = self.describe(boxes, request)
        self.glass_rows_before_push = glass_rows(self.simulator)

    def push_ended(self, boxes, request, pusher_result) -> None:
        entry, before = self.entry_of_push_under_way, self.glass_rows_before_push
        if pusher_result.made:
            after = glass_rows(self.simulator, before)
            entry |= {
                "outcome": MADE,
                "moved_mm": {str(r["glass"]): r["moved_mm"] for r in after if r["moved_mm"] >= 3},
                "moved_to_mm": {str(r["glass"]): [r["x_mm"], r["y_mm"]] for r in after if r["moved_mm"] >= 3},
                "nearest_centre_mm_after": nearest_centre_distance_mm(after, entry["glass"]),
                "fell_over": [
                    row_after["glass"]
                    for row_after, row_before in zip(after, before, strict=True)
                    if row_before["standing"] and not row_after["standing"]
                ],
                "separated_before": separated_counts(before)["separated"],
                "separated_after": separated_counts(after)["separated"],
            }
        else:
            entry |= {"outcome": REFUSED, "why": pusher_result.refusal_reason}
        self.keep(entry)

    def keep_pushes_turned_down_by_safety_check(self) -> None:
        """Keep the pushes the safety check turned down since this was last called."""
        if self.safety_check is None:
            return
        turned_down = self.safety_check.pushes_turned_down_this_table
        for boxes, request in turned_down[self.turned_down_pushes_kept :]:
            self.keep(self.describe(boxes, request) | {"outcome": REJECTED})
        self.turned_down_pushes_kept = len(turned_down)

    def keep(self, entry: dict) -> None:
        self.entries.append({"push": len(self.entries) + 1, **entry})

    def describe(self, boxes, request) -> dict:
        """The push as asked for, with the glass found by where the solution's box stood."""
        simulator = self.simulator
        positions = [
            tuple(float(value) for value in simulator.position(index))
            for index in range(len(simulator.glasses))
        ]
        box = boxes[request.glass]
        glass_index = min(
            range(len(positions)), key=lambda index: math.dist(positions[index], (box.x, box.y))
        )
        heading = math.degrees(request.heading)
        # Where the glass would end if it went exactly as asked, and whether it would have room there.
        aimed_at = (
            positions[glass_index][0] + request.travel * math.cos(request.heading),
            positions[glass_index][1] + request.travel * math.sin(request.heading),
        )
        other_glasses = [index for index in self.simulator.on_table() if index != glass_index]
        entry = {
            "glass": glass_index,
            "glass_x_mm": round(positions[glass_index][0] * 1000),
            "glass_y_mm": round(positions[glass_index][1] * 1000),
            "heading_deg": round(heading),
            "aimed_at_mm": [round(aimed_at[0] * 1000), round(aimed_at[1] * 1000)],
            "aimed_spot_has_room": bool(
                has_room(
                    *aimed_at,
                    [
                        (*positions[index], self.simulator.glasses[index].outline.max_diameter)
                        for index in other_glasses
                    ],
                )
            ),
            "nearest_centre_mm_before": nearest_centre_distance_mm(glass_rows(self.simulator), glass_index),
        }
        if other_glasses:
            nearest_neighbour = min(
                other_glasses, key=lambda index: math.dist(positions[index], positions[glass_index])
            )
            away_degrees = math.degrees(
                math.atan2(
                    positions[glass_index][1] - positions[nearest_neighbour][1],
                    positions[glass_index][0] - positions[nearest_neighbour][0],
                )
            )
            from_neighbour_degrees = (heading - away_degrees + 180) % 360 - 180
            entry |= {
                "nearest_neighbour": nearest_neighbour,
                "from_neighbour_deg": round(from_neighbour_degrees),
                "hand_comes_down": where_the_hand_comes_down(from_neighbour_degrees),
            }
        return entry | {
            "travel_mm": round(request.travel * 1000),
            "settings": {key: round(value, 3) for key, value in request.settings.__dict__.items()},
        }


# ------------------------------------------------------------------ the pictures

# How each push is drawn: an arrow pointing the way the hand pushed, ending at the glass.
ARROW_STYLES = {
    MADE: {"color": "#1f5fa8", "lw": 1.8, "ls": "-"},
    REFUSED: {"color": "#9a9a9a", "lw": 1.0, "ls": "--"},
    REJECTED: {"color": "#8e44ad", "lw": 1.0, "ls": ":"},
}
ARROW_LENGTH_MM = 45


def draw_table_picture(
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
    zone_x0, zone_x1, zone_y0, zone_y1 = (value * 1000 for value in GLASS_ZONE)
    axes.add_patch(
        plt.Rectangle(
            (zone_x0, zone_y0), zone_x1 - zone_x0, zone_y1 - zone_y0, fill=True, color="#f3ead9", zorder=0
        )
    )
    axes.add_patch(
        plt.Rectangle(
            (zone_x0, zone_y0),
            zone_x1 - zone_x0,
            zone_y1 - zone_y0,
            fill=False,
            ec="#b9a888",
            lw=1.2,
            zorder=1,
        )
    )
    for row, width in zip(rows, widths, strict=True):
        radius_mm = width * 500
        if start is not None and row["moved_mm"] >= 3:
            start_row = start[row["glass"]]
            axes.add_patch(
                plt.Circle(
                    (start_row["x_mm"], start_row["y_mm"]),
                    radius_mm,
                    fill=False,
                    ls="--",
                    ec="#888888",
                    lw=1,
                    zorder=2,
                )
            )
            # The arrow stops at the glass's edge, so its head is not hidden under the glass. A
            # glass that moved less than its own radius has only the ring.
            moved_mm = math.hypot(row["x_mm"] - start_row["x_mm"], row["y_mm"] - start_row["y_mm"])
            if moved_mm > radius_mm:
                arrow_tip = (
                    row["x_mm"] - (row["x_mm"] - start_row["x_mm"]) * radius_mm / moved_mm,
                    row["y_mm"] - (row["y_mm"] - start_row["y_mm"]) * radius_mm / moved_mm,
                )
                axes.annotate(
                    "",
                    arrow_tip,
                    (start_row["x_mm"], start_row["y_mm"]),
                    arrowprops={"arrowstyle": "-|>", "color": "#555555", "lw": 1.2},
                    zorder=6,
                )
        colour = "#9e9e9e" if not row["standing"] else "#4caf50" if row["separated"] else "#ef8a3c"
        axes.add_patch(
            plt.Circle(
                (row["x_mm"], row["y_mm"]),
                radius_mm,
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
    for push in pushes or []:
        along_push = (
            math.cos(math.radians(push["heading_deg"])),
            math.sin(math.radians(push["heading_deg"])),
        )
        radius_mm = widths[push["glass"]] * 500
        arrow_tip = (
            push["glass_x_mm"] - radius_mm * along_push[0],
            push["glass_y_mm"] - radius_mm * along_push[1],
        )
        arrow_tail = (
            arrow_tip[0] - ARROW_LENGTH_MM * along_push[0],
            arrow_tip[1] - ARROW_LENGTH_MM * along_push[1],
        )
        style = ARROW_STYLES[push["outcome"]]
        axes.annotate(
            "",
            arrow_tip,
            arrow_tail,
            arrowprops={"arrowstyle": "-|>", "color": style["color"], "lw": style["lw"], "ls": style["ls"]},
            zorder=7,
        )
        axes.text(
            arrow_tail[0] - 9 * along_push[0],
            arrow_tail[1] - 9 * along_push[1],
            str(push["push"]),
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
    for outcome in ARROW_STYLES:
        if any(push["outcome"] == outcome for push in pushes or []):
            style = ARROW_STYLES[outcome]
            legend.append(
                plt.Line2D([], [], color=style["color"], lw=style["lw"], ls=style["ls"], label=outcome)
            )
    axes.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False)
    axes.set_xlim(zone_x0 - 70, zone_x1 + 70)
    axes.set_ylim(zone_y0 - 70, zone_y1 + 70)
    axes.set_aspect("equal")
    axes.set_xlabel("x, mm from the arm's base (the arm is to the left)")
    axes.set_ylabel("y, mm")
    axes.set_title(title, fontsize=11)
    figure.savefig(path, bbox_inches="tight")
    plt.close(figure)


def glass_widths(simulator) -> list[float]:
    return [float(glass.outline.max_diameter) for glass in simulator.glasses]


# ------------------------------------------------------------------ the three steps


def record_start_arrangements(table_count: int = TABLES, first_table: int = FIRST) -> None:
    already_separated_allowed = int(table_count * ALREADY_DONE_SHARE)
    chosen_tables, already_separated, skipped_tables, table_number = [], 0, [], first_table
    RUNS.mkdir(exist_ok=True)
    with MoveItConnection() as moveit:
        while len(chosen_tables) < table_count:
            cell = one_table_cell.OneTableCell(table_number, moveit, with_wrist_camera=False)
            glass_rows_at_start = glass_rows(cell.simulator)
            counts = separated_counts(glass_rows_at_start)
            if counts["not_separated"] == 0:
                if already_separated >= already_separated_allowed:
                    skipped_tables.append(table_number)
                    table_number += 1
                    continue
                already_separated += 1
            table_folder = RUNS / str(table_number)
            table_folder.mkdir(exist_ok=True)
            record = {
                "table": table_number,
                **{key: value for key, value in counts.items() if key != "fell_over"},
                "glass_list": glass_rows_at_start,
            }
            (table_folder / "arrangement.json").write_text(json.dumps(record, indent=1))
            draw_table_picture(
                table_folder / "arrangement.png",
                f"Table {table_number} at the start: {counts['separated']} of {counts['glasses']} separated",
                glass_rows_at_start,
                glass_widths(cell.simulator),
            )
            chosen_tables.append(table_number)
            table_number += 1
    print(
        f"{len(chosen_tables)} tables, {already_separated} already separated, "
        f"skipped {skipped_tables or 'none'}"
    )


def recorded_tables() -> list[int]:
    return sorted(int(path.parent.name) for path in RUNS.glob("*/arrangement.json"))


def build_solution_to_record(recorded_name: str):
    solution_key, weights = RECORDED[recorded_name]
    return SolutionChoice(solution_key, weights).build_new_solution()


def record_solution_on_every_table(recorded_name: str) -> None:
    solution = None if recorded_name == "ceiling" else build_solution_to_record(recorded_name)
    with MoveItConnection() as moveit:
        for table_number in recorded_tables():
            table_folder = RUNS / str(table_number)
            rows_at_start = json.loads((table_folder / "arrangement.json").read_text())["glass_list"]
            if solution is None:
                cell = one_table_cell.OneTableCell(table_number, moveit, with_wrist_camera=False)
                recorder = PushRecorder(cell)
                pushes_made: list[dict] = []
                result = ceiling_search.clear_table_by_trying_pushes(
                    table_number,
                    moveit,
                    ARM_SECONDS_FOR_TABLE_LIST,
                    30,
                    random.Random(table_number),
                    pushes_made,
                    cell=cell,
                    watcher_of_pushes_made=recorder,
                )
                made_count, refused_count = len(pushes_made), 0
            else:
                arm_activity = ArmActivityCounts()
                examiner = SimulatedExaminer(moveit, ARM_SECONDS_FOR_TABLE_LIST, arm_activity)
                attempt = examiner.start_attempt(table_number)
                cell = examiner.cell_behind_attempt(attempt)
                safety_check = solution if isinstance(solution, SafetyCheckedSolution) else None
                recorder = PushRecorder(cell, safety_check)
                cell.pusher.push_watchers.append(recorder)
                result = examiner.run_solution_on_attempt(solution, attempt)
                recorder.keep_pushes_turned_down_by_safety_check()
                made_count, refused_count = arm_activity.pushes_made, arm_activity.pushes_refused
            rows_at_end = glass_rows(cell.simulator, rows_at_start)
            counts_at_start, counts_at_end = separated_counts(rows_at_start), separated_counts(rows_at_end)
            record = {
                "table": table_number,
                "solution": recorded_name,
                "name": "the ceiling (tries 30 pushes first)" if solution is None else solution.name,
                "start": {key: counts_at_start[key] for key in ("glasses", "separated", "not_separated")},
                "end": counts_at_end,
                "gain": counts_at_end["separated"] - counts_at_start["separated"],
                "ended_by": result.ended_by,
                "pushes": made_count,
                "refused": refused_count,
                "arm_seconds": round(result.arm_seconds, 1),
                "glass_list": rows_at_end,
                "push_list": recorder.entries,
            }
            (table_folder / f"{recorded_name}_result.json").write_text(json.dumps(record, indent=1))
            fell_text = f", {counts_at_end['fell_over']} fell over" if counts_at_end["fell_over"] else ""
            draw_table_picture(
                table_folder / f"{recorded_name}_result.png",
                f"Table {table_number}, {record['name']}:\n"
                f"{counts_at_start['separated']} -> {counts_at_end['separated']} "
                f"of {counts_at_end['glasses']} separated{fell_text}",
                rows_at_end,
                glass_widths(cell.simulator),
                rows_at_start,
                recorder.entries,
            )
            print(
                f"{recorded_name} {table_number}: "
                f"{counts_at_start['separated']}->{counts_at_end['separated']}/{counts_at_end['glasses']}, "
                f"{made_count} pushes, fell {counts_at_end['fell_over']}, {result.ended_by}",
                flush=True,
            )


def write_runs_summary() -> None:
    table_numbers = recorded_tables()
    arrangements_by_table = {
        table_number: json.loads((RUNS / str(table_number) / "arrangement.json").read_text())
        for table_number in table_numbers
    }
    per_solution, per_table = {}, {table_number: {} for table_number in table_numbers}
    for recorded_name in RECORDED:
        results = [
            json.loads(path.read_text()) for path in sorted(RUNS.glob(f"*/{recorded_name}_result.json"))
        ]
        if not results:
            continue
        for result in results:
            per_table[result["table"]][recorded_name] = {
                "separated_at_end": result["end"]["separated"],
                "fell_over": result["end"]["fell_over"],
                "pushes": result["pushes"],
            }
        per_solution[recorded_name] = {
            "name": results[0]["name"],
            "tables": len(results),
            "separated_at_start": sum(result["start"]["separated"] for result in results),
            "separated_at_end": sum(result["end"]["separated"] for result in results),
            "gain": sum(result["gain"] for result in results),
            "fell_over": sum(result["end"]["fell_over"] for result in results),
            "tables_better": sum(result["gain"] > 0 for result in results),
            "tables_worse": sum(result["gain"] < 0 or result["end"]["fell_over"] > 0 for result in results),
            "tables_not_touched": sum(result["pushes"] == 0 for result in results),
            "pushes": sum(result["pushes"] for result in results),
            "arm_minutes": round(sum(result["arm_seconds"] for result in results) / 60, 1),
            "asked_by_side": pushes_by_where_the_hand_came_down(results),
        }
    totals = {
        "tables": len(table_numbers),
        "glasses": sum(arrangement["glasses"] for arrangement in arrangements_by_table.values()),
        "separated_at_start": sum(arrangement["separated"] for arrangement in arrangements_by_table.values()),
        "tables_already_separated": sum(
            arrangement["not_separated"] == 0 for arrangement in arrangements_by_table.values()
        ),
    }
    (RUNS / "results.json").write_text(
        json.dumps({**totals, "solutions": per_solution, "per_table": per_table}, indent=1)
    )
    (RUNS / "results.md").write_text(
        runs_summary_markdown(totals, per_solution, per_table, arrangements_by_table)
    )
    print("wrote", RUNS / "results.json", "and results.md")


def pushes_by_where_the_hand_came_down(results: list[dict]) -> dict:
    """How many pushes were asked for with the hand coming down in each place, and how each ended."""
    counts = {name: {MADE: 0, REFUSED: 0, REJECTED: 0} for name, _ in HAND_SIDES}
    for result in results:
        for push in result.get("push_list", []):
            if "hand_comes_down" in push:
                counts[push["hand_comes_down"]][push["outcome"]] += 1
    return counts


def runs_summary_markdown(
    totals: dict, per_solution: dict, per_table: dict, arrangements_by_table: dict
) -> str:
    recorded_names = list(per_solution)
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
    for recorded_name in recorded_names:
        totals_for_solution = per_solution[recorded_name]
        lines.append(
            f"| {recorded_name} "
            f"| {totals_for_solution['separated_at_start']} → {totals_for_solution['separated_at_end']} "
            f"| {totals_for_solution['gain']:+d} | {totals_for_solution['fell_over']} "
            f"| {totals_for_solution['tables_better']} | {totals_for_solution['tables_worse']} "
            f"| {totals_for_solution['tables_not_touched']} | "
            f"{totals_for_solution['pushes']} | {totals_for_solution['arm_minutes']} |"
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
    for recorded_name in recorded_names:
        sides = per_solution[recorded_name]["asked_by_side"]
        cells = [f"{cell[MADE]} of {sum(cell.values())}" for cell in sides.values()]
        lines.append(
            f"| {recorded_name} | "
            + " | ".join(cells)
            + f" | {sum(cell[REFUSED] for cell in sides.values())} | "
            f"{sum(cell[REJECTED] for cell in sides.values())} |"
        )
    lines += [
        "",
        "## Each table",
        "",
        "Each cell is the number of separated glasses at the end, and ✗ marks a glass that fell "
        "over. The second column is the number at the start.",
        "",
        "| Table | Start | "
        + " | ".join(totals_for_solution.removeprefix("solution_") for totals_for_solution in recorded_names)
        + " |",
        "|---|---|" + "---|" * len(recorded_names),
    ]
    for table_number, row in per_table.items():
        arrangement = arrangements_by_table[table_number]
        cells = []
        for recorded_name in recorded_names:
            result = row.get(recorded_name)
            cells.append(
                "" if result is None else f"{result['separated_at_end']}{' ✗' if result['fell_over'] else ''}"
            )
        lines.append(
            f"| [{table_number}]({table_number}/arrangement.png) "
            f"| {arrangement['separated']} of {arrangement['glasses']} | " + " | ".join(cells) + " |"
        )
    lines += [
        "",
        "## Making it again",
        "",
        "`make runs` in the problem folder chooses the tables, runs every solution on them and "
        "writes this page.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=("arrangements", "solve", "summary"))
    parser.add_argument("solution", nargs="?", choices=sorted(RECORDED))
    parser.add_argument("--tables", type=int, default=TABLES)
    arguments = parser.parse_args()
    if arguments.step == "arrangements":
        record_start_arrangements(arguments.tables)
    elif arguments.step == "solve":
        if arguments.solution is None:
            parser.error("solve needs a solution")
        record_solution_on_every_table(arguments.solution)
    else:
        write_runs_summary()


if __name__ == "__main__":
    main()
