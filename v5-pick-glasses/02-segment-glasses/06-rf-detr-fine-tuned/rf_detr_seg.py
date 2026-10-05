"""Solution 6: RF-DETR-Seg, fine-tuned here, on one class, with two targets.

The model is a transformer that detects and segments in one pass. It carries a
fixed number of **queries**, each of which either reports one glass or reports
nothing, and each query's mask is computed over the whole picture rather than
inside a rectangle. Two things follow and both matter here. Two glasses whose
outlines join occupy two slots from the beginning, so nothing has to divide a
joined region. And **there is no rectangle for a mask to escape**, so a mask is
free to cover more of a glass than the picture shows.

**The second rung uses that freedom.** ``amodal`` in ``fit`` chooses what each
mask is trained against: the pixels the camera can see of a glass, or the
glass's whole silhouette. Nothing else about the model changes — not its shape,
not its last layer, only what the masks are compared with. That is the whole
difference between the two rungs.

**The trap, which is the one thing here most easily got wrong.** A mask covering
a whole silhouette claims pixels where the camera saw some other glass's
surface. The depth reading at such a pixel belongs to that other glass, so
feeding it into the shared arithmetic drags the computed place across the gap
and onto the glass in front. With exact masks the bench measured the cost: 46 mm
out against 12 mm. So every mask is split into its **observed** part and its
**asserted** part before the arithmetic runs, and ``masks_to_glasses`` is handed
the asserted pixels and leaves their readings out.

**How the split is read off the answer.** A camera looking straight down sees a
glass's outline thrown outwards from the point below it, so of two glasses whose
outlines overlap, the one standing **nearer that point** is the one in front.
Every pixel two reports both claim therefore belongs to whichever of them stands
nearer the point below the camera, and the other report must call that pixel
asserted. Nothing in this needs the truth: the places come from the pixels each
report holds alone, and the point below the camera comes from the camera's own
pose, which the cell knows from its joint encoders. The one case it cannot see
is a glass hidden by something the model never reported, and there is nothing in
the picture to work that out from either.

**Two checks, each of which can only refuse.** The width must lie inside the
range this kind of glass allows. And the asserted part must lie where the camera
could not see: a mask claiming a glass continues across a patch with a clear
view of it, where the reading comes back off something standing nowhere near
this glass, is contradicting a direct observation. A glass failing either is
reported as doubtful rather than placed.

**The visible fraction travels with every report**, because every consumer
further down has its own tolerance for how much of an answer was asserted and
none of them can apply it once the two parts have been merged.

**The kind of glass is handed in with the picture**, as the problem says the
cell is told it. What it settles here is the range of footprints a glass could
have, and no glass's size is written down anywhere.

**The camera belongs to data.py.** Nothing here chooses a viewpoint, so all six
solutions are guaranteed the same pictures.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import labels
import numpy as np
import weights

import data
import device
import masks_to_glasses
import pictures
import render
from masks_to_glasses import Found

# Which size of the model is fine-tuned. The smallest, because this machine's
# graphics processor shares its memory with the main processor and the pictures
# are 320 by 240; the package offers larger ones for a machine that has room.
SIZE = "RFDETRSegNano"

# What a query's class answer has to reach before its slot counts as filled.
# One plain number with an obvious meaning. There is no second number deciding
# when two claims are duplicates, because the training matched slots to glasses
# one to one and the duplicates were trained out rather than pruned out.
FILLED = 0.5

# The fine-tune. Short and small because the fitting runs on one laptop; both
# are arguments to ``fit`` so a longer run needs no edit here.
EPOCHS, BATCH, LEARNING_RATE = 12, 4, 1e-4

# How much of the training stream is held back to validate on. Still below the
# bench's held-out line, so nothing here can reach a scene a score is claimed on.
VALIDATION_SHARE = 0.2

# How much of a mask may read as a surface standing clear of this glass's own
# footprint before the report is doubtful rather than placed. A few pixels at
# the edge of an outline are ordinary; a patch of them means the mask leaked
# onto something else.
#
# Below masks_to_glasses.SPREAD's own tail on purpose, so that this check and
# the width check do different work. The width is twice the 95th percentile of
# how far the cloud reaches, so a mask with more than a twentieth of its
# readings beyond the kind's widest footprint already comes out too wide and is
# refused for that. What is left for this check is the smaller leak: a patch too
# small to move the width, large enough to be a claim about a part of the scene
# the camera plainly saw something else at.
OVER_A_CLEAR_VIEW = 0.03

# The order the package writes its best checkpoints in, best first. The averaged
# weights where there are any, because the fine-tune keeps a running average and
# that is the file the package itself treats as the result of a run.
BEST = ("checkpoint_best_ema.pth", "checkpoint_best_regular.pth", "checkpoint_best_total.pth")


@dataclass(frozen=True)
class Seen:
    """One filled slot, with the observed and the asserted part kept apart."""

    mask: np.ndarray  # boolean, the shape of the picture: every pixel this slot claims
    asserted: np.ndarray  # the pixels of it the camera did not see this glass at
    score: float
    found: Found | None  # the place and width, from the observed pixels alone
    doubt: str | None  # why it is not being reported, or None

    @property
    def visible_fraction(self) -> float:
        """How much of this glass the camera actually saw. One division, and it travels."""
        claimed = int(self.mask.sum())
        return 0.0 if claimed == 0 else 1.0 - float(self.asserted.sum()) / claimed


# ------------------------------------------------------------------- the model


@lru_cache(maxsize=2)
def _loaded(checkpoint: str):
    """The fine-tuned model, built back from the checkpoint ``fit`` wrote."""
    weights.borrowed()
    from rfdetr import from_checkpoint

    return from_checkpoint(checkpoint, device=str(device.pick()))


def fresh():
    """RF-DETR-Seg as Roboflow publishes it, before any fitting here.

    The borrowed weights are fitted on a large collection of ordinary labelled
    pictures. They download on first use, which is the one thing in this folder
    that needs the network.
    """
    weights.borrowed()
    import rfdetr

    return getattr(rfdetr, SIZE)(device=str(device.pick()))


def _slots(model, picture) -> list[tuple[np.ndarray, float]]:
    """Every slot the model filled on one picture: its mask, and how sure it is.

    The slots that report "nothing" are dropped by the score threshold. Nothing
    else is removed, because the one-to-one matching during training is what
    stops two slots reporting the same glass.
    """
    answer = model.predict(pictures.shade(picture), threshold=FILLED)
    if answer.mask is None:
        return []
    return [
        (np.asarray(mask, dtype=bool), float(score))
        for mask, score in zip(answer.mask, answer.confidence, strict=True)
    ]


# ------------------------------------------- observed pixels against asserted


def hidden_by_others(picture, masks: list[np.ndarray], nadir: tuple[float, float]) -> list[np.ndarray]:
    """Per mask, the pixels of it another report standing nearer the camera covers.

    Splay throws every outline outwards from the point below the camera, so of
    two reports whose masks overlap, the one standing nearer that point is the
    one in front and the reading in the overlap is its surface. Each report's own
    place comes from the pixels no other report claims, which are the pixels
    nothing can be hiding it at.
    """
    usable = [mask & np.isfinite(picture.depth) for mask in masks]
    if not usable:
        return []
    contested = np.sum(np.stack(usable), axis=0) > 1
    away = []
    for mine in usable:
        alone = masks_to_glasses.one_glass(picture, mine & ~contested)
        away.append(np.inf if alone is None else float(np.hypot(alone.x - nadir[0], alone.y - nadir[1])))

    behind = []
    for index, mine in enumerate(usable):
        theirs = np.zeros_like(mine)
        for other, nearer in enumerate(usable):
            if other != index and away[other] < away[index]:
                theirs |= nearer
        behind.append(mine & contested & theirs)
    return behind


def over_a_clear_view(picture, mask: np.ndarray, found: Found, widest: float) -> np.ndarray:
    """The pixels of a mask that contradict what the camera plainly saw.

    A model claiming a glass continues behind the glass in front of it is
    claiming something about a part of the scene the camera could not see, which
    is allowed. A model claiming it continues across a patch the camera had a
    clear view of, where the reading comes back off a surface standing further
    from this glass than any glass of this kind is wide, is contradicting an
    observation. That is arithmetic on the kind's own limits, with no reference
    to the model or to the truth.
    """
    rows, columns = np.nonzero(mask)
    wrong = np.zeros_like(mask)
    if rows.size == 0:
        return wrong
    points = render.to_world(picture, rows, columns)
    off = np.hypot(points[:, 0] - found.x, points[:, 1] - found.y) > widest / 2.0
    off &= np.isfinite(points).all(1)
    wrong[rows[off], columns[off]] = True
    return wrong


def cut_off(mask: np.ndarray) -> bool:
    """Whether a mask runs off the edge of the frame, so part of the glass is outside it."""
    return bool(mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any())


def _refused(mask, asserted, score, found, why) -> Seen:
    """One refusal, saying as well whether the glass was cut off at the frame edge.

    Worth saying because it is much the commonest reason a mask here is refused,
    and it is about the view rather than about the model: at the cell's own
    survey height one picture does not hold the glass zone. The survey stands at
    three overlapping stations for exactly this, so a glass cut off in one
    picture sits well inside another's and is reported from there.
    """
    if cut_off(mask):
        why = f"{why}, and it runs off the edge of the frame"
    return Seen(mask, asserted, score, found, why)


def _judge(picture, mask, behind, score, kind) -> Seen:
    """One slot's place and width, and whether either prescribed check refuses it.

    The width is judged first, on the observed pixels alone. That order matters:
    the clear-view check below throws away every reading standing further from
    the glass than the kind's widest footprint, so a region covering two glasses
    would come back a legal width if it ran first, and the loud failure this
    project relies on would have been quietly repaired into a plausible one.
    """
    narrowest, widest = data.widths(kind)
    first = masks_to_glasses.one_glass(picture, mask, behind)
    if first is None:
        return _refused(mask, behind, score, None, "too little of it was seen to place it")
    if not narrowest <= first.width <= widest:
        return _refused(mask, behind, score, first, "its width is outside what this kind can be")

    # Asserted twice over: hidden behind another report, and claimed where the
    # camera had a clear view. Both are left out of the arithmetic; only the
    # second is a reason to refuse.
    clear = over_a_clear_view(picture, mask & ~behind, first, widest)
    asserted = behind | clear
    found = masks_to_glasses.one_glass(picture, mask, asserted)
    if found is None:
        return _refused(mask, asserted, score, None, "too little of it was seen to place it")
    if clear.sum() > OVER_A_CLEAR_VIEW * mask.sum():
        return _refused(mask, asserted, score, found, "it claims glass where the camera saw past it")
    if not narrowest <= found.width <= widest:
        return _refused(mask, asserted, score, found, "its width is outside what this kind can be")
    return Seen(mask, asserted, score, found, None)


# ------------------------------------------------------------------ the finder


@dataclass(frozen=True)
class Finder:
    """A fine-tuned model, ready to be handed pictures."""

    checkpoint: Path

    def look(self, picture, kind: str) -> list[Seen]:
        """Every filled slot on one picture, split, measured and judged."""
        slots = _slots(_loaded(str(self.checkpoint)), picture)
        masks = [mask for mask, _ in slots]
        behind = hidden_by_others(picture, masks, data.under(picture.camera_to_world))
        return [
            _judge(picture, mask, theirs, score, kind)
            for (mask, score), theirs in zip(slots, behind, strict=True)
        ]

    def find(self, picture, kind: str) -> tuple[list[Found], list[str]]:
        """The shared interface: the glasses found, and what could not be settled."""
        return keep(self.look(picture, kind), kind)


def keep(seen: list[Seen], kind: str) -> tuple[list[Found], list[str]]:
    """Which of one picture's filled slots are reported, and what is handed on doubtful.

    A report is kept only if both checks passed. Surest first, so that where two
    reports land on one place it is the surer of them that keeps the place.

    Apart from ``find`` so that ``run.py`` can read the slots and report them in
    one pass: looking twice would cost a second pass of the model over every
    picture to arrive at the same answer.
    """
    surest = sorted(seen, key=lambda one: -one.score)
    kept = [one.found for one in surest if one.doubt is None and one.found is not None]
    doubts = [one.doubt for one in surest if one.doubt is not None]
    return masks_to_glasses.one_per_place(kept, data.widths(kind)[0]), doubts


def load(save: Path) -> Finder:
    """The fine-tuned model, as ``fit`` saved it."""
    save = Path(save)
    if not save.exists():
        raise FileNotFoundError(f"there is no fine-tuned model at {save}")
    return Finder(save)


# ------------------------------------------------------------------- the fit


def _split(examples: Iterable[data.Example], share: float) -> tuple[list, list]:
    """The training scenes and the scenes held back to validate on.

    Both come from the stream data.py hands over, which only ever draws seeds
    below the bench's held-out line, so neither can reach a scored scene.

    Taken every so many scenes rather than off the front, because the stream
    arrives spawned first and crowded afterwards, and a validation set cut off
    the front would hold none of the crowded scenes this model most needs to be
    watched on.
    """
    whole = list(examples)
    every = max(2, int(round(1.0 / share)))
    validating = whole[::every]
    return [one for index, one in enumerate(whole) if index % every], validating


def _dataset(fitting: list, validating: list, amodal: bool, folder: Path) -> dict:
    """Write both splits where the package expects to find them."""
    return {
        "train": labels.write(iter(fitting), amodal=amodal, folder=folder / "train"),
        "valid": labels.write(iter(validating), amodal=amodal, folder=folder / "valid"),
    }


def _best(folder: Path) -> Path | None:
    """The checkpoint the package calls the result of a run, or None if it wrote none."""
    return next((folder / name for name in BEST if (folder / name).exists()), None)


def fit(
    examples: Iterator[data.Example],
    *,
    amodal: bool,
    save: Path,
    epochs: int = EPOCHS,
    batch: int = BATCH,
) -> Mapping:
    """Continue the borrowed model's training on this cell's pictures, and save it.

    ``amodal`` is the whole of the difference between the two rungs: it chooses
    whether each mask is scored against the pixels the camera can see of a glass
    or against the glass's whole silhouette. The model's shape does not change.
    """
    save = Path(save)
    folder = weights.workings("amodal" if amodal else "modal")
    fitting, validating = _split(examples, VALIDATION_SHARE)
    written = _dataset(fitting, validating, amodal, folder / "dataset")

    model = fresh()
    model.train(
        dataset_dir=str(folder / "dataset"),
        output_dir=str(folder / "run"),
        epochs=epochs,
        batch_size=batch,
        lr=LEARNING_RATE,
        class_names=[labels.CLASS],
        tensorboard=False,
    )
    best = _best(folder / "run")
    if best is None:
        raise RuntimeError(f"the fine-tune wrote no checkpoint in {folder / 'run'}")
    shutil.copyfile(best, save)
    counted = {
        f"{split} {measure}": value
        for split, counts in written.items()
        for measure, value in counts.items()
    }
    return {
        "model": SIZE,
        "target": "whole silhouettes" if amodal else "the pixels the camera can see",
        "epochs": epochs,
        "scenes fitted on": len(fitting),
        "scenes validated on": len(validating),
    } | counted
