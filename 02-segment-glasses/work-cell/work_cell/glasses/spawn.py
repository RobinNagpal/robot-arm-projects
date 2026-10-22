"""Deciding what glasses to put on the table, and turning them into models.

Nothing about any one glass is fixed. Its kind, its proportions, where it
stands and which way it is turned are all drawn fresh for every run, so the
same code has to cope with a different table each time. A seed makes any one of
those tables repeatable, which is what makes a failure worth reporting: the run
that produced it can be run again.

The important part is that sizes are drawn rather than listed. A run with four
glasses on the table will have four different sizes even if two are the same
kind, and that is the only honest way to test an arm that is supposed to
measure rather than look up.

Meshes are generated here too, by spinning each outline. One mesh per glass
rather than one per kind, because no two glasses in a run are the same size.

Plain Python and numpy, no ROS, so a layout can be generated and checked
without a simulator.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..rack.layout import GLASS_ZONE, TABLE_TOP_Z
from .force import GLASS_DENSITY
from .shapes import KIND_RANGES, Outline, draw, hollow
from .spec import LIBRARY

TEMPLATE = Path(__file__).parent / "glass.sdf"

# Centre to centre. Two glasses closer than this are hard to tell apart in one
# picture, and — the binding reason — the wrist camera cannot get a clean
# side-on view of one without the other appearing behind it. The widest glass
# drawn is about 105 mm across, so this leaves 45 mm of daylight between the
# two widest that could ever stand side by side.
MIN_SEPARATION = 0.15

# How many slices the collision shape is cut into, top to bottom. Enough that a
# stem is its own cylinder rather than being averaged into the bowl above it.
COLLISION_SLICES = 8

# How many pieces the wall is built from around the glass. Each is a flat box,
# so the outside is a polygon rather than a circle; at 24 its corners stand
# under 1% proud of the circle, well inside what the fingers allow for.
COLLISION_STAVES = 24

# The thinnest a wall piece is made, whatever the real wall. A physics engine
# lets fast or heavily loaded contacts sink a little way in, and a wall thinner
# than that sinkage is one a peg can pass straight through.
MIN_STAVE_THICKNESS = 0.003


@dataclass(frozen=True)
class SpawnedGlass:
    """One glass, as the simulator will be told to create it."""

    name: str
    kind: str
    outline: Outline
    position: tuple[float, float, float]
    yaw: float
    proportions: dict[str, float] = field(default_factory=dict)

    @property
    def wall(self) -> float:
        return LIBRARY[self.kind].wall_thickness_m

    @property
    def mass(self) -> float:
        """What this glass really weighs, which the arm has to find out."""
        return self.mass_properties[0]

    @property
    def mass_properties(self) -> tuple[float, float, float, float]:
        """Mass, height of the centre of mass, and inertia across and about the axis.

        All worked out from the solid it is modelled as: everything inside the
        outline, less the hollow the drink goes in. The inertia is about the
        centre of mass, which is where the simulator applies it.

        The centre of mass matters more than it looks. Left out, the simulator
        puts all the weight at the model's origin, the bottom of the glass. A
        glass held above its base and turned over then has all its weight
        above the pads, balanced like a pencil on its point, and it tips back
        over in the fingers. Where it really is — up in the walls — it hangs
        below the pads and stays put.
        """
        outline = self.outline
        solid = (outline.height, outline.radius)
        empty = hollow(outline, self.wall)
        # Per unit height: area, area times height, the disc's own spin about
        # the axis, and its own tumble across it (r^2/2 and r^2/4 per unit area).
        terms = []
        for height, radius in (solid, empty):
            area = np.pi * radius**2
            terms.append(
                np.array(
                    [
                        np.trapezoid(area, height),
                        np.trapezoid(area * height, height),
                        np.trapezoid(area * height**2, height),
                        np.trapezoid(area * radius**2 / 2.0, height),
                        np.trapezoid(area * radius**2 / 4.0, height),
                    ]
                )
            )
        mass, first, second, spin, tumble = (terms[0] - terms[1]) * GLASS_DENSITY
        centre = first / mass
        across = tumble + second - mass * centre**2
        return float(mass), float(centre), float(across), float(spin)


# How many times the whole arrangement is redrawn before giving up.
#
# Glasses are placed one after another, each one somewhere the ones already
# down leave room for, and that fails far more often than the zone being full
# would suggest: one glass dropped in the middle early on can leave a zone that
# still has plenty of space but none of it usable. Starting the whole
# arrangement again costs nothing and clears it, where trying yet another spot
# for the last glass cannot.
LAYOUT_ATTEMPTS = 8


def random_glasses(count: int, seed: int, kinds: list[str] | None = None) -> list[SpawnedGlass]:
    """Lay out ``count`` glasses of random kinds and sizes in the glass zone."""
    for attempt in range(LAYOUT_ATTEMPTS):
        try:
            # Derived from the seed, so the same seed still gives the same
            # glasses however many attempts it took to place them. One value
            # per (seed, attempt) pair, so no two attempts redraw the same
            # arrangement.
            return _layout(random.Random(seed * LAYOUT_ATTEMPTS + attempt), count, kinds)
        except _Crowded:
            continue
    raise RuntimeError(
        f"could not fit {count} glasses in the glass zone without them crowding "
        f"each other, in {LAYOUT_ATTEMPTS} attempts; try fewer, or widen "
        f"GLASS_ZONE in rack/layout.py"
    )


class _Crowded(Exception):
    """No room left for the next glass. Caught by the retry above."""


def _layout(rng, count: int, kinds: list[str] | None) -> list[SpawnedGlass]:
    """One attempt at an arrangement, which may run out of room."""
    choices = kinds or sorted(KIND_RANGES)
    x_min, x_max, y_min, y_max = GLASS_ZONE

    placed: list[SpawnedGlass] = []
    for index in range(count):
        kind = rng.choice(choices)
        outline, proportions = draw(kind, rng)
        x, y = _free_spot(rng, placed, x_min, x_max, y_min, y_max)
        placed.append(
            SpawnedGlass(
                name=f"glass_{index}",
                kind=kind,
                outline=outline,
                position=(x, y, TABLE_TOP_Z),
                # A glass is round, so its yaw only matters if it has a handle.
                # It is drawn anyway, so that a handle rule cannot pass by
                # being lucky about which way the glass happened to face.
                yaw=rng.uniform(-math.pi, math.pi),
                proportions=proportions,
            )
        )
    return placed


def _free_spot(rng, placed, x_min, x_max, y_min, y_max) -> tuple[float, float]:
    """A place to stand a glass, far enough from the ones already down."""
    for _ in range(500):
        x = rng.uniform(x_min, x_max)
        y = rng.uniform(y_min, y_max)
        if all(math.dist((x, y), g.position[:2]) >= MIN_SEPARATION for g in placed):
            return x, y
    raise _Crowded(f"no room for glass {len(placed) + 1}")


# ------------------------------------------------------------------- meshes


def cross_section(outline: Outline, wall: float) -> tuple[np.ndarray, np.ndarray]:
    """The cut face of a glass sliced down its axis, as (radius, height) points.

    It runs from the middle of the base, out and up the outside, across the
    rim, down the inside and in across the floor to the axis. Spinning this
    gives a closed solid, so the glass has a wall you can see the thickness of
    at the rim and a bottom that says which end is which.
    """
    inner_height, inner_radius = hollow(outline, wall)
    radius = np.concatenate(([0.0], outline.radius, inner_radius[::-1], [0.0]))
    height = np.concatenate(([0.0], outline.height, inner_height[::-1], [outline.floor]))
    return radius, height


def revolve(outline: Outline, wall: float, segments: int = 48) -> tuple[np.ndarray, np.ndarray]:
    """Spin a glass's cross-section into a closed mesh: vertices and triangles.

    Written out rather than taken from trimesh so that the shape of a glass
    model is visible in this project rather than in a dependency, and so the
    tests can check it without one.

    Closed rather than a single open skin. A renderer draws only the side of a
    triangle that faces it, so a skin with no inside surface shows the far
    wall of the glass as missing whenever you look into it.
    """
    angles = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
    radius, height = cross_section(outline, wall)
    rings = len(radius)

    vertices = np.empty((rings * segments, 3), dtype=float)
    for ring, (z, r) in enumerate(zip(height, radius, strict=True)):
        vertices[ring * segments : (ring + 1) * segments] = np.column_stack(
            (r * np.cos(angles), r * np.sin(angles), np.full(segments, z))
        )

    faces: list[tuple[int, int, int]] = []
    for ring in range(rings - 1):
        for segment in range(segments):
            nxt = (segment + 1) % segments
            a = ring * segments + segment
            b = ring * segments + nxt
            c = (ring + 1) * segments + segment
            d = (ring + 1) * segments + nxt
            # Wound so each face points out of the glass. The cross-section
            # runs round with the glass on its left, so one winding does for
            # the outside, the rim, the inside and the bottom alike.
            faces.append((a, d, c))
            faces.append((a, b, d))

    # Where a ring sits on the axis all its points are one point, and half the
    # triangles beside it have no area.
    faces_array = np.array(faces, dtype=int)
    corners = vertices[faces_array]
    area = np.linalg.norm(np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]), axis=1)
    return vertices, faces_array[area > 1e-12]


def write_mesh(outline: Outline, wall: float, path: Path, segments: int = 48) -> Path:
    """Write one glass as an STL the simulator can load.

    Each facet carries its own normal. Writing zeroes there is legal STL and
    means "work it out from the winding", but it leaves the surface at the
    mercy of whatever the renderer decides, and a glass whose foot does not
    draw is a glass with no waist in it — which is a wine glass the arm will
    try to hold by the bowl.
    """
    vertices, faces = revolve(outline, wall, segments)
    lines = ["solid glass"]
    for a, b, c in faces:
        corners = vertices[[a, b, c]]
        normal = np.cross(corners[1] - corners[0], corners[2] - corners[0])
        normal = normal / np.linalg.norm(normal)
        lines.append(f"facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}")
        lines.append("  outer loop")
        for index in (a, b, c):
            x, y, z = vertices[index]
            lines.append(f"    vertex {x:.6f} {y:.6f} {z:.6f}")
        lines.append("  endloop")
        lines.append("endfacet")
    lines.append("endsolid glass")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    return path


def _slice_edges(outline: Outline, slices: int) -> tuple[np.ndarray, np.ndarray]:
    """Where to cut the solid part and the hollow part into slices.

    The floor is always a cut, so no slice is half solid and half hollow. The
    slices are shared between the two parts by how tall each is.
    """
    height = outline.total_height
    solid = max(1, round(slices * outline.floor / height))
    hollow_part = max(1, slices - solid)
    return (
        np.linspace(0.0, outline.floor, solid + 1),
        np.linspace(outline.floor, height, hollow_part + 1),
    )


def _widest_in(outline: Outline, bottom: float, top: float) -> float:
    """The largest radius the glass reaches between two heights."""
    inside = (outline.height >= bottom) & (outline.height <= top)
    ends = np.interp([bottom, top], outline.height, outline.radius)
    return float(max(outline.radius[inside].max(initial=0.0), ends.max()))


def collision_cylinders(outline: Outline, slices: int = COLLISION_SLICES) -> list[tuple[float, float, float]]:
    """The solid part of the collision shape: base, foot and stem.

    Each entry is (bottom height, top height, radius), from the table up to the
    floor. The radius of a slice is the largest the glass reaches inside it, so
    the shape is never thinner than the glass and the fingers cannot pass
    through it.
    """
    solid, _ = _slice_edges(outline, slices)
    # Pairwise over the edges, so the second list is one shorter on purpose.
    return [
        (float(bottom), float(top), _widest_in(outline, bottom, top))
        for bottom, top in zip(solid, solid[1:], strict=False)
    ]


def collision_staves(
    outline: Outline, wall: float, slices: int = COLLISION_SLICES, staves: int = COLLISION_STAVES
) -> list[tuple[float, float, float, float, float]]:
    """The hollow part of the collision shape: a ring of flat pieces per slice.

    Each entry is (bottom height, top height, outer radius, thickness, angle).
    The outer faces stand at the widest radius in the slice, like the
    cylinders, and meet edge to edge, so the fingers cannot close through the
    wall. Inside there is room, which is what lets a glass stood mouth down go
    over a peg instead of balancing on top of it.
    """
    thickness = max(wall, MIN_STAVE_THICKNESS)
    _, hollow_edges = _slice_edges(outline, slices)
    ring: list[tuple[float, float, float, float, float]] = []
    for bottom, top in zip(hollow_edges, hollow_edges[1:], strict=False):
        radius = _widest_in(outline, bottom, top)
        for index in range(staves):
            ring.append((float(bottom), float(top), radius, thickness, 2.0 * np.pi * index / staves))
    return ring


_SURFACE = (
    "          <surface>\n"
    "            <friction><ode><mu>1.1</mu><mu2>1.1</mu2></ode></friction>\n"
    "            <contact><ode><kp>5e5</kp><kd>50</kd></ode></contact>\n"
    "          </surface>\n"
)


def _collisions(outline: Outline, wall: float) -> list[str]:
    """Every collision element of one glass, as SDF."""
    parts = []
    for index, (bottom, top, radius) in enumerate(collision_cylinders(outline)):
        parts.append(
            f'        <collision name="solid_{index}">\n'
            f"          <pose>0 0 {(bottom + top) / 2.0:.4f} 0 0 0</pose>\n"
            f"          <geometry><cylinder>"
            f"<radius>{radius:.4f}</radius><length>{top - bottom:.4f}</length>"
            f"</cylinder></geometry>\n" + _SURFACE + "        </collision>"
        )
    staves = collision_staves(outline, wall)
    for index, (bottom, top, radius, thickness, angle) in enumerate(staves):
        # Wide enough that neighbours meet at the outside face.
        width = 2.0 * radius * np.tan(np.pi / COLLISION_STAVES)
        middle = radius - thickness / 2.0
        parts.append(
            f'        <collision name="wall_{index}">\n'
            f"          <pose>{middle * np.cos(angle):.4f} {middle * np.sin(angle):.4f} "
            f"{(bottom + top) / 2.0:.4f} 0 0 {angle:.4f}</pose>\n"
            f"          <geometry><box>"
            f"<size>{thickness:.4f} {width:.4f} {top - bottom:.4f}</size>"
            f"</box></geometry>\n" + _SURFACE + "        </collision>"
        )
    return parts


# A tint per glass, so that a person watching can tell them apart and see
# which one the arm is working on. Nothing in the arm reads these: a glass is
# found by its points standing above the table, which is a measurement of
# shape and not of colour. They are kept bright so that a glass is easy to
# pick out in the run report, and there are more of them than a run ever
# spawns.
GLASS_TINTS = (
    (0.90, 0.35, 0.35),  # red
    (0.35, 0.65, 0.90),  # blue
    (0.45, 0.80, 0.45),  # green
    (0.95, 0.75, 0.30),  # amber
    (0.75, 0.45, 0.85),  # violet
    (0.35, 0.80, 0.80),  # teal
    (0.95, 0.55, 0.75),  # pink
    (0.70, 0.70, 0.40),  # olive
)

# Opaque. Any transparency at all washes the tint out against the pale table
# — at 0.15 a green glass already measures within 12 counts of neutral — and
# a glass nobody can see is the thing this is meant to fix. What the arm can
# see is not affected either way: that is decided by the label, not by this.
GLASS_TRANSPARENCY = 0.0


def _index_of(name: str) -> int:
    """The number on the end of a spawned glass's name, or 0 if it has none."""
    tail = name.rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def glass_sdf(glass: SpawnedGlass, mesh_uri: str) -> str:
    """One glass as the simulator's own model format."""
    mass, centre, across, about_axis = glass.mass_properties
    outline = glass.outline

    collisions = _collisions(outline, glass.wall)

    x, y, z = glass.position
    # By position in the run rather than at random, so two glasses in one run
    # never come out the same colour and a repeated seed repaints them the same.
    tint = GLASS_TINTS[_index_of(glass.name) % len(GLASS_TINTS)]
    return (
        TEMPLATE.read_text()
        .split("-->\n", 1)[1]
        .format(
            name=glass.name,
            x=x,
            y=y,
            z=z,
            yaw=glass.yaw,
            mass=mass,
            centre=centre,
            ixx=across,
            iyy=across,
            izz=about_axis,
            collisions="\n".join(collisions),
            mesh_uri=mesh_uri,
            red=tint[0],
            green=tint[1],
            blue=tint[2],
            opacity=1.0 - GLASS_TRANSPARENCY,
            transparency=GLASS_TRANSPARENCY,
        )
    )
