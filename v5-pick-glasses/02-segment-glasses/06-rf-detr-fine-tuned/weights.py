"""Where this solution's weights live: the borrowed ones, and the ones fitted here.

Two kinds of file, both large and neither committed.

The **borrowed** weights are RF-DETR-Seg as Roboflow publishes them, fitted on a
large collection of ordinary labelled pictures. The package fetches them itself
and keeps them in a cache directory it reads from the ``RF_HOME`` environment
variable, so this module sets that variable to a folder beside the code. That
is the same choice ../05-sam2-with-a-keeper/weights.py makes and for the same
reason: what a run depends on sits beside the run, and ``weights/`` can be
deleted to start again.

The **fitted** weights are what ``train.py`` writes. There is one file per
target, because the two rungs of this solution are two different fits of the
same model and keeping them under one name would let a run score the first
rung's weights and call them the second's.

    pixi run python weights.py      # fetch the borrowed weights, and say where
"""

from __future__ import annotations

import os
from pathlib import Path

CACHE = Path(__file__).parent / "weights"
ROBOFLOW = CACHE / "roboflow"


def borrowed() -> Path:
    """Point the package's own cache at this folder, and say where that is.

    Called before the package is imported anywhere, because it reads ``RF_HOME``
    when its module is first loaded rather than when a model is built.
    """
    ROBOFLOW.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("RF_HOME", str(ROBOFLOW))
    return ROBOFLOW


def fitted(target: str) -> Path:
    """The checkpoint ``train.py`` writes for one target and ``run.py`` reads back."""
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"fitted-{target}.pth"


def workings(target: str) -> Path:
    """Where the fine-tune keeps its dataset, its logs and its own checkpoints.

    Separate from the one file ``fitted`` names, because the package writes a
    run's worth of files and only one of them is the answer.
    """
    folder = CACHE / f"training-{target}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def main() -> None:
    from rf_detr_seg import SIZE, fresh

    print(f"cache   {borrowed()}")
    fresh()
    print(f"model   {SIZE}, downloaded and built")


if __name__ == "__main__":
    main()
