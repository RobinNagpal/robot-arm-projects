"""Problem 4 with a learned model of what a push does: look, search, push, say done.

This is problem 3's solution 4 ported to problem 4. The model and the search
are its own -- a push goes in, what it will do to the whole table comes out,
and the cross-entropy method asks about a few thousand of them before the arm
moves. Everything about *seeing* is the geometry reference's, borrowed and not
written again: the ring of stands, the belief merged across looks, a push
written out as waypoints, and the rule that a table may only be declared
finished after a walk round the whole ring.

The reference says in as many words that this is how it expected to be reused:
``_choose`` is a method there rather than a call written into the loop,
"because the next solution in this problem is this same loop with a different
chooser". This is that chooser, and ``_decide`` is overridden rather than
``_choose`` for one reason, which is the interesting one.

**What the reference measures with the arm, this solution predicts.** A chunk
of waypoints cannot feel its way into a glass, so somebody has to say how far
the fingertips must travel before they meet it -- and the jaw meets a glass at
the jaw's own height, where a stemmed glass is its stem. The reference finds
out by poking: drive five millimetres deeper, look, and see whether the glass
moved, over and over, and every round of it is arm seconds. Here that distance
is an input the model has an opinion about, so there is no ranging push and no
test push, and the whole of ``_decide``'s probing branch goes away. That is
where this solution expects to win its arm time back.

It is also where it expects to lose glasses. The reference's test push is a
measurement, and nothing this model says is. The only thing between this
solution and a toppled glass is the model's own estimate of the chance, and in
problem 4 a toppled glass costs the whole table.

**Two ways of running it, and the second is the one problem 4 invites.** With
``predicting=False`` the arm looks after every push, as the reference does.
With ``predicting=True`` it does not: it writes what the model said would
happen into its own belief and pushes again from there, so several pushes are
planned from one look. Problem 3 could not tell the two apart, because seeing
the whole table was free there. Here looking costs arm seconds, so whether
believing the model is cheaper than looking is a question with a number for an
answer. ``measure.py`` measures both.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import replace

import encoding
import numpy as np
import search
from borrowed import WEIGHTS, jaw_paths, nudge
from push_model import Ensemble

from contract import Answer, Done, Look
from keeping_clear import why_not_clear
from open_run import interlocked
from partners import Seen, in_zone

import plan


class WorldModel(nudge.OneFixedNudge):
    """The geometry reference's loop, with the model and the search deciding."""

    name = "a world model"

    # What the test push has to show before a long push is made. The reference
    # asks the glass to *keep up* with the probe, because by then it has already
    # poked the glass and taken up the slack. This solution makes no ranging
    # push, so its test push is the first thing to touch the glass and the first
    # millimetre or two go into taking up contact. So the question here is
    # problem 3's own: did it move at all?
    kept_up = plan.PROBE_MOVED

    def __init__(
        self, model: Ensemble | None = None, *, predicting: bool = False, seed: int | None = None
    ) -> None:
        self.model = Ensemble.load(WEIGHTS) if model is None else model
        self.predicting = predicting
        # The search draws its candidates, so it carries a generator of its own.
        #
        # Left unseeded by default, and that is the right way round. This
        # solution draws its answer rather than computing it, so one run is not
        # a measurement of it, and ``examiner/judging.py`` walks the queue three
        # times and reports the spread -- which a solution seeded the same way
        # every time would report as zero while still varying. A caller that
        # wants one run repeated exactly passes a seed, and ``measure.py``
        # does, so the numbers in the README can be reproduced.
        self.generator = np.random.default_rng(seed)
        # What the model believed about every push this solution answered with,
        # over every table. See ``believed``.
        self.risked: list[dict] = []
        # Pushes the search chose and the clearance check would not let through,
        # counted by reason over the whole run. A model that keeps proposing a
        # push across a neighbour is worth knowing about.
        self.dropped: Counter = Counter()
        super().__init__()

    def begin(self, seed: int) -> None:
        super().begin(seed)
        self.seed = seed
        # What the model said the table would look like after the last push.
        # Only used when nobody is going to look.
        self.expected: dict[int, tuple[float, float]] = {}

    # ---------------------------------------------------------- what it believed

    def believed(self, push: str, choice: search.Choice) -> None:
        """Keep what the model said about a push this solution is about to make.

        The first held-out walk could say that eight glasses were broken and not
        whether the model had been confident about those pushes, because nothing
        wrote down what it believed. This costs no arm time -- it is all on the
        laptop's side of the fence -- and ``measure.py`` is what reads it back.
        """
        self.risked.append(
            {
                "table": self.seed,
                "kind": push,
                "glass": choice.target,
                "chance_of_a_topple": round(choice.risk, 5),
                "travel_mm": round(1000 * choice.travel, 1),
                "reach_mm": round(1000 * choice.reach, 1),
            }
        )

    # ------------------------------------------------------------- the deciding

    def _decide(self, look: Look) -> Answer:
        """The reference's deciding with the probing taken out, and the model put in."""
        glasses = [glass for glass in self.table.glasses() if glass.standing]
        # "Nothing more to do about this one": it has room, and it is somewhere
        # the arm could pick it up from. Both halves are the scorecard's own
        # test asked of the measurements, because the measurements are all the
        # arm has, and ``room`` is problem 3's. The reference asks the same
        # question in the same two lines; it cannot be shared, because asking
        # it is part of its ``_decide`` and this solution replaces that.
        settled = {
            glass.id
            for glass in glasses
            if in_zone(glass.x, glass.y) and plan.room(glass, glasses, nudge.ROOM_MARGIN)
        }
        verdicts = self._verdicts(glasses, settled | self.leave)
        choice = self._pick(look, glasses, verdicts)
        if choice is None:
            if not self.swept:
                # Nothing worth doing, on a table last looked at from one side.
                # A glass hidden behind a nearer one is not in the picture, and
                # the last push may have uncovered one, so the claim that the
                # table needs nothing costs a walk round the whole ring.
                return self._sweep(look)
            # The reference's own wording of why a table is being left, given
            # the model's reasons instead of the geometry's. A glass whose best
            # push was found but was not worth making has no reason of its own,
            # and the reference's default covers it.
            said = {glass: verdict.reason for glass, verdict in verdicts.items() if verdict.reason}
            return Done(super()._nothing_more(glasses, settled, said))

        target = next(glass for glass in glasses if glass.id == choice.target)
        # How far the fingertips go in before the model expects to meet the
        # glass. The reference reads this out of its ranging pushes; here it is
        # part of the push the search chose, and ``_make`` picks it up from the
        # same place either way.
        self.reach_for[choice.target] = choice.reach
        self.expected = search.predicted_table(self.model, glasses, target, choice)
        self.believed(nudge.PUSHING, choice)
        return self._make(look, self._push(target, choice), nudge.PUSHING)

    def _verdicts(self, glasses: list[Seen], skip: set[int]) -> dict[int, search.Verdict]:
        """The best push the model can find for each glass still worth pushing."""
        verdicts: dict[int, search.Verdict] = {}
        for glass in glasses:
            if glass.id in skip:
                continue
            if self.tries[glass.id] >= nudge.PUSHES_PER_GLASS:
                verdicts[glass.id] = search.Verdict(
                    None, f"pushed {nudge.PUSHES_PER_GLASS} times and still without room"
                )
                continue
            verdicts[glass.id] = search.best_push(self.model, glasses, glass, self.generator)
        return verdicts

    def _pick(self, look: Look, glasses: list[Seen], verdicts: dict[int, search.Verdict]):
        """The cheapest push the model expects to help and the cell would carry out.

        Cheapest by the crowding the table is expected to be left with. The
        cell's interlock is asked before the push is answered, because a path
        it refuses moves the arm nowhere: the solution would be handed the same
        table back and would choose the same push again, for ever. Asking costs
        nothing and the rule is published, so this is not a hidden advantage.
        """
        crowding = search.crowding_now(glasses)
        found = (verdict.choice for verdict in verdicts.values())
        wanted = sorted(
            (choice for choice in found if search.worth_making(choice, crowding)),
            key=lambda choice: choice.cost,
        )
        for choice in wanted:
            target = next(glass for glass in glasses if glass.id == choice.target)
            path = self._path(look, target, choice)
            if interlocked(path, glasses) is not None:
                self._leave(choice.target, "the cell's interlock would refuse the push of it")
                continue
            # The search weighs where the glasses will *end up* and never asks
            # what the hand passes through on the way in. The model is free to
            # choose a push whose approach crosses a neighbour, and a hand
            # sweeping a glass puts it over as surely as a shove does. So the
            # path is checked against every glass this solution has measured,
            # and a push that would reach one it did not choose is dropped here
            # rather than carried out.
            why = why_not_clear(
                path, glasses, target=choice.target, tested=search.accounted_for(target, choice)
            )
            if why:
                self.dropped[why] += 1
                continue
            return choice
        return None

    def _push(self, target: Seen, choice: search.Choice):
        """The chosen push, aimed where the model says the glass will land."""
        return encoding.push_of(target, choice.heading, choice.offset, choice.travel, choice.aim)

    def _path(self, look: Look, target: Seen, choice: search.Choice):
        return jaw_paths.to_push(look.jaw, self._push(target, choice), choice.reach)

    # -------------------------------------------------------------- the looking

    def _make(self, look: Look, push, doing: str) -> Answer:
        """Answer with the push, and forget every glass the model says it will move.

        The reference forgets only the glass it pushed, because its planner
        aims at a clear corridor and expects to move nothing else. This one is
        free to choose a push that moves a neighbour, and a reading of where a
        neighbour used to stand must not be averaged into a reading of where it
        stands now. The model is what says which ones moved; that it may be
        wrong costs a measurement, not a glass.
        """
        answer = super()._make(look, push, doing)
        for glass, place in self.expected.items():
            where = self.table.where(glass)
            if where is not None and math.dist(where, place) > search.STILL:
                self.table.forget(glass)
        return answer

    def _read_the_push(self, look: Look) -> Answer | None:
        """What the last push did: looked at, or taken from the model.

        Looking is the reference's way. It takes a frame from where the jaw is
        standing, which is free, and drives to a stand that can see the glass
        when it cannot be seen from there, which is not -- and it does that
        until three looks are averaged, because a push is judged on a
        difference of a millimetre or two.

        The other way is to look no further than the frames that are free and
        take the model's word for the rest. Every glass the current look did
        catch is believed from the look, because a measurement is better than a
        prediction and this one has already been paid for; the glasses nobody
        saw get the model's answer. That is a push planned from the look before
        it rather than from a look of its own, and it is the one trade problem 3
        could not make, where seeing the whole table was free.

        A predicted position is recorded as though a look had seen it, which is
        a lie about how well it is known and is the point of the experiment.
        The ring is still walked before any table is declared finished, so
        nothing is ever claimed about a table on the model's word alone.
        """
        if not self.predicting:
            return super()._read_the_push(look)
        for glass in self.table.glasses():
            place = self.expected.get(glass.id)
            if place is None or self.table.looks_of(glass.id) > 0:
                continue
            self.table.merge([replace(glass, x=place[0], y=place[1])])
        self.pushed = None
        return None
