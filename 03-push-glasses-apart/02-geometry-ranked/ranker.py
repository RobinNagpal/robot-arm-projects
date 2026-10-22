"""The fitted half: boosted regression trees that score one candidate at a time.

A decision tree is a sequence of threshold questions, each about one input,
with a number at every leaf. Boosting fits one shallow tree, fits the next to
what the first got wrong, adds them up and repeats, so the sum of two hundred
weak trees is the model. That is the standard tool for predicting a number
from a short table of quantities of different kinds, and it needs no rescaling
of the inputs, no accelerator and seconds of processor time.

The fitting is pointwise: the model sees one candidate at a time and scores it
on its own, with no knowledge of what it is competing against. Nothing
downstream reads the number it produces --- only the order it puts the
candidates in --- so a model wrong by the same amount everywhere would still
rank perfectly.

The model can never add a candidate to the list and never bring back one the
geometry refused. ``ranked`` below is handed a set that has already passed
every test, and all it does is sort it.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import features
import joblib
import numpy as np
from candidates import Candidate, survivors
from sklearn.ensemble import GradientBoostingRegressor

from bench import Push, Seen

MODEL = Path(__file__).parent / "model" / "ranker.joblib"

# Of order two hundred shallow trees, which is an ordinary size for a table of
# a few thousand rows. Depth three asks three questions of a candidate before
# it answers, which is enough for "a long push into a tight corner" and little
# enough that no tree memorises a table.
TREES = 200
DEPTH = 3
LEARNING_RATE = 0.05


class Scorer(Protocol):
    """One number per row. Anything that does this can order the candidates."""

    def __call__(self, rows: np.ndarray) -> np.ndarray: ...


class Ranker:
    """A fitted model, asked for a score per candidate."""

    def __init__(self, trees: GradientBoostingRegressor) -> None:
        self.trees = trees

    @classmethod
    def fit(cls, rows: np.ndarray, labels: np.ndarray, seed: int = 0) -> Ranker:
        trees = GradientBoostingRegressor(
            n_estimators=TREES, max_depth=DEPTH, learning_rate=LEARNING_RATE, random_state=seed
        )
        trees.fit(rows, labels)
        return cls(trees)

    def __call__(self, rows: np.ndarray) -> np.ndarray:
        return self.trees.predict(rows)

    def importances(self) -> list[tuple[str, float]]:
        """How much each input contributed, most first. A wrong answer can be investigated."""
        pairs = zip(features.NAMES, self.trees.feature_importances_, strict=True)
        return sorted(pairs, key=lambda pair: -pair[1])

    def save(self, path: Path = MODEL) -> None:
        path.parent.mkdir(exist_ok=True)
        joblib.dump(self.trees, path)

    @classmethod
    def load(cls, path: Path = MODEL) -> Ranker:
        return cls(joblib.load(path))


def ranked(
    seen: list[Seen], skip: set[int], score: Scorer
) -> tuple[list[Candidate], np.ndarray, dict[int, str]]:
    """Every safe push on the table, best first, with its score and the refusals.

    The geometry has already removed everything unsafe by the time ``score``
    is called, and ``score`` cannot put anything back.
    """
    kept, why = survivors(seen, skip)
    if not kept:
        return [], np.zeros(0), why
    scores = np.asarray(score(features.rows(seen, kept)), dtype=np.float64)
    order = np.argsort(-scores, kind="stable")
    return [kept[i] for i in order], scores[order], why


def choose(seen: list[Seen], skip: set[int], score: Scorer) -> tuple[Push | None, dict[int, str]]:
    """The push to make next: the first one on the sorted list."""
    best, _, why = ranked(seen, skip, score)
    return (best[0].push if best else None), why


def worst_first(score: Scorer) -> Callable[[np.ndarray], np.ndarray]:
    """The same model with its order reversed. Only used to show that safety is not the model's."""
    return lambda rows: -np.asarray(score(rows))
