"""The picture the policy reads, which is smaller than the one the bench renders.

The bench's straight-down view is 384 by 384. The policy is shown half of
that in each direction, for one reason: the vision backbone is most of the
cost of a training step, and that cost falls with the area. At 192 a step is
about a third of what it is at 384, which is the difference between a fit
that converges in an hour and one that does not converge in the hours
available.

Nothing needed is lost. A glass is about 50 pixels across in the bench's
picture and about 25 here, and one pixel is 1.6 mm on the table, far finer
than anything this policy has to resolve.

It lives in a module of its own because two places need it and neither
should import the other: ``collect.py`` stores demonstrations at this size,
so a few thousand of them fit in memory rather than a few gigabytes, and
``policy.py`` shrinks whatever the bench hands it at run time. The cost of
that is a coupling worth naming: **change ``SEEN_SIZE`` and the stored
demonstrations are the wrong size**, so they have to be collected again.
"""

from __future__ import annotations

import cv2
import numpy as np

SEEN_SIZE = (192, 192)


def shrink(pictures: np.ndarray) -> np.ndarray:
    """One picture or a batch of them at ``SEEN_SIZE``, still uint8 and still RGB.

    An area filter, which is the right one for making a picture smaller.
    ``cv2.resize`` does not care which way round the colours are, so the
    bench's RGB stays RGB. A picture already at the right size is handed
    straight back, so nothing is ever resampled twice.
    """
    batch = np.asarray(pictures)
    if batch.ndim == 3:
        batch = batch[None]
    if batch.shape[1:3] == SEEN_SIZE:
        return batch
    rows, columns = SEEN_SIZE
    return np.stack([cv2.resize(one, (columns, rows), interpolation=cv2.INTER_AREA) for one in batch])
