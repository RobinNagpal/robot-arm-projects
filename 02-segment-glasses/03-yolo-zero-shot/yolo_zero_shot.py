"""Solution 3: a borrowed instance segmenter, run exactly as it downloads.

The model is Ultralytics YOLO26-seg at the small end of the family, and its
weights fetch themselves the first time it is used. **Nothing whatsoever is
fitted in this cell**, so there is not one number in this file that came from
this project's own data. That is the whole point of the solution: it is the
cheapest of the six to try and the baseline the fitted ones are read against.

For every object it believes it has found, the model returns a box, a name from
its fixed list of categories, a number saying how sure it is, and an outline. The
chain here is short:

1. shade the depth picture into the three-channel picture the model expects,
   which is `pictures.shade` and is shared with every other borrowed model here;
2. keep the outlines the model named as drinking vessels, and drop the name;
3. drop an outline that covers substantially the same pixels as a better-scoring
   one, because a single glass can be named twice under two neighbouring
   categories and the bench counts a real glass with two reports as a split;
4. turn each surviving outline into a boolean mask and hand it to
   `masks_to_glasses`, which is the bench's arithmetic and not this solution's.

**The kind of glass is handed in and this solution has no use for it.** Every
other solution here uses it to refuse a footprint no glass of the kind could
have. This one does not, and the reason is worth stating: such a refusal would be
a check this solution's design does not contain, and the honest summary of a
borrowed model used as the decider is that its failures are *silent* — a glass
half covered by its neighbour comes back as a smaller glass in the wrong place,
with nothing in the run marking it as doubtful. Inventing a check here would hide
exactly the behaviour the comparison against solution 4 exists to measure.

**Nothing here is amodal.** The outlines the model returns mark only pixels where
the object was actually visible, so no mask asserts a pixel the camera did not
see the glass at and `masks_to_glasses` is given nothing to exclude.

**The camera belongs to data.py**, so this solution is handed the same pictures
as the other five and cannot win by its viewpoint.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import drinking_vessels
import numpy as np

import data
import device
import masks_to_glasses
import pictures
from masks_to_glasses import Found

# The model, as the document names it: YOLO26-seg at the small end of the family.
# The smaller end is the sensible place to start, because the glasses fill a
# reasonable part of the frame and a larger model costs time without obviously
# buying accuracy on silhouettes this plain. Solution 4 continues the training of
# this same file, because the pair is only a clean comparison while both start
# from the same weights.
MODEL = "yolo26n-seg.pt"

# Fetched into this folder rather than the home directory, so that what a run
# depends on sits beside the run and `weights/` can be deleted to start again.
CACHE = Path(__file__).parent / "weights"

# **A hand-set bar, not a probability.** The number beside each outline is
# calibrated, if it is calibrated at all, on photographs. These pictures are not
# photographs, and a model's confidence under changed input is the first thing to
# drift, usually becoming too sure. What survives the change is the *order* of
# the scores, so this bar is a knob checked by eye on the bench's training half
# and it claims nothing about how often an outline above it is really a glass.
# Calling it a probability threshold would be claiming a property nobody here has
# measured. It is written once, and read twice: once by the model, so it does not
# spend time building outlines that are going to be dropped, and once below, so
# the decision is this solution's own and can be tested.
CONFIDENCE_BAR_SET_BY_HAND = 0.25

# Two outlines overlapping by more than this are one glass named twice, and only
# the better-scoring one is kept. A share of the pixels either holds, so it means
# the same thing whatever size the outline is.
SAME_OUTLINE = 0.7

# A polygon with fewer corners than this encloses no pixels at all.
CORNERS_OF_A_SHAPE = 3


@lru_cache(maxsize=1)
def _model():
    """The borrowed model and the processor to run it on. Never trained here.

    The weights download themselves on the first call and are found on disk on
    every call after it, which is what makes a second run cheap.
    """
    from ultralytics import YOLO
    from ultralytics.utils.downloads import attempt_download_asset

    CACHE.mkdir(parents=True, exist_ok=True)
    return YOLO(attempt_download_asset(CACHE / MODEL)), device.pick()


def outline_to_mask(outline: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """One of the model's outlines as a boolean mask the shape of the picture.

    The model gives an outline as a ring of corners in the picture's own pixel
    coordinates, and the bench's arithmetic reads a mask. Filling the ring is the
    whole conversion. The corners are rounded rather than interpolated, because
    the outline was built from a weighted sum of coarse patterns and then
    enlarged, so it is already approximate to well over a pixel and pretending
    otherwise would be false precision.
    """
    mask = np.zeros(shape, dtype=np.uint8)
    corners = np.asarray(outline, dtype=np.float64).reshape(-1, 2)
    if len(corners) >= CORNERS_OF_A_SHAPE:
        cv2.fillPoly(mask, [np.round(corners).astype(np.int32)], 1)
    return mask.astype(bool)


def above_the_bar(confidences) -> np.ndarray:
    """Per outline, whether its confidence clears the hand-set bar."""
    return np.asarray(confidences, dtype=float).ravel() >= CONFIDENCE_BAR_SET_BY_HAND


def _overlap(one: np.ndarray, other: np.ndarray) -> float:
    """What share of the pixels either mask holds are held by both."""
    return float((one & other).sum() / max(int((one | other).sum()), 1))


def merge_doubles(masks: Iterable[np.ndarray]) -> list[np.ndarray]:
    """Keep the first of any outlines that cover substantially the same pixels.

    A single glass can come back twice, under two neighbouring drinking-vessel
    categories, with nearly the same pixels both times. Left alone that is one
    real glass collecting two reports, which the bench counts as a split, so the
    double naming is paid for here rather than in the scorecard. ``masks`` is
    read in order and the first of a group is kept, so a caller that wants its
    surest outline to win sorts first.
    """
    kept: list[np.ndarray] = []
    for mask in masks:
        if not any(_overlap(mask, other) > SAME_OUTLINE for other in kept):
            kept.append(mask)
    return kept


def masks_from(answer, shape: tuple[int, int]) -> list[np.ndarray]:
    """The masks this solution keeps out of one of the model's answers.

    This is where the borrowed name is used and thrown away: what comes out is a
    list of boolean masks carrying no category, no confidence and no claim about
    what kind of thing was outlined. Surest first, so that `merge_doubles` keeps
    the better-scoring of a pair.
    """
    if answer.masks is None or len(answer.masks.xy) == 0:
        return []
    names: Mapping[int, str] = answer.names
    confidences = np.asarray(answer.boxes.conf, dtype=float).ravel()
    keep = drinking_vessels.are_drinking_vessels(answer.boxes.cls, names) & above_the_bar(confidences)
    surest = sorted(range(len(confidences)), key=lambda index: -confidences[index])
    return merge_doubles(outline_to_mask(answer.masks.xy[index], shape) for index in surest if keep[index])


def look(picture) -> object:
    """One picture through the borrowed model, and its answer brought back to the processor.

    The picture the model is shown is `pictures.shade`'s, which every borrowed
    model in this folder is given, so a solution cannot beat another by shading.
    What goes in has the shape of a photograph and none of its content, and that
    is the largest risk in this solution rather than an accident of the code.
    """
    model, where = _model()
    answers = model.predict(
        pictures.shade(picture),
        conf=CONFIDENCE_BAR_SET_BY_HAND,
        device=where,
        verbose=False,
    )
    return answers[0].cpu()


def fit(examples: Iterable[data.Example], *, amodal: bool, save: Path) -> Mapping:
    """There is nothing to fit here, and saying so is the solution's whole claim.

    The interface every solution in this folder answers has a fitting step, and
    this one refuses it rather than quietly writing an empty file. The baseline's
    value is that not a single number in it came from this cell's data, so a
    `train.py` that appeared to do something would be the one way to break it.
    """
    raise RuntimeError(
        "solution 3 fits nothing in this cell: the model is used exactly as it downloads and the "
        "filter on its category names is a reading of the names, not a fit. There is no train step "
        "to run and nothing to save. Solution 4 is this same model with training added."
    )


@dataclass(frozen=True)
class Finder:
    """The borrowed model, ready to be handed pictures. It holds no fitted state."""

    def find(self, picture, kind: str) -> tuple[list[Found], list[str]]:
        """The whole chain on one picture: the glasses found, and what could not be settled.

        ``kind`` is accepted because every solution here is handed it, and is
        unused for the reason this module's own description gives.
        """
        masks = masks_from(look(picture), picture.depth.shape)
        if not masks:
            return [], ["the model named nothing in this picture a drinking vessel"]

        found, doubts = [], []
        for mask in masks:
            one = masks_to_glasses.one_glass(picture, mask)
            if one is None:
                doubts.append("an outline with too little of the table under it to place")
            else:
                found.append(one)
        return found, doubts


def load(save: Path | None = None) -> Finder:
    """A finder. ``save`` is accepted for the shared interface and there is nothing in it."""
    return Finder()
