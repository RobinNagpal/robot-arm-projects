"""Set results side by side, with a spread: ``python report.py results/final-*.json``.

A result quoted without a spread is not a result. Each solution is walked once over the
same fifty tables, and what varies is which tables there are, so the spread is a bootstrap
over tables: tables are drawn with replacement, the figure is worked out again, and the
middle ninety in a hundred of two thousand such redraws is quoted.

The pickable count follows problem 4's rule: a table on which a glass went over is left
out of both ends, so that breaking a glass pays nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


def load(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    return [row for run in data["tables"] for row in run]


def stats(rows: list[dict]) -> dict:
    clean = [r for r in rows if r["broken"] == 0]
    return {
        "tables": len(rows),
        "glasses": sum(r["glasses"] for r in rows),
        "start": sum(r["pickable_at_start"] for r in clean),
        "end": sum(r["pickable_at_end"] for r in clean),
        "gain": sum(r["pickable_at_end"] - r["pickable_at_start"] for r in clean),
        "broken": sum(r["broken"] for r in rows),
        "failed": sum(1 for r in rows if r["broken"] > 0),
        "separated": sum(1 for r in rows if r["outcome"] == "separated"),
        "said_done": sum(1 for r in rows if r["ended_by"] == "said done"),
        "arm_seconds": sum(r["arm_seconds"] for r in rows),
    }


def interval(rows: list[dict], key: str, draws: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(draws):
        pick = [rows[i] for i in rng.integers(0, len(rows), len(rows))]
        values.append(stats(pick)[key])
    return float(np.percentile(values, 5)), float(np.percentile(values, 95))


def table(paths: list[Path]) -> str:
    lines = [
        "| solution | tables | glasses | gain in pickable (90 % range) | glasses broken (90 % range) "
        "| tables failed | said done | arm minutes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for path in paths:
        rows = load(path)
        s = stats(rows)
        g, b = interval(rows, "gain"), interval(rows, "broken")
        lines.append(
            f"| {path.stem} | {s['tables']} | {s['glasses']} | {s['gain']:+d} ({g[0]:+.0f} to {g[1]:+.0f}) "
            f"| {s['broken']} ({b[0]:.0f} to {b[1]:.0f}) | {s['failed']} | {s['said_done']} "
            f"| {s['arm_seconds'] / 60:.1f} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(table([Path(p) for p in sys.argv[1:]]))
