"""Solution 8: SAM outlines everything, and a small fitted keeper picks out the glasses.

The borrowed half is `facebook/sam-vit-base`, used exactly as it was downloaded.
It is prompted with a regular grid of points over the picture, it answers every
prompt with an outline, and nothing here ever computes a gradient through it.
What comes back is a heap rather than a list of objects: the same region arrives
from dozens of prompts, and one prompt returns a part, a whole and something
larger. Scoring, stability and duplicate removal cut the heap down to a shortlist
of **proposals**, and none of that involves fitting either.

The fitted half is the **keeper**, which is the only thing in this solution that
knows anything about this cell. It is shown eight measurements of one proposal
and answers one of three things: this is one glass, this is not a glass, or this
is more than one glass. Boosted decision trees, because the input is a short
table of numbers of different kinds. Its probability is calibrated, and it has
two thresholds rather than one, so a proposal between them is reported as
doubtful instead of being quietly kept or quietly dropped.

The arithmetic keeps the last word. A proposal the keeper wants to keep is still
fitted with a circle by `masks_to_glasses`, and a width outside the range this
kind of glass can be is refused whatever the keeper said. A learned part chooses
among regions; a rule nobody trained decides whether the choice is believable.

**The kind of glass is handed in with the picture.** It is not derivable from a
picture and the problem statement says the cell is told it, so it arrives as an
argument rather than being read out of the scene behind the picture. What it
settles is the range of footprints a glass here could have and how fine the grid
of prompts has to be; no glass's size is written down anywhere for it.

**The camera belongs to data.py**, which stands it at the cell's own survey
height and takes the three pictures a survey there needs. Nothing in this file
chooses a viewpoint, so all three solutions are guaranteed the same pictures.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import torch
import weights
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from work_cell.table.layout import TABLE_TOP_Z

import data
import device
import masks_to_glasses
import pictures
import render
from masks_to_glasses import Found

# The keeper's three answers. Numbers rather than names because they are what
# the classifier is fitted on; the names are for reading the code.
DROP, ONE_GLASS, MORE_THAN_ONE = 0, 1, 2
ANSWERS = ("not a glass", "one glass", "more than one glass")

# What the keeper is shown about one proposal, in the order it is shown them.
# The set is fixed by the solution's document and is deliberately short: every
# one is a length, a count or a ratio measured on the table rather than in the
# picture, so none of them changes when the camera stands somewhere else.
MEASUREMENTS = (
    "how wide the circle fitted to it is, against the range this kind allows",
    "how round it is: its area against the area its outline could enclose",
    "how far its surface stands above the table, from the depth reading",
    "how far it sits from the point directly below the camera",
    "how many prompt points returned this same mask",
    "how much of its outline is a step in depth rather than a smooth run",
    "its area on the table, in square millimetres",
    "whether another proposal contains it, or it contains one",
)

# How many prompt points the smallest glass this kind allows should get across
# it. Fewer than this and a small glass can fall between the points of the grid;
# the grid is free to be finer, because every prompt after the first is one pass
# through the cheap half of the model.
POINTS_ACROSS_SMALLEST = 3

# Prompts are sent through the mask decoder this many at a time. The picture
# encoder has already run by then, so this is only about how much memory the
# masks take while they are being cut down.
PROMPTS_AT_ONCE = 64

# What SAM's own quality estimate and its stability have to reach. Stability is
# how little a mask changes when the cut-off that turns the model's output into
# a yes-or-no mask is nudged by STABILITY_NUDGE either way: a boundary the model
# is unsure of moves a long way for a small nudge.
GOOD_ENOUGH, STEADY, STABILITY_NUDGE = 0.8, 0.92, 1.0

# Two proposals overlapping by more than this are the same region arriving
# twice, and only the better-scoring one is kept.
DUPLICATE = 0.7

# One proposal is inside another when this much of it is covered by the other.
# Not 1.0, because the edges of two masks of the same thing never agree exactly.
CONTAINED = 0.9

# A jump in depth across a proposal's edge counts as a step rather than a smooth
# run when it is more than this much of the shortest glass this kind allows.
# Below that a jump is a wall sloping away across two pixels, not an edge.
STEP_OF_SHORTEST = 0.25

# Overlap tests are done on a mask sampled this coarsely. An overlap is a ratio
# of areas, so every second pixel each way answers it to a part in a thousand,
# and the whole shortlist can then be compared in one multiplication.
COARSE = 2

# The labels the keeper is fitted on. A glass is in a proposal when this much of
# the glass is, and the proposal is about glasses at all when this much of it is
# covered by the glasses it holds. The second is what keeps a mask of the whole
# table from being labelled "more than one glass" because the glasses stand on it.
MOSTLY = 0.5

# The keeper: 60 rounds of trees three questions deep, one set per answer, so
# 180 shallow trees added up. A table this size fits in seconds on the processor.
ROUNDS, DEPTH = 60, 3

# Calibration folds, and how many of the rarest answer are wanted before the
# probability is straightened with isotonic regression rather than a fitted
# sigmoid. Isotonic bends to any shape and needs the examples to pay for it.
FOLDS, ENOUGH_FOR_ISOTONIC = 3, 200

# The two thresholds on the calibrated chance that a proposal is one glass. Above
# the first it is reported, below the second it is dropped, and between them the
# keeper cannot tell, which is a reason to take another picture rather than to
# guess. The third answer is not a point on this line: more than one glass is a
# different thing to do next, not a doubtful glass.
SURE_ONE_GLASS, SURE_NOT_ONE_GLASS = 0.7, 0.3

# The fit is the same every time it is run on the same scenes, so a scorecard
# can be repeated.
FITTING_SEED = 0


@dataclass
class Proposal:
    """One region SAM proposed, and everything measured about it."""

    mask: np.ndarray  # boolean, the shape of the picture
    score: float  # SAM's own estimate of how good this mask is
    stability: float
    votes: int  # how many prompt points returned this same region
    found: Found  # its place and width, from the shared arithmetic
    features: np.ndarray  # the eight numbers the keeper reads


def _metres_per_pixel() -> float:
    """How much table one pixel covers, at the height the survey is taken from."""
    return data.frame()[0] / render.WIDTH


def prompt_spacing(kind: str) -> int:
    """How far apart the grid's points stand, in pixels.

    Taken from the smallest glass the kind allows rather than chosen: the grid
    has to put several points on that glass, and a glass nearer the camera than
    the table only comes out larger, so measuring it at the table is the safe end.
    """
    narrowest = data.widths(kind)[0] / _metres_per_pixel()
    return max(1, int(narrowest / POINTS_ACROSS_SMALLEST))


def _grid(spacing: int, inside: np.ndarray | None = None) -> list[list[float]]:
    """Prompt points (column, row) on a regular grid, optionally only where ``inside`` is true."""
    rows = np.arange(spacing // 2, render.HEIGHT, spacing)
    columns = np.arange(spacing // 2, render.WIDTH, spacing)
    points = [[float(column), float(row)] for row in rows for column in columns]
    if inside is None:
        return points
    return [point for point in points if inside[int(point[1]), int(point[0])]]


@lru_cache(maxsize=1)
def _sam():
    """SAM as downloaded, on whichever processor this machine has. Never trained."""
    from transformers import SamModel, SamProcessor

    path = weights.sam()
    where = device.pick()
    model = SamModel.from_pretrained(path).to(where).eval()
    return SamProcessor.from_pretrained(path), model, where


def _onto(tensor: torch.Tensor, where: torch.device) -> torch.Tensor:
    """Move a tensor to the device, in a dtype the device will take.

    The processor returns the prompt points as float64 and MPS refuses float64
    outright, so anything that arrives in it is cast on the way across.
    """
    if tensor.dtype == torch.float64:
        tensor = tensor.to(torch.float32)
    return tensor.to(where)


class _Look:
    """One picture through SAM's picture encoder, and any number of prompts after it.

    The split is what makes a grid of prompts affordable. The encoder is the
    expensive part and runs once here; every prompt afterwards is one pass
    through the small mask decoder.
    """

    def __init__(self, image: np.ndarray) -> None:
        self.image = image
        self.processor, self.model, self.where = _sam()
        prepared = self.processor(image, return_tensors="pt")
        with torch.no_grad():
            self.embeddings = self.model.get_image_embeddings(_onto(prepared["pixel_values"], self.where))

    def at(self, points: list[list[float]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Prompt at every point and return the masks worth keeping, with their scores.

        Every prompt gets three masks back, roughly a part, a whole and something
        larger, because SAM hands ambiguity back rather than resolving it. The
        low-scoring and the unstable ones are dropped here; the duplicates are
        dropped afterwards, once they can be compared with each other.
        """
        asked = [[[point] for point in points]]
        prepared = self.processor(self.image, input_points=asked, return_tensors="pt")
        all_points = _onto(prepared["input_points"], self.where)
        sizes = (prepared["original_sizes"], prepared["reshaped_input_sizes"])

        masks, scores, stability = [], [], []
        with torch.no_grad():
            for start in range(0, all_points.shape[1], PROMPTS_AT_ONCE):
                chunk = all_points[:, start : start + PROMPTS_AT_ONCE]
                out = self.model(image_embeddings=self.embeddings, input_points=chunk, multimask_output=True)
                # Judged small and enlarged afterwards. Most of what comes back
                # is thrown away, and enlarging a mask costs far more than
                # measuring one, so only the survivors are enlarged.
                small = out.pred_masks.float().cpu()
                strict = (small > STABILITY_NUDGE).sum((-1, -2))
                loose = (small > -STABILITY_NUDGE).sum((-1, -2))
                steadiness = (strict / loose.clamp(min=1)).reshape(-1).numpy()
                quality = out.iou_scores[0].float().cpu().reshape(-1).numpy()
                keep = (quality >= GOOD_ENOUGH) & (steadiness >= STEADY)
                if not keep.any():
                    continue
                chosen = small.reshape(1, -1, 1, *small.shape[-2:])[:, keep]
                raised = self.processor.image_processor.post_process_masks(chosen, *sizes, binarize=True)[0]
                masks.append(raised.reshape(-1, render.HEIGHT, render.WIDTH).numpy())
                scores.append(quality[keep])
                stability.append(steadiness[keep])

        if not masks:
            empty = np.zeros((0, render.HEIGHT, render.WIDTH), dtype=bool)
            return empty, np.zeros(0), np.zeros(0)
        return np.concatenate(masks), np.concatenate(scores), np.concatenate(stability)


def _overlaps(masks: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Every pair's overlap, and how much of each mask the other covers.

    Both come from one multiplication over coarsely sampled masks, which is the
    difference between comparing a few hundred masks in a moment and in a minute.
    """
    coarse = masks[:, ::COARSE, ::COARSE].reshape(len(masks), -1).astype(np.float32)
    shared = coarse @ coarse.T
    areas = np.maximum(np.diag(shared), 1.0)
    union = areas[:, None] + areas[None, :] - shared
    return shared / np.maximum(union, 1.0), shared / areas[:, None]


def _deduplicate(masks, scores):
    """Non-maximum suppression: keep the best of each region, and count its duplicates.

    The count is a measurement in its own right, because a region that many grid
    points agreed on is a different thing from one that a single prompt found.
    """
    if len(masks) == 0:
        return [], np.zeros(0, dtype=int)
    overlap, _ = _overlaps(masks)
    order = np.argsort(-scores)
    gone = np.zeros(len(masks), dtype=bool)
    kept, votes = [], []
    for index in order:
        if gone[index]:
            continue
        same = (overlap[index] > DUPLICATE) & ~gone
        gone |= same
        kept.append(int(index))
        votes.append(int(same.sum()))
    return kept, np.array(votes)


def _depth_jumps(picture) -> np.ndarray:
    """How far the depth reading moves within one pixel's reach of each pixel.

    A ray that hit nothing is treated as further away than any surface, so the
    edge of the table reads as the step it is rather than as a smooth run.
    """
    depth = np.asarray(picture.depth, dtype=np.float32)
    hit = np.isfinite(depth)
    beyond = float(depth[hit].max()) + 1.0 if hit.any() else 1.0
    filled = np.where(hit, depth, beyond).astype(np.float32)
    around = np.ones((3, 3), np.uint8)
    return cv2.dilate(filled, around) - cv2.erode(filled, around)


def _roundness(mask: np.ndarray) -> float:
    """The mask's area against the area its own outline could enclose.

    One for a filled disc, and well under one for a ring, for a crescent or for
    two footprints joined by a strip of table. A ratio, so it means the same
    thing whatever size the region is.
    """
    outlines, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    around = sum(cv2.arcLength(outline, True) for outline in outlines)
    if around <= 0.0:
        return 0.0
    return float(4.0 * math.pi * mask.sum() / (around * around))


def _table_area(points: np.ndarray) -> float:
    """How much table the proposal's points stand over, in square millimetres.

    Counted as cells of the table the points fall in, one pixel wide, so that the
    lid of a glass and the wall below it do not count their table twice.
    """
    cell = _metres_per_pixel()
    cells = np.unique(np.round(points[:, :2] / cell).astype(np.int64), axis=0)
    return float(len(cells) * cell * cell * 1e6)


def _measure(picture, mask, found, jumps, step, camera, widths) -> list[float]:
    """Seven of the keeper's eight numbers; the eighth needs the other proposals."""
    rows, columns = found.pixels[:, 0], found.pixels[:, 1]
    points = render.to_world(picture, rows, columns)

    low, high = widths
    edge = mask & ~cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    return [
        (found.width - low) / (high - low),  # where its width falls in the kind's range
        _roundness(mask),
        float(np.median(points[:, 2]) - TABLE_TOP_Z),  # how far its surface stands off the table
        float(math.dist((found.x, found.y), camera)),  # how far it sits from under the camera
        float(np.mean(jumps[edge] > step)) if edge.any() else 0.0,  # how much of its edge is a step
        _table_area(points),
    ]


def _proposals(picture, kind, masks, scores, stability, votes) -> list[Proposal]:
    """The shortlist, each proposal with its eight measurements.

    A mask the shared arithmetic cannot fit a footprint to is dropped before the
    keeper rather than shown to it: the keeper reads measurements on the table,
    and there are none to read.
    """
    widths = data.widths(kind)
    jumps = _depth_jumps(picture)
    step = STEP_OF_SHORTEST * data.shortest(kind)
    camera = tuple(picture.camera_to_world[:2, 3])

    fitted = [(index, masks_to_glasses.one_glass(picture, masks[index])) for index in range(len(masks))]
    usable = [(index, found) for index, found in fitted if found is not None]
    if not usable:
        return []

    kept_masks = masks[[index for index, _ in usable]]
    _, covered = _overlaps(kept_masks)
    # How this proposal sits among the others: positive when it is a part of
    # something larger, negative when it is the larger thing.
    inside = covered > CONTAINED
    np.fill_diagonal(inside, False)
    nesting = inside.sum(1) - inside.sum(0)

    proposals = []
    for place, (index, found) in enumerate(usable):
        numbers = _measure(picture, masks[index], found, jumps, step, camera, widths)
        numbers.insert(4, float(votes[index]))  # how many prompt points returned this same mask
        numbers.append(float(nesting[place]))
        proposals.append(
            Proposal(
                masks[index],
                float(scores[index]),
                float(stability[index]),
                int(votes[index]),
                found,
                np.array(numbers, dtype=float),
            )
        )
    return proposals


def survey(picture, kind: str) -> tuple[_Look, list[Proposal]]:
    """One picture through SAM, and the proposals that survived, measured and ready."""
    look = _Look(pictures.shade(picture))
    masks, scores, stability = look.at(_grid(prompt_spacing(kind)))
    kept, votes = _deduplicate(masks, scores)
    if not kept:
        return look, []
    return look, _proposals(picture, kind, masks[kept], scores[kept], stability[kept], votes)


def _label(mask: np.ndarray, visible: list[np.ndarray]) -> int:
    """Which of the three answers a proposal deserves, from the truth the simulator holds.

    Arithmetic rather than judgement: which glasses are mostly inside it, and
    whether it is mostly those glasses rather than the table they stand on.
    """
    holds = [glass for glass in visible if (mask & glass).sum() >= MOSTLY * glass.sum()]
    if not holds:
        return DROP
    together = np.logical_or.reduce(holds)
    if (mask & together).sum() < MOSTLY * mask.sum():
        return DROP
    return ONE_GLASS if len(holds) == 1 else MORE_THAN_ONE


def table(examples: Iterable[data.Example]) -> tuple[np.ndarray, np.ndarray, int]:
    """The keeper's training table: eight measurements per proposal, and its answer.

    One row per proposal rather than one per picture, so a few dozen scenes are
    enough to fit on. The labels cost nothing, because the simulator returns a
    glass identity for every pixel.
    """
    rows, answers, pictures_seen = [], [], 0
    for example in examples:
        for sight in example.sights:
            pictures_seen += 1
            for proposal in survey(sight.picture, example.kind)[1]:
                rows.append(proposal.features)
                answers.append(_label(proposal.mask, sight.visible))
    if not rows:
        raise RuntimeError(f"SAM proposed nothing on any of the {pictures_seen} pictures asked for")
    return np.stack(rows), np.array(answers), pictures_seen


def _calibration(answers: np.ndarray) -> tuple[str, int]:
    """How to straighten the probability, and over how many folds.

    Calibration holds one part of the table out from the fit and asks how often
    the claims made about it came true, so the rarest answer has to appear in
    every fold. Too few scenes and that cannot be done at all, and the answer is
    more scenes rather than a probability nothing checked.
    """
    rarest = min(int((answers == answer).sum()) for answer in np.unique(answers))
    if rarest < 2:
        raise RuntimeError(
            f"only {rarest} example of one of the three answers in this table, which is too few to "
            f"calibrate the keeper on. Fit it on more scenes."
        )
    method = "isotonic" if rarest >= ENOUGH_FOR_ISOTONIC else "sigmoid"
    return method, min(FOLDS, rarest)


def fit(examples: Iterable[data.Example], *, amodal: bool, save: Path) -> Mapping:
    """Fit the keeper on ``examples`` and save it to ``save``.

    The probability is calibrated as part of the fit, because two thresholds are
    put on it afterwards and a threshold on an uncalibrated number means nothing.

    ``amodal`` is what solutions 9 and 10 differ by and this solution has no use
    for: the keeper is asked which region is a glass, not how much of a glass a
    region is, so its labels come from the pixels the camera saw either way.
    """
    if amodal:
        raise ValueError("the keeper is fitted on what the camera saw; it has no amodal target")
    features, answers, seen = table(examples)
    trees = HistGradientBoostingClassifier(max_iter=ROUNDS, max_depth=DEPTH, random_state=FITTING_SEED)
    method, folds = _calibration(answers)
    keeper = CalibratedClassifierCV(trees, method=method, cv=folds)
    keeper.fit(features, answers)
    torch.save(keeper, save)
    counted = {ANSWERS[answer]: int((answers == answer).sum()) for answer in sorted(set(answers.tolist()))}
    return {"pictures": seen, "proposals": len(features), "calibrated": method} | counted


@dataclass(frozen=True)
class Finder:
    """A fitted keeper, ready to be handed pictures."""

    keeper: object

    def chances(self, features: np.ndarray) -> np.ndarray:
        """The calibrated chance of each of the three answers, in this module's order.

        The classifier only knows about the answers its training table held, so
        its columns are put back in a fixed order before anything reads them.
        """
        if len(features) == 0:
            return np.zeros((0, len(ANSWERS)))
        given = self.keeper.predict_proba(features)
        ordered = np.zeros((len(features), len(ANSWERS)))
        for column, answer in enumerate(self.keeper.classes_):
            ordered[:, int(answer)] = given[:, column]
        return ordered

    def find(self, picture, kind: str) -> tuple[list[Found], list[str]]:
        """The whole chain on one picture: the glasses found, and what could not be settled.

        The keeper sorts the proposals and the geometry disposes. A proposal it
        wants to keep still has to fit a circle inside the range this kind of
        glass can be, so a wrong keep becomes a doubtful report rather than a
        glass that is not there.
        """
        look, shortlist = survey(picture, kind)
        low, high = data.widths(kind)
        read = np.stack([p.features for p in shortlist]) if shortlist else np.zeros((0, len(MEASUREMENTS)))
        told = self.chances(read)

        kept: list[Found] = []
        doubts: list[str] = []
        # Most confident first, so that where two reports land on one place it is
        # the surer of them that keeps the place.
        surest = sorted(range(len(shortlist)), key=lambda index: -told[index].max())
        for proposal, chance in ((shortlist[index], told[index]) for index in surest):
            if int(np.argmax(chance)) == MORE_THAN_ONE:
                apart = _separate(look, picture, proposal, kind)
                if apart:
                    kept.extend(apart)
                else:
                    doubts.append("more than one glass, and they did not come apart")
            elif chance[ONE_GLASS] >= SURE_ONE_GLASS:
                if low <= proposal.found.width <= high:
                    kept.append(proposal.found)
                else:
                    doubts.append("kept, but its width is outside what this kind can be")
            elif chance[ONE_GLASS] > SURE_NOT_ONE_GLASS:
                doubts.append("cannot tell whether this is one glass")
        return masks_to_glasses.one_per_place(kept, low), doubts


def _separate(look, picture, proposal: Proposal, kind: str) -> list[Found]:
    """Prompt again inside one proposal, to see whether it comes apart into glasses.

    Two glasses in line with the camera make one region with no seam along it,
    which is why SAM proposed them as one thing. A fresh grid inside that region
    sometimes finds the step between the near glass's rim and the far one's wall,
    and only widths the kind allows are believed.
    """
    points = _grid(prompt_spacing(kind), inside=proposal.mask)
    if len(points) < 2:
        return []
    masks, scores, _ = look.at(points)
    kept, _ = _deduplicate(masks, scores)
    low, high = data.widths(kind)

    apart = []
    for index in kept:
        mask = masks[index] & proposal.mask
        found = masks_to_glasses.one_glass(picture, mask)
        if found is not None and low <= found.width <= high:
            apart.append(found)
    apart = masks_to_glasses.one_per_place(apart, low)
    return apart if len(apart) >= 2 else []


def load(save: Path) -> Finder:
    """The fitted keeper, as ``fit`` saved it."""
    return Finder(torch.load(save, weights_only=False))
