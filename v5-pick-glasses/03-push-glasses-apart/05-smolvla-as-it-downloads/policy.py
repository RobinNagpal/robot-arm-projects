"""SmolVLA, exactly as it downloads.

The weights come from ``lerobot/smolvla_base`` and nothing is changed in them.
What this module does is hand the model the three things it takes — a picture,
a sentence and the arm's own state — and give back the run of jaw waypoints it
amounts to. The reading in both directions is ``joining.py``, and it is
applied here so that the whole of the join between this cell and somebody
else's arm sits behind one call.

Three joins at the input had to be decided, and all three are forced by the
model's own configuration rather than chosen freely:

- **The picture.** The model declares three cameras, ``camera1`` to
  ``camera3``, and ``empty_cameras`` is 0, which means a camera that is absent
  from the batch is simply left out rather than padded with a blank. This cell
  has one straight-down view, so it fills ``camera1`` and the other two are
  absent. The array wants to be float 0 to 1, red-green-blue, channels first:
  ``top_view`` already gives RGB, so unlike ``film.py`` nothing is flipped.
- **The sentence.** One line, the same every time, in ``joining.INSTRUCTION``.
- **The state.** Six numbers, which ``joining.to_state`` fills from where the
  jaw is standing. The checkpoint ships no statistics for this input, so there
  is nothing that says what scale it expects; filling it with the jaw's own
  pose under the same reading the actions are read with is the only
  self-consistent answer available.

Loading downloads about 2 GB the first time and then reads it from the cache.
Nothing in the tests comes through here, because a test that needs a download
is not a test.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from joining import INSTRUCTION, UP_HIGHER, to_jaw, to_state

from bench import Waypoint

WEIGHTS = "lerobot/smolvla_base"
# The one camera slot this cell fills, of the three the model declares.
CAMERA = "observation.images.camera1"


def device_for() -> str:
    """The fastest device here. This laptop has Metal and no NVIDIA card."""
    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


@dataclass
class Downloaded:
    """The borrowed model and its own pre- and post-processing, ready to answer."""

    policy: object
    pre: object
    post: object
    # Which way the height slot runs. See joining.UP_HIGHER: it is the one
    # convention the checkpoint does not settle, and run.py can turn it over
    # to measure what it is worth.
    up: float = UP_HIGHER

    @classmethod
    def load(cls, device: str | None = None, up: float = UP_HIGHER) -> Downloaded:
        """Download the weights, or read them from the cache, and get them ready to run."""
        # Imported here and not at the top so that the tests, which never load
        # a model, do not pay for importing transformers to find that out.
        from lerobot.policies.factory import make_pre_post_processors
        from lerobot.policies.smolvla.configuration_smolvla import SmolVLAConfig
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

        where = device or device_for()
        config = SmolVLAConfig.from_pretrained(WEIGHTS)
        # The checkpoint was saved on a machine with an NVIDIA card.
        config.device = where
        policy = SmolVLAPolicy.from_pretrained(WEIGHTS, config=config).to(where)
        policy.eval()
        pre, post = make_pre_post_processors(
            config, WEIGHTS, preprocessor_overrides={"device_processor": {"device": where}}
        )
        return cls(policy, pre, post, up)

    def reset(self) -> None:
        """Forget the last table. Called between tables, not between pushes."""
        self.policy.reset()

    def ask(self, picture: np.ndarray, jaw: Waypoint) -> np.ndarray:
        """One answer: the picture and the jaw's pose in, a run of jaw waypoints out, (n, 4).

        The answer is drawn rather than computed — the policy denoises from
        fresh noise every time — so the same table asked twice gives two
        different runs. That is the only randomness this solution has.
        """
        if picture.dtype != np.uint8 or picture.ndim != 3 or picture.shape[2] != 3:
            raise ValueError(f"the top view is (rows, columns, 3) uint8, not {picture.shape} {picture.dtype}")
        batch = {
            CAMERA: torch.from_numpy(picture.copy()).permute(2, 0, 1).float() / 255.0,
            "observation.state": torch.from_numpy(to_state(jaw, self.up)).float(),
            "task": INSTRUCTION,
        }
        with torch.no_grad():
            actions = self.policy.predict_action_chunk(self.pre(batch))
        return to_jaw(self.post(actions)[0].numpy().astype(float), self.up)
