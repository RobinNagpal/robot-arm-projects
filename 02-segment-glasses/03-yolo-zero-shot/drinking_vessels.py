"""Which of the borrowed model's category names count as a drinking vessel.

The borrowed model can only ever answer with a name from the list it was fitted
on, and that list was written to describe photographs of the everyday world.
None of its entries is one of this cell's four kinds of glass, so a name here can
do exactly one job: decide whether an outline is worth keeping. It is read once,
in this module, and never travels any further.

**The name must not become the kind of glass.** A borrowed category carries an
implied size with it, because the model's idea of a cup was formed from
photographs of real cups at the sizes real cups come in. If the name travelled
into the record, that implied size would travel with it and a belief about how
big a glass is would have entered the cell without anything having measured it.
Problem 2 does not ask for the kind in any case. So the filter runs here and the
name is dropped, which is why nothing below this module knows what the model
called anything.

**The filter is generous on purpose.** The boundary the model draws between its
own categories was never meant to tell this cell's kinds apart, so accepting a
single category would throw away every glass the model happened to name with a
neighbouring one. Admitting a near neighbour costs little here: there is nothing
on this table but glasses, so a generous filter cannot let in a real bottle.

Nothing in this module is fitted. The list is the borrowed model's, and the
choice of which of its entries to accept is a reading of the names.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

# The two entries that are drinking vessels outright: the stemmed one, which the
# cell's stemmed and short stemmed kinds resemble, and the plain one, which its
# straight and tapered kinds resemble.
VESSELS = ("wine glass", "cup")

# Near neighbours of those two shapes. A bowl is a cup with no wall left, a vase
# is a tapered glass drawn tall, and a bottle is the narrow silhouette a straight
# glass makes from the side. Each is a name the model could reach for when shown
# a shape it has never met, and dropping it would lose a real glass.
NEIGHBOURS = ("bowl", "vase", "bottle")

ACCEPTED = frozenset(VESSELS + NEIGHBOURS)


def is_drinking_vessel(name: str) -> bool:
    """Whether one of the model's category names is kept."""
    return name in ACCEPTED


def accepted_ids(names: Mapping[int, str]) -> frozenset[int]:
    """The model's own class numbers for the names this solution keeps.

    ``names`` is the model's fixed list, as it reports it: class number to name.
    Taken from the model rather than written down, because the numbering belongs
    to whoever fitted the weights and a number copied here would rot silently.
    """
    return frozenset(number for number, name in names.items() if is_drinking_vessel(name))


def are_drinking_vessels(class_ids, names: Mapping[int, str]) -> np.ndarray:
    """Per detection, whether the model's name for it is a drinking vessel."""
    kept = accepted_ids(names)
    return np.array([int(number) in kept for number in np.asarray(class_ids).ravel()], dtype=bool)
