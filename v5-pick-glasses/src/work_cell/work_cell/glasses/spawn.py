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
from .shapes import KIND_RANGES, Outline, draw
from .spec import LIBRARY

TEMPLATE = Path(__file__).parent / "glass.sdf"

# Centre to centre. Two glasses closer than this are hard to tell apart in one
# picture, and — the binding reason — the wrist camera cannot get a clean
# side-on view of one without the other appearing behind it. The widest glass
# drawn is about 105 mm across, so this leaves 45 mm of daylight between the
# two widest that could ever stand side by side.
MIN_SEPARATION = 0.15

# How many cylinders the collision shape is built from. Enough that a stem is
# its own cylinder rather than being averaged into the bowl above it.
COLLISION_SLICES = 8


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
    def mass(self) -> float:
        """What this glass really weighs, which the arm has to find out."""
        thickness = LIBRARY[self.kind].wall_thickness_m
        radius = self.outline.radius
        lateral = float(np.trapezoid(2.0 * np.pi * radius, self.outline.height))
        base = float(np.pi * radius[0] ** 2)
        return (lateral + base) * thickness * GLASS_DENSITY


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


def revolve(outline: Outline, segments: int = 48) -> tuple[np.ndarray, np.ndarray]:
    """Spin an outline into a mesh: vertices and triangles.

    Written out rather than taken from trimesh so that the shape of a glass
    model is visible in this project rather than in a dependency, and so the
    tests can check it without one.
    """
    angles = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
    rings = len(outline.height)

    vertices = np.empty((rings * segments, 3), dtype=float)
    for ring, (height, radius) in enumerate(zip(outline.height, outline.radius, strict=True)):
        vertices[ring * segments : (ring + 1) * segments] = np.column_stack(
            (radius * np.cos(angles), radius * np.sin(angles), np.full(segments, height))
        )

    faces: list[tuple[int, int, int]] = []
    for ring in range(rings - 1):
        for segment in range(segments):
            nxt = (segment + 1) % segments
            a = ring * segments + segment
            b = ring * segments + nxt
            c = (ring + 1) * segments + segment
            d = (ring + 1) * segments + nxt
            # Wound so the face points away from the axis. A renderer with no
            # normals to go on works them out from this order, and one wound
            # the other way is a glass seen from the inside.
            faces.append((a, d, c))
            faces.append((a, b, d))
    return vertices, np.array(faces, dtype=int)


def write_mesh(outline: Outline, path: Path, segments: int = 48) -> Path:
    """Write one glass as an STL the simulator can load.

    Each facet carries its own normal. Writing zeroes there is legal STL and
    means "work it out from the winding", but it leaves the surface at the
    mercy of whatever the renderer decides, and a glass whose foot does not
    draw is a glass with no waist in it — which is a wine glass the arm will
    try to hold by the bowl.
    """
    vertices, faces = revolve(outline, segments)
    lines = ["solid glass"]
    for a, b, c in faces:
        corners = vertices[[a, b, c]]
        normal = np.cross(corners[1] - corners[0], corners[2] - corners[0])
        length = float(np.linalg.norm(normal))
        if length > 0.0:
            normal = normal / length
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


def collision_cylinders(outline: Outline, slices: int = COLLISION_SLICES) -> list[tuple[float, float, float]]:
    """The collision shape, as a stack of cylinders.

    Each entry is (bottom height, top height, radius). The radius of a slice is
    the largest the glass reaches inside it, so the collision shape is never
    thinner than the glass and the fingers cannot pass through the wall.
    """
    edges = np.linspace(0.0, outline.total_height, slices + 1)
    stack: list[tuple[float, float, float]] = []
    # Pairwise over the edges, so the second list is one shorter on purpose.
    for bottom, top in zip(edges, edges[1:], strict=False):
        inside = (outline.height >= bottom) & (outline.height <= top)
        if not inside.any():
            continue
        stack.append((float(bottom), float(top), float(outline.radius[inside].max())))
    return stack


# A tint per glass, so that a person watching can tell them apart and see
# which one the arm is working on. Nothing reads these: the arm finds a glass
# by the hole it leaves in the depth picture, and that hole comes from the
# label above. They are kept bright enough that a glass never reads as the
# unlit background, and there are more of them than a run ever spawns.
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
    mass = glass.mass
    outline = glass.outline
    radius = float(outline.radius.max())
    height = outline.total_height

    collisions = []
    for index, (bottom, top, slice_radius) in enumerate(collision_cylinders(outline)):
        middle = (bottom + top) / 2.0
        collisions.append(
            f'        <collision name="collision_{index}">\n'
            f"          <pose>0 0 {middle:.4f} 0 0 0</pose>\n"
            f"          <geometry><cylinder>"
            f"<radius>{slice_radius:.4f}</radius><length>{top - bottom:.4f}</length>"
            f"</cylinder></geometry>\n"
            f"          <surface>\n"
            f"            <friction><ode><mu>1.1</mu><mu2>1.1</mu2></ode></friction>\n"
            f"            <contact><ode><kp>5e5</kp><kd>50</kd></ode></contact>\n"
            f"          </surface>\n"
            f"        </collision>"
        )

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
            # A thin-walled tube about its own centre is close enough for a
            # glass, and much closer than a solid cylinder would be.
            ixx=mass * (3.0 * radius**2 + height**2) / 12.0,
            iyy=mass * (3.0 * radius**2 + height**2) / 12.0,
            izz=mass * radius**2 / 2.0,
            collisions="\n".join(collisions),
            mesh_uri=mesh_uri,
            red=tint[0],
            green=tint[1],
            blue=tint[2],
            opacity=1.0 - GLASS_TRANSPARENCY,
            transparency=GLASS_TRANSPARENCY,
        )
    )
