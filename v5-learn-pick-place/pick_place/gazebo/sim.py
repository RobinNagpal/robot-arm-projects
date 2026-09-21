"""Starting Gazebo, stepping it, and reading and commanding the arm, over Gazebo's own transport.

The world stays paused. Each control step, the new joint targets are
published, then the world is told to advance by exactly one control period,
and the step is over when joint states stamped with the new time come back.
So the loop runs in lockstep with the simulation, as the MuJoCo one does,
however fast or slow the computer is.

A newly advertised topic takes a moment before anyone receives what is
published on it, so the controllers' topics are advertised, then given time,
before the first command.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

from ..scene import ARM_JOINTS
from .models import ARM, FINGER_JOINTS, WORLD

# If simulated time has not moved this long after a step request, the
# request is taken as lost and sent again.
RESEND_AFTER = 3.0


class GazeboSim:
    def __init__(self, world_file: Path, gui: bool = False, verbose: bool = False):
        # A partition of its own, so a simulator from another project on the
        # same machine can neither answer these calls nor see these models.
        os.environ["GZ_PARTITION"] = f"v5-pick-place-{os.getpid()}"
        quiet = {} if verbose else {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        self._processes = [
            subprocess.Popen(
                ["gz", "sim", "-s", "--headless-rendering", "-v", "3" if verbose else "1", str(world_file)],
                start_new_session=True,
                **quiet,
            )
        ]
        if gui:
            # On macOS the window has to be its own process; it finds the
            # server through the shared partition.
            self._processes.append(
                subprocess.Popen(["gz", "sim", "-g", "-v", "1"], start_new_session=True, **quiet)
            )

        # Imported only now: the transport reads GZ_PARTITION when it loads.
        from gz.msgs10.double_pb2 import Double
        from gz.msgs10.image_pb2 import Image
        from gz.msgs10.model_pb2 import Model
        from gz.msgs10.pose_pb2 import Pose
        from gz.msgs10.world_stats_pb2 import WorldStatistics
        from gz.transport13 import Node

        self._Double = Double
        self._node = Node()
        self._lock = threading.Lock()
        self._latest: dict[str, object] = {}
        self._node.subscribe(Model, f"/world/{WORLD}/model/{ARM}/joint_state", self._keeper("joints"))
        self._node.subscribe(Image, "/overhead/depth", self._keeper("depth"))
        self._node.subscribe(Pose, "/model/block/pose", self._keeper("block"))
        self._node.subscribe(WorldStatistics, f"/world/{WORLD}/stats", self._keeper("stats"))
        self._publishers = {
            joint: self._node.advertise(f"/{ARM}/{joint}/command", Double)
            for joint in (*ARM_JOINTS, *FINGER_JOINTS)
        }
        self.time = 0.0
        self._wait_for_server()
        # Let every subscriber find the command topics before anything is sent.
        time.sleep(1.0)

    def close(self) -> None:
        for process in self._processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
        for process in self._processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)

    def __enter__(self) -> GazeboSim:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # Commanding and stepping.

    def command(self, arm: np.ndarray, finger_travel: float) -> None:
        """Joint angle targets for the six arm joints, and how far each finger closes, in metres."""
        for joint, value in zip(ARM_JOINTS, arm, strict=True):
            self._publishers[joint].publish(self._Double(data=float(value)))
        for joint in FINGER_JOINTS:
            self._publishers[joint].publish(self._Double(data=float(finger_travel)))

    def step(self, seconds: float, timeout: float = 60.0) -> None:
        """Advance the world by ``seconds`` of simulated time, and wait until it has.

        The step request is sent without waiting for Gazebo's reply. With
        cameras in the world, Gazebo carries out every step request but loses
        some of its replies, and a caller waiting for one would wait forever,
        or, retrying, step the world twice. So the joint states' timestamps say
        when the step is done, and only if time has not moved for a while is
        the rest of the step asked for again.
        """
        target = self.time + seconds
        # Give the commands just published a moment to arrive before the
        # world moves on; the transport delivers them on its own thread.
        time.sleep(0.002)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._request_steps(round((target - self._now()) / self.physics_step))
            resend = time.monotonic() + RESEND_AFTER
            while time.monotonic() < resend:
                if self._now() >= target - 1e-6:
                    self.time = self._now()
                    return
                time.sleep(0.0005)
        raise TimeoutError(f"Gazebo did not reach t = {target:.3f} s within {timeout} s")

    def _now(self) -> float:
        joints = self._get("joints")
        return stamp(joints) if joints is not None else 0.0

    def _request_steps(self, steps: int) -> None:
        from gz.msgs10.boolean_pb2 import Boolean
        from gz.msgs10.world_control_pb2 import WorldControl

        if steps > 0:
            # A short wait for the reply that is not relied on: the request
            # itself goes out at once.
            self._node.request(
                f"/world/{WORLD}/control",
                WorldControl(pause=True, multi_step=steps),
                WorldControl,
                Boolean,
                5,
            )

    physics_step = 0.001

    # Reading.

    def joints(self) -> dict[str, float]:
        message = self._get("joints")
        return {j.name: j.axis1.position for j in message.joint}

    def block_pose(self) -> tuple[np.ndarray, np.ndarray]:
        """The block's position, and its orientation as a w, x, y, z quaternion."""
        pose = self._get("block")
        p, q = pose.position, pose.orientation
        return np.array([p.x, p.y, p.z]), np.array([q.w, q.x, q.y, q.z])

    def depth_picture(self, after: float, timeout: float = 30.0) -> np.ndarray:
        """The first depth picture taken at or after simulated time ``after``, stepping until there is one."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            image = self._get("depth")
            if image is not None and stamp(image) >= after - 1e-6:
                depth = np.frombuffer(image.data, dtype=np.float32).reshape(image.height, image.width)
                return depth.astype(np.float64)
            self.step(0.05)
        raise TimeoutError("the depth camera sent no picture")

    # The plumbing.

    def _keeper(self, key: str):
        def keep(message) -> None:
            with self._lock:
                self._latest[key] = message

        return keep

    def _get(self, key: str):
        with self._lock:
            return self._latest.get(key)

    def _wait_for_server(self, timeout: float = 180.0) -> None:
        """Wait until the world is loaded and running its loop, which it reports by sending statistics.

        Its services answer earlier, while it is still loading, but a request
        to step then goes unanswered. Loading takes 30 to 40 s.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._processes[0].poll() is not None:
                raise RuntimeError("gz sim exited during start-up; run with --verbose to see why")
            if self._get("stats") is not None:
                return
            time.sleep(0.2)
        raise TimeoutError(f"gz sim did not finish loading the world within {timeout} s")


def stamp(message) -> float:
    s = message.header.stamp
    return s.sec + s.nsec * 1e-9
