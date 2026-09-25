"""Crowded tables, and a physics engine to push the glasses around on them.

Shared by problem-3-programmed and problem-3-learned, so the two are tested on
the same tables, start from the same measurements, push with the same jaw and
are judged by the same physics.

MuJoCo stands in for Gazebo for the reason render.py did in problem 2: a
learned approach needs thousands of pushes, and Gazebo runs each one at the
speed of real time. It is also physics that neither approach wrote. A push
model written for this bench would let the programmed approach win by knowing
the answer.

An approach gets three things from here, and nothing else:

- ``look()`` — what problem 2's camera work hands over: where each glass
  stands, how tall it is, how wide it is at its widest and at its foot, and
  whether it is standing. Each reading carries problem 2's measured error.
- ``push()`` — the closed jaw comes down behind a glass, feels forward until it
  touches, pushes, and backs off. It reports what it felt.
- ``take()`` — pick a glass up and rack it. Problem 1 does the real picking;
  here the glass is simply lifted off the table.

The rest is the simulator's own record, which only scoring.py reads.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import mujoco
import numpy as np
from work_cell.arm.dimensions import LOWEST_GRIP
from work_cell.glasses.shapes import Outline, draw
from work_cell.glasses.spawn import SpawnedGlass
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import TABLE_CENTRE_XY, TABLE_SIZE, TABLE_TOP_Z

# Glass on the table. The same on every table, and neither approach is told
# it: nothing in the cell measures friction. Glass on a dry wooden top is
# somewhere between 0.2 and 0.5.
TABLE_FRICTION = 0.35
GLASS_ON_GLASS = 0.4
# Aluminium finger and silicone pad, on glass.
JAW_FRICTION = 0.6

# The closed jaw, as arm/gripper.urdf.xacro declares it, held level with the
# fingers pointing the way it pushes. Two 10 mm fingers and two 4 mm pads side
# by side, 120 mm long and 30 mm tall; the 90 mm body behind them; and the
# wrist behind that, drawn as a box the size of the body.
FINGER_LENGTH = 0.12
FINGER_HEIGHT = 0.03
JAW_THICKNESS = 2 * (0.010 + 0.004)
BODY_SIZE = 0.09
BODY_LENGTH = 0.05
WRIST_LENGTH = 0.10
TOOL_LENGTH = FINGER_LENGTH + BODY_LENGTH + WRIST_LENGTH

# The middle of the jaw rides this high: as low as the gripper goes.
PUSH_HEIGHT = LOWEST_GRIP
# The top edge of the jaw. A glass that is wider higher up meets the jaw here
# first, so this, not PUSH_HEIGHT, is how high it is pushed.
JAW_TOP = PUSH_HEIGHT + FINGER_HEIGHT / 2
# Where the jaw travels between pushes: the body's bottom edge clears the
# tallest glass drawn.
TRAVEL_HEIGHT = 0.30

DESCEND_SPEED = 0.20
FEEL_SPEED = 0.01
PUSH_SPEED = 0.02
RETREAT = 0.02
# Over this, the jaw has touched something. Low, because the lightest glass
# slides under about a quarter of a newton, and a threshold above that pushes
# it along without ever noticing it was there.
TOUCH_FORCE = 0.1
# Over this, something is wedged. The push stops where it is.
JAM_FORCE = 20.0

TIMESTEP = 0.002
SETTLE = 0.5
# A glass leaning further than this has fallen over.
STANDING_TILT_DEG = 20.0

# How far out each measurement is, one standard deviation. Set from what
# problem-2-programmed scored: position 0.2 mm median, widths 1.7 mm, height
# 0.8 mm. For a normal error the median size is two thirds of this.
POSITION_NOISE = 0.0005
WIDTH_NOISE = 0.0025
HEIGHT_NOISE = 0.0012

# Clear room the open jaw needs from a glass's middle to anything else, from
# problem.md: half the widest opening, a finger and a pad each side, and a
# little to spare. A neighbour is in the way when its edge is inside this.
GRIP_ROOM = 0.070

# The collision shape is a stack of cylinders, each no more than this wider
# than the glass anywhere inside it.
SLICE_TOLERANCE = 0.0015

KINDS = ("straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass")

# Scenes from here on are for testing. Training draws only below it.
TEST_SEEDS = 10_000

# The share of glasses stood deliberately close to one already down. The rest
# go anywhere they do not touch, which crowds some of them too.
CROWD_SHARE = 0.6
# The least daylight between two glasses at the start. They never touch.
START_GAP = 0.005


def has_room(x: float, y: float, others: list[tuple[float, float, float]], margin: float = 0.0) -> bool:
    """Whether a glass at (x, y) can be gripped: no other glass's edge inside GRIP_ROOM.

    ``others`` is (x, y, widest width) for every other glass on the table.
    Not symmetric: a narrow glass beside a wide one is crowded before the
    wide one is.
    """
    return all(math.dist((x, y), (ox, oy)) >= GRIP_ROOM + width / 2 + margin for ox, oy, width in others)


def in_zone(x: float, y: float) -> bool:
    x_min, x_max, y_min, y_max = GLASS_ZONE
    return x_min <= x <= x_max and y_min <= y <= y_max


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


def slices(outline: Outline) -> list[tuple[float, float, float]]:
    """The glass as stacked cylinders: (bottom, top, radius), from the table up.

    Each cylinder is as wide as the glass is at its widest inside it, so the
    shape is never thinner than the glass. The bottom one is the foot, which is
    the edge a glass tips over.
    """
    height, radius = outline.height, outline.radius
    cut, start = [], 0
    for i in range(1, len(height)):
        inside = radius[start : i + 1]
        if inside.max() - inside.min() > SLICE_TOLERANCE and i - 1 > start:
            cut.append((float(height[start]), float(height[i - 1]), float(radius[start:i].max())))
            start = i - 1
    cut.append((float(height[start]), float(height[-1]), float(radius[start:].max())))
    return cut


def _glass_xml(index: int, glass: SpawnedGlass) -> str:
    mass, centre, across, spin = glass.mass_properties
    x, y, _ = glass.position
    geoms = "".join(
        f'<geom type="cylinder" size="{r:.5f} {(top - bottom) / 2:.5f}" pos="0 0 {(top + bottom) / 2:.5f}" '
        f'friction="{GLASS_ON_GLASS} 0.005 0.0001" rgba="0.6 0.8 0.9 1"/>'
        for bottom, top, r in slices(glass.outline)
    )
    return (
        f'<body name="glass_{index}" pos="{x:.5f} {y:.5f} {TABLE_TOP_Z}"><freejoint/>'
        f'<inertial pos="0 0 {centre:.5f}" mass="{mass:.5f}" '
        f'diaginertia="{across:.3e} {across:.3e} {spin:.3e}"/>'
        f"{geoms}</body>"
    )


def _world(glasses: list[SpawnedGlass]) -> str:
    half_x, half_y = TABLE_SIZE[0] / 2, TABLE_SIZE[1] / 2
    jaw = f'friction="{JAW_FRICTION} 0.005 0.0001" priority="2" rgba="0.6 0.6 0.62 1"'
    return f"""
<mujoco model="crowded table">
  <option timestep="{TIMESTEP}" cone="elliptic" impratio="10"/>
  <worldbody>
    <light pos="0.4 0 2.5"/>
    <geom name="table" type="plane" size="{half_x} {half_y} 0.01"
          pos="{TABLE_CENTRE_XY[0]} {TABLE_CENTRE_XY[1]} {TABLE_TOP_Z}"
          friction="{TABLE_FRICTION} 0.005 0.0001" priority="1" rgba="0.75 0.6 0.45 1"/>
    {"".join(_glass_xml(i, g) for i, g in enumerate(glasses))}
    <body name="jaw" mocap="true" pos="0 0.5 1.3">
      <geom name="fingers" type="box" size="{FINGER_LENGTH / 2} {JAW_THICKNESS / 2} {FINGER_HEIGHT / 2}"
            pos="{-FINGER_LENGTH / 2} 0 0" {jaw}/>
      <geom name="body" type="box" size="{BODY_LENGTH / 2} {BODY_SIZE / 2} {BODY_SIZE / 2}"
            pos="{-FINGER_LENGTH - BODY_LENGTH / 2} 0 0" {jaw}/>
      <geom name="wrist" type="box" size="{WRIST_LENGTH / 2} {BODY_SIZE / 2} {BODY_SIZE / 2}"
            pos="{-FINGER_LENGTH - BODY_LENGTH - WRIST_LENGTH / 2} 0 0" {jaw}/>
    </body>
  </worldbody>
</mujoco>"""


@dataclass(frozen=True)
class Seen:
    """One glass, as the camera measured it. All the arm ever knows about it."""

    id: int
    x: float
    y: float
    height: float
    widest: float
    foot: float
    standing: bool


@dataclass(frozen=True)
class Push:
    """One push, as an approach asks for it."""

    glass: int  # which glass it is meant to move
    start: tuple[float, float]  # where the fingertips come down
    heading: float  # the way the jaw points and moves, radians
    reach: float  # how far forward to feel for the glass before giving up
    travel: float  # how far to push once touching
    aim: tuple[float, float]  # where the approach expects the glass to end up


@dataclass(frozen=True)
class Felt:
    """What the jaw felt. The only thing a push reports back."""

    blocked: bool  # touched something on the way down, and went back up
    touched: float | None  # how far forward it went before touching; None if it never did
    jammed: bool  # the force passed JAM_FORCE and the push was stopped
    peak: float  # the most force felt, newtons
    pushed: float  # how far it moved after touching


@dataclass(frozen=True)
class Record:
    """One push, and what really happened. For scoring."""

    push: Push
    felt: Felt
    landed: tuple[float, float]


class Bench:
    """One table in the physics engine."""

    def __init__(self, seed: int, glasses: list[SpawnedGlass] | None = None) -> None:
        self.seed = seed
        self.glasses = glasses if glasses is not None else scene(seed)
        self.model = mujoco.MjModel.from_xml_string(_world(self.glasses))
        self.data = mujoco.MjData(self.model)
        self.bodies = [self.model.body(f"glass_{i}").id for i in range(len(self.glasses))]
        self.jaw_geoms = {self.model.geom(n).id for n in ("fingers", "body", "wrist")}
        self.taken: dict[int, bool] = {}
        self.records: list[Record] = []
        self.looks = 0
        self._settle()
        self.start = [self.position(i) for i in range(len(self.glasses))]

    # ------------------------------------------------------------ the arm's view

    def look(self) -> list[Seen]:
        """What the overhead survey and problem 2 measure, with their error."""
        rng = np.random.default_rng([self.seed, self.looks])
        self.looks += 1
        seen = []
        for i, glass in enumerate(self.glasses):
            if i in self.taken:
                continue
            x, y = self.position(i) + rng.normal(0.0, POSITION_NOISE, 2)
            outline = glass.outline
            seen.append(
                Seen(
                    id=i,
                    x=float(x),
                    y=float(y),
                    height=outline.total_height + float(rng.normal(0.0, HEIGHT_NOISE)),
                    widest=outline.max_diameter + float(rng.normal(0.0, WIDTH_NOISE)),
                    foot=2 * float(outline.radius[0]) + float(rng.normal(0.0, WIDTH_NOISE)),
                    standing=self.tilt(i) < STANDING_TILT_DEG,
                )
            )
        return seen

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
        others = self._others(glass)
        x, y = self.position(glass)
        self.taken[glass] = self.tilt(glass) < STANDING_TILT_DEG and has_room(x, y, others)
        address = self.model.jnt_qposadr[self.model.body_jntadr[self.bodies[glass]]]
        # Off to one side, well away from everything, standing on the endless floor.
        self.data.qpos[address : address + 7] = [-3.0, -3.0 + 0.5 * glass, TABLE_TOP_Z, 1, 0, 0, 0]
        self.data.qvel[:] = 0.0
        self._settle()

    # ------------------------------------------------------ the simulator's record

    def position(self, glass: int) -> np.ndarray:
        """Where the middle of the glass's base is, flat on the table."""
        return self.data.xpos[self.bodies[glass]][:2].copy()

    def tilt(self, glass: int) -> float:
        """How far the glass leans from upright, degrees."""
        return math.degrees(math.acos(np.clip(self.data.xmat[self.bodies[glass]][8], -1.0, 1.0)))

    def on_table(self) -> list[int]:
        return [i for i in range(len(self.glasses)) if i not in self.taken]

    def _others(self, glass: int) -> list[tuple[float, float, float]]:
        return [
            (*self.position(j), self.glasses[j].outline.max_diameter) for j in self.on_table() if j != glass
        ]

    # ---------------------------------------------------------------- motion

    def _drive(self, start: np.ndarray, end: np.ndarray, speed: float, stop_at: float) -> tuple[float, float]:
        """Move the jaw in a straight line. Stops when the force passes ``stop_at``.

        Returns how far it went and the most force it felt.
        """
        length = float(np.linalg.norm(end - start))
        steps = max(1, math.ceil(length / (speed * TIMESTEP)))
        peak = 0.0
        for k in range(1, steps + 1):
            self.data.mocap_pos[0] = start + (end - start) * (k / steps)
            self._step()
            force = self._jaw_force()
            peak = max(peak, force)
            if force > stop_at:
                return length * k / steps, peak
        return length, peak

    def _jaw_force(self) -> float:
        """The net force on the jaw, as the wrist's force sensor would read it."""
        total = np.zeros(3)
        wrench = np.zeros(6)
        contacts = self.data.contact
        for k in range(self.data.ncon):
            if contacts.geom1[k] in self.jaw_geoms or contacts.geom2[k] in self.jaw_geoms:
                mujoco.mj_contactForce(self.model, self.data, k, wrench)
                total += contacts.frame[k].reshape(3, 3).T @ wrench[:3]
        return float(np.linalg.norm(total))

    def _back_off(self, at: np.ndarray, u: np.ndarray) -> None:
        back = at - RETREAT * u
        self._drive(at, back, PUSH_SPEED, math.inf)
        self._lift(back)

    def _lift(self, at: np.ndarray) -> None:
        above = np.array([at[0], at[1], TABLE_TOP_Z + TRAVEL_HEIGHT])
        self._drive(at, above, DESCEND_SPEED, math.inf)
        self.data.mocap_pos[0] = [0.0, 0.5, 1.3]
        self._settle()

    def _settle(self) -> None:
        for _ in range(int(SETTLE / TIMESTEP)):
            self._step()

    def _step(self) -> None:
        """One step of physics. Every step goes through here, so film.py can watch them."""
        mujoco.mj_step(self.model, self.data)

    def _record(self, push: Push, felt: Felt) -> Felt:
        self.records.append(Record(push, felt, tuple(self.position(push.glass))))
        return felt
