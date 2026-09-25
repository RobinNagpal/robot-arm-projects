"""Film a table being cleared, to check by eye what the jaw did.

A Bench that also records a video. It changes nothing about the physics: it
only looks at the world after each step. Written the way
v5-learn-pick-place/pick_place/video.py films an episode, with MuJoCo's
offscreen renderer, so it needs no window and no mjpython.

Used by both approaches' run.py, with ``--film N`` to film the first N tables.

A take is shown, not just done. The bench racks a glass by moving it off the
table in one instant, which on film looks like the glass vanishing. So before
each take the film shows the jaw coming to the glass, lifting it and carrying
it off towards the rack. That is drawn on a copy of the world and never
stepped, so the physics, and every result, are the same filmed or not.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path

import cv2
import mujoco
import numpy as np
from work_cell.rack.layout import GLASS_ZONE, RACK_AREA
from work_cell.table.layout import TABLE_TOP_Z

from bench import KINDS, PUSH_HEIGHT, TIMESTEP, TRAVEL_HEIGHT, Bench, Push

WIDTH, HEIGHT = 640, 480
FPS = 30
# The film runs this many times faster than the physics. The jaw feels
# forward at 10 mm/s, which is slow to watch.
SPEED = 3
# The last picture is held this long, with the outcome on it.
HOLD = 2.0

# Where the jaw waits between moves, as bench.py parks it.
PARK = np.array([0.0, 0.5, 1.3])
# How long each part of a take lasts on film, seconds.
TAKE_MOVES = {"to the glass": 0.5, "down": 0.3, "in": 0.3, "lift": 0.4, "to the rack": 0.6}
# How high a taken glass is lifted before it is carried off.
LIFT = 0.25


class FilmedBench(Bench):
    def __init__(self, seed: int, approach: str = "") -> None:
        self.renderer = None
        super().__init__(seed)
        self.renderer = mujoco.Renderer(self.model, HEIGHT, WIDTH)
        # From the arm's side of the table, looking steeply down at the glass
        # zone, so the gaps between glasses show.
        self.camera = mujoco.MjvCamera()
        x_min, x_max, y_min, y_max = GLASS_ZONE
        self.camera.lookat[:] = [(x_min + x_max) / 2, (y_min + y_max) / 2, TABLE_TOP_Z + 0.05]
        self.camera.distance = 0.9
        self.camera.azimuth = 0
        self.camera.elevation = -55
        self.every = max(1, round(SPEED / (FPS * TIMESTEP)))
        self.steps = 0
        self.label = f"{approach}  table {seed}  {KINDS[seed % len(KINDS)].replace('_', ' ')}".strip()
        self.doing = "first look"
        self.frames: list[np.ndarray] = []
        self._capture()

    def push(self, push: Push):
        self.doing = f"push {len(self.records) + 1}: glass {push.glass}, {1000 * push.travel:.0f} mm"
        return super().push(push)

    def take(self, glass: int) -> None:
        self.doing = f"take glass {glass}"
        self._show_take(glass)
        super().take(glass)

    def _show_take(self, glass: int) -> None:
        """The jaw comes in from the arm's side, lifts the glass and carries it off.

        Drawn on a copy of the world: nothing here moves the real one.
        """
        world = copy.copy(self.data)
        x, y = self.position(glass)
        heading = math.atan2(y, x)
        along = np.array([math.cos(heading), math.sin(heading), 0.0])
        world.mocap_quat[0] = [math.cos(heading / 2), 0.0, 0.0, math.sin(heading / 2)]
        address = self.model.jnt_qposadr[self.model.body_jntadr[self.bodies[glass]]]
        glass_start = world.qpos[address : address + 3].copy()

        # The fingertips end up at the glass's middle, at the height the
        # gripper holds a glass. The jaw drawn is closed; problem 1's open
        # fingers would close round the glass here.
        hold = np.array([x, y, glass_start[2] + PUSH_HEIGHT])
        behind = hold - 0.06 * along
        above = np.array([*behind[:2], glass_start[2] + TRAVEL_HEIGHT])
        lifted = hold + [0.0, 0.0, LIFT]
        rack = np.array([(RACK_AREA[0] + RACK_AREA[1]) / 2, (RACK_AREA[2] + RACK_AREA[3]) / 2, lifted[2]])
        path = [
            (PARK, above, "to the glass", False),
            (above, behind, "down", False),
            (behind, hold, "in", False),
            (hold, lifted, "lift", True),
            (lifted, rack, "to the rack", True),
        ]
        for start, end, move, carrying in path:
            frames = max(1, round(TAKE_MOVES[move] * FPS))
            for k in range(1, frames + 1):
                tip = start + (end - start) * (k / frames)
                world.mocap_pos[0] = tip
                if carrying:
                    world.qpos[address : address + 3] = glass_start + (tip - hold)
                mujoco.mj_forward(self.model, world)
                self._capture(data=world)

    def _step(self) -> None:
        super()._step()
        if self.renderer is None:
            return
        self.steps += 1
        if self.steps % self.every == 0:
            self._capture()

    def _capture(self, extra: str = "", data: mujoco.MjData | None = None) -> None:
        self.renderer.update_scene(self.data if data is None else data, self.camera)
        frame = self.renderer.render()[:, :, ::-1].copy()
        for row, text in enumerate([self.label, extra or self.doing]):
            cv2.putText(
                frame, text, (12, 28 + 28 * row), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA
            )
        self.frames.append(frame)

    def save(self, path: Path, outcome: str = "") -> None:
        """Write the video, holding the last picture with ``outcome`` on it."""
        for _ in range(int(HOLD * FPS)):
            self._capture(outcome)
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
        for frame in self.frames:
            writer.write(frame)
        writer.release()
        self.renderer.close()
