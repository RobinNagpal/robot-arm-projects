"""Reporting a run: the spread over repeated runs, and the rows kept per table.

Shared by every problem that pushes glasses, so that a number is quoted the
same way in each of them. Nothing here knows what a push is or how a table is
marked; each problem's own ``scoring.py`` does that, and hands its summaries
here to be reported.

**A copy of this file must stay exactly as it is here**, for the reason
``common_bench.py`` gives.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def save_tables(save: Path, runs: list[list[dict]]) -> None:
    """Write the per-table rows beside a scorecard, one list per evaluation run.

    Kept in its own file rather than inside the scorecard so that results.json
    keeps the shape every solution has already committed. What it is for is
    choosing one table that stands for the whole run, which a film needs: a
    single table either finishes or it does not, so a film of an unusual table
    misrepresents the solution however honestly it was made.
    """
    beside = save.with_name(save.stem + "-tables.json")
    beside.write_text(json.dumps({"runs": runs}, indent=2) + "\n")
    print(f"per-table rows in {beside}")


def spread(each: list[dict]) -> dict:
    """The middle and the range of every number that every run reports.

    Keyed by a dotted path into the summary, so ``glasses_end.racked`` is the
    glasses racked. A count only some runs report is left out, because a
    spread over a different set of runs each time would not mean anything.
    """
    rows = [_flat(summary) for summary in each]
    shared = [key for key in rows[0] if all(key in row for row in rows)]
    return {key: _band_of([row[key] for row in rows]) for key in shared}


def _band_of(values: list[float]) -> dict:
    return {
        "median": round(float(np.median(values)), 3),
        "sd": round(float(np.std(values, ddof=1)) if len(values) > 1 else 0.0, 3),
        "least": round(min(values), 3),
        "most": round(max(values), 3),
    }


def _band(band: dict) -> str:
    return f"{band['median']:g} +/- {band['sd']:g} ({band['least']:g} to {band['most']:g})"


def _flat(summary: dict, prefix: str = "") -> dict[str, float]:
    """Every number in a summary, keyed by its dotted path."""
    out: dict[str, float] = {}
    for key, value in summary.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flat(value, f"{name}."))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            out[name] = float(value)
    return out
