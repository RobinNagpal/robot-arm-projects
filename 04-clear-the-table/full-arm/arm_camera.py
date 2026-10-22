"""The camera on the arm's wrist, moved off the hand's axis.

Problem 4 mounts its camera on a bracket directly above the hand. On the real
UR5e that spot is where the wrist is, and the hand points along the line the
camera looks down, so in the picture the arm and the hand fill the middle and the
glasses are behind them. The mounting here is the one change the full arm forces
on the camera: it sits to one side of the hand and a little above it, and is
turned to look at the patch of table ahead of the fingertips, so the hand is at
the edge of the picture and not in the way.

Everything else about the camera is problem 4's: the frame size, the angle of
view, and the rule for which glasses count as seen. The module replaces
``wrist.camera_pose`` with this mounting, so ``wrist.in_picture`` and the
renderer both use it and cannot disagree.
"""

from __future__ import annotations

import math

import numpy as np
from work_cell.table.layout import TABLE_TOP_Z

import wrist

BACK = 0.10  # behind the fingertips
UP = 0.22  # above the middle of the hand
SIDE = 0.12  # to the left of the pushing direction
AIM = 0.25  # the camera looks at the table this far ahead of the fingertips


def camera_pose(jaw) -> tuple[np.ndarray, np.ndarray]:
    ahead = np.array([math.cos(jaw.heading), math.sin(jaw.heading), 0.0])
    left = np.array([-ahead[1], ahead[0], 0.0])
    tip = np.array([jaw.x, jaw.y, TABLE_TOP_Z + jaw.z])
    eye = tip - BACK * ahead + SIDE * left + np.array([0.0, 0.0, UP])
    aim = np.array([jaw.x, jaw.y, TABLE_TOP_Z]) + AIM * ahead
    forward = aim - eye
    return eye, forward / np.linalg.norm(forward)


class ArmCamera(wrist.WristCamera):
    """Problem 4's renderer, pointed by this mounting instead of the bracket's."""

    def _point(self, jaw) -> None:
        eye, forward = camera_pose(jaw)
        if eye[2] <= TABLE_TOP_Z:
            raise ValueError("the camera is below the table top")
        self.camera.lookat[:] = eye + forward
        self.camera.distance = 1.0
        self.camera.azimuth = math.degrees(math.atan2(forward[1], forward[0]))
        self.camera.elevation = math.degrees(math.asin(forward[2]))


wrist.camera_pose = camera_pose
