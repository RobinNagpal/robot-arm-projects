"""Solution 5, the upper rung: one word instead of a grid of points, and no keeper.

The same solution one generation on. A promptable foundation model is still
borrowed whole and still never trained here, and the only thing that changes is
where the judgement "this is a glass" lives. On the lower rung it lives in the
keeper, a small model fitted in this cell from a table of measurements. Here it
lives inside the borrowed weights and is reached through a word.

So this file is mostly what is missing from `sam_keeper.py`. There is no grid of
prompt points, because the prompt is a phrase. There is no scoring and stability
gate and no duplicate removal, because what comes back is one outline per
instance of the concept rather than a heap. There is no table of measurements,
no classifier, no calibration, and no training step of any kind, because nothing
here is fitted. What is left is the model, the word, and the arithmetic in
`reports.py` that both rungs end with.

**What that costs is the thing this solution values most.** When the keeper
refuses a region, the reason is eight named measurements and the answer that
followed from them, and `sam_keeper.explanation` prints them. Here there is
nothing to print. A region is a glass because weights nobody here can inspect
say the word fits it, and the only available response to a glass it misses is to
try a different phrase. That is the whole of the trade the document weighs, and
it is why both rungs are run on the same held-out scenes rather than one being
chosen in advance.

**The weights are gated and could not be run on this machine.** `transformers`
in this environment has the model, and what follows is written against its
documented interface, but the upload will not hand its weights to an account
that has not been granted them, so no scorecard for this rung has been produced
here. See this folder's README. That is also the practical note the document
makes: the permissive licence of one generation is not inherited by the next.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import reports
import torch
import weights

import data
import device
import pictures
from masks_to_glasses import Found

# The word. One named constant, because it is the whole of this rung's deciding
# and the only knob it has: there is nothing else to turn when a glass is
# missed. It names the concept the cell is after rather than the kind on the
# table, since the kind is a range of sizes and not a different object.
PROMPT = "drinking glass"

# How sure the model has to be that an instance it returns is the concept the
# word named. The model's own number, and uncalibrated: unlike the keeper's
# probability, nothing here can check what it claims against how often the
# claim came true, because there is no fitted part to check it with.
SURE_ENOUGH = 0.3

# Where the outline is cut out of the model's soft mask, which is the same kind
# of cut-off the lower rung nudges to measure stability.
MASK_CUT = 0.5


@lru_cache(maxsize=1)
def _model():
    """The borrowed model as downloaded, on whichever processor this machine has."""
    from transformers import Sam3Model, Sam3Processor

    path = weights.sam3()
    where = device.pick()
    model = Sam3Model.from_pretrained(path).to(where).eval()
    return Sam3Processor.from_pretrained(path), model, where


def outlines(picture, prompt: str = PROMPT):
    """Every instance of ``prompt`` the borrowed model finds in one picture.

    One pass, because the word goes in with the picture rather than after it.
    There is no heap to clean up: what comes back is already one outline per
    instance, each with the model's own score.
    """
    processor, model, where = _model()
    image = pictures.shade(picture)
    asked = processor(images=image, text=prompt, return_tensors="pt").to(where)
    with torch.no_grad():
        answered = model(**asked)
    found = processor.post_process_instance_segmentation(
        answered, threshold=SURE_ENOUGH, mask_threshold=MASK_CUT, target_sizes=[image.shape[:2]]
    )[0]
    order = found["scores"].argsort(descending=True).cpu()
    masks = found["masks"][order].cpu().numpy().astype(bool)
    return list(masks), found["scores"][order].cpu().numpy()


def fit(examples: Iterable[data.Example], *, amodal: bool, save: Path) -> Mapping:
    """Refused: this rung fits nothing at all, which is the point of it.

    The interface is here because every solution in this folder answers the same
    three calls, and because a command that asks to fit this one should say why
    there is nothing to fit rather than quietly write an empty file.
    """
    raise SystemExit(
        "there is nothing to fit on this rung: the naming is done inside the borrowed weights, "
        "reached through a word. Run it without training it."
    )


@dataclass(frozen=True)
class Finder:
    """The borrowed model and the word, ready to be handed pictures."""

    prompt: str = PROMPT

    def find(self, picture, kind: str) -> tuple[list[Found], list[str]]:
        """The whole chain on one picture: the glasses found, and what could not be settled.

        The model names and the arithmetic disposes. ``kind`` reaches the word
        not at all — it is what the width check is against, which is the one
        thing this rung can still refuse a borrowed answer with.
        """
        masks, _ = outlines(picture, self.prompt)
        return reports.believable(picture, masks, kind)


def load(save: Path | None = None) -> Finder:
    """A finder. ``save`` is ignored, because nothing was ever fitted to save."""
    return Finder()
