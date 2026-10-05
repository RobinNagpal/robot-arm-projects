"""The borrowed weights: fetched into weights/ once, found there afterwards.

Two files, both large: SAM's, which solution 8 uses exactly as downloaded, and
Mask R-CNN's weights fitted on photographs, which solutions 9 and 10 fine-tune
from. They are cached inside this folder rather than in the home directory, so
that what a run depends on sits beside the run and `weights/` can be deleted to
start again.

Each function fetches its own model and returns what to load it by. A second
call finds the files already on disk, asks the network nothing, and returns the
same answer, which is what makes `make setup` cheap to repeat.

    pixi run python weights.py      # fetch both, and say where they landed
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import torch

CACHE = Path(__file__).parent / "weights"
HUGGING_FACE = CACHE / "huggingface"
TORCH_HUB = CACHE / "torch"

# SAM as the document names it: the base model, promptable with points.
SAM = "facebook/sam-vit-base"

# The upload holds the same weights three times over, for three libraries. Only
# the safetensors copy and the settings beside it are wanted; taking the lot
# would fetch a gigabyte to use a third of it.
SAM_FILES = ["*.json", "*.safetensors"]


def sam() -> str:
    """Fetch SAM's weights and return the path to load them from."""
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    HUGGING_FACE.mkdir(parents=True, exist_ok=True)
    try:
        # Already here: this reads the cache and asks the network nothing.
        return snapshot_download(
            SAM, cache_dir=str(HUGGING_FACE), allow_patterns=SAM_FILES, local_files_only=True
        )
    except LocalEntryNotFoundError:
        return snapshot_download(SAM, cache_dir=str(HUGGING_FACE), allow_patterns=SAM_FILES)


def mask_rcnn():
    """Fetch Mask R-CNN's photograph-fitted weights and return torchvision's handle for them.

    The handle, not the numbers: torchvision builds the model from it, and it
    also carries the transform the weights were fitted with.
    """
    from torchvision.models.detection import MaskRCNN_ResNet50_FPN_V2_Weights

    # torch.hub reads this when it downloads, so it is set before asking.
    TORCH_HUB.mkdir(parents=True, exist_ok=True)
    torch.hub.set_dir(str(TORCH_HUB))
    chosen = MaskRCNN_ResNet50_FPN_V2_Weights.DEFAULT
    if not checkpoint(chosen.url).exists():
        chosen.get_state_dict(progress=True)
    return chosen


def checkpoint(url: str) -> Path:
    """Where torch.hub puts the file behind a weights URL."""
    return TORCH_HUB / "checkpoints" / Path(urlparse(url).path).name


def fitted(solution: str) -> Path:
    """The file `make train SOLUTION=...` writes and `make test` reads back.

    Beside the downloaded weights, because it is the same kind of thing: not
    committed, and remade by a command.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"fitted-{solution}.pt"


def main() -> None:
    print(f"SAM         {sam()}")
    print(f"Mask R-CNN  {checkpoint(mask_rcnn().url)}")


if __name__ == "__main__":
    main()
