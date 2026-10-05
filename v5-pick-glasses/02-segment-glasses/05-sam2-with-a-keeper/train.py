"""Fit whatever the chosen solution fits, and save it beside the borrowed weights.

    pixi run python train.py --solution sam --scenes 20
    pixi run python train.py --solution maskrcnn
    pixi run python train.py --solution amodal

The three commands are the same command. That is the point of this file: a
solution here is a module to call and the masks to train against, and those two
facts are all of what this file knows about any of the three. Which model gets
loaded, what is fitted, how long it takes and what it writes belong to the
module named in the table below, so `sam`, `maskrcnn` and `amodal` are
indistinguishable from here and stay comparable for that reason.

The table is the only place in this folder that knows the three names apart.
Nothing else anywhere may branch on which solution is running; a module is told
what to do, not who it is. `maskrcnn` and `amodal` name one module on purpose.
They are solutions 9 and 10, which differ only in what their masks are trained
against, so the difference between them is one flag in the table.

Every solution is fitted through the same three calls:

    fit(examples, *, amodal, save) -> what was fitted, to print
    load(save) -> a finder
    finder.find(picture, kind) -> the glasses in it, and the doubts

A solution is handed a picture and the kind of glass on the table, which the
cell is told, and never the list of glasses behind the picture. That is what
stops a solution reaching the truth at test time.

The scenes come from data.py, which only ever hands out seeds below the held-out
line, so training cannot reach a scene that `run.py` will score on.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from importlib import import_module
from types import ModuleType

import weights

import data


@dataclass(frozen=True)
class Solution:
    """One solution: the module that does the work, what its masks mean, and how much to fit on."""

    module: str
    amodal: bool  # whole outlines rather than the pixels the camera can see
    scenes: int  # the default, because running SAM costs far more than a training step


# The scene count is set so that fitting the keeper finishes in a few minutes
# on this machine, which is a wait you can sit through; --scenes trades more of
# that wait for accuracy. Running the borrowed model over a picture costs
# several seconds, and every scene is a picture from each station.
SOLUTIONS = {
    "sam": Solution("sam_keeper", amodal=False, scenes=12),
}

NAMES = " ".join(SOLUTIONS)


def chosen(name: str) -> Solution:
    """The solution called ``name``, or a refusal that says what the names are.

    Refused here, before a model is loaded: a mistyped name should cost a
    second rather than the several minutes it takes to load borrowed weights
    and draw the first scenes.
    """
    if not name:
        raise SystemExit(f"--solution is missing. Say which solution to work on, one of: {NAMES}")
    if name not in SOLUTIONS:
        raise SystemExit(f"--solution {name} is not a solution here. Use one of: {NAMES}")
    return SOLUTIONS[name]


def module(name: str) -> ModuleType:
    """The module behind a solution, imported when it is wanted and not before.

    Late on purpose. The two modules pull in different large libraries, so a run
    waits only for the one it uses, and a command that is going to refuse a bad
    name refuses it without loading anything at all.
    """
    wanted = chosen(name).module
    try:
        return import_module(wanted)
    except ModuleNotFoundError as missing:
        # Only when the solution's own file is the one missing. Anything the
        # module itself failed to import is that module's problem to show.
        if missing.name != wanted:
            raise
        raise SystemExit(f"{name} is the work of {wanted}.py, and there is no such file here") from None


def command(what: str) -> argparse.ArgumentParser:
    """The arguments both entry points take, since both commands look alike."""
    parser = argparse.ArgumentParser(description=what)
    parser.add_argument("--solution", default="", help=f"which solution to work on: {NAMES}")
    parser.add_argument(
        "--scenes", type=int, default=0, help="how many scenes to use; 0 means the solution's own default"
    )
    return parser


def how_many(given, fallback: int) -> int:
    """The scene count asked for, or the default, refusing a count nothing can be done with."""
    scenes = given.scenes or fallback
    if scenes < 1:
        raise SystemExit(f"--scenes {given.scenes}: there would be nothing to work on")
    return scenes


def main() -> None:
    given = command("Fit what one solution fits, on scenes from the simulator").parse_args()
    solution = chosen(given.solution)
    scenes = how_many(given, solution.scenes)

    save = weights.fitted(given.solution)
    hard = data.how_many_crowded(scenes)
    print(
        f"{given.solution}: fitting {solution.module} on {scenes} scenes "
        f"({scenes - hard} spawned, {hard} crowded), {len(data.stations())} pictures each"
    )
    started = time.time()
    fitted = module(given.solution).fit(data.training(scenes), amodal=solution.amodal, save=save)
    spent = time.time() - started

    # What was fitted is the module's to describe, so whatever it reports is
    # printed as it comes rather than interpreted here.
    for measure, value in (fitted or {}).items():
        print(f"  {measure}: {value}")
    if not save.exists():
        raise SystemExit(f"{given.solution} fitted for {spent:.0f}s and wrote no {save.name}")
    print(f"{given.solution}: fitted in {spent:.0f}s, saved to {save}")


if __name__ == "__main__":
    main()
