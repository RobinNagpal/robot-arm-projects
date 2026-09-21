"""Find the block from the overhead depth camera, with geometry alone.

The same idea as v1: every depth pixel is turned back into a point in the
room through the camera's lens model. Points standing above the table are the
block. Of those, the ones at the block's full height are its top face, and
the top face seen from straight above is the block's outline. The centre of
mass follows from the outline, since the block is one solid material.

No model is trained here. The only inputs are the depth picture, where the
camera is, and its field of view.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import mujoco
import numpy as np

from .settings import BLOCK, CAMERA, PICK_ZONE
from .shapes import Grasp, Point, area, best_grasp, canonical_phi, centroid

# Anything this far above the table is part of a block. The table is flat,
# so the only thing that stands out of it is noise in the depth picture.
ABOVE_TABLE = 0.005
# Points within this distance of the block's full height are its top face.
TOP_FACE_BAND = 0.004
# How far outside the pick zone a block's corner can reach, metres.
ZONE_MARGIN = 0.07
# The hull of the top face's pixels has a corner every few pixels along each
# side. Merging corners that stray less than this from a straight line gives
# back the block's real sides, which the grasp is planned on. A pixel covers
# about 1.7 mm of table.
STRAIGHT_SIDE_TOLERANCE = 0.0015


@dataclass(frozen=True)
class Located:
    outline: list[Point]  # corners in world x, y, metres, around the centre of mass
    x: float  # centre of mass
    y: float
    thickness: float
    grasp: Grasp  # in world coordinates, phi already in (-pi/2, pi/2]


def depth_to_points(depth: np.ndarray, cam_pos: np.ndarray, cam_mat: np.ndarray, fovy: float) -> np.ndarray:
    """Each pixel's point in the room, as an (h, w, 3) array.

    A MuJoCo camera looks along its own -z, with x to the right of the
    picture and y up it. ``depth`` is the distance along that -z.
    """
    h, w = depth.shape
    f = (h / 2) / math.tan(math.radians(fovy) / 2)
    u = np.arange(w) + 0.5 - w / 2
    v = np.arange(h) + 0.5 - h / 2
    uu, vv = np.meshgrid(u, v)
    local = np.stack([uu / f * depth, -vv / f * depth, -depth], axis=-1)
    return local @ cam_mat.T + cam_pos


def locate_block(points: np.ndarray) -> Located:
    """The block standing in the pick zone, from the room points of one depth picture."""
    x, y, z = points[..., 0], points[..., 1], points[..., 2]
    in_zone = (
        (x > PICK_ZONE.x[0] - ZONE_MARGIN)
        & (x < PICK_ZONE.x[1] + ZONE_MARGIN)
        & (y > PICK_ZONE.y[0] - ZONE_MARGIN)
        & (y < PICK_ZONE.y[1] + ZONE_MARGIN)
    )
    mask = (in_zone & (z > ABOVE_TABLE)).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count < 2:
        raise LookupError("no block in the pick zone")
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    heights = z[labels == biggest]
    # The top face covers most of the block's pixels from above; the sides
    # show only near the edge of the picture. A high percentile is the top.
    thickness = float(np.percentile(heights, 90))
    top = (labels == biggest) & (z > thickness - TOP_FACE_BAND)
    xy = np.stack([x[top], y[top]], axis=-1).astype(np.float32)
    hull = cv2.convexHull(xy)
    hull = cv2.approxPolyDP(hull, STRAIGHT_SIDE_TOLERANCE, closed=True).reshape(-1, 2)
    outline_world = [(float(px), float(py)) for px, py in hull]
    # The shapes code wants corners anticlockwise.
    if area(outline_world) < 0:
        outline_world.reverse()
    cx, cy = centroid(outline_world)
    outline = [(px - cx, py - cy) for px, py in outline_world]
    grasp = best_grasp(outline, BLOCK.min_grip_width - 0.005, BLOCK.max_grip_width + 0.005)
    if grasp is None:
        raise LookupError("the block has no grasp that fits the gripper")
    world_grasp = Grasp(x=cx + grasp.x, y=cy + grasp.y, phi=canonical_phi(grasp.phi), width=grasp.width)
    return Located(outline=outline, x=cx, y=cy, thickness=thickness, grasp=world_grasp)


class OverheadDepth:
    """Renders the overhead camera's depth picture and turns it into room points."""

    def __init__(self, model: mujoco.MjModel):
        self.renderer = mujoco.Renderer(model, CAMERA.height, CAMERA.width)
        self.renderer.enable_depth_rendering()
        self.camera = model.camera("overhead").id

    def points(self, data: mujoco.MjData) -> np.ndarray:
        self.renderer.update_scene(data, self.camera)
        depth = self.renderer.render()
        return depth_to_points(
            depth, data.cam_xpos[self.camera], data.cam_xmat[self.camera].reshape(3, 3), CAMERA.fovy
        )

    def close(self) -> None:
        self.renderer.close()
