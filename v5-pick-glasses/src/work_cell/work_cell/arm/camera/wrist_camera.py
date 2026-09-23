"""The camera bolted to the wrist.

The camera moves with the arm, so a frame is only useful together with the
pose the arm was holding when it was taken. This class hands both back at
once: the images, the intrinsics, and the 4x4 transform that puts a pixel in
the world frame.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image
from tf2_ros import Buffer, TransformListener

from ...glasses.perception import Intrinsics
from ...rack.layout import MARKER_DICTIONARY, MARKER_ID
from ...table.layout import WORLD_FRAME
from ...transforms import transform_to_matrix

# The marker is the rack's, not the camera's, so which marker it is lives in
# rack/layout.py next to the rest of the rack. Importing it here is what stops
# the camera hunting for a square the rack does not carry.


@dataclass(frozen=True)
class View:
    """One RGB-D frame and where the camera was when it was taken."""

    rgb: np.ndarray
    depth: np.ndarray
    intrinsics: Intrinsics
    camera_to_world: np.ndarray

    def to_world(self, column: float, row: float, z: float) -> np.ndarray:
        """Where a pixel meets the horizontal plane at height ``z``.

        A pixel on its own is a ray, not a point: everything along it looks the
        same. Saying which height the thing is at picks one point off that ray,
        and here that height is the table top, which is known.

        This is the only way to place a glass from above, because a depth
        camera returns nothing where a glass is. The plane does the job the
        missing depth reading would have done.
        """
        # The ray, in the camera's own frame: x right, y down, z forwards.
        direction = np.array(
            [
                (column - self.intrinsics.cx) / self.intrinsics.fx,
                (row - self.intrinsics.cy) / self.intrinsics.fy,
                1.0,
            ]
        )
        eye = self.camera_to_world[:3, 3]
        ray = self.camera_to_world[:3, :3] @ direction

        if abs(ray[2]) < 1e-9:
            raise ValueError("this pixel looks along the plane, so it never meets it")
        return eye + ray * ((z - eye[2]) / ray[2])


@dataclass(frozen=True)
class Marker:
    """The marker on the rack base: where it is and which way it faces."""

    position: np.ndarray
    yaw: float


class CaptureTimeout(RuntimeError):
    """Raised when the camera did not deliver a frame in time."""


class WristCamera:
    def __init__(
        self,
        node: Node,
        *,
        image_topic: str = "/wrist_camera/image",
        depth_topic: str = "/wrist_camera/depth_image",
        info_topic: str = "/wrist_camera/camera_info",
        optical_frame: str = "wrist_camera_optical_frame",
    ) -> None:
        self._node = node
        self._optical_frame = optical_frame
        self._bridge = CvBridge()
        self._lock = threading.Lock()
        self._rgb: Image | None = None
        self._depth: Image | None = None
        self._info: CameraInfo | None = None
        self._counts = {"rgb": 0, "depth": 0, "info": 0}

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, node)

        # Its own callback group, so that a multi-threaded executor can deliver
        # camera frames on one thread while another is busy with the simulated
        # clock, which ticks far more often than the camera does.
        group = MutuallyExclusiveCallbackGroup()
        sensor = qos_profile_sensor_data
        node.create_subscription(Image, image_topic, self._on_rgb, sensor, callback_group=group)
        node.create_subscription(Image, depth_topic, self._on_depth, sensor, callback_group=group)
        node.create_subscription(CameraInfo, info_topic, self._on_info, sensor, callback_group=group)

    def _on_rgb(self, msg: Image) -> None:
        with self._lock:
            self._rgb = msg
            self._counts["rgb"] += 1

    def _on_depth(self, msg: Image) -> None:
        with self._lock:
            self._depth = msg
            self._counts["depth"] += 1

    def _on_info(self, msg: CameraInfo) -> None:
        with self._lock:
            self._info = msg
            self._counts["info"] += 1

    def wait_until_ready(self, timeout: float = 120.0) -> None:
        """Block until the first frames and the intrinsics have arrived.

        The camera only starts publishing once Gazebo has the sensor running,
        which is later than the rest of the cell comes up.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                ready = self._rgb is not None and self._depth is not None and self._info is not None
            if ready:
                return
            time.sleep(0.05)

        raise CaptureTimeout(f"no camera frames within {timeout:.0f}s (messages so far: {self._counts})")

    def capture(self, timeout: float = 10.0) -> View:
        """Take a fresh frame.

        Frames already in hand are thrown away first. The arm is standing
        still whenever this is called, so waiting for the next pair of images
        is enough to be sure they show the pose the arm is in now.
        """
        with self._lock:
            self._rgb = None
            self._depth = None

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                rgb, depth, info = self._rgb, self._depth, self._info
            if rgb is not None and depth is not None and info is not None:
                return self._build_view(rgb, depth, info)
            time.sleep(0.02)

        raise CaptureTimeout(f"no RGB-D frame within {timeout:.0f}s (messages so far: {self._counts})")

    def capture_marker(self, table_z: float, timeout: float = 10.0) -> Marker | None:
        """Find the rack, by reading the marker printed on its base.

        The rack is one object whose shape never changes, so a single reading
        of this marker places all six slots. It is read from a picture rather
        than written down because the rack is put on the table by hand and is
        never in quite the same place twice.

        Returns None when the marker is not in shot, which is a real answer:
        there is then nowhere to put anything, and the run should say so rather
        than guess.
        """
        view = self.capture(timeout)
        grey = cv2.cvtColor(view.rgb, cv2.COLOR_RGB2GRAY)
        detector = cv2.aruco.ArucoDetector(
            cv2.aruco.getPredefinedDictionary(MARKER_DICTIONARY),
            cv2.aruco.DetectorParameters(),
        )
        corners, ids, _ = detector.detectMarkers(grey)
        if ids is None or MARKER_ID not in ids.flatten().tolist():
            return None

        square = corners[ids.flatten().tolist().index(MARKER_ID)].reshape(4, 2)

        # The marker lies flat on the rack base, so its corners are all at a
        # known height and the plane does the work a pose estimate would.
        # Estimating the full 6-DOF pose of a 40 mm square from one camera is
        # famously twitchy about which way it is tilted; here it cannot be
        # tilted at all, so that failure mode is designed out rather than
        # filtered out.
        world = np.array([view.to_world(x, y, table_z) for x, y in square])

        along = (world[1] - world[0]) + (world[2] - world[3])
        return Marker(position=world.mean(axis=0), yaw=float(np.arctan2(along[1], along[0])))

    def _build_view(self, rgb: Image, depth: Image, info: CameraInfo) -> View:
        transform = self._tf_buffer.lookup_transform(
            WORLD_FRAME,
            self._optical_frame,
            rclpy.time.Time(),
            timeout=Duration(seconds=2.0),
        )
        return View(
            rgb=self._bridge.imgmsg_to_cv2(rgb, desired_encoding="rgb8"),
            depth=np.asarray(
                self._bridge.imgmsg_to_cv2(depth, desired_encoding="32FC1"), dtype=float
            ),
            intrinsics=Intrinsics.from_camera_info(info),
            camera_to_world=transform_to_matrix(transform.transform),
        )

