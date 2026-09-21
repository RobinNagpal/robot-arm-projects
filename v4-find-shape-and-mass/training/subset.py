"""A smaller dataset for a quick run, without copying or deleting any picture.

YOLO can read a split from a text file listing picture paths instead of from
a folder. So a subset is a few of those lists, and yaml files that point at
them. They are written into the run's own folder, where evaluate.py finds
them again and scores the model on the same smaller test sets.

Every split is cut by the same fraction as train, so the proportions stay as
they were. The pictures are picked at random, but from a fixed seed, so the
same subset comes out every time.

No Ultralytics in here, so the tests can check it.
"""

from __future__ import annotations

import random
from pathlib import Path

from synthetic.shapes import CLASSES

# data.yaml and data-unseen.yaml differ only in which split they test on.
YAML_FILES = {"data.yaml": "test", "data-unseen.yaml": "test-unseen"}
SPLITS = ("train", "val", "test", "test-unseen")


def pick(pictures: list[Path], count: int, seed: int, split: str) -> list[Path]:
    """``count`` of ``pictures`` chosen at random, in their original order."""
    rng = random.Random(f"{split}-{seed}")
    return sorted(rng.sample(sorted(pictures), count))


def counts(sizes: dict[str, int], train_count: int) -> dict[str, int]:
    """How many pictures each split keeps, when train keeps ``train_count``."""
    if not 0 < train_count <= sizes["train"]:
        raise ValueError(f"train has {sizes['train']} pictures; asked for {train_count}")
    fraction = train_count / sizes["train"]
    return {split: max(1, round(size * fraction)) for split, size in sizes.items()}


def write_subset(data: Path, out: Path, train_count: int, seed: int = 0) -> dict[str, int]:
    """Write the picture lists and both yaml files into ``out``. Returns the count per split."""
    data = data.resolve()
    pictures = {split: sorted((data / "images" / split).glob("*.jpg")) for split in SPLITS}
    kept = counts({split: len(files) for split, files in pictures.items()}, train_count)

    out.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        chosen = pick(pictures[split], kept[split], seed, split)
        # Full paths: YOLO finds each label by swapping /images/ for /labels/ in them.
        (out / f"{split}.txt").write_text("".join(f"{p}\n" for p in chosen))

    names = "".join(f"  {i}: {name}\n" for i, name in enumerate(CLASSES))
    for file, test in YAML_FILES.items():
        (out / file).write_text(
            f"# A random {train_count}-picture subset of {data}, written by training/subset.py.\n"
            f"path: {out.resolve()}\ntrain: train.txt\nval: val.txt\ntest: {test}.txt\n\nnames:\n{names}"
        )
    return kept
