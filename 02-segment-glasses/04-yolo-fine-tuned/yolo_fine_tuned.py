"""Solution 4: the borrowed YOLO26-seg model, with its training continued here.

The same library, the same model and the same downloaded file as solution 3.
One thing differs, which is that the weights this module loads have had their
training continued on this cell's own pictures, and the borrowed list of
everyday categories has been replaced by the single class "glass". That change
comes with the training rather than beside it, because a model cannot be
trained towards this cell's labels while still being asked which everyday
object it is looking at. So nothing varies between the pair that the training
did not bring, and the gap between the two scorecards is a measurement of what
fine-tuning bought.

**What one class removes.** Two of solution 3's failures go with the borrowed
category list. A glass can no longer come back twice under two neighbouring
everyday categories, because there is one name, so the two candidates covering
one glass are candidates of the same class and the model's own suppression step
reduces them to one answer before anything leaves it. And a glass can no longer
be lost because the model named it a bowl or a vase and a filter on names threw
it away, because there is no filter on names. This file therefore has no list of
acceptable categories anywhere in it, and that absence is the solution.

**What one class does not give** is the kind of glass. The model reports no kind
at all. Nothing asks it to: every glass in one arrangement is the same kind and
the cell is told which.

**What training does not fix.** The outline is still built coarsely — a short
weighted sum of pattern images, cut at a threshold and then enlarged — so a
thin stem is still the first thing lost and the mask's edge is still
approximate, which the shared arithmetic feels when it reads a width off that
edge. Fine-tuning closes the domain gap; it does not make the outline fine. The
masks are also still the pixels the camera saw, so a glass standing partly
behind another is still read as a smaller glass in the wrong place, and a glass
nothing saw at all leaves no candidate and no entry.

**The one refusal, and the one thing that excuses it.** A candidate whose
footprint no glass of this kind could have is reported as a doubt rather than
kept, which is the prescribed check and can only turn a glass into a doubt. It
is **not** applied to a candidate whose mask reaches the edge of the picture. At
the cell's own survey height one picture does not hold the glass zone, so a
glass near the frame edge shows part of its footprint and the width read off it
is not the glass's width. Two measurements say so. The bench's own exact masks,
one station at a time over 20 held-out spawned scenes, give a footprint outside
the kind's range for 66 of 297 glass sightings, and every one of those 66
reaches the frame edge; and of this model's own refusals over eight of those
scenes, all eleven too-narrow ones had a mask touching that edge. So the check
was refusing the view rather than the mask, and the fact it now reads first is
`masks_to_glasses.Found.cut_off`. The survey's three overlapping stations are
what make this safe rather than generous: where a glass was seen squarely by
another station, that station's report is the one `marking.survey` keeps.

**The camera belongs to data.py**, which stands it at the cell's own survey
height and takes the pictures a survey there needs. Nothing here chooses a
viewpoint, so this solution and its partner are guaranteed the same pictures.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import dataset
import numpy as np

import data
import device
import masks_to_glasses
import pictures
import render
from masks_to_glasses import Found

# The borrowed model, by the name Ultralytics fetches it under. **Solution 3
# must name this same file.** The pair is only a measurement of what training
# bought while both start from one download; if the two constants disagree the
# comparison is between two models rather than between one model trained and
# untrained. The small end of the family, which is where both documents say to
# start, because the glasses fill a reasonable part of the frame and a larger
# model costs time without obviously buying accuracy on silhouettes this plain.
MODEL = "yolo26n-seg.pt"

# The one class that replaces the borrowed category list.
CLASS = dataset.NAME

# The two settings this solution has. The bar is on the model's own confidence
# number: below it a candidate is ignored. The overlap is how much of a
# better-scoring candidate a candidate may cover before it is discarded as the
# same object arriving twice. Both are ratios, so neither has to be justified
# against the size of anything in the room.
#
# **Both are held at solution 3's values**, because the pair is only a
# measurement of what training bought while everything except the training is
# the same. The document says the bar could be chosen on the bench's training
# half now that the number comes from weights fitted here, and that has not been
# done: it is solution 3's hand-set bar, unmoved, so that moving it could not be
# mistaken for what training bought.
CONFIDENCE, OVERLAP = 0.25, 0.7

# The picture is 320 by 240 and this model works in multiples of 32, so it is
# letterboxed into a square this wide. The same size when training and when
# answering, because a model shown one size and asked about another is being
# asked about a different picture.
PICTURE = 320

# How much of one training run is kept back for the run to check itself on, as
# one scene in this many. Taken as every nth scene rather than as the last part
# of the list, because the scenes arrive spawned first and crowded afterwards,
# and a check made on crowded scenes alone would answer a different question.
CHECK_EVERY = 4

# How much training a default run does. Small on purpose, so that a short run
# is possible on this machine: it trains through MPS, which is this machine's
# integrated graphics, and there is no separate graphics card. A default run
# shows the method working; it is not enough to claim anything about the method,
# and train.py's flags are what buy that.
SCENES, EPOCHS = 16, 10

# How many pictures go through the model at once while training. Small, because
# the graphics processor here shares its memory with the main one.
BATCH = 8

# The training run is the same every time it is given the same scenes, so a
# scorecard claimed on it can be repeated.
FITTING_SEED = 0

# The two reasons a candidate is handed over instead of kept. Fixed strings,
# because the scorecard counts the doubts by reason.
TOO_LITTLE = "found something with too few depth readings to place"
NO_SUCH_WIDTH = "its width is outside what this kind can be, with the whole of it in frame"

WEIGHTS = Path(__file__).parent / "weights"


def borrowed() -> Path:
    """The starting weights, fetched on the first call and found on disk afterwards.

    Into this folder rather than the home directory, so that what a run depends
    on sits beside the run and ``weights/`` can be deleted to start again. The
    file is large, it comes from outside the project, and it is not committed.
    """
    from ultralytics.utils.downloads import attempt_download_asset

    WEIGHTS.mkdir(parents=True, exist_ok=True)
    return Path(attempt_download_asset(WEIGHTS / MODEL))


def fitted() -> Path:
    """Where ``train.py`` leaves the fine-tuned weights and ``run.py`` reads them back.

    Beside the download, because it is the same kind of thing: large, remade by
    a command, and bound by the download's own AGPL-3.0 licence, since a file
    derived from an AGPL work carries that licence with it.
    """
    WEIGHTS.mkdir(parents=True, exist_ok=True)
    return WEIGHTS / "fine-tuned.pt"


@dataclass(frozen=True)
class Finder:
    """The fine-tuned model, ready to be handed pictures."""

    model: object  # an ultralytics YOLO holding the fine-tuned weights

    def candidates(self, picture) -> tuple[np.ndarray, np.ndarray]:
        """What the model makes of one picture: a mask per candidate, surest first.

        The input is the grey picture shaded from depth, the same one every
        solution in this folder is shown. Its three channels all hold that one
        grey, so whether the library reads them as red-green-blue or the other
        way round makes no difference to anything.

        The bar on the confidence number and the discarding of candidates that
        overlap a better one both happen inside this call. With one class there
        is nothing left to do afterwards: where solution 3 has to filter the
        names it got back and collapse a glass that arrived under two of them,
        here there is one name and the model's own suppression has already
        reduced each cluster of candidates to a single answer.
        """
        answer = self.model.predict(
            pictures.shade(picture),
            conf=CONFIDENCE,
            iou=OVERLAP,
            imgsz=PICTURE,
            device=device.pick(),
            retina_masks=True,  # the masks come back at the picture's own size
            verbose=False,
        )[0]
        if answer.masks is None:
            return np.zeros((0, render.HEIGHT, render.WIDTH), dtype=bool), np.zeros(0)
        masks = np.asarray(answer.masks.data.cpu().numpy()) > 0.5
        sure = np.asarray(answer.boxes.conf.cpu().numpy())
        # Surest first, so that where two reports land on one place on the table
        # it is the model's own best answer that keeps the place.
        order = np.argsort(-sure)
        return masks[order], sure[order]

    def find(self, picture, kind: str) -> tuple[list[Found], list[str]]:
        """The glasses in one picture, and what could not be settled.

        ``kind`` is the kind of glass on the table, which the cell is told. The
        model is not asked about it and could not answer, because it knows one
        class. What the kind settles is the range of footprints a glass here
        could have, so that a candidate whose footprint no glass of this kind
        could have is reported as a doubt rather than kept as a glass. A limit
        on the kind, never the size of any one glass.

        A candidate the frame cut short is kept whatever its width, for the
        reason this module's own description gives: the picture ran out before
        the glass did, so its width is not the glass's width and cannot refuse
        it.
        """
        narrowest, widest = data.widths(kind)
        kept: list[Found] = []
        doubts: list[str] = []
        for mask in self.candidates(picture)[0]:
            found = masks_to_glasses.one_glass(picture, mask)
            if found is None:
                doubts.append(TOO_LITTLE)
            elif narrowest <= found.width <= widest or found.cut_off:
                kept.append(found)
            else:
                doubts.append(NO_SUCH_WIDTH)
        return masks_to_glasses.one_per_place(kept, narrowest), doubts


def load(save: Path) -> Finder:
    """The fine-tuned model, as ``fit`` saved it."""
    from ultralytics import YOLO

    return Finder(YOLO(str(save), task="segment"))


def fit(examples: Iterable[data.Example], *, amodal: bool, save: Path, epochs: int = EPOCHS) -> Mapping:
    """Continue the borrowed model's training on ``examples``, and save the result to ``save``.

    What is fitted is every weight in the model, starting from the downloaded
    file rather than from random numbers, which is why a model of this size can
    be trained at all on a machine with no separate graphics card. The head is
    rebuilt for one class, so the weights that held the borrowed category names
    are the only ones that do not carry over.

    The scenes are split into a part to fit on and a part for the run to check
    itself on while it runs. Both come from below the bench's dividing line, so
    neither is a scene a scorecard is later claimed on.

    ``amodal`` is the flag the solutions that differ by their target take. This
    one has no use for it: it is trained on the pixels the camera saw, and the
    whole silhouette is solution 6's choice.
    """
    if amodal:
        raise ValueError(
            "this model is trained on the pixels the camera saw, so it has no amodal target; "
            "training towards the whole silhouette is solution 6's choice"
        )
    drawn = list(examples)
    fitting = [example for place, example in enumerate(drawn) if place % CHECK_EVERY]
    checking = [example for place, example in enumerate(drawn) if not place % CHECK_EVERY]
    if not fitting or not checking:
        raise RuntimeError(
            f"{len(drawn)} scenes cannot be both fitted on and checked on; ask for {CHECK_EVERY} or more"
        )
    from ultralytics import YOLO

    described, counts = dataset.build(fitting, checking)
    model = YOLO(str(borrowed()), task="segment")
    model.train(
        data=str(described),
        epochs=epochs,
        imgsz=PICTURE,
        batch=BATCH,
        device=device.pick(),
        project=str(Path(__file__).parent / "runs"),
        name="fine-tune",
        exist_ok=True,
        # One process. The set is small, the pictures are already on disk, and a
        # worker per core costs more to start than it saves in reading.
        workers=0,
        seed=FITTING_SEED,
        deterministic=True,
        plots=False,
        verbose=False,
    )
    shutil.copy(model.trainer.best, save)

    measured = model.trainer.metrics or {}
    return {
        "starting weights": borrowed().name,
        "classes": CLASS,
        "scenes fitted on": len(fitting),
        "pictures fitted on": counts[dataset.FIT]["pictures"],
        "outlines fitted on": counts[dataset.FIT]["outlines"],
        "pictures checked on": counts[dataset.CHECK]["pictures"],
        "epochs": epochs,
        "run": str(model.trainer.save_dir),
        # What the training run measured on its own check pictures, which are
        # below the dividing line. Not a score: run.py is what scores this.
    } | {name: round(float(value), 3) for name, value in measured.items() if "mAP50(M)" in name}
