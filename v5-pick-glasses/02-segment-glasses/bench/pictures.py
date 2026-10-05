"""A depth picture dressed up as the colour photograph these models expect.

The renderer gives a distance for every pixel and no colour at all. Every model
in this folder arrives with weights fitted to ordinary photographs, which are
three eight-bit channels, so the distance is shaded into a grey value and that
one channel is repeated three times.

All three solutions share this assumption, so it is written once, here. That is
the point of the module: the three scorecards are only comparable if the
pictures behind them are identical, and a solution with its own shading could
beat another by shading rather than by method. It is also the largest risk in
the folder, because what comes out has the shape of a photograph and none of
its content: no texture, no reflection, no colour, and brightness that means
distance rather than surface.

Two choices are worth stating.

**Near is light, far is dark, over the range each picture actually holds.** The
edge these models have to find is a glass's outline against the table behind
it, which is a step in distance, so the shading is stretched to put the nearest
rim and the farthest table at the two ends of the range. A fixed range would
squeeze a scene into a narrow band of grey and weaken exactly that edge.

**A ray that hit nothing is background, below any real surface.** Off the table
there is no distance to shade. Giving those pixels their own value keeps them
from reading as a surface further away than the table, which is what a value
inside the range would make them.

Nothing here is random, and the same picture always shades to the same bytes.
"""

from __future__ import annotations

import numpy as np
import torch

from render import Picture

# The grey a ray that hit nothing gets, and the band real surfaces are shaded
# into. Kept apart so the edge of the table is an edge and not a far surface.
BACKGROUND = 0
DARKEST, DARKEST_TO_LIGHTEST = 32, 255 - 32

# A picture with less depth range than this has nothing to stretch, so
# stretching it would only amplify the renderer's rounding into fake edges.
FLAT = 1e-6


def grey(picture: Picture) -> np.ndarray:
    """The one grey channel, (rows, columns) of uint8."""
    depth = np.asarray(picture.depth, dtype=np.float64)
    hit = np.isfinite(depth)
    shade = np.full(depth.shape, BACKGROUND, dtype=np.uint8)
    if not hit.any():
        return shade

    near = depth[hit].min()
    span = depth[hit].max() - near
    if span < FLAT:
        shade[hit] = DARKEST + DARKEST_TO_LIGHTEST
        return shade

    away = (depth[hit] - near) / span
    shade[hit] = np.round(DARKEST + (1.0 - away) * DARKEST_TO_LIGHTEST).astype(np.uint8)
    return shade


def shade(picture: Picture) -> np.ndarray:
    """The picture as (rows, columns, 3) of uint8: one grey channel, three times."""
    return np.repeat(grey(picture)[:, :, None], 3, axis=2)


def as_tensor(picture: Picture) -> torch.Tensor:
    """The same picture as (3, rows, columns) between 0 and 1, the way torchvision takes one."""
    channels = shade(picture).transpose(2, 0, 1)
    return torch.from_numpy(np.ascontiguousarray(channels)).float() / 255.0
