"""SmolVLA with a small low-rank correction learned on this bench's pushes.

The model is the one [solution 5](../05-smolvla-as-it-downloads) downloads,
and it is loaded the same way: the same weights, the same configuration, the
same pre- and post-processing, the same picture and the same sentence. This
module adds one thing and removes nothing. ``Fitted`` is solution 5's
``Downloaded`` with the correction loaded on top of it, so the asking is
inherited rather than written again — the pair is only clean while everything
but the training is the same code.

**What the correction is.** Every weight table the training touches keeps its
borrowed numbers, and a correction is added beside it. The correction is
forced through a narrow squeeze: a thin table down to ``RANK`` numbers and a
thin table back out to full width. That is LoRA, and the two thin tables
together hold about one per cent of the model, which is what makes the
training fit in the memory this machine has.

**Where it is put.** On the query, key, value and output projections of every
attention layer, in the vision-language half and in the action expert alike.
Those are the tables a change in what the model attends to has to go through,
and they are the standard place to put an adapter. The feed-forward tables
are left alone, which is the ordinary trade: fewer numbers to fit, less of
the model that can move.

**What happens to it afterwards.** Once trained, the two thin tables are
multiplied out and added into the borrowed table, and what is left is a model
of exactly the original size, running at exactly the original speed. So the
compute column on the scorecard is solution 5's, and nothing separating the
two scores can be put down to one of them being given more computation.

Loading downloads about 2 GB the first time and then reads the cache.
Nothing in the tests comes through here, because a test that needs a download
is not a test.
"""

from __future__ import annotations

from pathlib import Path

from chunks import CHUNK
from partners import WEIGHTS, device_for
from policy import Downloaded

HERE = Path(__file__).parent
# Where train.py writes the correction. Only the correction: the borrowed
# weights are never copied here, because they are not ours to keep and the
# library fetches them.
CORRECTION = HERE / "correction"

# How narrow the squeeze is, and how hard the correction is allowed to pull.
# Sixteen is the usual starting rank for a model of this size; the scaling is
# twice the rank, which is the usual pairing and keeps the correction's effect
# independent of the rank it was fitted at.
RANK = 16
SCALING = 32
# The tables the correction is added to: attention's four projections.
TABLES = ("q_proj", "k_proj", "v_proj", "o_proj")


def missing(where: Path = CORRECTION) -> str | None:
    """Why the correction cannot be loaded from ``where``, or None if it can."""
    if not (where / "adapter_config.json").exists():
        return (
            f"no correction at {where}. Fit one with "
            "`pixi run python 06-smolvla-fine-tuned/train.py`, which needs the demonstrations "
            "`demonstrations.py` writes."
        )
    return None


def borrowed(device: str | None = None):
    """The downloaded model, its configuration and its processing, with nothing changed.

    The starting point for both the training and the run. Returns the policy,
    the pre-processor and the post-processor, which is what ``Downloaded``
    holds.
    """
    from lerobot.policies.factory import make_pre_post_processors
    from lerobot.policies.smolvla.configuration_smolvla import SmolVLAConfig
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

    where = device or device_for()
    config = SmolVLAConfig.from_pretrained(WEIGHTS)
    # The checkpoint was saved on a machine with an NVIDIA card.
    config.device = where
    if config.chunk_size != CHUNK:
        raise ValueError(
            f"the model emits {config.chunk_size} actions in a pass and the demonstrations hold "
            f"{CHUNK}. Set CHUNK in chunks.py to the model's own chunk size and collect again."
        )
    policy = SmolVLAPolicy.from_pretrained(WEIGHTS, config=config).to(where)
    pre, post = make_pre_post_processors(
        config, WEIGHTS, preprocessor_overrides={"device_processor": {"device": where}}
    )
    return policy, pre, post


def with_correction(policy, rank: int = RANK, scaling: int = SCALING):
    """Add a fresh, untrained correction to the model and freeze everything else.

    What comes back answers exactly as it did before, because a correction
    starts at zero. What has changed is which numbers the optimiser may move.
    """
    from peft import LoraConfig, get_peft_model

    policy.model = get_peft_model(
        policy.model,
        LoraConfig(r=rank, lora_alpha=scaling, lora_dropout=0.0, bias="none", target_modules=list(TABLES)),
    )
    return policy


def counts(policy) -> tuple[int, int]:
    """How many numbers the training moves, and how many there are altogether."""
    moving = sum(p.numel() for p in policy.parameters() if p.requires_grad)
    return moving, sum(p.numel() for p in policy.parameters())


class Fitted(Downloaded):
    """Solution 5's model with this bench's correction folded into it.

    Everything about answering — the picture, the sentence, the state, the
    chunk that comes back — is solution 5's, inherited unchanged. Only where
    the weights came from is different, which is the one thing this solution
    is a measurement of.
    """

    @classmethod
    def load(cls, device: str | None = None, correction: Path = CORRECTION) -> Fitted:
        """The borrowed weights with the correction added into them, ready to run."""
        from peft import PeftModel

        wrong = missing(correction)
        if wrong is not None:
            raise FileNotFoundError(wrong)
        policy, pre, post = borrowed(device)
        # Folded in rather than kept beside: the run-time cost is then the
        # partner's exactly, which is what makes the two scores comparable.
        policy.model = PeftModel.from_pretrained(policy.model, correction).merge_and_unload()
        policy.eval()
        return cls(policy, pre, post)
