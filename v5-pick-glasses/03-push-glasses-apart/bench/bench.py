"""Crowded tables, and a physics engine to push the glasses around on them.

Shared by every solution in 03-push-glasses-apart, so they are tested on the
same tables, start from the same measurements, push with the same jaw and are
judged by the same physics.

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

A solution that thinks in trajectories rather than in push parameters calls
``follow()`` instead of ``push()``. It submits a ``Chunk`` of jaw waypoints,
the bench carries them out in the same physics, and it reports the same
``Felt`` into the same record, so the scorecard cannot tell the two apart.
``top_view.py`` renders the straight-down picture the policies that read
pictures take as their input.

The rest is the simulator's own record, which only scoring.py reads.
"""

from __future__ import annotations

import math
import random
import time
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
# The fastest this cell ever moves the jaw, which is the speed it comes down at.
# follow() holds a commanded path to it: a solution may ask the jaw to go
# anywhere, but not to get there faster than the arm can move, because a bench
# that allowed that would be reporting the physics of an arm nobody has. It is
# deliberately not a new number. It is the largest of the speeds above, so it
# never binds on anything the bench itself does, and binds only on a path this
# cell could not carry out.
TOP_SPEED = DESCEND_SPEED
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
# 02-segment-glasses/01-rules-on-the-table scored: position 0.2 mm median, widths 1.7 mm, height
# 0.8 mm. For a normal error the median size is two thirds of this.
POSITION_NOISE = 0.0005
WIDTH_NOISE = 0.0025
HEIGHT_NOISE = 0.0012

# The straight-down camera top_view.py renders from: directly above the middle
# of the glass zone, this far above the table top.
TOP_VIEW_HEIGHT = 0.75
# How many pixels that view is, (rows, columns). Square, because the frame is.
TOP_VIEW_SIZE = (384, 384)

# Clear room the open jaw needs from a glass's middle to anything else, from
# problem.md: half the widest opening, a finger and a pad each side, and a
# little to spare. A neighbour is in the way when its edge is inside this.
GRIP_ROOM = 0.070

# Half the straight-down view's frame, measured on the table top. It has to
# hold the whole glass zone, and a little more: in a view from above a glass
# leans outwards from the point under the camera, so something standing at the
# zone's edge appears further out than it stands. TRAVEL_HEIGHT is the height
# nothing on the table reaches, and half GRIP_ROOM is wider than any glass the
# jaw can grip, so this frames the zone with every glass on it whole.
_ZONE_REACH = max(
    (GLASS_ZONE[1] - GLASS_ZONE[0]) / 2,
    (GLASS_ZONE[3] - GLASS_ZONE[2]) / 2,
)
TOP_VIEW_HALF_FRAME = (_ZONE_REACH + GRIP_ROOM / 2) * TOP_VIEW_HEIGHT / (TOP_VIEW_HEIGHT - TRAVEL_HEIGHT)
TOP_VIEW_FOVY_DEG = math.degrees(2 * math.atan(TOP_VIEW_HALF_FRAME / TOP_VIEW_HEIGHT))

# The collision shape is a stack of cylinders, each no more than this wider
# than the glass anywhere inside it.
SLICE_TOLERANCE = 0.0015

KINDS = ("straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass")

# Scenes from here on are for testing. Training draws only below it.
TEST_SEEDS = 10_000

# How often a waypoint is consumed, seconds. A controller eats a trajectory at
# a fixed rate, so a chunk's speed is in how far apart its waypoints are: 1 mm
# apart is PUSH_SPEED. The jaw's own path is sampled at the same rate, so a
# parameterised push can be read back as a chunk and replayed exactly.
WAYPOINT_PERIOD = 0.05
TRACE_EVERY = round(WAYPOINT_PERIOD / TIMESTEP)
# A chunk longer than this is a runaway, not a short run of waypoints. A whole
# push sampled at WAYPOINT_PERIOD is a few hundred, so this leaves room.
MAX_WAYPOINTS = 500

# One push budget for all six solutions, which every runner reads from here. It
# used to live in each runner, and the two that existed then disagreed, so the
# push counts were not comparable. The larger pair was taken, so that moving to
# a shared budget could not cramp a solution that already worked: measured, the
# solution that had the smaller pair scores the same under either, because it
# refuses for want of room long before it runs out of tries.
PUSHES_PER_GLASS = 4
PUSHES_PER_TABLE = 16

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
    zone_x, zone_y = (GLASS_ZONE[0] + GLASS_ZONE[1]) / 2, (GLASS_ZONE[2] + GLASS_ZONE[3]) / 2
    # The camera top_view.py renders from. Its axes are the table's own: the
    # picture's right is +x and the picture's up is +y. It is a camera and not
    # a body, so adding it changes nothing about the physics.
    return f"""
<mujoco model="crowded table">
  <option timestep="{TIMESTEP}" cone="elliptic" impratio="10"/>
  <worldbody>
    <light pos="0.4 0 2.5"/>
    <camera name="top" pos="{zone_x:.5f} {zone_y:.5f} {TABLE_TOP_Z + TOP_VIEW_HEIGHT:.5f}"
            xyaxes="1 0 0 0 1 0" fovy="{TOP_VIEW_FOVY_DEG:.5f}"/>
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
class Waypoint:
    """One target for the jaw, on the path it is told to follow."""

    x: float
    y: float
    z: float  # the middle of the jaw, above the table top: 0.0 is the table
    heading: float  # the way the jaw points and moves, radians


@dataclass(frozen=True)
class Chunk:
    """A short run of jaw waypoints, as a policy that thinks in trajectories emits it.

    ``follow()`` carries the waypoints out one WAYPOINT_PERIOD apart, so how
    far apart they are is how fast the jaw goes, up to TOP_SPEED. Past that the
    jaw cannot keep up and the leg simply takes longer. Nothing expands a
    chunk: it is already a jaw trajectory.
    """

    glass: int  # which glass it is meant to move
    waypoints: tuple[Waypoint, ...]
    aim: tuple[float, float]  # where the policy expects the glass to end up

    @classmethod
    def from_array(cls, glass: int, action: np.ndarray, aim: tuple[float, float]) -> Chunk:
        """Build a chunk from an (n, 4) array of x, y, z, heading — a policy's own output."""
        action = np.asarray(action, dtype=float)
        if action.ndim != 2 or action.shape[1] != 4:
            raise ValueError(f"a chunk is (n, 4) of x, y, z, heading, not {action.shape}")
        return cls(glass, tuple(Waypoint(*row) for row in action.tolist()), aim)

    def as_push(self) -> Push:
        """The one push this chunk amounts to, for the record.

        The scorecard reads ``glass`` and ``aim``, which are the chunk's own.
        ``start`` and ``heading`` are where the jaw comes down and which way it
        first points; ``reach`` is the whole distance it is told to travel
        across the table and ``travel`` the distance from first waypoint to
        last. A chunk has no feel-then-push split, so those two describe its
        extent rather than a request.
        """
        first, last = self.waypoints[0], self.waypoints[-1]
        across = sum(
            math.dist((a.x, a.y), (b.x, b.y))
            for a, b in zip(self.waypoints, self.waypoints[1:], strict=False)
        )
        return Push(
            glass=self.glass,
            start=(first.x, first.y),
            heading=first.heading,
            reach=across,
            travel=math.dist((first.x, first.y), (last.x, last.y)),
            aim=self.aim,
        )


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
    """One action, and what really happened. For scoring.

    A chunk of waypoints records the same three fields, with ``push`` the one
    push it amounts to, so nothing downstream can tell the two paths apart.
    ``waypoints`` is the path the jaw really followed, sampled every
    WAYPOINT_PERIOD: replay it with ``follow()`` and the same thing happens.
    """

    push: Push
    felt: Felt
    landed: tuple[float, float]
    waypoints: tuple[Waypoint, ...] = ()


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
        # Wall time spent inside the bench. A runner subtracts it from its own
        # clock to report what the solution's thinking cost, not the physics.
        self.seconds = 0.0
        self._trace: list[Waypoint] | None = None
        self._driven = 0
        self._began = 0.0
        self._settle()
        self.start = [self.position(i) for i in range(len(self.glasses))]

    # ------------------------------------------------------------ the arm's view

    def look(self) -> list[Seen]:
        """What the overhead survey and problem 2 measure, with their error."""
        started = time.perf_counter()
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
        self.seconds += time.perf_counter() - started
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

    def follow(self, chunk: Chunk) -> Felt:
        """Carry out a chunk of jaw waypoints, and report what the jaw felt.

        The other half of ``push()``: same physics, same ``Felt``, same record,
        for a policy whose answer is already a trajectory. The jaw is placed
        clear above where the chunk starts — nothing on the table reaches
        TRAVEL_HEIGHT — and comes down to the first waypoint. Then it is driven
        through the waypoints, one WAYPOINT_PERIOD apart.

        What is reported, against what ``push()`` reports:

        - ``blocked`` — touched something while still coming down, before any
          waypoint had moved it across the table. The jaw goes straight back up
          and nothing is pushed, as in ``push()``.
        - ``touched`` — how far it had moved across the table when the force
          first passed TOUCH_FORCE. ``None`` if it never touched anything.
        - ``jammed`` — the force passed JAM_FORCE and the chunk was stopped.
        - ``peak`` — the most force felt at any moment.
        - ``pushed`` — the furthest the jaw got from where it first touched.

        Once the jaw is moving across the table the force no longer stops it
        below JAM_FORCE: the chunk is carried out as it was given, which is
        the point of accepting one. The jaw turns to a waypoint's heading as
        that leg starts, so a chunk that turns should turn over several
        waypoints rather than in one.

        Raises ValueError for a chunk the jaw cannot follow: empty, longer than
        MAX_WAYPOINTS, below the lowest the gripper reaches or above travel
        height, or off the table.
        """
        points = _checked(chunk.waypoints)
        above = self._place(points[0])
        legs = [above, *(np.array([p.x, p.y, TABLE_TOP_Z + p.z]) for p in points)]

        peak, across, pushed = 0.0, 0.0, 0.0
        touched_at, touch_xy = None, np.zeros(2)
        coming_down, lead_in = True, True
        at = above
        for target, point in zip(legs[1:], points, strict=True):
            self._aim(point.heading)
            length = float(np.linalg.norm(target - at))
            if length < 1e-12:
                continue
            flat = float(np.linalg.norm(target[:2] - at[:2]))
            coming_down = coming_down and flat < 1e-12
            # The lead-in comes down at the speed push() descends at. Every
            # other leg takes one waypoint period, unless it is so long that
            # covering it in one period would need more than the jaw's top
            # speed, in which case it takes the time the jaw really needs. So
            # how far apart the waypoints are still sets the speed, up to the
            # point where the arm runs out of speed to give.
            seconds = length / DESCEND_SPEED if lead_in else max(WAYPOINT_PERIOD, length / TOP_SPEED)
            lead_in = False
            gone, force, touch = self._slide(at, target, seconds, TOUCH_FORCE if coming_down else JAM_FORCE)
            peak = max(peak, force)
            stopped = gone < length - 1e-9
            if coming_down and stopped:
                # Touched something on the way down. Straight back up, no push.
                self._lift(at + (target - at) * (gone / length))
                return self._record(chunk.as_push(), Felt(True, None, False, peak, 0.0))
            was = at
            at = at + (target - at) * (gone / length)
            if touched_at is None and touch is not None:
                touched_at = across + touch * flat / length
                touch_xy = (was + (target - was) * (touch / length))[:2]
            across += gone * flat / length
            if touched_at is not None:
                pushed = max(pushed, float(np.linalg.norm(at[:2] - touch_xy)))
            if stopped:
                felt = Felt(False, touched_at, True, peak, pushed)
                self._back_off(at, _along(was, target))
                return self._record(chunk.as_push(), felt)

        felt = Felt(False, touched_at, False, peak, pushed)
        self._lift(at)
        return self._record(chunk.as_push(), felt)

    def _place(self, first: Waypoint) -> np.ndarray:
        """Put the jaw clear above where the chunk starts, without any physics."""
        above = np.array([first.x, first.y, TABLE_TOP_Z + TRAVEL_HEIGHT])
        self._aim(first.heading)
        self.data.mocap_pos[0] = above
        mujoco.mj_forward(self.model, self.data)
        return above

    def _aim(self, heading: float) -> None:
        self.data.mocap_quat[0] = [math.cos(heading / 2), 0.0, 0.0, math.sin(heading / 2)]

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
            self._advance(start + (end - start) * (k / steps))
            force = self._jaw_force()
            peak = max(peak, force)
            if force > stop_at:
                return length * k / steps, peak
        return length, peak

    def _slide(
        self, start: np.ndarray, end: np.ndarray, seconds: float, stop_at: float
    ) -> tuple[float, float, float | None]:
        """Move the jaw to ``end`` over ``seconds``: one leg of a chunk.

        Like ``_drive``, but the speed comes from the time a waypoint is given
        rather than from a fixed speed, and the first touch is noted without
        stopping. Returns how far it went, the most force it felt, and how far
        along it first felt TOUCH_FORCE.
        """
        length = float(np.linalg.norm(end - start))
        steps = max(1, round(seconds / TIMESTEP))
        peak, touch = 0.0, None
        for k in range(1, steps + 1):
            self._advance(start + (end - start) * (k / steps))
            force = self._jaw_force()
            peak = max(peak, force)
            if touch is None and force > TOUCH_FORCE:
                touch = length * k / steps
            if force > stop_at:
                return length * k / steps, peak, touch
        return length, peak, touch

    def _advance(self, position: np.ndarray) -> None:
        """One step with the jaw told to be at ``position``, sampling the path.

        The sampling is what makes a parameterised push readable as a chunk:
        every WAYPOINT_PERIOD the jaw's target is written down, so the record
        of a push is a trajectory a policy could have emitted.
        """
        if self._trace is None:
            # The first step of an action. The jaw has already been put where
            # the action starts, so that pose is the path's first waypoint.
            self._trace, self._driven = [self._jaw_waypoint()], 0
            self._began = time.perf_counter()
        self.data.mocap_pos[0] = position
        self._step()
        self._driven += 1
        if self._driven % TRACE_EVERY == 0:
            self._trace.append(self._jaw_waypoint())

    def _jaw_waypoint(self) -> Waypoint:
        x, y, z = self.data.mocap_pos[0]
        w, _, _, spin = self.data.mocap_quat[0]
        return Waypoint(float(x), float(y), float(z - TABLE_TOP_Z), 2 * math.atan2(float(spin), float(w)))

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
        # Everything from the action's first step to here was the bench, not
        # the solution: the physics, the force sums, the back off and the lift.
        self.seconds += time.perf_counter() - self._began
        path = tuple(self._trace or ())
        self._trace = None
        self.records.append(Record(push, felt, tuple(self.position(push.glass)), path))
        return felt


def _along(start: np.ndarray, end: np.ndarray) -> np.ndarray:
    """The flat direction from ``start`` to ``end``; zero if it only went up or down."""
    step = np.array([end[0] - start[0], end[1] - start[1], 0.0])
    length = float(np.linalg.norm(step))
    return step / length if length > 1e-12 else step


def _checked(waypoints: tuple[Waypoint, ...]) -> tuple[Waypoint, ...]:
    """The chunk, if the jaw can follow it. Otherwise say exactly what is wrong."""
    if not 1 <= len(waypoints) <= MAX_WAYPOINTS:
        raise ValueError(f"a chunk is 1 to {MAX_WAYPOINTS} waypoints, not {len(waypoints)}")
    half_x, half_y = TABLE_SIZE[0] / 2, TABLE_SIZE[1] / 2
    for i, point in enumerate(waypoints):
        if not PUSH_HEIGHT - 1e-9 <= point.z <= TRAVEL_HEIGHT + 1e-9:
            raise ValueError(
                f"waypoint {i} is {1000 * point.z:.0f} mm up; the jaw rides between "
                f"{1000 * PUSH_HEIGHT:.0f} and {1000 * TRAVEL_HEIGHT:.0f} mm above the table"
            )
        if abs(point.x - TABLE_CENTRE_XY[0]) > half_x or abs(point.y - TABLE_CENTRE_XY[1]) > half_y:
            raise ValueError(f"waypoint {i} at ({point.x:.3f}, {point.y:.3f}) is off the table")
    return waypoints
