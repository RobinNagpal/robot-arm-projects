"""Film a table being cleared, to see by eye what the arm did and what it could see.

A film is not a measurement and it cannot become one: the table is scored in
the world ``bench.py`` builds, and everything drawn here is drawn in a second
world of its own. What a film is for is the one question a scorecard cannot
answer, which is *why* a number came out as it did. A solution that freed no
glass could be aiming at nothing, or aiming at the wrong glass, or aiming well
and never coming low enough to touch one, and those three read identically in
a table of totals.

**The recording itself is borrowed from problem 3 rather than written again.**
Problem 3's ``bench/film.py`` already holds the second world with the real hand
drawn in it, the camera that stands off the arm's side of the table, the
writing drawn over each frame and the pipe that hands frames to ffmpeg. All of
that is about recording a table and nothing about which problem the table
belongs to, so this file subclasses it and changes only what problem 4 shows.
``partners.py`` is where the rest of the debt to problem 3 is written down, and
this is the same debt.

Three things make a problem 4 film different from a problem 3 film, and all
three come from the two assumptions problem 4 takes away.

**The arm's own camera is in the corner of the picture.** Problem 3 hands a
solution the whole table from a camera bolted above it, so there is nothing to
show: what the solution knows is what the viewer can see. Here the solution
knows only the patch of table its own camera caught, and a viewer who cannot
see that patch cannot tell a bad choice from a choice made without the glass in
view. So each frame carries the standing view of the table and, in the corner,
the last picture the solution was actually given. They are the same scene from
two camera positions, which is the one case where two panels belong in one
picture.

**Nothing is picked up, so no pick is drawn.** Problem 3 racks a glass at the
end of a table and its film draws a stand-in for that pick. Problem 4 racks
nothing: it marks the arrangement the solution left behind. The inherited
drawing is therefore never reached, because nothing in problem 4 calls
``take``.

**The captions are read off the conversation, not off a script.** Problem 4 is
a loop of looks and answers, so a film has to say which answer is on screen and
what kind of answer it is. ``FilmedCell`` below works that out from the calls
the loop makes to the cell, and it does not change the loop: ``view`` is one
look, ``truth`` is the interlock being consulted about one answer, and
``follow`` is a path being carried out. An answer whose ``truth`` was consulted
and whose path was never followed is an answer the cell refused, and a refused
path moves the arm nowhere, so the film holds the picture for a moment and says
so. Without that the film would jump and a viewer would read a solution's worst
habit -- asking for paths the cell will not take -- as the film skipping.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import cv2
import numpy as np

import partners
from contract import TableResult
from open_run import OpenCell
from partners import Chunk, Record, Seen, Waypoint
from stopping import is_a_push


def _module(name: str, path: Path) -> ModuleType:
    """One file, loaded from its path under a name of this file's choosing.

    Problem 3's film module is called ``film``, and so is this one. Both
    problems' bench folders are on the import path and this problem's comes
    first, so a plain ``import film`` here would find this file rather than the
    one it means. Loading by path under another name is the only way to have
    both, and it is the pattern the solutions' own ``borrowed.py`` files use.
    """
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pushing = _module("pushing_film", partners.PUSHING / "bench" / "film.py")

# How big the arm's own picture is drawn in the corner, and how far it is kept
# from the edges. The picture is square, as the camera's is, and it is drawn
# smaller than it is rendered so that the table it sits on top of is still the
# larger half of the frame.
INSET = 320
MARGIN = 24
# What the corner picture is called. Short, because it is written over the
# table and a label that needed two lines would be prose the film has to
# carry rather than a name for what the viewer is looking at.
CORNER = "the arm's own camera"

# How long the film holds still on a path the cell would not take, and how many
# of those moments it keeps.
#
# A refusal has to be shown, because the arm does not move for one and the film
# would otherwise skip it. It also has to be rationed. A policy that computes
# the same refused answer over and over is stopped by the cap on answers rather
# than by the clock, and that cap is read off the arm time left, so it can run
# into the thousands. Filming each of them would bury the table under a quarter
# of an hour of a still picture. So the first few are filmed and the rest are
# counted, which is what the number printed when the film is saved is for.
REFUSAL_BEAT = 0.25
REFUSALS_FILMED = 40


def outcome_lines(result: TableResult) -> tuple[str, str]:
    """What the table came to, for writing on the last picture.

    Every number in it is read off the result the loop handed back, so the end
    of a film says exactly what the scorecard says about the same table.
    """
    short = result.glasses - result.pickable_at_end
    if result.failed:
        glasses = "glass" if result.toppled == 1 else "glasses"
        what = f"{result.toppled} {glasses} went over: the table is forfeit"
    elif result.separated:
        what = "separated: every glass has room, and none went over"
    elif result.said_done:
        what = f"said done, {short} of {result.glasses} glasses still short of room"
    else:
        what = f"the clock ran out, {short} of {result.glasses} short of room"
    spent = (
        f"{result.arm_seconds:.0f} arm s, {result.answers} answers, "
        f"{result.pickable_at_start} of {result.glasses} had room at the start"
    )
    return what, spent


class FilmedBench(pushing.FilmedBench):
    """Problem 3's filmed bench, labelled for problem 4 and with the arm's view in the corner."""

    # The film's first frame is written by the inherited constructor, before
    # it returns, so everything that frame says has to be true before then.
    # These are the defaults it says it with: no picture from the arm's camera
    # yet, because nothing has been looked at, and nothing being done yet.
    inset: np.ndarray | None = None
    said: str = "before the first look"

    def __init__(self, seed: int, approach: str, glasses: list) -> None:
        # Set before the recording starts, for the reason above. Which table
        # this is comes off the drawn table rather than being worked out from
        # the seed as problem 3 works it out, because problem 4 draws its own:
        # one kind of glass to a table, and three to five of them. Worked out
        # from the argument rather than from ``self.glasses``, which the
        # inherited constructor has not set yet.
        self.approach = approach
        kind = glasses[0].kind.replace("_glass", "").replace("_", " ")
        self.table_is = f"table {seed}: {len(glasses)} {kind} glasses"
        super().__init__(seed, approach, glasses)

    # ------------------------------------------------------------ what is drawn

    def view(self, sync: bool = True) -> np.ndarray:
        """The standing view of the table, with the arm's own picture on top of it."""
        frame = super().view(sync)
        if self.inset is not None:
            self._draw_inset(frame)
        return frame

    def _capture(self, extra: str = "", sync: bool = True) -> np.ndarray:
        """One frame, with what is happening written on it.

        Problem 3 writes which table it is on the top line beside the name of
        the solution, and here that line is too long to fit: this problem's
        names are longer, and two of its films have to say which of three fits
        they are of. So which table it is moves to the bottom, where it reads
        as what it is -- standing context rather than something that changes --
        and the top is left for the solution and the answer it is giving.
        """
        frame = self.view(sync)
        for row, text in enumerate([self.approach, extra or self.said, *self.note]):
            self._ink(frame, text, (20, 46 + 44 * row), 1.0)
        self._ink(frame, self.table_is, (20, frame.shape[0] - 24), 0.7)
        self._write(frame)
        return frame

    def _draw_inset(self, frame: np.ndarray) -> None:
        """Put the last picture the solution was given into the corner of the frame.

        The two views are kept the same way round as the table itself, so the
        corner can be read against the picture it sits on: both look across the
        table from the arm's side. The camera's picture is held until the
        solution looks again, which means it is on screen for the whole of the
        answer it was decided from.
        """
        picture = cv2.resize(self.inset[:, :, ::-1], (INSET, INSET), interpolation=cv2.INTER_AREA)
        top = frame.shape[0] - INSET - MARGIN
        left = frame.shape[1] - INSET - MARGIN
        frame[top : top + INSET, left : left + INSET] = picture
        edge = (left - 2, top - 2), (left + INSET + 1, top + INSET + 1)
        cv2.rectangle(frame, *edge, (255, 255, 255), 2)
        self._ink(frame, CORNER, self._centred(CORNER, left, top - 12))

    @staticmethod
    def _centred(text: str, left: int, baseline: int, scale: float = 0.75) -> tuple[int, int]:
        """Where to start a line so that it sits centred over the corner picture.

        Measured rather than guessed, because a line written from the corner's
        own left edge is wider than the corner and runs off the frame.
        """
        width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)[0][0]
        return left + (INSET - width) // 2, baseline

    @staticmethod
    def _ink(frame: np.ndarray, text: str, place: tuple[int, int], scale: float = 0.75) -> None:
        """One line of writing, drawn twice so that it reads over a light table and a dark one."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, text, place, font, scale, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(frame, text, place, font, scale, (255, 255, 255), 2, cv2.LINE_AA)

    # ------------------------------------------------------------- the recording

    def beat(self, seconds: float) -> None:
        """Hold the picture while the arm stands still, so a moment can be read.

        Every other frame of a film is written from inside a motion, and the
        bench is already charged for the time those take. This one is not, so
        it is charged here, the way problem 3's film charges the pick it draws.
        A frame written while nothing moves must not be counted as the solution
        thinking.
        """
        started = time.perf_counter()
        for _ in range(max(1, round(seconds * pushing.FPS))):
            self._capture()
        self.seconds += time.perf_counter() - started

    def save(self, path: Path, outcome: str = "", also: tuple[str, ...] = ()) -> None:
        """Finish the video, holding the last picture with the outcome written on it.

        This is problem 3's ``save`` with one line added, and the line is why it
        is written again: what a problem 4 table came to takes two sentences --
        what happened, and what it cost -- and the borrowed version clears the
        second before it draws the first.
        """
        self.note = also
        for _ in range(int(pushing.HOLD * pushing.FPS)):
            self._capture(outcome)
        self._pipe.stdin.close()
        if self._pipe.wait() != 0:
            raise RuntimeError("ffmpeg could not write the film")
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(self._file, path)
        shutil.rmtree(self._file.parent, ignore_errors=True)
        self.renderer.close()


@dataclass
class FilmedCell(OpenCell):
    """The cell the loop talks to, with a film attached. The same cell in every other way.

    It answers the ``Cell`` protocol by handing every call to ``OpenCell``, so
    what the solution is shown and what the table is scored on are untouched.
    What it adds is the caption, and the caption is worked out from the order
    the loop calls it in rather than from anything the loop was changed to tell
    it. That order is fixed by ``open_run.clear_table``: one ``view`` a look,
    then ``truth`` if the answer was a path, then ``follow`` if the cell's
    interlock allowed it.
    """

    bench: FilmedBench
    # How many looks have been taken, which is also how many answers have been
    # given, because the loop asks for exactly one answer a look.
    answers: int = 0
    # The tallest glass the solution has been shown. The rule that tells a push
    # from a look needs it, because a path can clear the jaw's own pushing
    # height and still sweep through a glass standing taller than it.
    tallest: float = 0.0
    asked: bool = False  # the interlock was consulted about the last answer
    followed: bool = False  # and the path was then carried out
    refusals: int = 0
    filmed_refusals: int = 0
    # How many of the answers carried out were pushes rather than moves made
    # only to see. It is the reading problem 4 turns on -- looking is most of
    # what the task is once the overhead camera is gone -- and a film is where
    # it can be checked against what the arm is seen doing.
    pushes: int = 0

    def view(self, jaw: Waypoint) -> tuple[np.ndarray, tuple[Seen, ...]]:
        if self.asked and not self.followed:
            # The loop asked for the true table and then never followed the
            # path, which happens for one reason: the cell's own interlock
            # stopped it. The glass it stopped for is not something the film
            # can know, because the loop never hands the path over.
            self._refused("a glass on the path would tip rather than slide")
        picture, seen = super().view(jaw)
        self.answers += 1
        self.asked = self.followed = False
        self.bench.inset = picture
        self.tallest = max(self.tallest, *(glass.height for glass in seen), 0.0)
        self.bench.said = (
            f"look {self.answers}: {len(seen)} of {self.glasses()} glasses in the picture"
        )
        return picture, seen

    def truth(self) -> tuple[Seen, ...]:
        self.asked = True
        return super().truth()

    def follow(self, chunk: Chunk) -> Record:
        push = is_a_push(chunk, self.tallest)
        self.bench.said = self._what(push)
        try:
            record = super().follow(chunk)
        except ValueError as refusal:
            # The bench would not take the path at all: off the table, outside
            # the heights the jaw rides at, or too long. The arm never moved,
            # so this is a refusal like the interlock's, and it is reported
            # here because the reason is in hand only here.
            self.asked = False
            self._refused(str(refusal))
            raise
        self.followed = True
        # Counted here and not where the answer was read, because an answer the
        # bench would not take moved no glass and must not be counted as a push.
        self.pushes += push
        return record

    def _what(self, push: bool) -> str:
        """Whether this answer is a push or a look, in the stopping rule's own words.

        It is the same question ``stopping.is_a_push`` answers for the solutions
        that have no word for "finished", and it is asked through that function
        rather than written again, so that a film cannot call an answer a push
        that the scorecard counted as quiet.
        """
        if push:
            return f"answer {self.answers}: a push, the hand comes down to the glasses"
        return f"answer {self.answers}: a look, the hand stays above them"

    def _refused(self, why: str) -> None:
        """Film a moment of the arm not moving, because the cell would not take the path."""
        self.refusals += 1
        self.bench.said = f"answer {self.answers}: refused, so the arm does not move"
        self.bench.note = tuple(textwrap.wrap(why, pushing.LINE_LENGTH))
        if self.filmed_refusals < REFUSALS_FILMED:
            self.filmed_refusals += 1
            self.bench.beat(REFUSAL_BEAT)
        self.bench.note = ()

    def close(self) -> None:
        """Let go of the arm's camera. The film's own renderer is closed when it is saved."""
        self.camera.close()


def filmed_cell(seed: int, approach: str) -> FilmedCell:
    """The cell for one table, with a film of it. Built as ``open_run.open_cell`` builds its own.

    The camera on the arm is pointed at the scored world and not at the world
    the film draws, so the pictures the solution is given are the pictures it
    would have been given had nothing been filmed.
    """
    import tables
    import wrist

    bench = FilmedBench(seed, approach, tables.table(seed))
    return FilmedCell(bench, wrist.WristCamera(bench), wrist.in_picture)


def save(cell: FilmedCell, path: Path, result: TableResult) -> None:
    """Finish the film of one table, with what the table came to written on it."""
    what, spent = outcome_lines(result)
    cell.bench.save(path, what, (spent,))
    cell.close()
    # The outcome is printed as well as written on the last picture, because the
    # comparison page has a column for how each film ends and that column has to
    # be read from somewhere other than watching six videos.
    print(
        f"filmed {path.name}: {result.answers} answers, {cell.pushes} of them pushes, "
        f"{cell.refusals} refused, {result.arm_seconds:.0f} arm s, {what}"
    )
