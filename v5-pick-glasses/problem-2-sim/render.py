"""The scenes, and depth pictures of them, without Gazebo.

Shared by problem-2-learned and problem-2-programmed, so the two are tested
on exactly the same tables and the same pictures.

The wrist camera's lens and size, the project's own glass shapes and the
project's own layout. What Gazebo would add is a slower picture of the same
thing, so for training and scoring a few hundred scenes this draws them here.

Every picture comes with an id image: which glass each pixel shows. That is
the label a learned model trains on, and the arm is never given it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from work_cell.arm.dimensions import MEASURE_FRAME_MARGIN, MEASURE_STANDOFF, MEASURE_VIEW_HEIGHT
from work_cell.glasses.perception import Intrinsics
from work_cell.glasses.spawn import random_glasses
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE, TABLE_TOP_Z

# The wrist camera, as arm/camera/wrist_camera.urdf.xacro declares it.
WIDTH, HEIGHT = 320, 240
HORIZONTAL_FOV = 1.047
FOCAL = (WIDTH / 2.0) / math.tan(HORIZONTAL_FOV / 2.0)
LENS = Intrinsics(fx=FOCAL, fy=FOCAL, cx=WIDTH / 2.0, cy=HEIGHT / 2.0)

# The tallest glass the cell handles, as task.py has it. Only used to work out
# the side standoff the same way the task does.
TALLEST_GLASS = 0.26

# How far back the side pictures are taken from, worked out as task.py does:
# the tallest glass, aimed at MEASURE_VIEW_HEIGHT, filling the frame with margin.
_half_frame = (HEIGHT / 2.0) / LENS.fy
STANDOFF = max(
    MEASURE_STANDOFF,
    max(MEASURE_VIEW_HEIGHT, TALLEST_GLASS - MEASURE_VIEW_HEIGHT) / (_half_frame * MEASURE_FRAME_MARGIN),
)

# The one overhead picture: above the middle of the glass zone, high enough
# that the rim of a tall glass at the zone's edge is still in shot. Rims lean
# outwards in a picture from above, so 0.55 cut them off. The real task takes
# several pictures from lower down instead; one is simpler to learn from.
TOP_HEIGHT = 0.75

# Surface points are laid this far apart. Under a pixel's width at the
# nearest the camera ever gets, so the drawn surface has no holes.
POINT_SPACING = 0.0007


@dataclass(frozen=True)
class Glass:
    """One glass as the simulator knows it. The arm never sees this."""

    kind: str
    x: float
    y: float
    height: np.ndarray  # outline heights, metres
    radius: np.ndarray  # outline radii, metres

    @property
    def total_height(self) -> float:
        return float(self.height[-1])

    @property
    def max_radius(self) -> float:
        return float(self.radius.max())


@dataclass(frozen=True)
class Picture:
    depth: np.ndarray  # metres along the view axis; inf where nothing was hit
    ids: np.ndarray  # 0 for table or nothing, i + 1 for glass i
    camera_to_world: np.ndarray


KINDS = ("straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass")

# Scenes from here on are for testing. Training draws only below it, so no
# test scene is ever trained on.
TEST_SEEDS = 10_000


def scene(seed: int) -> list[Glass]:
    """Problem 2's table number ``seed``: four to six glasses of one kind.

    150 mm apart or more. Six do not always fit in the zone; then five.
    """
    kind, count = KINDS[seed % len(KINDS)], 4 + seed % 3
    try:
        spawned = random_glasses(count, seed, [kind])
    except RuntimeError:
        spawned = random_glasses(count - 1, seed, [kind])
    return [Glass(kind, g.position[0], g.position[1], g.outline.height, g.outline.radius) for g in spawned]


def look_at(eye: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Camera-to-world transform, optical frame: x right, y down, z forwards.

    Up in the picture is up in the room for a level camera, and away from the
    arm's base for one looking straight down.
    """
    forward = target - eye
    forward = forward / np.linalg.norm(forward)
    hint = np.array([1.0, 0.0, 0.0]) if abs(forward[2]) > 0.99 else np.array([0.0, 0.0, 1.0])
    down = -(hint - hint.dot(forward) * forward)
    down /= np.linalg.norm(down)
    right = np.cross(down, forward)
    pose = np.eye(4)
    pose[:3, 0], pose[:3, 1], pose[:3, 2], pose[:3, 3] = right, down, forward, eye
    return pose


def top_pose() -> np.ndarray:
    x_min, x_max, y_min, y_max = GLASS_ZONE
    middle = np.array([(x_min + x_max) / 2.0, (y_min + y_max) / 2.0, TABLE_TOP_Z])
    return look_at(middle + [0.0, 0.0, TOP_HEIGHT], middle)


def side_pose(x: float, y: float, angle: float) -> np.ndarray:
    """Level camera STANDOFF back from (x, y), on the side ``angle`` points to."""
    aim = np.array([x, y, TABLE_TOP_Z + MEASURE_VIEW_HEIGHT])
    eye = aim + STANDOFF * np.array([math.cos(angle), math.sin(angle), 0.0])
    return look_at(eye, aim)


def _surface(glass: Glass) -> np.ndarray:
    """Points over the outside of one glass and a lid across its rim, in the world.

    Opaque, as the problem statement assumes, so the lid stands in for the
    inside: from above both are simply something standing on the table.
    """
    total = glass.total_height
    # Spaced along the outline, not up it: a foot is nearly flat, so equal
    # steps in height leave gaps across it.
    along = np.concatenate(([0.0], np.cumsum(np.hypot(np.diff(glass.height), np.diff(glass.radius)))))
    steps = np.linspace(0.0, along[-1], max(3, int(along[-1] / POINT_SPACING)))
    heights = np.interp(steps, along, glass.height)
    radii = np.interp(steps, along, glass.radius)
    turns = max(24, int(2 * math.pi * glass.max_radius / POINT_SPACING))
    angles = np.linspace(0.0, 2 * math.pi, turns, endpoint=False)
    h, a = np.meshgrid(heights, angles, indexing="ij")
    r = np.broadcast_to(radii[:, None], h.shape)
    wall = np.stack([r * np.cos(a), r * np.sin(a), h], axis=-1).reshape(-1, 3)

    rim = float(glass.radius[-1])
    ring = np.arange(0.0, rim, POINT_SPACING)
    lid = [
        np.stack([rr * np.cos(aa), rr * np.sin(aa), np.full_like(aa, total)], axis=-1)
        for rr in ring
        for aa in [np.linspace(0.0, 2 * math.pi, max(6, int(2 * math.pi * rr / POINT_SPACING)))]
    ]
    points = np.concatenate([wall, *lid])
    return points + [glass.x, glass.y, TABLE_TOP_Z]


def _rays(pose: np.ndarray) -> np.ndarray:
    """World direction of each pixel's ray, scaled so its camera z is 1."""
    rows, columns = np.indices((HEIGHT, WIDTH))
    local = np.stack(
        [(columns - LENS.cx) / LENS.fx, (rows - LENS.cy) / LENS.fy, np.ones((HEIGHT, WIDTH))], axis=-1
    )
    return local @ pose[:3, :3].T


def render(glasses: list[Glass], pose: np.ndarray) -> Picture:
    """What the wrist camera at ``pose`` would see."""
    eye = pose[:3, 3]

    # The table: where each ray meets the plane, if it meets the table there.
    rays = _rays(pose)
    with np.errstate(divide="ignore", invalid="ignore"):
        along = (TABLE_TOP_Z - eye[2]) / rays[..., 2]
        hit = eye + rays * along[..., None]
    on_table = (
        (along > 0)
        & (np.abs(hit[..., 0] - TABLE_CENTRE_XY[0]) <= TABLE_SIZE[0] / 2)
        & (np.abs(hit[..., 1] - TABLE_CENTRE_XY[1]) <= TABLE_SIZE[1] / 2)
    )
    depth = np.where(on_table, along, np.inf)
    ids = np.zeros((HEIGHT, WIDTH), dtype=np.int32)

    # Each glass: its surface points, nearest one per pixel.
    for index, glass in enumerate(glasses):
        local = (_surface(glass) - eye) @ pose[:3, :3]
        local = local[local[:, 2] > 0.05]
        column = np.round(LENS.fx * local[:, 0] / local[:, 2] + LENS.cx).astype(int)
        row = np.round(LENS.fy * local[:, 1] / local[:, 2] + LENS.cy).astype(int)
        # Close to the camera, neighbouring points land several pixels apart,
        # so each is drawn as a square that wide. Otherwise a near glass comes
        # out full of holes, and what is behind it shows through.
        size = np.ceil(POINT_SPACING * LENS.fx / local[:, 2]).astype(int)
        mine = np.full((HEIGHT, WIDTH), np.inf)
        for side in np.unique(size):
            these = size == side
            for down in range(side):
                for across in range(side):
                    r, c = row[these] + down - side // 2, column[these] + across - side // 2
                    keep = (c >= 0) & (c < WIDTH) & (r >= 0) & (r < HEIGHT)
                    np.minimum.at(mine, (r[keep], c[keep]), local[these][keep, 2])
        closer = mine < depth
        depth[closer] = mine[closer]
        ids[closer] = index + 1

    return Picture(depth, ids, pose)


def project(pose: np.ndarray, point: np.ndarray) -> tuple[float, float]:
    """Pixel (column, row) a world point lands on."""
    local = (np.asarray(point) - pose[:3, 3]) @ pose[:3, :3]
    return LENS.fx * local[0] / local[2] + LENS.cx, LENS.fy * local[1] / local[2] + LENS.cy


def to_world(picture: Picture, rows: np.ndarray, columns: np.ndarray) -> np.ndarray:
    """World points for the given pixels, from their depth readings."""
    z = picture.depth[rows, columns]
    local = np.stack([(columns - LENS.cx) / LENS.fx * z, (rows - LENS.cy) / LENS.fy * z, z], axis=-1)
    return local @ picture.camera_to_world[:3, :3].T + picture.camera_to_world[:3, 3]
