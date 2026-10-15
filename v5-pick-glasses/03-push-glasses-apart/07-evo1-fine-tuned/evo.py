"""Evo-1, a 0.77B vision-language-action model, fitted on this bench's pushes.

**What Evo-1 is.** It is a borrowed model of the same family as the one
[solution 5](../05-smolvla-as-it-downloads) downloads: it reads a picture and
a sentence and answers with a run of actions. It is newer, published in
November 2025, and about seventy per cent larger, at 775 million numbers
against SmolVLA's 450 million. Its vision-language half is InternVL3-1B, and
its action half draws a chunk by flow matching, which means it starts from
noise and walks the noise towards an answer in a fixed number of steps.

**Why that makes it worth a solution of its own.** Solutions 5 and 6 pin down
what a 450M borrowed model does here, used as it downloads and fitted here.
This solution changes the model and nothing else, so what it measures is
whether a newer and larger borrowed model is worth its cost on a task this
narrow. It is fitted rather than used as it downloads, because its action half
has never seen this cell: a chunk from an unfitted Evo-1 would measure the
reading convention and not the model.

**What is fitted, and what is not.** Evo-1 names two training stages of its
own. In the first the vision-language half is frozen and only the action half
moves; in the second everything moves. This solution uses the first, so 122
million of the 775 million numbers are fitted. That is not a saving invented
here: it is the model's own first stage, and it is also what makes the fit
possible in this machine's memory, in the same way that the low-rank
correction does for solution 6.

**Two things it forces, and both are recorded rather than chosen.** The first
is the picture: Evo-1 refuses any size but its checkpoint's own 448 pixels,
because the number of image tokens is baked into the checkpoint, so this
cell's 384-pixel view has to be scaled up before it goes in. The second is
the answer's width: the model always answers 24 numbers a waypoint, whatever
the cell needs, and its own post-processing trims that to the 6 this cell
uses. Neither is a difference anybody here wanted, and both are stated in the
document because they are differences from solutions 5 and 6 all the same.

Loading downloads about 2 GB of InternVL3 weights the first time and then
reads the cache. Nothing in the tests comes through here, because a test that
needs a download is not a test.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from partners import (
    ACTION_SPAN,
    CAMERA,
    INSTRUCTION,
    SLOTS,
    UP_HIGHER,
    Downloaded,
    device_for,
    to_jaw,
    to_state,
)

from bench import Waypoint

HERE = Path(__file__).parent
# Where train.py writes a fit. Only the action half is written: the borrowed
# vision-language weights are never copied here, because they are not ours to
# keep and the library fetches them.
FITTED = HERE / "fitted"

# Evo-1's own backbone and its own layer count. Fourteen layers is the
# model's default and is what makes it the 0.77B model the paper describes, so
# it is left alone: a shallower one would be a different model wearing the
# same name.
BACKBONE = "OpenGVLab/InternVL3-1B-hf"
LAYERS = 14
# Forced by the checkpoint, not chosen. See the module docstring.
SIDE = 448
# The model's first training stage: the vision-language half frozen.
STAGE = "stage1"
# How many steps the flow matching walks from noise to an answer. This is the
# config's own default and it is the whole run-time cost of a chunk, so it is
# reported on the scorecard rather than tuned away.
DENOISING_STEPS = 32


def span(width: int = SLOTS) -> dict:
    """The range a number may take, which the reading convention already fixes.

    Evo-1 scales its inputs and outputs from a smallest and a largest value,
    and those are usually measured off the training set. Here they do not have
    to be guessed at, because solution 5's reading convention already says
    that ``ACTION_SPAN`` spans the picture's frame exactly, so the range is
    known in advance and is the same for every fit. Taking it from the
    convention rather than from the data also means two fits on two different
    demonstration sets are still scaled identically, which is one fewer thing
    that can differ between them.
    """
    edge = np.full(width, ACTION_SPAN, dtype=np.float32)
    return {"min": -edge, "max": edge}


def missing(where: Path = FITTED) -> str | None:
    """Why a fit cannot be loaded from ``where``, or None if it can."""
    for name in ("head.pt", "stats.json"):
        if not (where / name).exists():
            return (
                f"no fit at {where}. Make one with "
                "`pixi run python 07-evo1-fine-tuned/train.py`, which needs solution 6's "
                "demonstrations."
            )
    return None


def settings(chunk: int, device: str) -> object:
    """Evo-1's configuration for this cell: one camera, six numbers a waypoint.

    Everything here either describes the cell or switches off something this
    machine does not have. Nothing is tuned.
    """
    from lerobot.configs.types import FeatureType, PolicyFeature
    from lerobot.policies.evo1.configuration_evo1 import Evo1Config

    return Evo1Config(
        chunk_size=chunk,
        n_action_steps=chunk,
        training_stage=STAGE,
        vlm_model_name=BACKBONE,
        vlm_num_layers=LAYERS,
        image_resolution=(SIDE, SIDE),
        num_inference_timesteps=DENOISING_STEPS,
        # Three settings this machine forces. Flash attention is an NVIDIA
        # kernel and is absent, so the model falls back to plain attention.
        # Automatic mixed precision is guarded by the model itself to CUDA, so
        # saying no here only makes that explicit. Float32 is used because
        # Metal's bfloat16 support is not something this result should rest on.
        use_flash_attn=False,
        use_amp=False,
        vlm_dtype="float32",
        # Off because the fit is small enough without it, and recomputing
        # activations would cost time this machine has less of than memory.
        enable_gradient_checkpointing=False,
        device=device,
        input_features={
            CAMERA: PolicyFeature(FeatureType.VISUAL, (3, SIDE, SIDE)),
            "observation.state": PolicyFeature(FeatureType.STATE, (SLOTS,)),
        },
        output_features={"action": PolicyFeature(FeatureType.ACTION, (SLOTS,))},
    )


def built(chunk: int, stats: dict, device: str | None = None):
    """A fresh Evo-1: borrowed vision-language half, new action half.

    The action half is new because nothing has ever asked this model for a
    push on this table. Returns the policy with its pre- and post-processing,
    which is the same three-part shape solutions 5 and 6 use.
    """
    from lerobot.policies.evo1.modeling_evo1 import Evo1Policy
    from lerobot.policies.factory import make_pre_post_processors

    where = device or device_for()
    config = settings(chunk, where)
    policy = Evo1Policy(config).to(where)
    pre, post = make_pre_post_processors(
        config, dataset_stats=stats, preprocessor_overrides={"device_processor": {"device": where}}
    )
    return policy, pre, post


def counts(policy) -> tuple[int, int]:
    """How many numbers the fitting moves, and how many there are altogether."""
    moving = sum(p.numel() for p in policy.parameters() if p.requires_grad)
    return moving, sum(p.numel() for p in policy.parameters())


def head(policy) -> dict:
    """Just the numbers the fitting moved, for saving.

    The frozen vision-language half is four fifths of the model and is
    downloadable, so writing it out beside every seed would cost gigabytes to
    store something the library already has.
    """
    moving = {name for name, p in policy.named_parameters() if p.requires_grad}
    return {name: value.cpu() for name, value in policy.state_dict().items() if name in moving}


def scaled(rows: torch.Tensor) -> torch.Tensor:
    """A picture already in the model's layout, scaled to the side it insists on.

    Takes ``(3, rows, columns)`` or a batch of those, so the training and the
    run scale the same way through the same code.
    """
    if rows.shape[-2:] == (SIDE, SIDE):
        return rows
    flat = rows.unsqueeze(0) if rows.dim() == 3 else rows
    out = torch.nn.functional.interpolate(flat, size=(SIDE, SIDE), mode="bilinear", align_corners=False)
    return out[0] if rows.dim() == 3 else out


def picture_for(picture: np.ndarray) -> torch.Tensor:
    """This cell's 384-pixel view, scaled to the 448 the checkpoint insists on.

    Scaling up adds no information, so this is not an advantage over solutions
    5 and 6; it is the price of the checkpoint's fixed token count, and it is
    done once here rather than in several places.
    """
    if picture.dtype != np.uint8 or picture.ndim != 3 or picture.shape[2] != 3:
        raise ValueError(f"the top view is (rows, columns, 3) uint8, not {picture.shape} {picture.dtype}")
    return scaled(torch.from_numpy(picture.copy()).permute(2, 0, 1).float() / 255.0)


class Fitted(Downloaded):
    """Evo-1 with this bench's action half, ready to answer.

    It inherits solution 5's loop and solution 5's reading of an action as a
    jaw waypoint, and overrides only the two places where Evo-1 differs from
    SmolVLA: how it is loaded and how a batch is put together for it.
    """

    @classmethod
    def load(cls, device: str | None = None, fit: Path = FITTED, up: float = UP_HIGHER) -> Fitted:
        wrong = missing(fit)
        if wrong is not None:
            raise FileNotFoundError(wrong)
        facts = json.loads((fit / "stats.json").read_text())
        stats = {
            key: {name: np.asarray(value, dtype=np.float32) for name, value in each.items()}
            for key, each in facts["stats"].items()
        }
        policy, pre, post = built(int(facts["chunk"]), stats, device)
        policy.load_state_dict(torch.load(fit / "head.pt", map_location="cpu"), strict=False)
        policy.to(policy.config.device)
        policy.eval()
        return cls(policy, pre, post, up)

    def ask(self, picture: np.ndarray, jaw: Waypoint) -> np.ndarray:
        """One answer: the picture and the jaw's pose in, a run of jaw waypoints out, (n, 4)."""
        batch = {
            CAMERA: picture_for(picture),
            "observation.state": torch.from_numpy(to_state(jaw, self.up)).float(),
            "task": INSTRUCTION,
        }
        with torch.no_grad():
            actions = self.policy.predict_action_chunk(self.pre(batch))
        return to_jaw(self.post(actions)[0].cpu().numpy().astype(float), self.up)
