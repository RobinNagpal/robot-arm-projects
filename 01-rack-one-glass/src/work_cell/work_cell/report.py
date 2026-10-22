"""A written record of one run, for a person to read afterwards.

A run is a few minutes of an arm moving and a wall of log lines, and when it
ends with nothing on the rack the log says what failed but not what the arm
could see at the time. This writes the other half: what it was looking at,
what it made of it, and what it did next, as a markdown file with the
pictures beside the sentences.

Three rules make it worth having.

**It is written as it happens.** Every call appends and flushes, so a run that
dies half way through still leaves everything up to the moment it died. A
report assembled at the end is a report you do not get on the runs you most
want it for.

**It follows the walkthrough.** The headings are the six steps of `docs/`, in
order, and under each one the lines written by ``doing()`` are the lines of
that step's pseudocode block, word for word. A reader can hold the two side by
side: the document says what is meant to happen, and the report says what
happened, with the real numbers and the real pictures against the same lines.
That is only true as long as somebody keeps them the same, which is what
`test_report.py` checks.

**The pictures carry their own caption.** An image file found on its own, or
opened from the folder rather than through the markdown, still says what the
arm was doing when it was taken.

No ROS here, so the whole thing can be tested on drawn pictures.
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

# The caption is drawn into a strip above the picture rather than over it, so
# that it never hides the thing the picture was taken to show.
CAPTION_HEIGHT = 22
CAPTION_FONT = cv2.FONT_HERSHEY_SIMPLEX
CAPTION_SCALE = 0.4

# Where the walkthrough is, from inside a run folder: runs/<when>/report.md.
WALKTHROUGH = "../../docs"


def annotate(image: np.ndarray, doing: str) -> np.ndarray:
    """The picture with a caption strip above it saying what was going on."""
    picture = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if picture.dtype != np.uint8:
        picture = picture.astype(np.uint8)

    width = picture.shape[1]
    # About this many characters fit across at this font size.
    lines = textwrap.wrap(doing, width=max(int(width / 6.2), 20)) or [""]
    strip = np.full((CAPTION_HEIGHT * len(lines) + 6, width, 3), 24, dtype=np.uint8)
    for index, line in enumerate(lines):
        cv2.putText(
            strip,
            line,
            (6, CAPTION_HEIGHT * (index + 1) - 6),
            CAPTION_FONT,
            CAPTION_SCALE,
            (235, 235, 235),
            1,
            cv2.LINE_AA,
        )
    return np.vstack([strip, picture])


def run_folder(root: Path | None = None) -> Path:
    """A folder of its own for this run, under ``runs/``.

    Named by the clock rather than by the settings, so that two runs of the
    same thing do not overwrite each other. Comparing a run that worked with
    one that did not is most of what these are for, so nothing here ever
    deletes an old one.

    Down to the second, and separated all the way through: two runs a minute
    apart have to land in different folders, and a reader has to be able to
    tell which is which without counting digits.
    """
    folder = (Path(root) if root else Path.cwd() / "runs") / f"{datetime.now():%Y-%m-%d-%H-%M-%S}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


class Report:
    """One run's folder: a markdown file, and the pictures it points at."""

    def __init__(self, folder: Path, title: str) -> None:
        self.folder = Path(folder)
        self.images = self.folder / "images"
        self.images.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "report.md"
        self._taken = 0

        # The launch file opens one of these to write down what it put on the
        # table, and the task opens another when it starts. They are the same
        # run and the same file, so only the first one lays the header down.
        if not self.path.exists():
            self._write(
                f"# {title}\n\n_{datetime.now():%Y-%m-%d %H:%M:%S}_\n\n"
                "Read this beside [the walkthrough](../../docs/README.md). The headings "
                "below are its six steps, in order, and the lines in **`bold code`** are "
                "the lines of that step's pseudocode block, word for word, each followed "
                "by what it produced on this run.\n\n"
            )

    # ---------------------------------------------------------------- words

    def step(
        self,
        title: str,
        *,
        doc: str | None = None,
        code: str | None = None,
        level: int = 2,
    ) -> None:
        """A heading, for one step of the run.

        ``doc`` is the walkthrough page this step is explained on, and ``code``
        is where it lives in the source. Both are written under the heading as
        links, because the first question anybody has about a line in a report
        is where the thing that wrote it is.
        """
        self._write(f"\n{'#' * level} {title}\n\n")
        trail = []
        if doc:
            trail.append(f"Walkthrough: [`docs/{doc}`]({WALKTHROUGH}/{doc})")
        if code:
            trail.append(f"Code: `{code}`")
        if trail:
            self._write("_" + " · ".join(trail) + "_\n\n")

    def doing(self, line: str, result: str | None = None) -> None:
        """One line of this step's pseudocode, and what it produced.

        ``line`` is copied from the pseudocode block in the step's walkthrough
        page rather than reworded, so that the two can be read against each
        other. ``result`` is the part the document cannot have: the actual
        number, this run, on this glass.
        """
        self._write(f"**`{line}`**" + (f" — {result}" if result else "") + "\n\n")

    def say(self, text: str) -> None:
        """A sentence about what is happening, or about to."""
        self._write(f"{text}\n\n")

    def table(self, rows: dict[str, object]) -> None:
        """A handful of named values, as a two column table."""
        if not rows:
            return
        out = ["| | |", "| --- | --- |"]
        out += [f"| {name} | {value} |" for name, value in rows.items()]
        self._write("\n".join(out) + "\n\n")

    def trouble(self, text: str) -> None:
        """Something went wrong, called out so it can be found by eye."""
        self._write(f"> **{text}**\n\n")

    # -------------------------------------------------------------- pictures

    def picture(self, image: np.ndarray, doing: str, *, then: str | None = None) -> None:
        """Save a picture with its caption drawn on, and point the markdown at it.

        ``doing`` is what the arm was doing when the picture was taken, and it
        goes both into the image and above it. ``then`` is what happened next,
        and goes below — which is the pair a reader needs to tell a picture
        that explains a failure from one that merely preceded it.
        """
        self._taken += 1
        name = f"{self._taken:02d}-{_slug(doing)}.png"
        cv2.imwrite(str(self.images / name), annotate(_as_bgr(image), doing))

        self._write(f"{doing}\n\n![{doing}](images/{name})\n\n")
        if then:
            self._write(f"{then}\n\n")

    # ---------------------------------------------------------------- ending

    def finish(self, text: str) -> None:
        self._write(f"\n## How it ended\n\n{text}\n")

    # --------------------------------------------------------------- writing

    def _write(self, text: str) -> None:
        # Appended and flushed every time, so a run that dies still leaves
        # everything up to the moment it died.
        with self.path.open("a", encoding="utf-8") as out:
            out.write(text)


def with_mask(rgb: np.ndarray, mask: np.ndarray, colour=(80, 220, 80)) -> np.ndarray:
    """The picture with the outline of what was found drawn on it.

    The mask is what the arm believes is glass, and seeing it against the
    picture it came from is the quickest way to tell a measurement that is
    wrong from one that is right about the wrong thing.
    """
    picture = _as_bgr(rgb).copy()
    edges = np.asarray(mask).astype(np.uint8)
    found, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(picture, found, -1, colour, 1)
    return picture


def with_marks(rgb: np.ndarray, marks: list[tuple[float, float, str]]) -> np.ndarray:
    """The picture with a cross and a label at each named pixel."""
    picture = _as_bgr(rgb).copy()
    for x, y, label in marks:
        at = (int(round(x)), int(round(y)))
        cv2.drawMarker(picture, at, (60, 90, 240), cv2.MARKER_CROSS, 11, 1)
        cv2.putText(
            picture, label, (at[0] + 6, at[1] - 4), CAPTION_FONT, 0.32, (60, 90, 240), 1, cv2.LINE_AA
        )
    return picture


def _as_bgr(image: np.ndarray) -> np.ndarray:
    """Whatever was handed over, as something cv2 can write."""
    picture = np.asarray(image)
    if picture.dtype == bool:
        picture = (picture * 255).astype(np.uint8)
    if picture.dtype != np.uint8:
        finite = picture[np.isfinite(picture)] if picture.size else picture
        top = float(finite.max()) if finite.size else 1.0
        picture = (np.nan_to_num(picture) / (top or 1.0) * 255).astype(np.uint8)
    return picture


def _slug(text: str) -> str:
    """A short file name from a sentence, in the project's naming style."""
    kept = [c.lower() if c.isalnum() else "-" for c in text]
    slug = "".join(kept).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:48] or "picture"
