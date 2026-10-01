"""Solutions 9 and 10: one Mask R-CNN, and one flag that changes its target.

Solution 9 trains the mask branch against the pixels the camera can see of each
glass. Solution 10 trains it against each glass's whole silhouette, as if
nothing stood in front of it, which is called an amodal mask. Everything else —
the architecture, the borrowed weights, the optimiser, the loop, the thresholds
and the inference path — is the same for both, so this is one file and the flag
is the only fork in it. Two files would hide the claim both documents make,
which is that the difference between the two solutions is a target and nothing
else. The flag is also the only thing this module knows: it is never told which
solution it is, so it cannot treat one better than the other.

The flag reaches the mask and the box together, and that is not a detail. Mask
R-CNN paints a mask *inside* a box, on a small grid stretched to the box's size,
so a mask cannot reach past its box's edge. A whole silhouette sticks out beyond
the visible part of a hidden glass, so if the box were still drawn round the
visible pixels every completion would be clipped at the box edge and the model
would be asked for something it has no room to express. Both targets therefore
take the box from the same mask they take the pixels from, which is one line
rather than two cases.

**The camera belongs to data.py**, which stands it at the cell's own survey
height and takes the three pictures a survey there needs. Nothing in this file
chooses a viewpoint, so solution 8 and these two are guaranteed the same
pictures and the scorecards can be compared.

**What the completion is worth, and where it is not worth anything.** An amodal
mask claims pixels whose depth reading is some other glass's surface. Handing
those readings to the shared arithmetic drags the fitted centre onto the glass in
front, which was measured rather than argued, so they are named here and left
out: ``observed`` and ``asserted`` split every reported mask, and the split is
read off the answer itself, because where two reported outlines overlap the
nearer of the two is what the camera saw there. Solution 10's own document asks
for exactly that separation. What the completion then supplies is the split and a
glass reported at all where a truncated mask would have been too small to fit; it
supplies no depth reading, because it has none to supply.
"""

from __future__ import annotations

import random
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torchvision.models.detection import maskrcnn_resnet50_fpn_v2
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.models.detection.mask_rcnn import MaskRCNNPredictor

import data
import device
import masks_to_glasses
import pictures
import weights
from masks_to_glasses import Found

# Background and glass. The borrowed weights know 91 classes of everyday
# object; both predictors are replaced because neither of those lists is this.
CLASSES = 2

# The width of the mask branch's last hidden layer, as torchvision builds it.
MASK_HIDDEN = 256

# How many of the backbone's stages are let move. The early stages hold edge
# and gradient detectors, and an edge in a shaded depth picture is the same
# thing as an edge in a photograph, so they arrive right and are left alone.
# The deeper stages arrive describing texture and colour this cell does not
# have, and they are the ones that have to move.
TRAINABLE_STAGES = 3

# Two glasses can genuinely overlap heavily here, because a tall glass's
# outline is splayed right over a short one's, and more so for solution 10
# where the boxes are drawn round whole silhouettes. Non-maximum suppression
# assumes heavy overlap means duplication, so its ratio has to be loose enough
# to survive the worst overlap the cell can legitimately produce.
OVERLAP = 0.7

# The two thresholds on the model's own score, and how sure the mask branch has
# to be about a pixel before it belongs to the instance. Above SURE an instance
# is reported, below DOUBTED it is dropped, and between them the model cannot
# tell, which is a reason to take another picture rather than to guess. Both
# solutions use the same pair, so neither is flattered by its thresholds.
SURE, DOUBTED = 0.5, 0.25
PIXEL = 0.5

# A target mask smaller than this is a scrap the box arithmetic cannot use and
# the mask branch cannot learn a shape from.
TINY = 16

# A few passes over a few dozen pictures is not much, and it does not need to be:
# nearly every weight in the model arrives already useful and only has to be
# nudged. How many scenes those pictures come from is train.py's to say, because
# it is the same question for all three solutions. Two pictures at a time is what
# fits comfortably beside the model in this machine's shared memory.
EPOCHS = 3
BATCH = 2

# Plain SGD with momentum, as torchvision's own detection reference uses, at a
# rate scaled down for this batch size.
RATE = 0.005
MOMENTUM = 0.9
DECAY = 0.0005

# The first few steps run at a fraction of the rate. Detection losses are large
# at the moment the two new predictors start from noise, and a full-rate step
# on that gradient can undo the borrowed weights before any of them help.
WARMUP_STEPS = 20
WARMUP_START = 0.02


@dataclass(frozen=True)
class Finder:
    """A fitted segmenter, ready to be handed pictures."""

    model: torch.nn.Module
    amodal: bool

    def find(self, picture, kind: str) -> tuple[list[Found], list[str]]:
        """The glasses in one picture, and one reason per instance left unsettled.

        ``kind`` is what the cell is told about the glasses on the table. This
        solution does not use it: the model was fitted on all four kinds and
        answers about pixels rather than about a range of sizes. It is taken
        because the three solutions here answer one interface, and solution 8
        cannot work without it.
        """
        image = pictures.as_tensor(picture).to(device.pick())
        with torch.no_grad():
            out = self.model([image])[0]

        scores = out["scores"].cpu().numpy()
        masks = out["masks"].cpu().numpy()[:, 0] > PIXEL
        reported = [index for index, score in enumerate(scores) if score >= SURE]
        hidden = asserted(picture, masks[reported]) if self.amodal else [None] * len(reported)

        found, doubts = [], []
        for index, mine in zip(reported, hidden, strict=True):
            glass = masks_to_glasses.one_glass(picture, masks[index], mine)
            # A mask the shared arithmetic cannot use is not a glass this run
            # can report. For an amodal mask that is the completely hidden
            # case: the outline is there and nothing was seen inside it.
            if glass is None:
                doubts.append("an outline with too little seen inside it to place")
            else:
                found.append(glass)
        doubts += ["cannot tell whether this is a glass" for score in scores if DOUBTED <= score < SURE]
        return found, doubts


def asserted(picture, masks: np.ndarray) -> list[np.ndarray | None]:
    """Per reported mask, the pixels of it that show some other reported glass.

    The depth reading is what tells the two apart, as solution 10's document
    says it can: where two reported outlines overlap, both bodies lie along
    those rays, so one is in front of the other and the camera saw the nearer.
    Which is nearer is read off the part of each outline that no other outline
    claims, since those pixels are certainly the glass's own.
    """
    if len(masks) == 0:
        return []
    depth = np.asarray(picture.depth)
    claims = masks.sum(0)
    alone = []
    for mask in masks:
        readings = depth[mask & (claims == 1)]
        readings = readings[np.isfinite(readings)]
        alone.append(float(np.median(readings)) if readings.size else np.inf)

    split: list[np.ndarray | None] = []
    for mine, near in zip(masks, alone, strict=True):
        theirs = np.zeros_like(mine)
        for other, other_near in zip(masks, alone, strict=True):
            if other_near < near:
                theirs |= mine & other
        split.append(theirs if theirs.any() else None)
    return split


def build() -> torch.nn.Module:
    """Mask R-CNN with COCO weights, its two predictors replaced for one class of thing.

    The weights arrive fitted to photographs of everyday objects, and the two
    predictors are the only parts whose shape depends on that list of objects,
    so they are the only parts thrown away. Everything below them — the
    backbone, the feature pyramid and the region proposal network — is kept and
    carried on from.
    """
    model = maskrcnn_resnet50_fpn_v2(
        weights=weights.mask_rcnn(),
        trainable_backbone_layers=TRAINABLE_STAGES,
        box_nms_thresh=OVERLAP,
    )
    boxes_in = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(boxes_in, CLASSES)
    masks_in = model.roi_heads.mask_predictor.conv5_mask.in_channels
    model.roi_heads.mask_predictor = MaskRCNNPredictor(masks_in, MASK_HIDDEN, CLASSES)
    return model


def target(sight: data.Sight, amodal: bool) -> dict[str, torch.Tensor] | None:
    """What the model is asked to produce for one picture, or None if it holds nothing to learn.

    Every glass is one instance: class "glass", the mask the solution trains
    against, and the smallest box containing that same mask. Taking the box
    from the mask is what lets the amodal target ask for pixels outside the
    visible part; a box round the visible pixels would clip every completion.
    """
    boxes, masks = [], []
    for mask in sight.masks(amodal):
        rows, columns = np.nonzero(mask)
        if rows.size < TINY:
            continue
        boxes.append([columns.min(), rows.min(), columns.max() + 1, rows.max() + 1])
        masks.append(mask)
    if not masks:
        return None
    return {
        "boxes": torch.as_tensor(np.array(boxes), dtype=torch.float32),
        "labels": torch.ones(len(masks), dtype=torch.int64),
        "masks": torch.as_tensor(np.array(masks), dtype=torch.uint8),
    }


def _rate(optimiser: torch.optim.Optimizer, step: int) -> None:
    """Ease the first steps in, while the two new predictors are still noise."""
    share = 1.0 if step >= WARMUP_STEPS else WARMUP_START + (1.0 - WARMUP_START) * step / WARMUP_STEPS
    for group in optimiser.param_groups:
        group["lr"] = RATE * share


def _signal(example: data.Example) -> int:
    """How many pixels of this scene's glasses are hidden by another glass.

    What solution 10 exists to learn is in these pixels and nowhere else, so
    counting them is how a training set is judged rather than by its size.
    """
    return sum(
        int((whole & ~visible).sum())
        for sight in example.sights
        for whole, visible in zip(sight.whole, sight.visible, strict=True)
    )


def fit(examples: Iterable[data.Example], *, amodal: bool, save: Path) -> Mapping:
    """Fine-tune the segmenter on ``examples`` and save it to ``save``.

    The same loop, optimiser and loss whichever the target is; only what the
    mask branch is compared against differs, and that was decided in target().
    """
    picked = device.pick()
    torch.manual_seed(0)

    drawn = time.time()
    ready, scenes, hidden = [], {True: 0, False: 0}, {True: 0, False: 0}
    for example in examples:
        scenes[example.crowded] += 1
        hidden[example.crowded] += _signal(example)
        for sight in example.sights:
            wanted = target(sight, amodal)
            if wanted is not None:
                ready.append((sight, wanted))
    if not ready:
        raise RuntimeError("no scene held a glass big enough to train on")
    instances = sum(len(wanted["labels"]) for _, wanted in ready)
    print(
        f"{len(ready)} pictures and {instances} glasses drawn in {time.time() - drawn:.0f}s, "
        f"masks are {'whole silhouettes' if amodal else 'visible pixels'}"
    )

    model = build().to(picked)
    model.train()
    moving = [p for p in model.parameters() if p.requires_grad]
    optimiser = torch.optim.SGD(moving, lr=RATE, momentum=MOMENTUM, weight_decay=DECAY)

    started, step = time.time(), 0
    order = random.Random(0)
    for epoch in range(EPOCHS):
        shuffled = list(ready)
        order.shuffle(shuffled)
        total, batches = 0.0, 0
        for first in range(0, len(shuffled), BATCH):
            batch = shuffled[first : first + BATCH]
            images = [pictures.as_tensor(s.picture).to(picked) for s, _ in batch]
            wanted = [{k: v.to(picked) for k, v in t.items()} for _, t in batch]
            losses = model(images, wanted)
            loss = sum(losses.values())
            _rate(optimiser, step)
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            total, batches, step = total + float(loss.detach()), batches + 1, step + 1
        print(f"epoch {epoch + 1}  loss {total / max(1, batches):.3f}  ({time.time() - started:.0f}s)")

    torch.save({"whole": amodal, "state": model.cpu().state_dict()}, save)
    everything = max(1, hidden[True] + hidden[False])
    return {
        "pictures": len(ready),
        "glasses": instances,
        "spawned scenes": scenes[False],
        "crowded scenes": scenes[True],
        "hidden pixels from spawned scenes": f"{100 * hidden[False] / everything:.1f}%",
        "hidden pixels from crowded scenes": f"{100 * hidden[True] / everything:.1f}%",
    }


def load(save: Path) -> Finder:
    """The fitted segmenter, as ``fit`` saved it."""
    kept = torch.load(save, map_location="cpu", weights_only=False)
    model = build()
    model.load_state_dict(kept["state"])
    return Finder(model.to(device.pick()).eval(), bool(kept["whole"]))
