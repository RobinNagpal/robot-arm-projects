"""Set results side by side, with a spread: ``python compare_results.py ../results/final-*.json``.

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


def load_table_rows(path: Path) -> list[dict]:
    saved = json.loads(path.read_text())
    return [row for run_rows in saved["tables"] for row in run_rows]


def totals_over_tables(table_rows: list[dict]) -> dict:
    tables_without_breakage = [row for row in table_rows if row["broken"] == 0]
    return {
        "tables": len(table_rows),
        "glasses": sum(row["glasses"] for row in table_rows),
        "start": sum(row["pickable_at_start"] for row in tables_without_breakage),
        "end": sum(row["pickable_at_end"] for row in tables_without_breakage),
        "gain": sum(row["pickable_at_end"] - row["pickable_at_start"] for row in tables_without_breakage),
        "broken": sum(row["broken"] for row in table_rows),
        "failed": sum(1 for row in table_rows if row["broken"] > 0),
        "separated": sum(1 for row in table_rows if row["outcome"] == "separated"),
        "said_done": sum(1 for row in table_rows if row["ended_by"] == "said done"),
        "arm_seconds": sum(row["arm_seconds"] for row in table_rows),
    }


def bootstrap_interval(
    table_rows: list[dict], total: str, redraws: int = 2000, seed: int = 0
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(redraws):
        redrawn = [table_rows[index] for index in rng.integers(0, len(table_rows), len(table_rows))]
        values.append(totals_over_tables(redrawn)[total])
    return float(np.percentile(values, 5)), float(np.percentile(values, 95))


def comparison_table(paths: list[Path]) -> str:
    lines = [
        "| solution | tables | glasses | gain in pickable (90 % range) | glasses broken (90 % range) "
        "| tables failed | said done | arm minutes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for path in paths:
        table_rows = load_table_rows(path)
        totals = totals_over_tables(table_rows)
        gain_range, broken_range = (
            bootstrap_interval(table_rows, "gain"),
            bootstrap_interval(table_rows, "broken"),
        )
        lines.append(
            f"| {path.stem} | {totals['tables']} | {totals['glasses']} "
            f"| {totals['gain']:+d} ({gain_range[0]:+.0f} to {gain_range[1]:+.0f}) "
            f"| {totals['broken']} ({broken_range[0]:.0f} to {broken_range[1]:.0f}) "
            f"| {totals['failed']} | {totals['said_done']} "
            f"| {totals['arm_seconds'] / 60:.1f} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(comparison_table([Path(p) for p in sys.argv[1:]]))
