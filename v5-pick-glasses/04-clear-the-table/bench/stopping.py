"""How a trained policy says it has finished, when it has no words for it.

Problem 4 asks every solution to declare a table done, and that is a sentence
a trained policy cannot utter. A policy of the kind solutions 5 and 6 borrow
answers with a path for the jaw and nothing else: there is no spare output
meaning "nothing here needs moving", and nothing in what it was trained on
ever taught it to produce one. Problem 3 never had to face this, because its
shared loop decided for every policy when a table was finished.

Three answers were possible and this module is the third.

The first is to give the policy an extra output and train it to use that
output. It is the proper answer and it is also a different experiment: it
changes what the policy is, so a result from it would not compare with
problem 3's, and nothing in the demonstrations says when a table is done.

The second is to let the clock stop every trained policy on every table. That
is honest, costs nothing, and throws away the distinction the problem exists
to measure: a policy that tidies a table in ten seconds and one that flails
for ten minutes would both be recorded as "the clock stopped it".

The third, which is here, is to **read the declaration out of the policy's own
behaviour**. A policy that has stopped proposing pushes is saying, in the only
language it has, that it sees nothing worth doing. So a run of answers that
would not touch a glass is taken as the policy saying it is finished.

That is a rule about the *shape* of an answer and not about its quality, which
is what keeps it fair. It never asks whether a push was a good idea, and it
treats a policy that waves the jaw in the air exactly as it treats one that
has genuinely tidied the table — both are proposing no pushes, and the
scorecard, which looks at the table rather than at the policy, is what tells
them apart afterwards.
"""

from __future__ import annotations

from partners import JAW_HALF_HEIGHT, PUSH_HEIGHT, Chunk

# A millimetre of room for the arithmetic that built a path, so that a path
# meant to reach a height is not thrown out for missing it by a rounding.
A_WHISKER = 0.001

# How far below the number a waypoint carries the hand actually reaches is
# JAW_HALF_HEIGHT, and that is the correction this module exists to make.
#
# An earlier version of this rule asked whether a path came down to the height
# the jaw pushes at, and it was wrong. A waypoint's number is the **middle** of
# the jaw, the fingers hang below it, and so a path counted as quiet was
# sweeping the tops of the glasses: one run broke a glass while every one of
# its answers was being recorded as quiet. A rule that calls a policy finished
# while it is knocking glasses over is not a rule about finishing.
#
# No glass height is written down here, because no glass measurement is written
# down anywhere in this project. The caller passes the tallest glass it has
# **measured**, and a caller that has seen nothing falls back to the gripper's
# own pushing height, which belongs to the hand rather than to any glass.

# How many such answers in a row are taken as the policy saying it is done.
#
# One is too few, because a policy that draws its answer rather than computing
# it will draw a stray one. The number has to come from somewhere, though, and
# the right place is the teacher: however many answers in a row the geometry
# reference gives without touching a glass, a learned policy must be allowed at
# least as many before anyone calls it finished.
#
# Measured on forty tables of the demonstration band, with every answer
# classified by ``is_a_push`` below so that the two cannot disagree: the
# teacher's longest quiet spell that then ends in a push is eight answers, with
# two in the middle, and the spell it finishes a table with is eleven at its
# longest and ten in the middle. So three is far too few -- a policy would be
# declared done partway through its first look round the table, on every table
# -- and sixteen sits comfortably above both. Solution 3's ``teacher.py`` is
# the measurement and its ``teacher-quiet-spells.json`` holds the numbers.
#
# Being wrong in this direction is cheap and being wrong in the other is not. A
# threshold set too high costs a few arm seconds of waving at a table that was
# already finished; a threshold set too low ends the table.
QUIET_ANSWERS = 16


def is_a_push(answer: Chunk, tallest: float = 0.0) -> bool:
    """Whether any part of the hand on this path comes low enough to touch a glass.

    The test is the lowest waypoint rather than the first, because a policy is
    free to come down part way along its path, and a path that comes low
    anywhere can move a glass there.

    ``tallest`` is the height of the tallest glass the solution has measured on
    this table. Passing it is what makes the answer mean "proposing nothing"
    rather than "proposing nothing that would reach the pushing height": a path
    may clear the jaw's own working height and still sweep through a glass
    standing taller than it. A solution that has seen nothing yet passes
    nothing, and the test falls back to the hand's own pushing height.
    """
    lowest = min(point.z for point in answer.waypoints) - JAW_HALF_HEIGHT
    return lowest <= tallest + A_WHISKER or lowest <= PUSH_HEIGHT + A_WHISKER


class Quiet:
    """Counts answers that are not pushes, and says when there have been enough.

    One of these belongs to one table. A solution makes a fresh one in
    ``begin`` so that a quiet spell on the last table cannot end this one.
    """

    def __init__(self, enough: int = QUIET_ANSWERS) -> None:
        self.enough = enough
        self.quiet = 0

    def saw(self, answer: Chunk, tallest: float = 0.0) -> None:
        """Take account of what the policy has just answered.

        ``tallest`` is the tallest glass the solution has measured on this
        table, and passing it is what makes the count mean "proposing nothing"
        rather than "proposing nothing that would reach the pushing height".
        """
        self.quiet = 0 if is_a_push(answer, tallest) else self.quiet + 1

    @property
    def finished(self) -> bool:
        """Whether the policy has now gone quiet for long enough to be taken at its word."""
        return self.quiet >= self.enough

    @property
    def why(self) -> str:
        """What to record as the reason, which the scorecard keeps but never scores."""
        return f"{self.quiet} answers in a row that would not touch a glass"
