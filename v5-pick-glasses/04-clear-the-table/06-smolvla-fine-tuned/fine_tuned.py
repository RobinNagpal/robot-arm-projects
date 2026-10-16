"""The borrowed model with this problem's correction, answering problem 4's contract.

[Solution 5](../05-smolvla-as-it-downloads) is the same model with nothing
fitted, and it is the one that wrote down how a trained policy joins problem 4's
conversation: a picture from the camera on the arm goes in, a path for the jaw
comes out, ``bench/stopping.py`` reads the declaration that a table is finished
out of the shape of the answers, and the solution keeps its own split of the arm
time it asked for. **All of that is inherited rather than written again**, which
is the whole of why this file is short. The pair is only clean while everything
but the weights is the same code, and a second copy of the loop here would be a
second thing that could vary.

One thing is added, and nothing else is.

**The weights.** ``borrowed.correction.Fitted`` is problem 3's loader: the
downloaded weights with a low-rank correction multiplied into them, so what runs
afterwards is a model of exactly the original size at exactly the original speed.
The correction is the one ``train.py`` fitted on problem 4's demonstrations.

**How long a quiet spell has to be is the bench's number and not this
folder's.** The stopping rule counts answers that could not touch a glass and
takes enough of them in a row as the policy saying the table needs nothing more.
``stopping.QUIET_ANSWERS`` is that count, and this solution takes it as it comes
rather than setting one of its own, so that every solution in problem 4 is
stopped by one rule. The count matters far more here than for solution 5, which
never gave even that many quiet answers in a row: a fitted model has learned its
teacher's habit of driving the arm about to see, so it goes quiet for a spell and
then acts, and a count set below the longest such spell would end the table in
the middle of one. ``quiet_for`` can still be given, which is how the count was
compared on the tables below the held-out line, and what that comparison found
is in the README.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from borrowed import as_downloaded, correction, policy

from contract import Answer, Look
from stopping import QUIET_ANSWERS, Quiet

# Where a refusal came from. The contract tells a solution why its last path was
# not carried out, and the two reasons call for opposite responses, so they are
# counted apart rather than together.
INTERLOCK = "the cell would not drive the jaw"


class FineTuned(as_downloaded.AsItDownloads):
    """Solution 5's solution, with the fitted weights in it.

    One of these holds one loaded model and is used for a whole walk of the
    queue, because loading the weights is slow and nothing in the model changes
    between tables.
    """

    name = "smolvla fine-tuned"

    def __init__(self, model, pinned: bool = False, quiet_for: int = QUIET_ANSWERS) -> None:
        super().__init__(model, pinned=pinned)
        self.quiet_for = quiet_for
        self.quiet = Quiet(quiet_for)
        # Why the cell would not carry out a path, in its own words. Diagnosis
        # rather than score: a policy that keeps asking for refused paths is
        # spending its budget on nothing, and nothing else reports it.
        self.refusals: Counter = Counter()

    def begin(self, seed: int) -> None:
        super().begin(seed)
        self.quiet = Quiet(self.quiet_for)

    def answer(self, look: Look) -> Answer:
        if look.refused:
            kind = "the tipping interlock" if look.refused.startswith(INTERLOCK) else "the bench"
            self.refusals[kind] += 1
        return super().answer(look)

    def summary(self) -> dict:
        """What this walk of the queue asked for, beside what the scorecard marked.

        The shape of the answers is the reading that matters for a borrowed
        model, and it is solution 5's own three numbers: how low a chunk comes,
        how far across the table it travels, and how far apart its waypoints
        are, which in this cell is the speed being asked for.
        """
        looking, pushing = self.look_seconds, self.push_seconds
        return {
            "quiet_answers_taken_as_done": self.quiet_for,
            "looking_seconds": round(looking, 1),
            "pushing_seconds": round(pushing, 1),
            "looking_share": round(looking / (looking + pushing), 3) if looking + pushing else 0.0,
            "refused_because": dict(self.refusals),
            "shape": self.shape.summary(),
        }


def load(folder: Path, device: str | None = None):
    """The borrowed weights with one fitted correction multiplied into them.

    ``folder`` is never defaulted. Problem 3's ``correction.py`` is what loads
    this, and its own default folder is problem 3's own correction, fitted on
    problem 3's pushes: a run that fell back on it would be measuring the wrong
    model and would look exactly like a run that was not.
    """
    return correction.Fitted.load(device, folder)


def as_it_downloads(device: str | None = None):
    """The same weights with nothing fitted, loaded the way solution 5 loads them.

    This is here so that the pair can be measured rather than read across.
    Solution 5 stops after three quiet answers and this solution does not, so
    its published numbers and this solution's are not two readings of one
    arrangement. Running the uncorrected weights under this solution's own
    stopping count leaves the training as the only difference between them.
    """
    return policy.Downloaded.load(device)
