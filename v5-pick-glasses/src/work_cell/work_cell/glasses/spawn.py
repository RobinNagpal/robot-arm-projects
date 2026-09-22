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


def random_glasses(count: int, seed: int, kinds: list[str] | None = None) -> list[SpawnedGlass]:
    """Lay out ``count`` glasses of random kinds and sizes in the glass zone."""
    rng = random.Random(seed)
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
    raise RuntimeError(
        f"could not fit {len(placed) + 1} glasses in the glass zone without them "
        f"crowding each other; try fewer, or widen GLASS_ZONE in rack/layout.py"
    )


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
            faces.append((a, c, d))
            faces.append((a, d, b))
    return vertices, np.array(faces, dtype=int)


def write_mesh(outline: Outline, path: Path, segments: int = 48) -> Path:
    """Write one glass as an STL the simulator can load."""
    vertices, faces = revolve(outline, segments)
    lines = ["solid glass"]
    for a, b, c in faces:
        lines.append("facet normal 0 0 0")
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


# The label the segmentation camera reports glass under. Any value but 0,
# which means "no label"; the camera side reads it from here so the model and
# the reader cannot disagree.
GLASS_LABEL = 10


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
            label=GLASS_LABEL,
        )
    )
