"""SmolVLA, exactly as it downloads, answering problem 4's contract.

Nothing is trained and nothing is fitted. The weights come from
``lerobot/smolvla_base``, the join between what they emit and this cell's jaw
is problem 3's ``joining.py`` held still, and all this file does is sit the
model in problem 4's conversation: a picture from the camera on the arm goes
in, a path for the jaw comes out, and ``stopping.Quiet`` reads the policy's
declaration that the table is finished out of the shape of its own answers.

**Why this is worth running again in problem 4 rather than copying problem 3's
number across.** The model was pretrained on real robots, and a real robot
almost always carries its camera on the wrist. Problem 3 handed it a picture
from a camera bolted above the table, which is a view it would hardly have met
in training. Problem 4 takes that camera away and gives it the one it is used
to. So problem 4's input is **closer to the model's home ground than problem
3's was**, and the question is whether that shows up in its answers.

Two things change between the two problems, and keeping them apart is the
whole care in reading the result.

1. **The picture**, which is the change this problem is about: a wrist view
   from the jaw's own pose instead of a fixed straight-down view.
2. **The state**, which changes as a side effect and not by choice. Problem 3
   asked the model with the jaw parked off the table above travel height, so
   the state clipped to the top of the reading's range at every ask on every
   table, and problem 3 measured that pinning as worth about 60 to 70 mm of
   height in the answers. Problem 4's ``Look.jaw`` is the last waypoint of the
   last path carried out, which ``joining.to_jaw`` has already clipped into
   the box the reading can express. So from the second answer on the state is
   a real pose inside its range rather than a number pinned at the edge, and
   it varies. That is not a tuning -- the contract says what ``Look.jaw`` is
   and this solution reads it -- but it means a lower answer here could be the
   wrist view or could be the unpinned state. ``pinned=True`` holds the state
   at problem 3's parked pose so that the two can be told apart.

**What this file does not do.** It does not rack a glass, because problem 4
racks nothing. And it does not count pushes, because problem 4 has no push
budget. Problem 3's ``clear.py`` did both, which is why it is not borrowed and
this file exists instead.

**What it does do, since the first measurement, is keep the hand clear.** The
first walk of the held-out queue broke twenty glasses, and the model's own page
measures how: its paths travel across the table at a height that looks like a
look and drags the fingers through the tops of the glasses, because the hand
hangs below the number a waypoint carries. The cell does not save a solution
from that -- its interlock refuses only a path into a glass the tipping rule
flatly refuses -- so the solution has to. Every answer now goes through
``keeping_clear``: a path that cannot be shown to reach only the glass it names
is raised to travel height, where it touches nothing and costs the same arm
time. The model still chooses every answer. What it no longer does is carry one
out that nobody can account for.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from borrowed import joining

from clock import crossing_seconds, path_seconds
from contract import Answer, Done, Look
from keeping_clear import Measured, Shoves, driven_home, kept_clear
from partners import PUSH_HEIGHT, TABLE_TOP_Z, Chunk, Seen, Waypoint
from stopping import A_WHISKER, Quiet, is_a_push

# How low a waypoint's own number has to be for the jaw to be down at pushing
# height, which is what the shape recorder counts. It is not the same question
# as whether a path could touch a glass -- the hand hangs below the number a
# waypoint carries, and ``stopping.is_a_push`` is what answers that.
REACHES_PUSH_HEIGHT = PUSH_HEIGHT + A_WHISKER

# Where problem 3's bench leaves the jaw between actions, in a waypoint's own
# numbers. The bench sets it in world metres at the end of every lift, and it
# is above travel height, which is why problem 3's state clipped to the top of
# its range at every ask. It is written down here for one purpose: the
# sensitivity check that holds the state there, so that problem 4's lower,
# varying state can be told apart from problem 4's different picture.
PARKED = (0.0, 0.5, 1.3 - TABLE_TOP_Z)


@dataclass
class Shape:
    """What the model's answers looked like, which is how problem 3 reports this solution.

    Problem 3 keeps these three numbers in its own ``clear.Tally``, beside
    counters for a push budget and a racking rule that problem 4 does not
    have. Only the three are wanted here, so they are kept on their own rather
    than borrowing a class most of which would be dead.

    They are the reading that matters for this solution. A model whose chunks
    never come down to the height a push happens at cannot move a glass
    however well aimed it is, so **how low a chunk comes** is the first
    number, and **how far across the table one chunk travels** is the second.
    The step between waypoints is the third, because the bench eats waypoints
    at a fixed rate, so how far apart they are is the speed being asked for.
    """

    lowest_mm: list[float] = field(default_factory=list)
    across_mm: list[float] = field(default_factory=list)
    step_mm: list[float] = field(default_factory=list)

    def saw(self, path: np.ndarray) -> None:
        """Note the shape of one answer, as an (n, 4) array of jaw waypoints."""
        steps = np.hypot(np.diff(path[:, 0]), np.diff(path[:, 1]))
        self.lowest_mm.append(1000 * float(path[:, 2].min()))
        self.across_mm.append(1000 * float(steps.sum()))
        self.step_mm.append(1000 * float(np.median(steps)))

    def add(self, other: Shape) -> None:
        self.lowest_mm += other.lowest_mm
        self.across_mm += other.across_mm
        self.step_mm += other.step_mm

    def summary(self) -> dict:
        """The middle and the ends of each, because one drawn answer is not a measurement."""
        out: dict = {"answers": len(self.lowest_mm)}
        for name, values in (
            ("lowest_mm", self.lowest_mm),
            ("across_mm", self.across_mm),
            ("step_mm", self.step_mm),
        ):
            if not values:
                continue
            out[f"{name}_median"] = round(float(np.median(values)), 1)
            out[f"{name}_least"] = round(float(np.min(values)), 1)
            out[f"{name}_most"] = round(float(np.max(values)), 1)
        if self.lowest_mm:
            # The share of answers that come down to the height a push happens
            # at. The test is the stopping rule's own, so the two agree by
            # construction rather than through two copies of one threshold.
            #
            # It is **not** the share of answers that could touch a glass, and
            # the measurement in the README says why. A waypoint's z is the
            # middle of the jaw and the hand reaches JAW_HALF_HEIGHT below
            # that, so a path well above the pushing height still drags the
            # hand through the top of a glass. Glasses here stand 97 to 224 mm
            # tall, so nothing under about 294 mm is clear of all of them.
            reaching = sum(1 for low in self.lowest_mm if low <= 1000 * REACHES_PUSH_HEIGHT)
            out["share_reaching_the_table"] = round(reaching / len(self.lowest_mm), 3)
        return out


class AsItDownloads:
    """The borrowed model, run as a problem 4 solution.

    One of these holds one loaded model and is used for a whole run of tables,
    because loading the weights is slow and nothing in the model changes
    between tables. ``begin`` is what forgets a table: it resets the policy's
    own action queue and starts a fresh ``Quiet``, so that a quiet spell at the
    end of one table cannot end the next one before it starts.

    ``pinned`` is the sensitivity check described at the top of this file. It
    hands the model problem 3's parked jaw pose as its state while the picture
    still comes from where the jaw really is. It is never the scored result.
    """

    name = "smolvla as it downloads"

    def __init__(self, model, pinned: bool = False) -> None:
        self.model = model
        self.pinned = pinned
        self.quiet = Quiet()
        self.shape = Shape()
        # The split of arm time between answers that could have touched a
        # glass and answers that could only have changed the view. See
        # ``_charge`` for why this is the only honest split here.
        self.look_seconds = 0.0
        self.push_seconds = 0.0
        # The glasses from the last look that showed any, for the glass index a
        # Chunk has to carry. See ``_glasses_for_the_record``.
        self.last_seen: tuple[Seen, ...] = ()
        # Why answers had to be raised to travel height, counted by reason. It
        # is the one thing worth reporting about the check: a model whose every
        # answer is raised is a model proposing nothing anybody can account for,
        # and the counts say which of the reasons it fails on.
        self.raised: Counter = Counter()
        self.pulled_onto_the_heights = 0
        self.driven = 0
        self.driven_mm = 0.0
        # What this solution has tried on each glass of the table in front of it.
        # Every glass this cell draws is one the tipping rule is unsure about, so
        # a shove this solution has watched move a glass is the only evidence it
        # can have that the glass slides rather than tips.
        self.shoves = Shoves()
        # Every glass measured on this table, which is more than the glasses in
        # the last picture: the camera rides on the arm, so a neighbour this
        # solution measured two answers ago may be out of frame while a path is
        # drawn at the glass beside it. The clearance check is run against all
        # of them.
        self.measured = Measured()
        self.out_of_frame = 0

    def begin(self, seed: int) -> None:
        self.model.reset()
        self.quiet = Quiet()
        self.last_seen = ()
        # A new table is a table nothing has been tried on, and nothing measured.
        self.shoves = Shoves()
        self.measured = Measured()

    def answer(self, look: Look) -> Answer:
        """One forward pass, read as a path for the jaw -- or the end of the table.

        The answer is drawn and not computed: the policy denoises from fresh
        noise every time, so the same picture asked twice gives two different
        paths. That is the only randomness this solution has, and it is why a
        run of this solution is not a measurement and three are.
        """
        path = self.model.ask(look.picture, self._state_pose(look.jaw))
        self.shape.saw(path)
        if look.seen:
            self.last_seen = look.seen
        self.shoves.saw(self.last_seen)
        self.measured.saw(look.seen)
        known = self.measured.all() or self.last_seen
        self.out_of_frame += len(self.measured.out_of_frame(look.seen))
        chunk = joining.chunk_for(path, list(self._glasses_for_the_record()))
        # The glass the path is aimed at, in so far as it is aimed at anything:
        # ``chunk_for`` reads back the glass the jaw comes nearest to while low
        # enough to touch it. That read-back is bookkeeping for the record, so
        # the check treats it as a claim to be tested rather than as a decision:
        # a path that does not actually reach that glass, or that would reach a
        # second one on the way, is raised like any other.
        tested = self.shoves.tested(known)
        kept = kept_clear(chunk, known, target=chunk.glass, tested=tested)
        chunk, why = kept.chunk, kept.why
        if why:
            self.raised[why] += 1
        self.pulled_onto_the_heights += kept.pulled
        if not why and chunk.glass is not None and chunk.glass in tested:
            # A shove at a glass this solution has watched move is a push at the
            # task, and a push at the task is meant to give the glass room.
            # ``driven_home`` says why the distance is arithmetic: one shove moves
            # a glass about as far as a drawn path's own error, so a drawn shove
            # that stops at the glass frees nothing. A shove at a glass nothing
            # has tested is left as it was, because that is how the evidence is
            # got.
            # How far it may be driven is this solution's own evidence: the
            # distance it has already watched this glass slide. ``driven_home``
            # says why, and the measurement behind it is that every glass these
            # solutions lost went over on a carried-on push.
            aimed_at = next((g for g in known if g.id == chunk.glass), None)
            chunk, moved = driven_home(
                chunk,
                known,
                chunk.glass,
                tested=tested,
                no_further_than=self.shoves.moved(aimed_at) if aimed_at else None,
            )
            self.driven += 1
            self.driven_mm += 1000 * moved
        # An answer left as a shove at the glass it names is one this solution
        # really made at that glass, so the next look's reading of where that
        # glass stands is this solution's own evidence about whether it slides.
        if not why and chunk.glass is not None:
            self.shoves.aimed_at(chunk.glass)

        # The tallest glass this solution has measured is what decides whether a
        # path could touch anything, because the hand hangs below the number a
        # waypoint carries and a path clearing the pushing height can still sweep
        # a tall glass.
        self.quiet.saw(chunk, self._tallest_seen())
        if self.quiet.finished:
            # The policy has gone quiet for long enough to be taken at its
            # word. This last path is not carried out: it would not touch a
            # glass, so following it would spend arm seconds to change nothing.
            return Done(why=self.quiet.why)

        self._charge(chunk, look.jaw)
        return chunk

    # ------------------------------------------------------------------ the bookkeeping

    def _tallest_seen(self) -> float:
        """The tallest glass this solution has measured on this table, or nothing.

        Nothing rather than a guess: ``is_a_push`` falls back to the gripper's
        own working height, and no glass measurement is written down anywhere
        in this project.
        """
        return max((glass.height for glass in self.last_seen), default=0.0)

    def _state_pose(self, jaw: Waypoint) -> Waypoint:
        """The pose the model is told the jaw is in, which is the real one unless pinned."""
        if not self.pinned:
            return jaw
        return Waypoint(x=PARKED[0], y=PARKED[1], z=PARKED[2], heading=jaw.heading)

    def _glasses_for_the_record(self) -> tuple[Seen, ...]:
        """Something for ``chunk_for`` to name the path after.

        ``Chunk.glass`` is which glass a path is meant to move, and the model
        was never asked. Problem 3 reads it back off the path afterwards -- the
        glass the jaw comes nearest to while low enough to touch it -- and
        nothing is planned with it. In problem 4 nothing scores it either, so
        it is pure bookkeeping, and the brief says as much.

        The one new wrinkle is that a look can show no glasses at all, which
        could not happen in problem 3: the camera is on the arm now and may be
        pointing at bare table. ``chunk_for`` needs a non-empty list, so the
        last look that showed something is used instead, and failing that glass
        zero. Glass zero is always a safe name here because problem 4 never
        racks a glass, so every glass it drew is still on the table -- a
        toppled one included -- for the whole of the table.
        """
        if self.last_seen:
            return self.last_seen
        return (Seen(id=0, x=0.0, y=0.0, height=0.0, widest=0.0, foot=0.0, standing=True),)

    def _charge(self, chunk: Chunk, jaw: Waypoint) -> None:
        """Keep this solution's own split of the arm time it is about to spend.

        The cell charges the truth and ``TableResult.arm_seconds`` reports it.
        This is the solution's own accounting of *why* the arm moved, which the
        cell cannot know, and it is a weaker reading here than it is for the
        geometry reference. The geometry reference moves the arm either to see
        or to push and knows which. This solution never says: every answer is
        one path, and the jaw's new pose is where the next picture is taken
        from whether or not the path touched anything. So the split is by the
        one thing that can be read off a path, which is whether it comes down
        to the height a push happens at.

        **Read it as that and not as more.** A path on the looking side is a
        path the stopping rule counts as quiet, and the measurement shows that
        such a path can still knock a glass over, because the hand hangs
        JAW_HALF_HEIGHT below the z a waypoint names. So this says how the arm
        time divided by the shape of the answers, not that the looking seconds
        were spent harmlessly.
        """
        seconds = crossing_seconds(jaw, chunk.waypoints[0]) + path_seconds(chunk)
        if is_a_push(chunk, self._tallest_seen()):
            self.push_seconds += seconds
        else:
            self.look_seconds += seconds
