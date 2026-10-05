"""The policy: LeRobot's ACT, with Diffusion Policy as the second rung.

Neither model is written here. Both are taken from
`LeRobot <https://github.com/huggingface/lerobot>`_, which is Apache-2.0, and
both are fitted from random numbers on demonstrations made inside this
project. **Nothing is downloaded.** LeRobot's ACT starts its vision backbone
from ImageNet weights by default; that default is turned off here, because
the document says the model is fitted from random numbers and a downloaded
backbone would make that untrue.

What this module adds is the three things LeRobot does not decide for you.

**Putting the numbers on one footing.** LeRobot 0.6 leaves normalisation to a
processor pipeline outside the policy. This folder does it here instead, so
the arithmetic is in one place and can be tested without the library. Both
rungs use the same scheme: every action column is mapped onto -1 to 1 from
the range the demonstrations cover, and the picture is scaled to 0-1 and then
centred per colour. Diffusion Policy clips its samples to -1 to 1 while it
denoises, so an action space that already fits inside that is not optional
for the second rung.

**The empty state.** Every LeRobot policy expects a robot state beside the
picture. This one has none: the jaw is parked in the same place between
pushes, so its pose carries nothing the picture does not, and the document is
explicit that what goes in is the view of the table. So the state is passed
as a tensor with no columns. ACT reads the key only to find out which device
it is on; Diffusion Policy needs the feature declared, and a feature of width
zero adds no numbers to the model.

**The chunk is the whole answer.** ``n_action_steps`` is the chunk's full
length for both rungs, because one push is one chunk. Nothing re-plans part
way through.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from chunks import ACTION_WIDTH, CHUNK
from lerobot.configs.types import FeatureType, NormalizationMode, PolicyFeature
from pictures import SEEN_SIZE, shrink

KINDS = ("act", "diffusion")
PICTURE = "observation.images.top"
STATE = "observation.state"


# The denoising rung's sampler. DDIM reaches the same place as the training
# schedule's hundred steps in far fewer, and a push takes the arm seconds, so
# the remaining cost is still small beside the motion. It is many times ACT's
# single pass, which is the difference the compute column is there to show.
DENOISE_STEPS = 16
# Diffusion Policy's own default channel widths are (512, 1024, 2048), which
# is a quarter of a billion parameters for a five-column action. Halved, the
# rung is a few tens of millions, like ACT, and the pair differ in how they
# answer rather than in how big they are.
DENOISE_WIDTHS = (256, 512, 1024)

# Everything the library might normalise is left alone: the scaling below is
# this folder's, applied before anything reaches the model.
_UNTOUCHED = {
    "VISUAL": NormalizationMode.IDENTITY,
    "STATE": NormalizationMode.IDENTITY,
    "ACTION": NormalizationMode.IDENTITY,
}



def _colours(pictures: np.ndarray, batch: int = 64) -> tuple[np.ndarray, np.ndarray]:
    """The middle and the spread of each colour over every picture, 0 to 1.

    A batch at a time, because the whole set as floats is several gigabytes
    and nothing here needs it in one piece.
    """
    total = np.zeros(3)
    squares = np.zeros(3)
    count = 0
    for first in range(0, len(pictures), batch):
        some = shrink(pictures[first : first + batch]).astype(np.float64) / 255.0
        flat = some.reshape(-1, some.shape[-1])
        total += flat.sum(axis=0)
        squares += (flat**2).sum(axis=0)
        count += len(flat)
    middle = total / max(count, 1)
    return middle.astype(np.float32), np.sqrt(
        np.maximum(squares / max(count, 1) - middle**2, 0.0)
    ).astype(np.float32)


class Scale:
    """The mapping between table units and the numbers the model sees.

    Actions go onto -1 to 1, column by column, from the range the
    demonstrations cover. A column that never varies --- the height, which
    the teacher's macro holds at the lowest the gripper reaches --- maps to
    the middle and stays there.
    """

    def __init__(self, low: np.ndarray, high: np.ndarray, middle: np.ndarray, spread: np.ndarray) -> None:
        self.low = np.asarray(low, dtype=np.float32)
        self.high = np.asarray(high, dtype=np.float32)
        self.middle = np.asarray(middle, dtype=np.float32)
        self.spread = np.asarray(spread, dtype=np.float32)

    @classmethod
    def of(cls, pictures: np.ndarray, actions: np.ndarray) -> Scale:
        """The scaling the collected demonstrations imply."""
        flat = actions.reshape(-1, actions.shape[-1])
        low, high = flat.min(axis=0), flat.max(axis=0)
        # A column with no range would divide by zero. Give it one.
        narrow = (high - low) < 1e-6
        low = np.where(narrow, low - 0.5, low)
        high = np.where(narrow, high + 0.5, high)
        middle, spread = _colours(pictures)
        return cls(low, high, middle, np.where(spread < 1e-6, 1.0, spread))

    def forward(self, action: np.ndarray) -> np.ndarray:
        return (2 * (np.asarray(action, dtype=np.float32) - self.low) / (self.high - self.low) - 1).astype(
            np.float32
        )

    def back(self, action: np.ndarray) -> np.ndarray:
        return ((np.asarray(action, dtype=np.float32) + 1) / 2 * (self.high - self.low) + self.low).astype(
            np.float32
        )

    def picture(self, pictures: np.ndarray) -> np.ndarray:
        """One picture or a batch of them, as (batch, colour, row, column) floats.

        Shrunk to ``SEEN_SIZE`` on the way, so nothing outside this module has
        to know what size the model reads.
        """
        batch = shrink(pictures)
        scaled = (batch.astype(np.float32) / 255.0 - self.middle) / self.spread
        return np.ascontiguousarray(scaled.transpose(0, 3, 1, 2))

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "low": self.low.tolist(),
                    "high": self.high.tolist(),
                    "picture_middle": self.middle.tolist(),
                    "picture_spread": self.spread.tolist(),
                },
                indent=2,
            )
            + "\n"
        )

    @classmethod
    def load(cls, path: Path) -> Scale:
        held = json.loads(path.read_text())
        return cls(
            np.array(held["low"], dtype=np.float32),
            np.array(held["high"], dtype=np.float32),
            np.array(held["picture_middle"], dtype=np.float32),
            np.array(held["picture_spread"], dtype=np.float32),
        )


def where_to_run() -> str:
    """The accelerator this machine has. Apple's, or the processor."""
    return "mps" if torch.backends.mps.is_available() else "cpu"


def _features(kind: str) -> tuple[dict, dict]:
    rows, columns = SEEN_SIZE
    inputs = {PICTURE: PolicyFeature(FeatureType.VISUAL, (3, rows, columns))}
    if kind == "diffusion":
        # Only this rung insists on the feature existing. Width zero, so it
        # adds nothing to the model.
        inputs[STATE] = PolicyFeature(FeatureType.STATE, (0,))
    return inputs, {"action": PolicyFeature(FeatureType.ACTION, (ACTION_WIDTH,))}


def build(kind: str, seed: int = 0, chunk: int = CHUNK):
    """A fresh, unfitted policy of one of the two rungs."""
    if kind not in KINDS:
        raise ValueError(f"the rungs are {KINDS}, not {kind!r}")
    inputs, outputs = _features(kind)
    torch.manual_seed(seed)
    if kind == "act":
        from lerobot.policies.act.configuration_act import ACTConfig
        from lerobot.policies.act.modeling_act import ACTPolicy

        return ACTPolicy(
            ACTConfig(
                input_features=inputs,
                output_features=outputs,
                chunk_size=chunk,
                n_action_steps=chunk,
                pretrained_backbone_weights=None,
                normalization_mapping=_UNTOUCHED,
                push_to_hub=False,
            )
        )
    from lerobot.policies.diffusion.configuration_diffusion import DiffusionConfig
    from lerobot.policies.diffusion.modeling_diffusion import DiffusionPolicy

    return DiffusionPolicy(
        DiffusionConfig(
            input_features=inputs,
            output_features=outputs,
            horizon=chunk,
            n_action_steps=chunk,
            n_obs_steps=1,
            down_dims=DENOISE_WIDTHS,
            noise_scheduler_type="DDIM",
            num_inference_steps=DENOISE_STEPS,
            pretrained_backbone_weights=None,
            normalization_mapping=_UNTOUCHED,
            push_to_hub=False,
        )
    )


class Imitator:
    """A fitted policy, asked for one chunk per push."""

    def __init__(self, net, scale: Scale, kind: str, device: str | None = None) -> None:
        self.kind = kind
        self.scale = scale
        self.device = device or where_to_run()
        self.net = net.to(self.device)

    @classmethod
    def new(cls, kind: str, scale: Scale, seed: int = 0, device: str | None = None) -> Imitator:
        return cls(build(kind, seed), scale, kind, device)

    @property
    def chunk_length(self) -> int:
        config = self.net.config
        return config.chunk_size if self.kind == "act" else config.horizon

    def batch(self, pictures: np.ndarray, actions: np.ndarray | None = None) -> dict:
        """One training or run-time batch, scaled and on the device."""
        seen = torch.as_tensor(self.scale.picture(pictures), device=self.device)
        if self.kind == "diffusion":
            # One observation step, so the pictures carry a time axis of one.
            seen = seen.unsqueeze(1)
        count = seen.shape[0]
        state = torch.zeros(count, 0, device=self.device)
        batch = {PICTURE: seen, STATE: state.unsqueeze(1) if self.kind == "diffusion" else state}
        if actions is not None:
            wanted = torch.as_tensor(self.scale.forward(actions), device=self.device)
            batch["action"] = wanted
            batch["action_is_pad"] = torch.zeros(
                count, wanted.shape[1], dtype=torch.bool, device=self.device
            )
        return batch

    def loss(self, pictures: np.ndarray, actions: np.ndarray):
        """How wrong the model is on these demonstrations, as the model's own objective."""
        loss, _ = self.net.forward(self.batch(pictures, actions))
        return loss

    def chunk(self, picture: np.ndarray) -> np.ndarray:
        """One action chunk from one picture: (chunk, 5) in the table's own units."""
        self.net.eval()
        with torch.no_grad():
            answer = self.net.predict_action_chunk(self.batch(picture))
        return self.scale.back(answer[0].float().cpu().numpy())

    def save(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        self.net.save_pretrained(folder)
        self.scale.save(folder / "scale.json")
        (folder / "rung.txt").write_text(self.kind + "\n")

    @classmethod
    def load(cls, folder: Path, device: str | None = None) -> Imitator:
        kind = (folder / "rung.txt").read_text().strip()
        if kind == "act":
            from lerobot.policies.act.modeling_act import ACTPolicy as Net
        else:
            from lerobot.policies.diffusion.modeling_diffusion import DiffusionPolicy as Net
        return cls(Net.from_pretrained(folder), Scale.load(folder / "scale.json"), kind, device)
