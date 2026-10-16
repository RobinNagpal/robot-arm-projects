"""Where a fitted correction is kept, and nothing else.

One page, because two files need to agree about it and because the wrong answer
is silent. ``borrowed.correction`` is problem 3's file and its own default folder
is problem 3's: a run of this solution that fell back on that default would load
a correction fitted on problem 3's pushes, score it on problem 4's tables, and
look exactly like a run of this solution. So nothing here has a default, and
every caller names the seed it means.

The correction itself is small -- two thin tables beside each attention
projection, about four million numbers -- and it is made again from the
demonstrations by ``train.py``, so it is left out of git. ``training.json``,
which says what the fitting did, is small and is the record a reader needs, so
that stays in.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FITS = HERE / "weights"
# What the fit wrote about itself: one file for every seed, beside them.
RECORD = FITS / "training.json"


def correction(seed: int, folder: Path = FITS) -> Path:
    """Where the correction fitted at this seed lives."""
    return folder / f"correction-{seed}"


def fitted(seeds: int, first: int = 0, folder: Path = FITS) -> list[Path]:
    """The corrections on disk for these seeds, or a plain statement of what is missing."""
    found = [correction(seed, folder) for seed in range(first, first + seeds)]
    missing = [one for one in found if not (one / "adapter_config.json").exists()]
    if missing:
        raise SystemExit(
            "these corrections are not on disk: "
            + ", ".join(one.name for one in missing)
            + "\nFit them with `pixi run python -u 06-smolvla-fine-tuned/train.py`."
        )
    return found
