"""Film each solution clearing the same table, for the comparison page.

The six solutions are compared by numbers on the page beside this file, and
numbers cannot say why a solution did what it did. A table of totals records
that three of the six freed no glass at all; it cannot show that one of them
never comes low enough to touch one while another comes down in the wrong
place. So each solution is also filmed, on one table, and the films are what
the pages link to.

    pixi run python results/films.py 01-one-fixed-nudge
    pixi run python results/films.py --all

**One solution to a run, and that is not a convenience.** Each solution folder
loads its own borrowed files under plain names -- several of them have a module
called ``borrowed`` -- so two solutions in one process would fight over those
names and whichever lost would be running somebody else's wiring. Running them
one at a time removes the question.

**The film is one fresh run and not a replay of a scored walk.** Nothing of a
walk is kept but its numbers, so a film has to be made by running the table
again. The two geometry solutions answer the same way every time and so film
exactly what they were scored doing. The other four draw from noise or come
from one of three fits, so a film of one of them is one run of that table: it
shows what the solution does, and its numbers are its own rather than the
middle of the three walks in the results file. Each film writes what it cost
on its own last picture, so no film can be read as a number it did not produce.

**Every film is given the whole queue's budget for its one table.** In a walk
the table would be handed whatever the earlier tables had left, which differs
for every solution and would make the six films six different arrangements.
Giving each the full budget asks one question of all of them: what does this
solution do with a table when nothing but its own judgement stops it.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from contract import Solution
from film import filmed_cell, save
from open_run import ARM_BUDGET, clear_table
from partners import TEST_SEEDS

HERE = Path(__file__).resolve().parent
PROBLEM = HERE.parent
# Beside problem 3's films, which the same pages link to for the same six
# methods on the problem before this one.
FILMS = PROBLEM.parent / "videos" / "04-clear-the-table"

# The one held-out table every solution is filmed on. It is chosen by a rule
# rather than by eye, and the rule has to answer two things.
#
# The table has to be one every solution reached. A solution is handed the
# tables of the queue in order until its arm time runs out, and the shortest
# walk of the six got through ten of them, so the film table is among the first
# ten or some of the films would be of a table that solution was never given.
#
# And the table has to be worth watching. On most of those ten the geometry
# reference looks round the table, finds no push it believes in, and says it is
# finished, which is honest and shows nothing. So the film table is the first
# of them on which the reference frees a glass. That is table 10001: the
# reference, the ranked chooser and the world model all separate it, and the
# three solutions that answer from a picture all cross it without coming down
# at a glass and then say it needs nothing more. Those are the two halves of
# this problem's result, on one table.
FILM_TABLE = 10_001

# What each film says about itself beyond the solution's own name. Two of the
# solutions are fitted three times over and walk the queue once with each fit,
# so a viewer holding one of their films against the spread in the results file
# needs to know which fit it is of.
NOTES = {
    "03-imitation-from-demonstrations": "fit 1 of 3",
    "06-smolvla-fine-tuned": "fit 1 of 3",
}


def _on_path(folder: str) -> Path:
    """Put one solution's folder on the import path and hand back where it is.

    The folder cannot be imported by name, because its name starts with a digit
    and so it is not a package. Appending rather than inserting keeps this
    problem's own examiner ahead of it, so a solution can never shadow the
    contract it is being run against.
    """
    where = PROBLEM / folder
    if str(where) not in sys.path:
        sys.path.append(str(where))
    return where


def one_fixed_nudge() -> Solution:
    """The geometry reference: one push a table, chosen by arithmetic."""
    _on_path("01-one-fixed-nudge")
    import nudge

    return nudge.OneFixedNudge()


def geometry_ranked() -> Solution:
    """The same loop with the fitted trees ordering the candidate pushes."""
    _on_path("02-geometry-ranked")
    from ranked import GeometryRanked

    return GeometryRanked()


def imitation() -> Solution:
    """The fitted gate and the chunked policy, both from the first seed.

    The two are fitted in one run under one seed, so a gate from one seed with a
    policy from another would be a pair nothing was measured on. ``run.py`` pairs
    them the same way.
    """
    folder = _on_path("03-imitation-from-demonstrations")
    import gate
    from clear import Imitation
    from wiring import pictures, policy

    return Imitation(
        policy.Imitator.load(folder / "weights" / "act-0"),
        gate.Decider.load(gate.saved(0), pictures.shrink),
    )


def a_world_model() -> Solution:
    """The reference's loop with a fitted model of what a push does, and a search."""
    _on_path("04-a-world-model")
    import learned

    # The search draws its candidate pushes, so the seed is what makes a film
    # of it repeatable.
    return learned.WorldModel(seed=0)


def fine_tuned() -> Solution:
    """The same borrowed model with one correction fitted on this problem's demonstrations."""
    _on_path("06-smolvla-fine-tuned")
    import torch
    import weights
    from fine_tuned import FineTuned, load

    torch.manual_seed(0)
    return FineTuned(load(weights.correction(0)))


BUILD: dict[str, Callable[[], Solution]] = {
    "01-one-fixed-nudge": one_fixed_nudge,
    "02-geometry-ranked": geometry_ranked,
    "03-imitation-from-demonstrations": imitation,
    "04-a-world-model": a_world_model,
    "06-smolvla-fine-tuned": fine_tuned,
}


def film(folder: str, seed: int, room: float, path: Path | None = None) -> Path:
    """Film one solution clearing one table, and write the video beside the others."""
    solution = BUILD[folder]()
    note = NOTES.get(folder, "")
    cell = filmed_cell(seed, f"{solution.name}{',  ' + note if note else ''}")
    result = clear_table(solution, seed, room, cell=cell)
    path = path or FILMS / f"{folder}.mp4"
    save(cell, path, result)
    return path


def film_run(folder: str, first: int, count: int, room: float) -> None:
    """Film ``count`` tables in a row and join them into one video.

    Each table is filmed on its own, as one film is, because a table's picture
    ends with what it cost and that line must belong to that table. The clips
    are joined without re-encoding, which is only safe because every clip is
    written by the same encoder with the same settings.
    """
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as scratch:
        seeds = range(first, first + count)
        clips = [film(folder, seed, room, Path(scratch) / f"{seed}.mp4") for seed in seeds]
        listing = Path(scratch) / "clips.txt"
        listing.write_text("".join(f"file '{clip}'\n" for clip in clips))
        target = FILMS / f"{folder}-{count}-tables.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c", "copy", str(target)],
            check=True,
        )
    print(f"{count} tables from {first} -> {target}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("solution", nargs="?", choices=sorted(BUILD), help="which one to film")
    parser.add_argument("--all", action="store_true", help="every solution, one after another")
    parser.add_argument("--table", type=int, default=FILM_TABLE, help="which table to film")
    parser.add_argument(
        "--tables", type=int, default=1, help="how many tables in a row to film, from --table, as one video"
    )
    parser.add_argument(
        "--room", type=float, default=ARM_BUDGET, help="arm seconds the one table may spend"
    )
    arguments = parser.parse_args()

    if arguments.all:
        # One process a solution, for the reason at the top of this file. The
        # work is done by this same script, called again.
        import subprocess

        for folder in sorted(BUILD):
            print(f"\n--- {folder}", flush=True)
            subprocess.run(
                [sys.executable, __file__, folder, "--table", str(arguments.table),
                 "--tables", str(arguments.tables), "--room", str(arguments.room)],
                check=True,
            )
        print(f"\nsix videos in {FILMS}")
        return

    if not arguments.solution:
        raise SystemExit("name a solution to film, or pass --all")
    if arguments.table < TEST_SEEDS:
        print(
            f"table {arguments.table} is below the held-out band, so this film is of a "
            "table the solutions were built on"
        )
    if arguments.tables > 1:
        film_run(arguments.solution, arguments.table, arguments.tables, arguments.room)
        return
    film(arguments.solution, arguments.table, arguments.room)


if __name__ == "__main__":
    main()
