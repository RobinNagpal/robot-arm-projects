"""Film a table being cleared, to check by eye what the hand did.

A bench that also records a video. It changes nothing about the physics, and it
cannot: the table is scored in the world the bench builds, and everything here
is drawn in a second world of its own. Written the way
07-learn-pick-place/pick_place/video.py films an episode, with MuJoCo's
offscreen renderer, so it needs no window and no mjpython.

Shared by every problem that pushes glasses. Each problem's own ``film.py``
extends ``CommonFilmedBench`` with what its films show: problem 3 draws a pick
when a glass is racked, and problem 4 puts the arm's own picture in a corner.

**The hand is drawn twice.** The bench collides a simplified hand: each pair of
fingers is one box covering both fingers and the 82 mm gap between them, which
is the safe assumption for a push, because a glass standing in that gap would
be swept along just the same. The film draws the real pieces solid and that
larger collided shape as a faint shell around them, so a viewer can see both the
hand and the volume the simulator treats as solid.

**A copy of this file must stay exactly as it is here**, for the reason
``common_bench.py`` gives.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import mujoco
import numpy as np
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import TABLE_TOP_Z

from common_bench import TIMESTEP, CommonBench

WIDTH, HEIGHT = 1280, 960
FPS = 30
# The film runs this many times faster than the physics. The hand feels forward
# at 10 mm/s, which is too slow to watch at life size and too fast to follow at
# three times life size, which is what these films used to run at.
SPEED = 1.5
# The last picture is held this long, with the outcome on it.
HOLD = 2.0
# How many characters of a line fit across the picture, at the size the writing
# is drawn. A long note, such as a refusal, is a whole sentence and has to be
# broken over several lines rather than run off the edge.
LINE_LENGTH = 62


class CommonFilmedBench(CommonBench):
    """A bench that writes a video of what it did. Identical to the bench it extends otherwise.

    A problem films its own bench by extending both, with this class first:
    ``class FilmedBench(CommonFilmedBench, Bench)``. Then the table is built by
    that problem's ``Bench``, and every step of its physics is filmed here.
    """

    def __init__(self, seed: int, approach: str = "", glasses: list | None = None) -> None:
        self.renderer = None
        super().__init__(seed, glasses)
        # A second world, with the real hand drawn in it. Nothing is ever
        # stepped here: every frame copies the scored world's positions across
        # and this one is only looked at. See CommonBench.world_xml.
        self.drawn_model = mujoco.MjModel.from_xml_string(self.world_xml(draw_hand=True))
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
        # Kept, so that anything that moves the camera can put it back.
        self.standing = (self.camera.lookat.copy(), 0.9, -55.0)
        self.camera.distance, self.camera.elevation = self.standing[1], self.standing[2]
        self.every = max(1, round(SPEED / (FPS * TIMESTEP)))
        self.steps = 0
        self.label = self.film_label(seed, approach)
        self.doing = "first look"
        self.note: tuple[str, ...] = ()
        # How many frames have been written.
        self.captured = 0
        self._pipe: subprocess.Popen | None = None
        self._file: Path | None = None
        self._capture()

    def film_label(self, seed: int, approach: str) -> str:
        """The top line of every frame: which solution, and which table."""
        return f"{approach}  table {seed}".strip()

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
        print(f"filmed {path.name}{self.saved_note()}")
        shutil.rmtree(self._file.parent, ignore_errors=True)
        self.renderer.close()

    def saved_note(self) -> str:
        """Anything worth printing beside the film's name when it is saved."""
        return ""
