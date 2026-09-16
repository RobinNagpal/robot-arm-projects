"""Turning numpy poses into ROS messages and back."""

from __future__ import annotations

import numpy as np
from geometry_msgs.msg import Pose, Quaternion

from .transforms import matrix_to_quaternion, quaternion_to_matrix


def make_pose(position: np.ndarray, rotation: np.ndarray) -> Pose:
    """geometry_msgs/Pose from a 3-vector and a 3x3 rotation."""
    pose = Pose()
    pose.position.x, pose.position.y, pose.position.z = (float(v) for v in position)
    x, y, z, w = matrix_to_quaternion(rotation)
    pose.orientation = Quaternion(x=x, y=y, z=z, w=w)
    return pose


def pose_to_matrix(pose: Pose) -> np.ndarray:
    """4x4 matrix for a geometry_msgs/Pose."""
    matrix = np.eye(4)
    q = pose.orientation
    matrix[:3, :3] = quaternion_to_matrix(q.x, q.y, q.z, q.w)
    matrix[:3, 3] = (pose.position.x, pose.position.y, pose.position.z)
    return matrix


def transform_to_matrix(transform) -> np.ndarray:
    """4x4 matrix for a geometry_msgs/Transform."""
    matrix = np.eye(4)
    rotation = transform.rotation
    matrix[:3, :3] = quaternion_to_matrix(rotation.x, rotation.y, rotation.z, rotation.w)
    matrix[:3, 3] = (transform.translation.x, transform.translation.y, transform.translation.z)
    return matrix
