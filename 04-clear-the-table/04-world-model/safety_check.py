"""A safety check on another solution's push: the world model looks at it before MoveIt does.

Imitation and SmolVLA learn only from pushes that worked, so neither was ever shown
a push that tipped a glass, and neither can tell a safe push from a risky one. The
world model was shown both, and of all its nine answers the one it gives best is
whether a glass goes over. This wraps a solution so that every push it chooses is
first shown to the world model:

- If the world model expects the push to tip a glass less often than ``HIGHEST_TOPPLE_CHANCE``, the
  push goes to MoveIt as the solution chose it.
- If not, and ``MEND_RISKY_PUSHES`` is on, the same glass is pushed the same way and the same
  distance, but the world model chooses the six settings handed to MoveIt.
- If the push is still too risky, the glass is set aside for this table and the
  solution is asked again, exactly as if MoveIt had refused it.

So the solution still decides which glass and where it goes (job 1). The check only
takes part in job 2, how it is pushed, and only when the solution's own answer
looks dangerous. A solution with a check is a hybrid and is reported as one. It looks the way the solution
it wraps looks.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from world_model import WEIGHTS_FOLDER, WorldModelSolution

from shared.learning import table_and_push_encoding
from shared.turn_by_turn_loop import TableFinished, TurnByTurnSolution

CHECKER_WEIGHTS = WEIGHTS_FOLDER / "world-models-v3.pt"


class SafetyCheckedSolution(TurnByTurnSolution):
    # The highest chance of a glass going over, if MoveIt plans the push, that is let through,
    # and whether a risky push is mended before it is set aside. Set on tables 2,000 to 2,023,
    # where mending did no better than setting the glass aside and so is left off.
    HIGHEST_TOPPLE_CHANCE = 0.15
    MEND_RISKY_PUSHES = 0
    MENDING_TRIES = 200  # settings the world model imagines when it mends a push

    def __init__(self, wrapped_solution, checker_weights: Path | None = None, seed: int = 0) -> None:
        self.wrapped_solution = wrapped_solution
        self.world_model = WorldModelSolution(checker_weights or CHECKER_WEIGHTS, seed)
        self.name = f"{wrapped_solution.name}, checked by the world model"
        self.looking_mode = wrapped_solution.looking_mode
        self.rng = np.random.default_rng(seed)
        self.pushes_vetoed = self.pushes_mended = 0

    def start_new_table(self) -> None:
        self.wrapped_solution.start_new_table()
        self.rng = np.random.default_rng(0)

    def topple_risk(self, boxes, glass: int, vectors: np.ndarray):
        """The world model's score for each push, and its chance of a glass going over if MoveIt plans it."""
        scores, _, topple_chance = self.world_model.score_pushes(boxes, np.full(len(vectors), glass), vectors)
        return scores, topple_chance

    def mended_settings(self, boxes, request):
        """The same glass, way and distance, with the settings the world model likes best."""
        base = table_and_push_encoding.encode_push(request)
        vectors = np.repeat(base[None], self.MENDING_TRIES, 0)
        vectors[:, 3:] = self.rng.random((self.MENDING_TRIES, len(table_and_push_encoding.SETTING_NAMES)))
        scores, topple_chance = self.topple_risk(boxes, request.glass, vectors)
        best = int(np.argmax(np.where(topple_chance <= self.HIGHEST_TOPPLE_CHANCE, scores, -np.inf)))
        if topple_chance[best] > self.HIGHEST_TOPPLE_CHANCE:
            return None
        return table_and_push_encoding.decode_push(request.glass, vectors[best])

    def decide_turn(self, observation):
        boxes = list(observation.boxes)
        for _ in range(table_and_push_encoding.GLASS_SLOTS + 1):
            answer = self.wrapped_solution.decide_turn(observation)
            if isinstance(answer, TableFinished) or answer.glass >= len(boxes):
                return answer
            _, topple_chance = self.topple_risk(
                boxes, answer.glass, table_and_push_encoding.encode_push(answer)[None]
            )
            if topple_chance[0] <= self.HIGHEST_TOPPLE_CHANCE:
                return answer
            if self.MEND_RISKY_PUSHES:
                mended = self.mended_settings(boxes, answer)
                if mended is not None:
                    self.pushes_mended += 1
                    return mended
            self.pushes_vetoed += 1
            self.wrapped_solution.refused_glasses.remember(boxes, answer.glass)
        return TableFinished("every push it offered would tip a glass")


def checked_imitation(weights: Path | None = None) -> SafetyCheckedSolution:
    from imitation import ImitationSolution

    return SafetyCheckedSolution(ImitationSolution(weights))


def checked_reinforcement_learning(weights: Path | None = None) -> SafetyCheckedSolution:
    from reinforcement_learning import ReinforcementLearningSolution

    return SafetyCheckedSolution(ReinforcementLearningSolution(weights))


def checked_smolvla(weights: Path | None = None) -> SafetyCheckedSolution:
    from smolvla_fine_tuned import SmolVLASolution

    return SafetyCheckedSolution(SmolVLASolution(weights))
