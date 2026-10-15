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

from partners import PUSH_HEIGHT, Chunk

# How close to the pushing height a path has to come before it counts as a
# push. The jaw pushes at one height in this cell, so an answer that never
# descends to it cannot move a glass whatever else it does. A millimetre of
# room is left for the arithmetic that built the path.
REACHES_DOWN = PUSH_HEIGHT + 0.001

# How many such answers in a row are taken as the policy saying it is done.
# One is too few, because a policy that draws its answer rather than computing
# it will draw a stray one. Three in a row from a policy that acts at all is
# not a coincidence, and three is also cheap: at about two arm seconds an
# answer, being wrong about this costs a few seconds rather than a table.
QUIET_ANSWERS = 3


def is_a_push(answer: Chunk) -> bool:
    """Whether this path comes down to the height a push happens at.

    The test is the lowest waypoint rather than the first, because a policy is
    free to come down part way along its path, and a path that touches the
    pushing height anywhere can move a glass.
    """
    return min(point.z for point in answer.waypoints) <= REACHES_DOWN


class Quiet:
    """Counts answers that are not pushes, and says when there have been enough.

    One of these belongs to one table. A solution makes a fresh one in
    ``begin`` so that a quiet spell on the last table cannot end this one.
    """

    def __init__(self, enough: int = QUIET_ANSWERS) -> None:
        self.enough = enough
        self.quiet = 0

    def saw(self, answer: Chunk) -> None:
        """Take account of what the policy has just answered."""
        self.quiet = 0 if is_a_push(answer) else self.quiet + 1

    @property
    def finished(self) -> bool:
        """Whether the policy has now gone quiet for long enough to be taken at its word."""
        return self.quiet >= self.enough

    @property
    def why(self) -> str:
        """What to record as the reason, which the scorecard keeps but never scores."""
        return f"{self.quiet} answers in a row that would not touch a glass"
