"""Film a table being cleared, to check by eye what the hand did.

A Bench that also records a video. It changes nothing about the physics, and it
cannot: the table is scored in the world ``bench.py`` builds, and everything
here is drawn in a second world of its own. Written the way
v5-learn-pick-place/pick_place/video.py films an episode, with MuJoCo's
offscreen renderer, so it needs no window and no mjpython.

Used by every solution's run.py, with ``--film N`` to film the first N tables.

Three things about these films are worth knowing before watching one.

**The hand never opens during a push.** This problem shoves glasses apart with
the gripper held shut, which is what the parallel locking kit on a Robotiq
2F-85 is for, so a push is the whole hand driven sideways into a glass. Nothing
is gripped and nothing is lifted. If the fingers opened on film during a push,
the film would be wrong.

**The hand is drawn twice.** The bench collides a simplified hand: each pair of
fingers is one box covering both fingers and the 82 mm gap between them, which
is the safe assumption for a push, because a glass standing in that gap would
be swept along just the same. The film draws the real pieces solid and that
larger collided shape as a faint shell around them, so a viewer can see both the
hand and the volume the simulator treats as solid.

**The pick at the end of a take is drawn, not simulated.** The bench racks a
glass by moving it off the table in one instant, which on film would look like
the glass vanishing. So the film draws a stand-in for a pick: the wrist rolls
back level, the fingers open to the width the glass was measured to be, the
hand reaches in so that the pads pass either side of it, the fingers close, and
the glass is carried off. It is a stand-in and not problem 1's grip rule, which
is a harder question and mostly answers no on these glasses; ``_grip`` says why.
It is drawn in the second world and never stepped, so the physics, and every
result, are the same filmed or not. ``test_bench.py`` checks it.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

import cv2
import mujoco
import numpy as np
from work_cell.arm import robotiq_2f85
from work_cell.arm.dimensions import LOWEST_GRIP
from work_cell.rack.layout import GLASS_ZONE, RACK_AREA
from work_cell.table.layout import TABLE_TOP_Z

from bench import (
    KINDS,
    TIMESTEP,
    TOOL_LENGTH,
    TRAVEL_HEIGHT,
    WRIST_ACROSS,
    WRIST_LENGTH,
    Bench,
    Push,
    drawing_world,
    segment_distance,
    slices,
)

WIDTH, HEIGHT = 1280, 960
FPS = 30
# The film runs this many times faster than the physics. The hand feels forward
# at 10 mm/s, which is too slow to watch at life size and too fast to follow at
# three times life size, which is what these films used to run at.
SPEED = 1.5
# The last picture is held this long, with the outcome on it.
HOLD = 2.0

# Where the hand waits between moves, as bench.py parks it.
PARK = np.array([0.0, 0.5, 1.3])
# How long each part of a drawn pick lasts on film, in seconds. A pick is drawn
# rather than simulated, so these are a reader's pace and not a measurement.
PICK_MOVES = {
    "unrolling the wrist": 0.5,
    "across to it": 0.6,
    "down beside it": 0.5,
    "in around it": 0.4,
    "closing on it": 0.4,
    "lifting": 0.4,
    "to the rack": 0.7,
}
# How high a taken glass is lifted before it is carried off.
LIFT = 0.25
# Where up the glass the drawn pick holds it, as a fraction of the glass's own
# height. A fraction rather than a height, because no glass's size may be
# written down anywhere in this project.
GRIP_FRACTION = 0.40
# How much wider than the glass the fingers open before they come in around it.
GRIP_CLEARANCE = 0.030
# How far short of the glass the hand stops before reaching in, so that the pads
# pass either side of it rather than arriving on top of it.
STAND_OFF = 0.12
# How many ways in are tried before giving up on finding a clear one. The hand
# is long, so whether it can reach a glass depends on which side it comes from,
# and on a crowded table most sides are blocked.
WAYS_IN = 24
# How much daylight the hand is drawn keeping from a glass it is not holding.
# The same figure solution 1 keeps when it decides whether a push would drag the
# hand through a neighbour.
CLEARANCE = 0.008

# The two ways the hand is held, as quaternions. Pushing, it is rolled a quarter
# turn about the approach, so the two fingers stack one above the other and the
# hand is only 27 mm wide, which is the whole reason this problem can be solved
# at all. Gripping, it is level, so the fingers sit either side of the glass.
# A pick begins by rolling back from the first to the second, and that turn is a
# real cost of pushing with a gripper rather than with a blade.
ROLLED = np.array([math.cos(math.pi / 4), math.sin(math.pi / 4), 0.0, 0.0])
LEVEL = np.array([1.0, 0.0, 0.0, 0.0])
# The hand reaches in along this heading for a drawn pick, which is away from
# the camera. The gripper's body trails behind its fingertips, so a hand coming
# the other way would put its own body between the camera and the glass and hide
# the one thing the pick is there to show. Reaching away leaves the body behind
# the glass, and the fingers open across the view, which is the one direction
# from which both fingers and the gap between them show. The bench has no arm,
# so no approach is more correct than another.
PICK_HEADING = math.pi
# How many characters of a line fit across the picture, at the size the writing
# is drawn. A refusal from the grip rule is a whole sentence and has to be
# broken over several lines rather than run off the edge.
LINE_LENGTH = 62
# Where the camera goes to watch a drawn pick: closer, and much less steeply
# down. From the standing view the gripper's own body is between the camera and
# the glass, so the one thing the pick is there to show would be hidden behind
# it. The camera eases in as the wrist rolls and eases out as the glass is
# carried off, so the move is part of the pick rather than a cut.
PICK_DISTANCE = 0.62
PICK_ELEVATION = -30.0
PICK_RISE = 0.13


def _slerp(first: np.ndarray, second: np.ndarray, part: float) -> np.ndarray:
    """A turn part of the way from one orientation to another, along the short arc."""
    dot = float(np.dot(first, second))
    if dot < 0.0:
        second, dot = -second, -dot
    angle = math.acos(min(1.0, dot))
    if angle < 1e-6:
        return first
    return (math.sin((1 - part) * angle) * first + math.sin(part * angle) * second) / math.sin(angle)


def _matrix(quaternion: np.ndarray) -> np.ndarray:
    """The same turn written as a matrix, which is what a position is turned by."""
    turn = np.zeros(9)
    mujoco.mju_quat2Mat(turn, quaternion)
    return turn.reshape(3, 3)


class FilmedBench(Bench):
    """A bench that writes a video of what it did. Identical to Bench otherwise."""

    def __init__(self, seed: int, approach: str = "", glasses: list | None = None) -> None:
        self.renderer = None
        super().__init__(seed, glasses)
        # A second world, with the real hand drawn in it. Nothing is ever
        # stepped here: every frame copies the scored world's positions across
        # and this one is only looked at. See bench.drawing_world.
        self.drawn_model = mujoco.MjModel.from_xml_string(drawing_world(self.glasses))
        self.drawn_model.vis.global_.offwidth = WIDTH
        self.drawn_model.vis.global_.offheight = HEIGHT
        # Eight samples a pixel rather than the usual four, because the hand is
        # a stack of thin boxes and its edges are what a viewer is reading.
        self.drawn_model.vis.quality.offsamples = 8
        self.drawn_data = mujoco.MjData(self.drawn_model)
        self.renderer = mujoco.Renderer(self.drawn_model, HEIGHT, WIDTH)
        self.shell = [
            self.drawn_model.geom(name).id for name in ("fingertips", "fingers", "body", "wrist")
        ]
        names = (
            mujoco.mj_id2name(self.drawn_model, mujoco.mjtObj.mjOBJ_GEOM, i)
            for i in range(self.drawn_model.ngeom)
        )
        self.drawn = {
            name: self.drawn_model.geom(name).id
            for name in names
            if name and name.startswith("drawn_")
        }
        # From the arm's side of the table, looking steeply down at the glass
        # zone, so the gaps between glasses show.
        self.camera = mujoco.MjvCamera()
        x_min, x_max, y_min, y_max = GLASS_ZONE
        self.camera.lookat[:] = [(x_min + x_max) / 2, (y_min + y_max) / 2, TABLE_TOP_Z + 0.05]
        self.camera.azimuth = 0
        # Kept, because a drawn pick moves the camera and has to put it back.
        self.standing = (self.camera.lookat.copy(), 0.9, -55.0)
        self._watch(np.zeros(3), 0.0)
        self.every = max(1, round(SPEED / (FPS * TIMESTEP)))
        self.steps = 0
        self.label = f"{approach}  table {seed}  {KINDS[seed % len(KINDS)].replace('_', ' ')}".strip()
        self.doing = "first look"
        self.note: tuple[str, ...] = ()
        # How many frames have been written, and the one frame from a pick
        # worth keeping, which is the glass halfway up off the table.
        self.captured = 0
        self.lifted: np.ndarray | None = None
        # How many picks were drawn, and how many of those had to stop short
        # because the hand could not reach the glass from any side. Reported
        # when the film is saved, because whether it happens is a fact about
        # the table and not about the drawing.
        self.picks = self.stopped_short = 0
        self._pipe: subprocess.Popen | None = None
        self._file: Path | None = None
        self._capture()

    # ------------------------------------------------------------- what is shown

    def push(self, push: Push):
        self.doing = f"push {len(self.records) + 1}: glass {push.glass}, {1000 * push.travel:.0f} mm"
        self.note = ()
        return super().push(push)

    def take(self, glass: int) -> None:
        self.doing = f"take glass {glass}"
        # Drawing the pick is the bench's time, not the solution's. Every other
        # frame is captured inside an action, which is already charged.
        started = time.perf_counter()
        self._show_pick(glass)
        self.seconds += time.perf_counter() - started
        # The bench settles the table after a glass leaves it, and those frames
        # are filmed too. They are no longer the pick, so they do not say so.
        self.doing = f"glass {glass} taken"
        super().take(glass)

    # ------------------------------------------------------------- the drawn pick

    def _way_in(self, glass: int, opening: float) -> tuple[float, float]:
        """Which side to reach in from, and how far in the hand can get.

        The drawn hand is drawn and not simulated, so nothing stops it passing
        through a glass it is not holding. That would be a lie of exactly the
        kind these films exist to avoid, because a viewer would read it as the
        arm having somewhere to put its hand when it has not. So the way in is
        checked here instead, with the same geometry solution 1 uses to decide
        whether a push would drag the hand through a neighbour: the hand's
        silhouette as a list of stretches back from the fingertips, each against
        its own half width, swept along the approach.

        The hand is long — about 266 mm from fingertips to the back of the wrist
        — so whether a glass can be reached depends heavily on which side the
        hand comes from. Every side is tried, nearest the camera's own first so
        that the framing stays the same when it can. Returns the heading chosen
        and how far along the reach the hand can go, 1 being all the way in. A
        fraction below 1 means the hand stops where it would have touched
        something, which is what the film then draws.
        """
        here = self.position(glass)
        others = [
            (self.position(other), self.glasses[other].outline.max_diameter / 2)
            for other in self.on_table()
            if other != glass
        ]
        # The open hand, held level: each stretch's half width across the
        # approach, with the force sensor and wrist behind as one more stretch.
        parts = robotiq_2f85.jaw(robotiq_2f85.angle_for(opening))
        reach_back = max(p["back"] + p["depth"] for p in parts)
        stretches = [(p["back"], p["back"] + p["depth"], p["across"] / 2.0) for p in parts]
        stretches.append((reach_back, TOOL_LENGTH, WRIST_ACROSS / 2.0))
        pads = robotiq_2f85.pads(robotiq_2f85.angle_for(opening))[0]["back"]

        def reaches(heading: float, part: float) -> bool:
            u = np.array([math.cos(heading), math.sin(heading)])
            tip = here + u * pads - u * STAND_OFF * (1.0 - part)
            return all(
                segment_distance(centre, tip - far * u, tip - near * u) >= half + radius + CLEARANCE
                for centre, radius in others
                for near, far, half in stretches
            )

        ways = sorted(
            (PICK_HEADING + turn * 2.0 * math.pi / WAYS_IN for turn in range(WAYS_IN)),
            key=lambda heading: abs(math.remainder(heading - PICK_HEADING, 2.0 * math.pi)),
        )
        best = (PICK_HEADING, 0.0)
        for heading in ways:
            if reaches(heading, 1.0):
                return heading, 1.0
            got = max((k / 20.0 for k in range(21) if reaches(heading, k / 20.0)), default=0.0)
            best = max(best, (heading, got), key=lambda pair: pair[1])
        return best

    def _grip(self, glass: int) -> tuple[float, float]:
        """Where the drawn pick holds this glass, and how far apart the pads go.

        This is a stand-in and not problem 1's grip rule. Problem 1 chooses where
        to hold a glass from its shape, and on these glasses it usually chooses
        nothing at all: it comes in level and cannot reach below 50 mm, so it
        refuses most of what problem 3 leaves standing. That is a real and
        documented gap, and the-examiner.md counts it, but it is problem 1's gap
        rather than anything these films are about. Drawing it here would turn
        every pick in every film into a notice about another problem.

        So the drawing keeps problem 1's two bounds, because they decide what the
        hand can be drawn doing — no lower than the force sensor can go without
        meeting the table, and no higher than halfway up, which is where the
        fingers would foul the rack after the turn — and inside them it simply
        holds the glass where it can be seen. The width is this glass's own
        width there, measured rather than written down.
        """
        cuts = slices(self.glasses[glass].outline)
        top = max(high for _, high, _ in cuts)
        height = min(max(GRIP_FRACTION * top, LOWEST_GRIP), top / 2)
        inside = [cut for cut in cuts if cut[0] <= height <= cut[1]]
        cut = inside[0] if inside else min(cuts, key=lambda c: abs((c[0] + c[1]) / 2 - height))
        return height, 2.0 * cut[2]

    def _hold_hand(self, turn: float, angle: float) -> float:
        """Place every drawn piece for a knuckle angle and a quarter-turn of wrist.

        ``turn`` runs from 0, the hand rolled on its side as it pushes, to 1,
        the hand level as it grips. Returns how far the middle of the pads sits
        behind the fingertips, which is what the caller needs to put the pads on
        the glass rather than the fingertips.

        The pads come forward as the fingers close, by about 13 mm over the full
        stroke, because the fingers swing rather than slide. Nothing here corrects
        for that: the pieces are placed where the linkage puts them, so the arc is
        visible on film.
        """
        model = self.drawn_model
        rotation = _matrix(_slerp(ROLLED, LEVEL, turn))
        pieces = robotiq_2f85.parts(angle)
        pieces = pieces + robotiq_2f85.pads(angle) + [
            {
                "name": "wrist",
                "side": 0,
                "back": max(p["back"] + p["depth"] for p in pieces),
                "depth": WRIST_LENGTH,
                "offset": 0.0,
            }
        ]
        for piece in pieces:
            side = "left" if piece["side"] > 0 else "right" if piece["side"] < 0 else "middle"
            geom = self.drawn[f"drawn_{piece['name']}_{side}"]
            place = np.array([-(piece["back"] + piece["depth"] / 2.0), piece["offset"], 0.0])
            model.geom_pos[geom] = rotation @ place
            mujoco.mju_mat2Quat(model.geom_quat[geom], rotation.reshape(9))
        return robotiq_2f85.pads(angle)[0]["back"]

    def _show_pick(self, glass: int) -> None:
        """The hand rolls level, opens, reaches in around the glass and carries it off.

        Drawn on the second world: nothing here moves the scored one, and the
        pieces it moves are the ones no solution ever sees.
        """
        self._sync()
        model, world = self.drawn_model, self.drawn_data
        kept = model.geom_pos.copy(), model.geom_quat.copy(), model.geom_rgba.copy()
        # The collided shell means nothing here, because nothing is being
        # collided, and left on it would hang through the glass as a brick.
        model.geom_rgba[self.shell, 3] = 0.0
        self.note = tuple(
            textwrap.wrap(
                "drawn: the bench racks a glass in one instant, and problem 1 does "
                "the real pick",
                LINE_LENGTH,
            )
        )

        x, y = self.position(glass)
        address = model.jnt_qposadr[model.body_jntadr[self.bodies[glass]]]
        glass_start = world.qpos[address : address + 3].copy()
        height, width = self._grip(glass)
        # Held level, what the pads can close on is MAX_GRIP rather than the
        # full stroke: coming in from the side, the glass reaches back towards
        # the gripper's own body by its own width, and past about 80 mm it
        # touches. That is what grips_clear_of_the_palm answers.
        held = min(max(width, robotiq_2f85.MIN_OPENING), robotiq_2f85.MAX_GRIP)
        opened = min(width + GRIP_CLEARANCE, robotiq_2f85.MAX_OPENING)
        wide, shut = robotiq_2f85.angle_for(opened), robotiq_2f85.angle_for(held)

        was = self.data.mocap_quat[0].copy()
        turned = math.atan2(was[3], was[0]) * 2.0
        # Which side the hand comes from, and how far in it can get without
        # passing through a glass it is not holding.
        facing, got = self._way_in(glass, opened)
        self.picks += 1
        if got < 1.0:
            self.stopped_short += 1
            # Nothing closes, because the pads never arrive. The glass still
            # leaves the table, because the bench racked it, and the note is
            # there so that is not read as the hand having picked it up.
            held, shut = opened, wide
            self.note += tuple(
                textwrap.wrap(
                    "the hand cannot reach this glass from any side without touching "
                    "another, so it is drawn stopping where it would have",
                    LINE_LENGTH,
                )
            )
        # The hand comes in level, so the pads pass either side of the glass and
        # finish on its middle. It is placed by where its pads are rather than by
        # its fingertips, which reach further on than the pads do.
        along = np.array([math.cos(facing), math.sin(facing), 0.0])
        grip = np.array([x, y, TABLE_TOP_Z + height]) - along * STAND_OFF * (1.0 - got)
        beside = np.array([x, y, TABLE_TOP_Z + height]) - along * STAND_OFF
        over = np.array([*beside[:2], TABLE_TOP_Z + TRAVEL_HEIGHT])
        rack = np.array(
            [
                (RACK_AREA[0] + RACK_AREA[1]) / 2,
                (RACK_AREA[2] + RACK_AREA[3]) / 2,
                grip[2] + LIFT,
            ]
        )

        moves = list(PICK_MOVES)
        for move, length in PICK_MOVES.items():
            frames = max(1, round(length * FPS))
            for frame in range(1, frames + 1):
                part = frame / frames
                # The camera comes in as the wrist rolls and goes back out as
                # the glass is carried away, so it is never moving while the
                # fingers are doing something worth watching.
                close = part if move == moves[0] else 1.0 - part if move == moves[-1] else 1.0
                self._watch(np.array([x, y, TABLE_TOP_Z + PICK_RISE]), close)
                turn, angle, where = 1.0, wide, grip
                if move == "unrolling the wrist":
                    turn, where = part, PARK
                    angle = robotiq_2f85.angle_for(
                        robotiq_2f85.MIN_OPENING + part * (opened - robotiq_2f85.MIN_OPENING)
                    )
                elif move == "across to it":
                    where = PARK + (over - PARK) * part
                elif move == "down beside it":
                    where = over + (beside - over) * part
                elif move == "in around it":
                    where = beside + (grip - beside) * part
                elif move == "closing on it":
                    angle = robotiq_2f85.angle_for(opened + (held - opened) * part)
                elif move == "lifting":
                    angle, where = shut, grip + [0.0, 0.0, LIFT * part]
                else:
                    carry = grip + [0.0, 0.0, LIFT]
                    angle, where = shut, carry + (rack - carry) * part
                pads = self._hold_hand(turn, angle)
                heading = turned + (facing - turned) * turn
                world.mocap_pos[0] = where + along * pads
                world.mocap_quat[0] = [math.cos(heading / 2), 0.0, 0.0, math.sin(heading / 2)]
                if move in ("lifting", "to the rack"):
                    world.qpos[address : address + 3] = glass_start + (where - grip)
                mujoco.mj_forward(model, world)
                shot = self._capture(sync=False)
                # Halfway up, which is where a picture of a glass being picked
                # up reads best: the glass is clear of the table and still in
                # the frame. trace_table.py puts this one in its trace.
                if move == "lifting" and frame == max(1, frames // 2):
                    self.lifted = shot

        model.geom_pos[:], model.geom_quat[:], model.geom_rgba[:] = kept
        self._watch(np.zeros(3), 0.0)
        self.note = ()

    def _watch(self, glass: np.ndarray, close: float) -> None:
        """Ease the camera between the standing view and the close one on a pick.

        ``close`` is 0 for the view every push is filmed from and 1 for the view a
        drawn pick is filmed from. In between it is eased rather than run
        straight, so the move starts and stops gently.
        """
        lookat, distance, elevation = self.standing
        eased = close * close * (3.0 - 2.0 * close)
        self.camera.lookat[:] = lookat + (glass - lookat) * eased
        self.camera.distance = distance + (PICK_DISTANCE - distance) * eased
        self.camera.elevation = elevation + (PICK_ELEVATION - elevation) * eased

    # ------------------------------------------------------------------ recording

    def _step(self) -> None:
        super()._step()
        if self.renderer is None:
            return
        self.steps += 1
        if self.steps % self.every == 0:
            self._capture()

    def _sync(self) -> None:
        """Copy the scored world's positions into the drawn one. One way only."""
        self.drawn_data.qpos[:] = self.data.qpos
        self.drawn_data.mocap_pos[:] = self.data.mocap_pos
        self.drawn_data.mocap_quat[:] = self.data.mocap_quat
        mujoco.mj_forward(self.drawn_model, self.drawn_data)

    def view(self, sync: bool = True) -> np.ndarray:
        """The table as the film sees it now, with nothing written on it."""
        if sync:
            self._sync()
        self.renderer.update_scene(self.drawn_data, self.camera)
        return self.renderer.render()[:, :, ::-1].copy()

    def _capture(self, extra: str = "", sync: bool = True) -> np.ndarray:
        frame = self.view(sync)
        lines = [self.label, extra or self.doing, *self.note]
        for row, text in enumerate(lines):
            scale = 1.1 if row == 0 else 1.0
            place, font = (20, 46 + 44 * row), cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(frame, text, place, font, scale, (0, 0, 0), 7, cv2.LINE_AA)
            cv2.putText(frame, text, place, font, scale, (255, 255, 255), 2, cv2.LINE_AA)
        self._write(frame)
        return frame

    def _write(self, frame: np.ndarray) -> None:
        """Hand one frame to ffmpeg.

        Frames go out as they are made rather than being kept until the end. At
        this size a minute of film is several gigabytes of raw pixels, which is
        more than a machine should be asked to hold to save a video of it.
        """
        if self._pipe is None:
            self._file = Path(tempfile.mkdtemp(prefix="film-")) / "part.mp4"
            self._pipe = subprocess.Popen(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-f", "rawvideo", "-pix_fmt", "bgr24",
                    "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
                    "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
                    # Not every player will open a video whose colour is stored
                    # any other way, and these are meant to be opened from a
                    # document by whoever is reading it.
                    "-pix_fmt", "yuv420p", str(self._file),
                ],
                stdin=subprocess.PIPE,
            )
        self._pipe.stdin.write(frame.tobytes())
        self.captured += 1

    def save(self, path: Path, outcome: str = "") -> None:
        """Finish the video, holding the last picture with ``outcome`` on it."""
        self.note = ()
        for _ in range(int(HOLD * FPS)):
            self._capture(outcome)
        self._pipe.stdin.close()
        if self._pipe.wait() != 0:
            raise RuntimeError("ffmpeg could not write the film")
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(self._file, path)
        print(
            f"filmed {path.name}: {self.picks} picks drawn, "
            f"{self.stopped_short} of them stopping short for want of a way in"
        )
        shutil.rmtree(self._file.parent, ignore_errors=True)
        self.renderer.close()
