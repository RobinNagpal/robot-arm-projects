"""Problem 3's bench: crowded tables, and a physics engine to push the glasses around on them.

Shared by every solution in 03-push-glasses-apart, so they are tested on the
same tables, start from the same measurements, push with the same jaw and are
judged by the same physics.

Most of it is in ``common_bench.py``, which holds the physics any problem that
pushes glasses shares, and which problem 4 keeps a copy of. This file extends
it with what belongs to problem 3 alone, and every name in ``common_bench`` can
still be imported from here, so a solution imports from ``bench`` only.

An approach gets three things from here, and nothing else:

- ``look()`` — what problem 2's camera work hands over: where each glass
  stands, how tall it is, how wide it is at its widest and at its foot, and
  whether it is standing. Each reading carries problem 2's measured error.
- ``push()`` — the closed jaw comes down behind a glass, feels forward until it
  touches, pushes, and backs off. It reports what it felt.
- ``take()`` — pick a glass up and rack it. Problem 1 does the real picking;
  here the glass is simply lifted off the table.

A solution that thinks in trajectories rather than in push parameters calls
``follow()`` instead of ``push()``. It submits a ``Chunk`` of jaw waypoints,
the bench carries them out in the same physics, and it reports the same
``Felt`` into the same record, so the scorecard cannot tell the two apart.
``top_view.py`` renders the straight-down picture the policies that read
pictures take as their input, from the camera this file writes into the world.

The rest is the simulator's own record, which only scoring.py reads.
"""

from __future__ import annotations

import math
import random
import time

import mujoco
import numpy as np
from work_cell.glasses.shapes import Outline, draw
from work_cell.glasses.spawn import SpawnedGlass
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import TABLE_TOP_Z

from common_bench import (  # noqa: F401  (re-exported: every solution imports them from here)
    CROWD_SHARE,
    DESCEND_SPEED,
    DRAWN_PIECES,
    FEEL_SPEED,
    FINGER_HEIGHT,
    FINGER_LENGTH,
    GLASS_ON_GLASS,
    GRIP_ROOM,
    HEIGHT_NOISE,
    JAM_FORCE,
    JAW_FRICTION,
    JAW_HALF_HEIGHT,
    JAW_PARTS,
    JAW_SEGMENTS,
    JAW_THICKNESS,
    JAW_TOP,
    KINDS,
    MAX_WAYPOINTS,
    POSITION_NOISE,
    PUSH_HEIGHT,
    PUSH_SPEED,
    PUSHES_PER_GLASS,
    PUSHES_PER_TABLE,
    RETREAT,
    ROLLED,
    SETTLE,
    SLICE_TOLERANCE,
    STANDING_TILT_DEG,
    START_GAP,
    TABLE_FRICTION,
    TEST_SEEDS,
    TIMESTEP,
    TOOL_LENGTH,
    TOP_SPEED,
    TOUCH_FORCE,
    TRACE_EVERY,
    TRAVEL_HEIGHT,
    WAYPOINT_PERIOD,
    WIDTH_NOISE,
    WRIST_ACROSS,
    WRIST_LENGTH,
    Chunk,
    CommonBench,
    Felt,
    Push,
    Record,
    Seen,
    Waypoint,
    _along,
    _checked,
    _drawn_hand_xml,
    _glass_xml,
    _jaw_xml,
    _rolled,
    has_room,
    in_zone,
    segment_distance,
    slices,
)
from common_bench import (
    _world as _common_world,
)
from top_view import (  # noqa: F401  (re-exported, as above)
    TOP_VIEW_FOVY_DEG,
    TOP_VIEW_HALF_FRAME,
    TOP_VIEW_HEIGHT,
    TOP_VIEW_SIZE,
)


def scene(seed: int) -> list[SpawnedGlass]:
    """Table number ``seed``: four to six glasses of one kind, some too close.

    The same kind and count cycle as problem 2's scenes. Every table has at
    least one glass without room.
    """
    rng = random.Random(seed)
    kind, count = KINDS[seed % len(KINDS)], 4 + seed % 3
    for _ in range(200):
        outlines = [draw(kind, rng)[0] for _ in range(count)]
        spots = _crowded_layout(rng, outlines)
        if spots is not None:
            return [
                SpawnedGlass(f"glass_{i}", kind, outline, (x, y, TABLE_TOP_Z), 0.0)
                for i, (outline, (x, y)) in enumerate(zip(outlines, spots, strict=True))
            ]
    raise RuntimeError(f"no crowded layout for scene {seed}")


def _crowded_layout(rng: random.Random, outlines: list[Outline]) -> list[tuple[float, float]] | None:
    x_min, x_max, y_min, y_max = GLASS_ZONE
    placed: list[tuple[float, float, float]] = []
    for outline in outlines:
        width = outline.max_diameter
        for _ in range(300):
            if placed and rng.random() < CROWD_SHARE:
                px, py, pwidth = rng.choice(placed)
                # Between touching and having room.
                near = rng.uniform((width + pwidth) / 2 + START_GAP, GRIP_ROOM + max(width, pwidth) / 2)
                angle = rng.uniform(-math.pi, math.pi)
                x, y = px + near * math.cos(angle), py + near * math.sin(angle)
            else:
                x, y = rng.uniform(x_min, x_max), rng.uniform(y_min, y_max)
            if in_zone(x, y) and all(
                math.dist((x, y), (qx, qy)) >= (width + qwidth) / 2 + START_GAP for qx, qy, qwidth in placed
            ):
                placed.append((x, y, width))
                break
        else:
            return None
    crowded = [not has_room(x, y, [q for q in placed if q is not p]) for p in placed for x, y in [p[:2]]]
    return [(x, y) for x, y, _ in placed] if any(crowded) else None


def _top_camera() -> str:
    """The camera top_view.py renders from, as MuJoCo XML.

    Its axes are the table's own: the picture's right is +x and the picture's
    up is +y. It is a camera and not a body, so adding it changes nothing about
    the physics.
    """
    zone_x, zone_y = (GLASS_ZONE[0] + GLASS_ZONE[1]) / 2, (GLASS_ZONE[2] + GLASS_ZONE[3]) / 2
    return f"""
    <camera name="top" pos="{zone_x:.5f} {zone_y:.5f} {TABLE_TOP_Z + TOP_VIEW_HEIGHT:.5f}"
            xyaxes="1 0 0 0 1 0" fovy="{TOP_VIEW_FOVY_DEG:.5f}"/>"""


def _world(glasses: list[SpawnedGlass], draw_hand: bool = False) -> str:
    """Problem 3's world: the common one, with the overhead camera in it."""
    return _common_world(glasses, draw_hand, _top_camera())


def drawing_world(glasses: list[SpawnedGlass]) -> str:
    """The same world with the real hand drawn in it, for film.py and nothing else.

    It is a second world rather than a setting on the scored one on purpose.
    Three of the six solutions read an overhead picture of the table and decide
    from it, so anything added to the world they are scored in could change
    what they do. Keeping the drawn hand in a world of its own means the scored
    world is the same object whether a table is filmed or not, and the film can
    be made as clear as it likes.
    """
    return _world(glasses, draw_hand=True)


class Bench(CommonBench):
    """One of problem 3's tables in the physics engine.

    The common bench, with problem 3's own draw, its overhead camera, ``push()``
    and ``take()``. A glass that is taken leaves the table, so ``on_table`` and
    everything built on it leave it out.
    """

    def __init__(self, seed: int, glasses: list[SpawnedGlass] | None = None) -> None:
        self.taken: dict[int, bool] = {}
        super().__init__(seed, glasses if glasses is not None else scene(seed))

    def cameras_xml(self) -> str:
        return _top_camera()

    def on_table(self) -> list[int]:
        return [i for i in range(len(self.glasses)) if i not in self.taken]

    def push(self, push: Push) -> Felt:
        """Come down behind the glass, feel forward, push, back off, go up."""
        u = np.array([math.cos(push.heading), math.sin(push.heading), 0.0])
        self.data.mocap_quat[0] = [math.cos(push.heading / 2), 0.0, 0.0, math.sin(push.heading / 2)]
        above = np.array([*push.start, TABLE_TOP_Z + TRAVEL_HEIGHT])
        low = np.array([*push.start, TABLE_TOP_Z + PUSH_HEIGHT])
        self.data.mocap_pos[0] = above
        mujoco.mj_forward(self.model, self.data)

        peak = 0.0
        down, force = self._drive(above, low, DESCEND_SPEED, TOUCH_FORCE)
        peak = max(peak, force)
        if down < np.linalg.norm(low - above) - 1e-9:
            felt = Felt(True, None, False, peak, 0.0)
            self._lift(above - (np.linalg.norm(low - above) - down) * np.array([0, 0, 1.0]))
            return self._record(push, felt)

        forward, force = self._drive(low, low + push.reach * u, FEEL_SPEED, TOUCH_FORCE)
        peak = max(peak, force)
        if forward >= push.reach - 1e-9:
            felt = Felt(False, None, False, peak, 0.0)
            self._back_off(low + forward * u, u)
            return self._record(push, felt)

        contact = low + forward * u
        pushed, force = self._drive(contact, contact + push.travel * u, PUSH_SPEED, JAM_FORCE)
        peak = max(peak, force)
        felt = Felt(False, forward, pushed < push.travel - 1e-9, peak, pushed)
        self._back_off(contact + pushed * u, u)
        return self._record(push, felt)

    def take(self, glass: int) -> None:
        """Pick the glass up and rack it. Whether it really had room is recorded."""
        started = time.perf_counter()
        others = self._others(glass)
        x, y = self.position(glass)
        self.taken[glass] = self.tilt(glass) < STANDING_TILT_DEG and has_room(x, y, others)
        address = self.model.jnt_qposadr[self.model.body_jntadr[self.bodies[glass]]]
        # Off to one side, well away from everything, standing on the endless floor.
        self.data.qpos[address : address + 7] = [-3.0, -3.0 + 0.5 * glass, TABLE_TOP_Z, 1, 0, 0, 0]
        self.data.qvel[:] = 0.0
        self._settle()
        self.seconds += time.perf_counter() - started
