"""A safety check on another solution's push: the world model looks at it before MoveIt does.

Imitation and SmolVLA learn only from pushes that worked, so neither was ever shown
a push that tipped a glass, and neither can tell a safe push from a risky one. The
world model was shown both, and of all its nine answers the one it gives best is
whether a glass goes over. This wraps a solution so that every push it chooses is
first shown to the world model:

- If the world model expects the push to tip a glass less often than ``LIMIT``, the
  push goes to MoveIt as the solution chose it.
- If not, and ``REPAIR`` is on, the same glass is pushed the same way and the same
  distance, but the world model chooses the six settings handed to MoveIt.
- If the push is still too risky, the glass is set aside for this table and the
  solution is asked again, exactly as if MoveIt had refused it.

So the solution still decides which glass and where it goes (job 1). The check only
takes part in job 2, how it is pushed, and only when the solution's own answer
looks dangerous. A solution with a check is a hybrid and is reported as one.
"""

from __future__ import annotations

from pathlib import Path

import features as F
import numpy as np
from world_model import WEIGHTS, PlanningSolution

from contract import Done

CHECKER = WEIGHTS / "world-models-v3.pt"


class Checked:
    # The highest chance of a glass going over, if MoveIt plans the push, that is let through,
    # and whether a risky push is mended before it is set aside. Set on tables 2,000 to 2,023,
    # where mending did no better than setting the glass aside and so is left off.
    LIMIT = 0.15
    REPAIR = 0
    TRIES = 200  # settings the world model imagines when it mends a push

    def __init__(self, inner, checker: Path | None = None, seed: int = 0) -> None:
        self.inner = inner
        self.model = PlanningSolution(checker or CHECKER, seed)
        self.name = f"{inner.name}, checked by the world model"
        self.rng = np.random.default_rng(seed)
        self.vetoed = self.mended = 0

    def begin(self, seed: int) -> None:
        self.inner.begin(seed)
        self.rng = np.random.default_rng(seed)

    def risk(self, boxes, glass: int, vectors: np.ndarray):
        """The world model's score for each push, and its chance of a glass going over if MoveIt plans it."""
        scores, _, topple = self.model.score(boxes, np.full(len(vectors), glass), vectors)
        return scores, topple

    def mend(self, boxes, request):
        """The same glass, way and distance, with the settings the world model likes best."""
        base = F.action_vector(request)
        vectors = np.repeat(base[None], self.TRIES, 0)
        vectors[:, 3:] = self.rng.random((self.TRIES, len(F.SETTING_NAMES)))
        scores, topple = self.risk(boxes, request.glass, vectors)
        best = int(np.argmax(np.where(topple <= self.LIMIT, scores, -np.inf)))
        if topple[best] > self.LIMIT:
            return None
        return F.request_from(request.glass, vectors[best])

    def decide(self, look):
        boxes = list(look.boxes)
        for _ in range(F.SLOTS + 1):
            answer = self.inner.decide(look)
            if isinstance(answer, Done) or answer.glass >= len(boxes):
                return answer
            _, topple = self.risk(boxes, answer.glass, F.action_vector(answer)[None])
            if topple[0] <= self.LIMIT:
                return answer
            if self.REPAIR:
                mended = self.mend(boxes, answer)
                if mended is not None:
                    self.mended += 1
                    return mended
            self.vetoed += 1
            self.inner.refused.add(answer.glass)
        return Done("every push it offered would tip a glass")


def imitation(weights: Path | None = None) -> Checked:
    from imitation import Imitation

    return Checked(Imitation(weights))


def reinforcement(weights: Path | None = None) -> Checked:
    from reinforcement import Learner

    return Checked(Learner(weights))


def vla(weights: Path | None = None) -> Checked:
    from vla import FineTuned

    return Checked(FineTuned(weights))
