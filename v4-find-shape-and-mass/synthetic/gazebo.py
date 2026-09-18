"""Running Gazebo with no window, and taking one picture of one scene at a time.

The generator talks to the simulator directly over Gazebo's own transport,
not through ROS. It starts the server, then for each picture: removes what
the last scene put on the table, creates the new scene, moves the camera,
sets the lights, and steps the paused world forward until one picture comes
out.

Two things about the simulator shape this file.

A change to the scene does not reach the picture straight away. A service
call returns as soon as Gazebo has queued the change, the change is made on a
later step, and the renderer draws it on the render after that. Taking the
first picture after a change can therefore show the previous scene, with the
new scene's labels written against it. So the world stays paused, and after
each change it is stepped one render at a time until two renders in a row
give the same mask. Only then is the picture kept.

Two more things follow from the queue. It does not keep removals and
creations in the order they were sent, so every scene's models get names no
earlier scene used, and a new model can never be refused as a duplicate of
an old one that is still waiting to be removed. And a call can go unanswered
while the transport is still finding its way to the server, so every call is
retried rather than trusted to arrive the first time.
"""

from __future__ import annotations

import math
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

WORLD = "shapes"
WORLD_FILE = Path(__file__).parent / "world.sdf"


class Gazebo:
    """A headless Gazebo server, and a client that sets scenes and takes pictures in it."""

    def __init__(self, verbose: bool = False):
        # A partition of its own, so a simulator from another project running
        # on the same machine can neither answer these calls nor see these models.
        os.environ["GZ_PARTITION"] = f"v4-shapes-{os.getpid()}"
        self._server = subprocess.Popen(
            ["gz", "sim", "-s", "--headless-rendering", "-v", "2" if verbose else "1", str(WORLD_FILE)],
            start_new_session=True,  # so stopping it also stops the processes it starts
            stdout=None if verbose else subprocess.DEVNULL,
            stderr=None if verbose else subprocess.DEVNULL,
        )
        # Imported only now: the transport reads GZ_PARTITION when it is loaded.
        from gz.msgs10.image_pb2 import Image
        from gz.transport13 import Node

        self._node = Node()
        self._lock = threading.Lock()
        self._latest: dict[str, object] = {}
        self._node.subscribe(Image, "/camera/rgb", self._keeper("rgb"))
        self._node.subscribe(Image, "/camera/segmentation/labels_map", self._keeper("mask"))
        self._last_stamp = -1
        self._on_table: list[str] = []

        self._wait_for_server()
        # The first render after start-up takes much longer than the rest,
        # while the renderer loads. Do it now so it is not a real picture.
        self._render(timeout=60.0)

    def close(self) -> None:
        if self._server.poll() is None:
            os.killpg(self._server.pid, signal.SIGINT)
            try:
                self._server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(self._server.pid, signal.SIGKILL)

    def __enter__(self) -> Gazebo:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # Changing the scene.

    def replace_models(self, models: dict[str, str]) -> None:
        """Remove every model the last call created, then create ``models``, given as SDF strings.

        Each model's name in its SDF must not have been used before in this run.
        """
        from gz.msgs10.entity_factory_pb2 import EntityFactory
        from gz.msgs10.entity_factory_v_pb2 import EntityFactory_V
        from gz.msgs10.entity_pb2 import Entity

        for name in self._on_table:
            self._call("remove", Entity(name=name, type=Entity.MODEL), Entity)
        batch = EntityFactory_V(data=[EntityFactory(sdf=sdf) for sdf in models.values()])
        self._call("create_multiple", batch, EntityFactory_V)
        self._on_table = list(models)

    def move_camera(
        self, position: tuple[float, float, float], roll: float, pitch: float, yaw: float
    ) -> None:
        from gz.msgs10.pose_pb2 import Pose

        pose = Pose(name="camera")
        pose.position.x, pose.position.y, pose.position.z = position
        w, x, y, z = _quaternion(roll, pitch, yaw)
        pose.orientation.w, pose.orientation.x, pose.orientation.y, pose.orientation.z = w, x, y, z
        self._call("set_pose", pose, Pose)

    def set_light(
        self,
        name: str,
        direction: tuple[float, float, float],
        colour: tuple[float, float, float],
        shadows: bool,
    ) -> None:
        from gz.msgs10.light_pb2 import Light

        light = Light(name=name, type=Light.DIRECTIONAL, cast_shadows=shadows)
        # Left at its default of 0 the light is switched off, not full strength.
        light.intensity = 1.0
        light.diffuse.r, light.diffuse.g, light.diffuse.b, light.diffuse.a = *colour, 1.0
        light.specular.r, light.specular.g, light.specular.b, light.specular.a = (
            0.3 * c for c in (*colour, 1.0)
        )
        light.direction.x, light.direction.y, light.direction.z = direction
        self._call("light_config", light, Light)

    # Taking the picture.

    def take_picture(self, max_renders: int = 8) -> tuple[np.ndarray, np.ndarray]:
        """Render until the scene has settled, and return (RGB image, label mask).

        Settled means two renders in a row gave the same mask. The first
        render after a change is never kept, even if it happens to match.
        """
        previous = None
        for _ in range(max_renders):
            rgb, mask = self._render()
            if previous is not None and np.array_equal(mask, previous):
                return rgb, mask
            previous = mask
        raise RuntimeError(f"the scene was still changing after {max_renders} renders")

    def _render(self, timeout: float = 10.0) -> tuple[np.ndarray, np.ndarray]:
        # Ten 10 ms steps pass exactly one of the cameras' 100 ms updates.
        self._step(10)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                rgb, mask = self._latest.get("rgb"), self._latest.get("mask")
            if rgb is not None and mask is not None:
                stamp = _stamp(rgb)
                if stamp == _stamp(mask) and stamp > self._last_stamp:
                    self._last_stamp = stamp
                    return _pixels(rgb), _pixels(mask)[:, :, 0]
            time.sleep(0.002)
        raise TimeoutError(f"the cameras did not produce a new picture within {timeout} s")

    # The plumbing.

    def _keeper(self, key: str):
        def keep(message) -> None:
            with self._lock:
                self._latest[key] = message

        return keep

    def _wait_for_server(self, timeout: float = 60.0) -> None:
        deadline = time.monotonic() + timeout
        wanted = f"/world/{WORLD}/create_multiple"
        while time.monotonic() < deadline:
            if self._server.poll() is not None:
                raise RuntimeError("gz sim exited during start-up; run with --verbose to see why")
            if wanted in self._node.service_list():
                return
            time.sleep(0.2)
        raise TimeoutError(f"gz sim did not offer {wanted} within {timeout} s")

    def _step(self, steps: int) -> None:
        from gz.msgs10.world_control_pb2 import WorldControl

        self._call("control", WorldControl(pause=True, multi_step=steps), WorldControl)

    def _call(self, service: str, request, request_type, attempts: int = 20) -> None:
        from gz.msgs10.boolean_pb2 import Boolean

        for _ in range(attempts):
            answered, reply = self._node.request(
                f"/world/{WORLD}/{service}", request, request_type, Boolean, 2000
            )
            if answered and reply.data:
                return
            time.sleep(0.1)
        raise RuntimeError(f"gz sim did not accept a {service} request after {attempts} attempts")


def _stamp(image) -> int:
    return image.header.stamp.sec * 1_000_000_000 + image.header.stamp.nsec


def _pixels(image) -> np.ndarray:
    return np.frombuffer(image.data, dtype=np.uint8).reshape(image.height, image.width, -1).copy()


def _quaternion(roll: float, pitch: float, yaw: float) -> tuple[float, float, float, float]:
    """w, x, y, z for a turn of roll about x, then pitch about y, then yaw about z, all about fixed axes."""
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    )
