"""The borrowed weights: fetched into weights/ once, found there afterwards.

Two files, one per rung of this solution. SAM 2's, which the keeper sits behind,
and SAM 3's, which takes a word instead of a grid of points. Neither is trained
here and no gradient is ever computed through either. They are cached inside
this folder rather than in the home directory, so that what a run depends on
sits beside the run and `weights/` can be deleted to start again.

Each function fetches its own model and returns what to load it by. A second
call finds the files already on disk, asks the network nothing, and returns the
same answer, which is what makes fetching cheap to repeat.

    pixi run python 05-sam2-with-a-keeper/weights.py   # fetch what can be fetched

**The licence is not inherited from one generation to the next.** SAM 2 is
Apache 2.0 and downloads without an account. SAM 3's weights are released under
terms of their own and the upload is gated, so fetching them needs an account
that has been granted access. That is checked here rather than discovered
halfway through a run.
"""

from __future__ import annotations

from pathlib import Path

CACHE = Path(__file__).parent / "weights"
HUGGING_FACE = CACHE / "huggingface"

# The two generations, as the document names them. SAM 2 at the base-plus size,
# which is the middle of the four and the one whose stronger picture encoder is
# the reason to prefer this generation to the first.
SAM2 = "facebook/sam2.1-hiera-base-plus"
SAM3 = "facebook/sam3"

# Each upload holds the same weights twice over, once for this library and once
# for the authors' own. Only the safetensors copy and the settings beside it are
# wanted; taking the lot would fetch twice what is used. SAM 3 is prompted with
# a word, so its tokenizer's tables come too.
MODEL_FILES = ["*.json", "*.safetensors"]
WORD_FILES = [*MODEL_FILES, "*.txt"]


def _fetch(repo: str, patterns: list[str]) -> str:
    """The local path to ``repo``, downloading it only if it is not already here."""
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    HUGGING_FACE.mkdir(parents=True, exist_ok=True)
    try:
        # Already here: this reads the cache and asks the network nothing.
        return snapshot_download(
            repo, cache_dir=str(HUGGING_FACE), allow_patterns=patterns, local_files_only=True
        )
    except LocalEntryNotFoundError:
        return snapshot_download(repo, cache_dir=str(HUGGING_FACE), allow_patterns=patterns)


def sam2() -> str:
    """Fetch SAM 2's weights and return the path to load them from."""
    return _fetch(SAM2, MODEL_FILES)


def sam3() -> str:
    """Fetch SAM 3's weights and return the path to load them from.

    Refused with the reason when the upload will not hand them over. Access is
    granted per account, so a machine that has never been given it cannot run
    this rung at all, and saying that is more use than a stack trace from
    inside the library.
    """
    from huggingface_hub.errors import GatedRepoError

    try:
        return _fetch(SAM3, WORD_FILES)
    except GatedRepoError as refused:
        raise SystemExit(
            f"{SAM3} will not hand over its weights to this machine: {refused.__class__.__name__}.\n"
            f"They are gated, which means the terms have to be accepted at "
            f"https://huggingface.co/{SAM3} and the account that accepted them has to be logged in "
            f"here, with `hf auth login`.\n"
            f"Nothing else in this folder needs an account: SAM 2 is Apache 2.0 and downloads "
            f"without one."
        ) from None


def fitted(solution: str) -> Path:
    """The file `train.py` writes and `run.py` reads back.

    Beside the downloaded weights, because it is the same kind of thing: not
    committed, and remade by a command.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"fitted-{solution}.pt"


def main() -> None:
    print(f"SAM 2  {sam2()}")
    try:
        print(f"SAM 3  {sam3()}")
    except SystemExit as refused:
        # Printed rather than raised: fetching what can be fetched is the job
        # here, and weights that are out of reach are an answer about them.
        print(f"SAM 3  not fetched.\n{refused}")


if __name__ == "__main__":
    main()
