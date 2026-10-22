"""Every push the geometry allows, kept as a set rather than chosen from.

The enumeration itself is not written here. It is solution 1's, in
``../01-one-fixed-nudge/plan.py``, imported below as ``nudge``: the heading
sweep, the stepped travel, the four tests, the tipping rule and the shortfall
of room all come from there unchanged. The only thing this module adds is that
it keeps the survivors instead of applying the printed rule to them, because
the survivors are what the ranker is handed.

One property of that enumerator decides what the ranker can learn, so it is
worth repeating here: ``nudge.along`` stops a heading at the first travel that
gives the glass room. So a heading offers at most one job-finishing push, and
every job-finishing push in a group lands just past the same contour --- the
line where the glass has its room, plus ``nudge.AIM_MARGIN``. ``spread.py``
measures what that does to the labels.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from bench import Push, Seen, has_room


def _enumerator():
    """Solution 1's ``plan.py``, loaded from its own folder.

    By file rather than by putting that folder on the path. Its name starts
    with a digit, so it is not a package and cannot be imported from; and a
    folder on the path brings its ``run.py`` with it, which would quietly
    shadow this folder's.
    """
    path = Path(__file__).resolve().parent.parent / "01-one-fixed-nudge" / "plan.py"
    spec = importlib.util.spec_from_file_location("one_fixed_nudge_plan", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


nudge = _enumerator()

HEADINGS = np.arange(nudge.HEADINGS) * (2 * math.pi / nudge.HEADINGS)


@dataclass(frozen=True)
class Candidate:
    """One safe push, with the two things the geometry already knows about it."""

    push: Push
    glass: Seen
    freeing: bool  # the destination has room, so this push finishes the job
    eased: float  # metres of the table's shortfall of room this destination removes


def survivors(seen: list[Seen], skip: set[int]) -> tuple[list[Candidate], dict[int, str]]:
    """Every safe push on the table, and why the glasses with none have none.

    The same loop solution 1's ``choose`` runs, with the choosing taken out.
    ``skip`` is glasses not to push again.
    """
    kept: list[Candidate] = []
    why: dict[int, str] = {}
    before = nudge.shortfall([(g.x, g.y, g.widest) for g in seen])
    for glass in seen:
        if glass.id in skip:
            continue
        if nudge.slides(glass) == "no":
            why[glass.id] = "tips before it slides"
            continue
        others = [o for o in seen if o.id != glass.id]
        layout = [(o.x, o.y, o.widest) for o in others]
        pushes = [p for heading in HEADINGS for p in nudge.along(glass, others, heading)]
        if not pushes:
            why[glass.id] = "nowhere clear to push it to"
            continue
        for push in pushes:
            eased = before - nudge.shortfall([*layout, (*push.aim, glass.widest)])
            freeing = has_room(*push.aim, layout, nudge.AIM_MARGIN)
            # A push that neither frees a glass nor loosens the table by a
            # worthwhile amount is not offered, as solution 1 does not offer it.
            if freeing or eased >= nudge.LEAST_EASING:
                kept.append(Candidate(push, glass, freeing, float(eased)))
    return kept, why


def rule_choice(kept: list[Candidate]) -> Candidate | None:
    """The printed rule solution 1 uses: the shortest push that frees a glass.

    Failing that, the push that most loosens the table. This is what the model
    has to beat, and what the solution falls back to with no model.
    """
    freeing = [c for c in kept if c.freeing]
    if freeing:
        return min(freeing, key=lambda c: c.push.travel)
    if kept:
        return max(kept, key=lambda c: (c.eased, -c.push.travel))
    return None
