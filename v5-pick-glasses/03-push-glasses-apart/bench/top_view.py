"""The table seen from straight above, for the solutions that read pictures.

Three of the six take an image rather than a list of numbers, so the bench
has to hand them one. It is the same table at the same moment as ``look()``,
rendered rather than measured, which keeps the input the same information in a
different form.

``film.py`` also renders, but its camera looks steeply down from the arm's
side and its frames are for watching a run by eye. This one is fixed: the same
height, the same frame and the same pixels on every table, because a policy
cannot be compared with itself if the view moves.

    from bench import Bench
    from top_view import TopCamera, top_view, to_pixel

    table = Bench(10_000)
    picture = top_view(table)          # one picture
    camera = TopCamera(table)          # keep one for a loop; building it is slow
    picture = camera.view()

Nothing here is a measurement the arm could not take: it is a camera above the
table, which [the cell](../../docs/the-cell.md) already has.
"""

from __future__ import annotations

import time

import mujoco
import numpy as np
from work_cell.rack.layout import GLASS_ZONE

from bench import TOP_VIEW_HALF_FRAME, TOP_VIEW_HEIGHT, TOP_VIEW_SIZE, Bench

# The whole of this module's surface. The two constants come from bench.py,
# where the camera they describe is written into the world.
__all__ = [
    "METRES_PER_PIXEL",
    "TOP_VIEW_HALF_FRAME",
    "TOP_VIEW_HEIGHT",
    "TOP_VIEW_SIZE",
    "VIEW_CENTRE",
    "TopCamera",
    "to_pixel",
    "to_table",
    "top_view",
]

# The point on the table directly under the camera, and the middle of the frame.
VIEW_CENTRE = ((GLASS_ZONE[0] + GLASS_ZONE[1]) / 2, (GLASS_ZONE[2] + GLASS_ZONE[3]) / 2)
# How much of the table one pixel covers, at the table top.
METRES_PER_PIXEL = 2 * TOP_VIEW_HALF_FRAME / TOP_VIEW_SIZE[1]


class TopCamera:
    """The straight-down camera on one table. Building it is slow; keep it.

    A renderer holds a graphics context, so make one per table and call
    ``view()`` as often as you like.
    """

    def __init__(self, bench: Bench) -> None:
        self.bench = bench
        self.renderer = mujoco.Renderer(bench.model, *TOP_VIEW_SIZE)

    def view(self) -> np.ndarray:
        """The table from above, right now. See ``top_view`` for the shape and colours."""
        started = time.perf_counter()
        self.renderer.update_scene(self.bench.data, camera="top")
        picture = self.renderer.render().copy()
        # Rendering is the bench's cost, not the solution's.
        self.bench.seconds += time.perf_counter() - started
        return picture

    def close(self) -> None:
        self.renderer.close()


def top_view(bench: Bench) -> np.ndarray:
    """The table from directly above, as an array a policy can take.

    **Shape** ``TOP_VIEW_SIZE + (3,)``, that is ``(384, 384, 3)``, ``uint8``.

    **Colours** red, green, blue in that order — *not* the BGR that film.py
    hands OpenCV. Values run 0 to 255. The table is a warm tan, every glass the
    same pale blue, and the jaw, when it is in frame, mid grey. The glasses are
    shaded and lit, so their pixels are not one value: the rim catches a white
    highlight and the inside of the bowl is almost black. What does hold on
    every table is that **a glass pixel's blue is at least its red, and a table
    pixel's never is**, so ``picture[:, :, 2] >= picture[:, :, 0]`` is the
    glasses. They are opaque, with none of the transparency a real drinking
    glass has, and all one colour, so nothing in the picture tells one kind of
    glass from another.

    **Where the camera is** directly above ``VIEW_CENTRE``, the middle of the
    glass zone, ``TOP_VIEW_HEIGHT`` (750 mm) above the table top, looking
    straight down. It never moves, on any table.

    **Which way round** the picture's right is the table's +x, away from the
    arm's base; the picture's up is the table's +y. So column grows with x and
    row grows as y falls. ``to_pixel`` and ``to_table`` are that mapping, exact
    for anything standing on the table top; use them rather than rederiving it.

    **What is in frame** the whole glass zone, with room around it, so a glass
    standing at the zone's edge is whole in the picture. The view is a
    perspective one, so a glass leans outwards from the middle of the frame and
    you see a little of its inside on the far side. The jaw is parked outside
    the frame between actions, and is in the picture while it works.

    Building a renderer is slow. In a loop keep a ``TopCamera`` instead.
    """
    camera = TopCamera(bench)
    try:
        return camera.view()
    finally:
        camera.close()


def to_pixel(x: float, y: float) -> tuple[float, float]:
    """Where a point standing on the table top falls in the picture: (row, column).

    Fractional, and outside 0..383 for a point outside the frame. Exact only
    on the table top: anything higher leans outwards from the middle.
    """
    rows, columns = TOP_VIEW_SIZE
    across = (x - VIEW_CENTRE[0]) / (2 * TOP_VIEW_HALF_FRAME)
    up = (y - VIEW_CENTRE[1]) / (2 * TOP_VIEW_HALF_FRAME)
    return (0.5 - up) * rows - 0.5, (0.5 + across) * columns - 0.5


def to_table(row: float, column: float) -> tuple[float, float]:
    """Where a pixel of the picture lands on the table top: (x, y) in metres."""
    rows, columns = TOP_VIEW_SIZE
    across = (column + 0.5) / columns - 0.5
    up = 0.5 - (row + 0.5) / rows
    return (
        VIEW_CENTRE[0] + across * 2 * TOP_VIEW_HALF_FRAME,
        VIEW_CENTRE[1] + up * 2 * TOP_VIEW_HALF_FRAME,
    )
