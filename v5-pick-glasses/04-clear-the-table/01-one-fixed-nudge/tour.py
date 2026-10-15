"""Where the jaw stands to see the table, and in what order it goes there.

Problem 3 needed no file like this. Its camera is bolted above the table and
frames the whole glass zone on every table, so a solution is handed the
arrangement for nothing. Here the camera rides on the wrist, so seeing is
driving, and something has to decide where to drive.

**A stand is a pose, not a patch.** A look is taken from a pose the jaw can
hold, and what it catches is whatever falls inside the picture from there. So
this file works the other way round from how it reads: it proposes poses, asks
``wrist`` what each one would catch, and keeps the ones worth going to.

**The poses tried are a ring around the glass zone, each facing across it.**
That is how a person surveys a table: stand off the edge and look in. Standing
inside the zone and looking out is worse at both ends -- the camera is tipped
down, so the near table in front of the jaw is the one patch the picture always
has, and the far side of the zone would then be behind the lens.

**A point counts as surveyed only when it lands in the middle of a picture.**
Merely being inside the frame is not enough. The arm reads a glass's width and
foot off its silhouette, and a silhouette cut by the edge of the frame has its
middle in the wrong place: ``arm/dimensions.py`` says so where it sets
``SURVEY_OVERLAP`` for problem 2's own survey, and the same reasoning applies
to the same lens here. So the middle of the picture is what counts, and that
share is borrowed from there rather than invented.

**The tour is every side, not the fewest sides.** One pose on this cell already
frames the whole zone, so a tour chosen to cover the ground would be a single
stand. It would also be wrong, and the reason is the thing the geometry cannot
be asked about: a glass standing behind another is not in the picture, however
well framed the ground under it is. Which glass hides which depends on where
the glasses are, so no tour worked out from the cell alone can promise to catch
them all. What it can do is look from every side the arm can hold, because two
glasses in line from one side are not in line from another. So the tour keeps
the best stand at each bearing and walks round them, and ``wrist.py`` says the
same thing from its end: the glasses that hide each other are the crowded ones,
which are exactly the ones worth seeing, so the arm has to go round the group
and pay for the trip.

Measured on the twenty tables below ``TEST_SEEDS`` that the calibration run
uses: the eight stands between them catch all 117 glasses on all twenty tables.
The best stand on a table catches nine in ten, and an average one seven in ten,
so the sweep is buying the last glass rather than the first. Walking all eight
is about six seconds of arm time, and about eight from where a table starts.

**The reach band is asked of the jaw and not of the flange.** A push has to put
the hand down between glasses, so solution 1 checks the flange as well as the
fingertips, and it is right to. A look puts nothing anywhere: the jaw rides at
travel height with the camera behind it, and ``arm/dimensions.py`` says in as
many words that ``COMFORTABLE_REACH`` is for choosing which side of a glass to
stand the camera on. That is this, so the band is applied to the pose itself.
Asking for the flange as well costs six of the eight bearings and most of what
the tour is for.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache

import numpy as np
from work_cell.arm.dimensions import COMFORTABLE_REACH, SURVEY_OVERLAP
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import ROBOT_BASE, TABLE_CENTRE_XY, TABLE_SIZE

from partners import TRAVEL_HEIGHT, Seen, Waypoint
from wrist import WRIST_VIEW_SIZE, sees, showing, to_pixel

# A look is taken from as high as the jaw rides. The picture is widest from
# there -- about 560 mm of table against 260 mm down at push height -- and
# nothing on the table reaches that height, so the jaw can cross the zone to
# reach a stand without touching anything on the way.
LOOK_HEIGHT = TRAVEL_HEIGHT

# The ring of poses tried: how many bearings round the zone, and how far
# outside its rim. Twelve bearings is every thirty degrees, which is finer than
# the arm can hold -- on this cell eight of the twelve survive the reach band --
# so the ring is not what limits the tour. Three distances because the near ones
# see a smaller patch and the far ones are easier to reach, and which wins is
# the lens's business rather than a thing to guess here.
BEARINGS = 12
STAND_OFFS = (0.06, 0.14, 0.22)

# The share of the picture a point has to land inside to count as surveyed.
# ``SURVEY_OVERLAP`` is how much of one picture problem 2's survey makes the
# next one repeat, for the reason given at the top of this file.
WELL_INSIDE = 1.0 - SURVEY_OVERLAP

# How finely the zone is checked for cover, across and along. Fine enough that
# no gap wide enough to hide a glass can slip between the checked points: the
# zone is 320 by 360 mm, so these leave the points about 50 mm apart, well
# under the narrowest glass the library draws.
CHECKED = (7, 8)

# The jaw is kept this far inside the edge of the table. A pose on the very rim
# is one the arm would have to reach over the edge to hold.
TABLE_MARGIN = 0.02


@dataclass(frozen=True)
class Stand:
    """One pose a look is taken from: where the fingertips are, and the way they point."""

    x: float
    y: float
    heading: float

    def jaw(self) -> Waypoint:
        """The same pose as a waypoint, which is how a path is written."""
        return Waypoint(self.x, self.y, LOOK_HEIGHT, self.heading)


def surveyed(stand: Stand, x: float, y: float) -> bool:
    """Whether a glass standing at ``x, y`` would be measured properly from this stand.

    The foot is what is asked about rather than the whole glass. A tall glass
    whose foot is outside the frame can still have its body in the picture, and
    ``wrist.in_picture`` would hand it over; but its foot sets its place on the
    table, so a stand that cannot see the foot is not a stand that surveyed it.
    Asking about the foot is therefore the cautious question, and a tour built
    on it is good for every glass the library draws.
    """
    jaw = stand.jaw()
    if not sees(jaw, x, y, 0.0):
        return False
    rows, columns = WRIST_VIEW_SIZE
    row, column = to_pixel(jaw, x, y, 0.0)
    low, high = (1.0 - WELL_INSIDE) / 2.0, (1.0 + WELL_INSIDE) / 2.0
    return low * rows <= row <= high * rows and low * columns <= column <= high * columns


def checked() -> list[tuple[float, float]]:
    """The points of the glass zone a tour has to be able to measure."""
    x_min, x_max, y_min, y_max = GLASS_ZONE
    across, along = CHECKED
    return [
        (float(x), float(y))
        for x in np.linspace(x_min, x_max, across)
        for y in np.linspace(y_min, y_max, along)
    ]


def holdable(stand: Stand) -> bool:
    """Whether the arm can stand the jaw here without folding over itself or reaching out flat.

    ``COMFORTABLE_REACH`` is asked of the pose itself. ``dimensions.py`` calls
    that band a preference rather than a limit -- "used to choose which side of
    a glass to stand the camera on" are its own words -- and standing the camera
    is exactly what this is for. A push is the stricter case and keeps the
    stricter test: ``plan.along`` asks it of the flange behind the fingertips as
    well, because a push has to put the hand down between two glasses.
    """
    tip = np.array([stand.x, stand.y])
    on_table = (
        abs(stand.x - TABLE_CENTRE_XY[0]) <= TABLE_SIZE[0] / 2 - TABLE_MARGIN
        and abs(stand.y - TABLE_CENTRE_XY[1]) <= TABLE_SIZE[1] / 2 - TABLE_MARGIN
    )
    reach = float(np.linalg.norm(tip - ROBOT_BASE[:2]))
    return on_table and COMFORTABLE_REACH[0] <= reach <= COMFORTABLE_REACH[1]


def ring() -> list[tuple[int, Stand]]:
    """Every pose on the ring the arm can hold, facing across the zone, with its bearing."""
    x_min, x_max, y_min, y_max = GLASS_ZONE
    middle = np.array([(x_min + x_max) / 2, (y_min + y_max) / 2])
    radius = math.dist((x_min, y_min), (x_max, y_max)) / 2
    out = []
    for turn in range(BEARINGS):
        bearing = turn * 2 * math.pi / BEARINGS
        outward = np.array([math.cos(bearing), math.sin(bearing)])
        for off in STAND_OFFS:
            at = middle + (radius + off) * outward
            # Facing back across the zone, which is the whole point of standing
            # off its rim.
            # Kept inside one turn, so that a heading printed in a log or a
            # record reads the same as the one the cell hands back.
            facing = (bearing + math.pi + math.pi) % (2 * math.pi) - math.pi
            stand = Stand(float(at[0]), float(at[1]), facing)
            if holdable(stand):
                out.append((turn, stand))
    return out


@cache
def survey() -> tuple[Stand, ...]:
    """The tour: the best stand at each bearing the arm can hold, in bearing order.

    Best means it has the most of the zone in the middle of its picture. Where
    two distances from the zone's rim both work, the one that frames more of the
    ground wins, and the choice between bearings is not made at all -- every
    bearing that can be held is in the tour, for the reason at the top of this
    file.

    Cached because it depends on nothing but the cell. It costs a few thousand
    frustum tests, which is a fraction of a second once and nothing after.
    """
    points = checked()
    best: dict[int, tuple[Stand, int]] = {}
    for bearing, stand in ring():
        covers = sum(1 for x, y in points if surveyed(stand, x, y))
        if bearing not in best or covers > best[bearing][1]:
            best[bearing] = (stand, covers)
    return tuple(best[bearing][0] for bearing in sorted(best))


def uncovered() -> list[tuple[float, float]]:
    """The points of the zone no stand in the tour can measure. Empty on this cell.

    Empty ground is not the same as every glass seen: a glass can stand on
    surveyed ground and still be hidden behind a nearer one. This is the half of
    the question geometry can answer.
    """
    return [point for point in checked() if not any(surveyed(stand, *point) for stand in survey())]


def ordered(jaw: Waypoint) -> list[Stand]:
    """The whole tour from where the jaw is standing: round the ring, the near way about.

    The stands sit on a ring, so bearing order is already the short walk round
    them. All that is left to choose is which end to start at, and that is the
    end nearer the jaw. Starting in the middle and wrapping round would cross
    the zone once for nothing.
    """
    walk = list(survey())
    if not walk:
        return walk
    near_first = math.dist((jaw.x, jaw.y), (walk[0].x, walk[0].y))
    near_last = math.dist((jaw.x, jaw.y), (walk[-1].x, walk[-1].y))
    return walk if near_first <= near_last else walk[::-1]


def nearest(x: float, y: float) -> Stand:
    """The stand to go to in order to look at a point: one that surveys it, else the closest.

    The fallback matters for a glass shoved outside the zone, which no stand
    promises to measure. Going to the nearest stand is then the best the tour
    can offer, and the solution finds out by looking rather than by assuming.
    """
    good = [stand for stand in survey() if surveyed(stand, x, y)]
    return min(good or survey(), key=lambda stand: math.dist((x, y), (stand.x, stand.y)))


def clearest(glass: Seen, others: Sequence[Seen]) -> Stand:
    """The stand from which this glass should be least hidden, going by what is believed.

    This is the one place the tour uses the table rather than only the cell. A
    glass that has just been pushed has to be looked at again, and which side of
    the group it can be seen from depends on what else is standing there. The
    belief can be wrong -- that is why the arm looks -- but a side chosen from
    a wrong belief is still a better bet than a side chosen from none.

    Ties go to the nearer stand, because the walk is what it costs.
    """
    crowd = [glass, *others]
    return max(
        [stand for stand in survey() if surveyed(stand, glass.x, glass.y)] or list(survey()),
        key=lambda stand: (
            showing(stand.jaw(), glass, crowd),
            -math.dist((glass.x, glass.y), (stand.x, stand.y)),
        ),
    )
