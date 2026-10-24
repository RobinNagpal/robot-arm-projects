"""Every solution of problem 4 by the name the tools know it by, and how a new one is built.

The tools that run a solution, such as the evaluation, the films and the per-table records,
are given a solution's name on the command line. This file turns that name into a solution,
so that every tool builds a solution the same way and none of them needs its own copy of the
steps.

**Why the classes are named by strings.** Each solution lives in its own folder, which pixi
puts on the Python path, and some of them import large libraries such as PyTorch and
LeRobot. Importing every solution at the top of this file would load all of those libraries
to run even the geometry solution, so a solution's module is imported only when that
solution is built.

**A checked solution** is a learned solution wrapped in the world model's safety check
(``04-world-model/safety_check.py``). The catalogue says which solution is wrapped, rather
than holding a separate class for each pairing.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from examiner.examining.solution_contract import Solution


@dataclass(frozen=True)
class SolutionInCatalogue:
    """Where a solution's class is, and whether the safety check wraps it."""

    module_name: str  # the solution's own file, without ``.py``
    class_name: str  # its class, built with the weights file when one is given
    checked_by_world_model: bool = False


SOLUTION_CATALOGUE = {
    "geometry": SolutionInCatalogue("geometry_reference", "GeometryReference"),
    "geometry-ranked": SolutionInCatalogue("geometry_ranked", "GeometryRanked"),
    "imitation": SolutionInCatalogue("imitation", "ImitationSolution"),
    "world-model": SolutionInCatalogue("world_model", "WorldModelSolution"),
    "reinforcement": SolutionInCatalogue("reinforcement_learning", "ReinforcementLearningSolution"),
    "vla": SolutionInCatalogue("smolvla_fine_tuned", "SmolVLASolution"),
    "imitation-checked": SolutionInCatalogue("imitation", "ImitationSolution", checked_by_world_model=True),
    "reinforcement-checked": SolutionInCatalogue(
        "reinforcement_learning", "ReinforcementLearningSolution", checked_by_world_model=True
    ),
    "vla-checked": SolutionInCatalogue("smolvla_fine_tuned", "SmolVLASolution", checked_by_world_model=True),
}


@dataclass(frozen=True)
class SolutionChoice:
    """Which solution to build: its name in the catalogue, its weights, and settings to change on it.

    It is a description and not a solution, so an evaluation of several runs can build a fresh
    solution for every run from it.
    """

    name: str
    weights: Path | None = None  # the solution's own weights file; its default one when ``None``
    # (attribute, value) pairs set on the built solution, for tuning on training tables
    settings_to_change: tuple[tuple[str, float], ...] = ()

    def build_new_solution(self) -> Solution:
        entry = SOLUTION_CATALOGUE[self.name]
        solution_class = getattr(importlib.import_module(entry.module_name), entry.class_name)
        solution = solution_class(self.weights) if self.weights else solution_class()
        if entry.checked_by_world_model:
            from safety_check import SafetyCheckedSolution

            solution = SafetyCheckedSolution(solution)
        for attribute, value in self.settings_to_change:
            setattr(solution, attribute, value)
        return solution
