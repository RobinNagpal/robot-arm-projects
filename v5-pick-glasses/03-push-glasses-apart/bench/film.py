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
the glass vanishing. So the film draws what a real pick-up is: the wrist turns
the hand upright, the fingers open to the width the glass was measured to be,
the hand comes down around it, the fingers close, and the glass is carried off.
That is drawn on a copy of the world and never stepped, so the physics, and
every result, are the same filmed or not. ``test_bench.py`` checks it.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import cv2
import mujoco
import numpy as np
from work_cell.arm import robotiq_2f85
from work_cell.rack.layout import GLASS_ZONE, RACK_AREA
from work_cell.table.layout import TABLE_TOP_Z

from bench import (
    KINDS,
    TIMESTEP,
    TRAVEL_HEIGHT,
    WRIST_LENGTH,
    Bench,
    Push,
    drawing_world,
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
    "turning the wrist upright": 0.5,
    "over the glass": 0.6,
    "down around it": 0.5,
    "closing on it": 0.4,
    "lifting": 0.4,
    "to the rack": 0.7,
}
# How high a taken glass is lifted before it is carried off.
LIFT = 0.25
# Where up the glass the pads are put, as a fraction of the glass's own height.
# A fraction rather than a height, because no glass's size may be written down
# anywhere in this project. Where a real grip would go is problem 1's business
# and is decided from the glass's shape; this only has to look right.
GRIP_FRACTION = 0.45
# How much wider than the glass the fingers open before coming down around it.
GRIP_CLEARANCE = 0.030

# The two ways the hand is held, as quaternions. Pushing, it is rolled a quarter
# turn about the approach so the fingers stack one above the other and the hand
# is only 27 mm wide. Picking, it points straight down with the fingers opening
# sideways. A pick begins by turning from the first to the second, which is a
# real cost of pushing with a gripper and is worth seeing.
ROLLED = np.array([math.cos(math.pi / 4), math.sin(math.pi / 4), 0.0, 0.0])
POINTING_DOWN = np.array([math.cos(math.pi / 4), 0.0, math.sin(math.pi / 4), 0.0])
# The hand is turned to face this way for a drawn pick. The camera looks along
# the table's x axis, so fingers opening along y are seen from the side, which
# is the one direction from which both fingers and the gap are visible.
PICK_HEADING = 0.0
# Where the camera goes to watch a drawn pick: closer, and much less steeply
# down. From the standing view the gripper's own body is between the camera and
# the glass, so the one thing the pick is there to show would be hidden behind
# it. The camera eases in as the wrist turns and eases out as the glass is
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

    def __init__(self, seed: int, approach: str = "") -> None:
        self.renderer = None
        super().__init__(seed)
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
        self.note = ""
        # How many frames have been written, and the one frame from a pick
        # worth keeping, which is the glass halfway up off the table.
        self.captured = 0
        self.lifted: np.ndarray | None = None
        self._pipe: subprocess.Popen | None = None
        self._file: Path | None = None
        self._capture()

    # ------------------------------------------------------------- what is shown

    def push(self, push: Push):
        self.doing = f"push {len(self.records) + 1}: glass {push.glass}, {1000 * push.travel:.0f} mm"
        self.note = ""
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

    def _grip(self, glass: int) -> tuple[float, float]:
        """How high up the glass the pads go, and how far apart they must be.

        Both come from the glass standing in front of the arm rather than from a
        table of sizes, which is the rule the whole project is built on. The
        height is a fraction of this glass's own height, and the width is how wide
        this glass is at that height.

        The fraction alone is not enough, because the fingers are only so long.
        Between the pads and the palm behind them there is about 35 mm, so a glass
        held low enough would have its rim inside the gripper's body, which cannot
        happen and would look wrong on film. Whichever is higher wins: the
        fraction, or the lowest hold that leaves the rim clear of the palm. On a
        tall glass that is the palm, and the hand takes it near the top.
        """
        cuts = slices(self.glasses[glass].outline)
        top = max(high for _, high, _ in cuts)
        body = next(p for p in robotiq_2f85.parts() if p["name"] == "body")["back"]
        clear = body - robotiq_2f85.pads()[0]["back"] - robotiq_2f85.PALM_CLEARANCE
        height = min(max(GRIP_FRACTION * top, top - clear), top)
        radius = min(cuts, key=lambda cut: abs((cut[0] + cut[1]) / 2 - height))[2]
        return height, 2.0 * radius

    def _hold_hand(self, turn: float, angle: float) -> float:
        """Place every drawn piece for a knuckle angle and a quarter-turn of wrist.

        ``turn`` runs from 0, the hand rolled on its side as it pushes, to 1,
        the hand upright as it picks. Returns how far the middle of the pads sits
        behind the fingertips, which is what the caller needs to put the pads on
        the glass rather than the fingertips.

        The pads come forward as the fingers close, by about 13 mm over the full
        stroke, because the fingers swing rather than slide. Nothing here corrects
        for that: the pieces are placed where the linkage puts them, so the arc is
        visible on film.
        """
        model = self.drawn_model
        rotation = _matrix(_slerp(ROLLED, POINTING_DOWN, turn))
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
        """The hand turns upright, opens, comes down around the glass and carries it off.

        Drawn on the second world: nothing here moves the scored one, and the
        pieces it moves are the ones no solution ever sees.
        """
        self._sync()
        model, world = self.drawn_model, self.drawn_data
        kept = model.geom_pos.copy(), model.geom_quat.copy(), model.geom_rgba.copy()
        # The collided shell means nothing here, because nothing is being
        # collided, and left on it would hang through the glass as a brick.
        model.geom_rgba[self.shell, 3] = 0.0
        self.note = "drawn: the bench racks a glass in one instant"

        x, y = self.position(glass)
        address = model.jnt_qposadr[model.body_jntadr[self.bodies[glass]]]
        glass_start = world.qpos[address : address + 3].copy()
        height, width = self._grip(glass)
        held = min(max(width, robotiq_2f85.MIN_OPENING), robotiq_2f85.MAX_GRIP)
        opened = min(width + GRIP_CLEARANCE, robotiq_2f85.MAX_OPENING)
        wide, shut = robotiq_2f85.angle_for(opened), robotiq_2f85.angle_for(held)

        was = self.data.mocap_quat[0].copy()
        turned = math.atan2(was[3], was[0]) * 2.0
        # Where the pads must finish, which is what the hand is placed by. The
        # fingertips reach past the pads, so they end up lower than this.
        on_the_glass = TABLE_TOP_Z + height
        over = np.array([x, y, TABLE_TOP_Z + TRAVEL_HEIGHT])
        down = np.array([x, y, on_the_glass])

        moves = list(PICK_MOVES)
        for move, length in PICK_MOVES.items():
            frames = max(1, round(length * FPS))
            for frame in range(1, frames + 1):
                part = frame / frames
                # The camera comes in as the wrist turns and goes back out as
                # the glass is carried away, so it is never moving while the
                # fingers are doing something worth watching.
                close = part if move == moves[0] else 1.0 - part if move == moves[-1] else 1.0
                self._watch(np.array([x, y, TABLE_TOP_Z + PICK_RISE]), close)
                turn, angle, where = 1.0, wide, down
                if move == "turning the wrist upright":
                    turn, where = part, PARK
                    angle = robotiq_2f85.angle_for(
                        robotiq_2f85.MIN_OPENING + part * (opened - robotiq_2f85.MIN_OPENING)
                    )
                elif move == "over the glass":
                    where = PARK + (over - PARK) * part
                elif move == "down around it":
                    where = over + (down - over) * part
                elif move == "closing on it":
                    angle = robotiq_2f85.angle_for(opened + (held - opened) * part)
                elif move == "lifting":
                    angle, where = shut, down + [0.0, 0.0, LIFT * part]
                else:
                    rack = np.array(
                        [
                            (RACK_AREA[0] + RACK_AREA[1]) / 2,
                            (RACK_AREA[2] + RACK_AREA[3]) / 2,
                            on_the_glass + LIFT,
                        ]
                    )
                    carry = down + [0.0, 0.0, LIFT]
                    angle, where = shut, carry + (rack - carry) * part
                # The hand is placed by where its pads are rather than by where
                # its fingertips are, so the pads land on the glass. They creep
                # forward as the fingers close, which lifts the hand a little.
                pads = self._hold_hand(turn, angle)
                heading = turned + (PICK_HEADING - turned) * turn
                world.mocap_pos[0] = where - [0.0, 0.0, pads]
                world.mocap_quat[0] = [math.cos(heading / 2), 0.0, 0.0, math.sin(heading / 2)]
                if move in ("lifting", "to the rack"):
                    world.qpos[address : address + 3] = glass_start + (where - down)
                mujoco.mj_forward(model, world)
                shot = self._capture(sync=False)
                # Halfway up, which is where a picture of a glass being picked
                # up reads best: the glass is clear of the table and still in
                # the frame. trace_table.py puts this one in its trace.
                if move == "lifting" and frame == max(1, frames // 2):
                    self.lifted = shot

        model.geom_pos[:], model.geom_quat[:], model.geom_rgba[:] = kept
        self._watch(np.zeros(3), 0.0)
        self.note = ""

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
        lines = [self.label, extra or self.doing] + ([self.note] if self.note else [])
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
        self.note = ""
        for _ in range(int(HOLD * FPS)):
            self._capture(outcome)
        self._pipe.stdin.close()
        if self._pipe.wait() != 0:
            raise RuntimeError("ffmpeg could not write the film")
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(self._file, path)
        shutil.rmtree(self._file.parent, ignore_errors=True)
        self.renderer.close()
