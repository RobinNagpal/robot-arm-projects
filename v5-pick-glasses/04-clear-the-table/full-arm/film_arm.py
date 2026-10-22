"""Film a solution clearing tables with the whole arm.

``python film_arm.py SOLUTION --first 10004 --tables 1``

The picture is the cell as it is: the UR5e, the table, the glasses, in the physics engine, from
a fixed camera at the side. Every frame is rendered from a step of the real run, as it happens,
so nothing in the film is replayed or drawn on top: the arm is where the physics says it is.
The words on the film say what the solution is and what the table looked like at the start and
at the end, and the arm time spent so far.

The run is real, which means a table is filmed at the speed it was carried out and then sped up
``SPEED`` times, since a push takes about ten seconds of arm time.
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path

import arm_camera  # noqa: F401
import av
import cv2
import mujoco
import numpy as np
from evaluate import SOLUTIONS
from examiner import ARM_BUDGET, SimExaminer
from moveit_link import MoveItLink

SIZE = (720, 1080)  # rows, columns
FPS = 30
SPEED = 3.0
FILMS = Path(__file__).resolve().parents[2] / "videos" / "04-clear-the-table" / "full-arm"


class Camera:
    def __init__(self, bench) -> None:
        # The world's offscreen buffer is 640 by 480 unless it is told otherwise.
        bench.model.vis.global_.offheight, bench.model.vis.global_.offwidth = SIZE
        self.renderer = mujoco.Renderer(bench.model, *SIZE)
        self.view = mujoco.MjvCamera()
        self.view.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.view.lookat[:] = (0.42, -0.24, 0.90)
        self.view.distance = 1.55
        self.view.azimuth = 128.0
        self.view.elevation = -24.0

    def frame(self, bench) -> np.ndarray:
        self.renderer.update_scene(bench.data, self.view)
        return self.renderer.render().copy()


class Film:
    def __init__(self, path: Path, title: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.container = av.open(str(path), "w")
        self.stream = self.container.add_stream("libx264", rate=FPS)
        self.stream.width, self.stream.height, self.stream.pix_fmt = SIZE[1], SIZE[0], "yuv420p"
        self.stream.options = {"crf": "26"}
        self.title = title
        self.line = ""
        self.frames = 0

    def write(self, picture: np.ndarray, extra: str = "") -> None:
        picture = np.ascontiguousarray(picture)
        for text, y, scale in ((self.title, 36, 0.9), (self.line + extra, 72, 0.7)):
            cv2.putText(picture, text, (24, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (20, 20, 20), 4, cv2.LINE_AA)
            cv2.putText(
                picture, text, (24, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 2, cv2.LINE_AA
            )
        frame = av.VideoFrame.from_ndarray(picture, format="rgb24")
        for packet in self.stream.encode(frame):
            self.container.mux(packet)
        self.frames += 1

    def close(self) -> None:
        for packet in self.stream.encode():
            self.container.mux(packet)
        self.container.close()


def film_table(solution, seed: int, link, film: Film, left: float) -> None:
    stride = max(1, round(SPEED / (FPS * 0.002)))
    count = {"steps": 0}
    watched = {}

    def watch(run) -> None:
        cell = SimExaminer.cell_of(run)
        camera = Camera(cell.bench)
        watched.update(cell=cell, camera=camera)

        def hook(bench) -> None:
            count["steps"] += 1
            if count["steps"] % stride == 0:
                film.write(
                    camera.frame(bench),
                    f"   arm time {bench.arm_seconds:5.0f} s   glasses the gripper could pick: "
                    f"{cell.pickable()} of {cell.glasses()}",
                )

        cell.bench.hooks.append(hook)

    film.line = f"table {seed}"
    result = SimExaminer(link, left).run(solution, seed, prepare=watch)
    # The last picture is held for two seconds, with what happened.
    end = (
        f"   {result.separated_at_start} -> {result.separated_at_end} of {result.glasses} pickable, "
        f"{result.ended_by}"
    )
    # A table can end because a glass went over, and then ``ended_by`` already says so.
    if result.fell_over and "went over" not in result.ended_by:
        end += f", {result.fell_over} glass went over"
    print(f"table {seed}:{end}", flush=True)
    last = watched["camera"].frame(watched["cell"].bench)
    for _ in range(2 * FPS):
        film.write(last.copy(), end)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("solution", choices=sorted(SOLUTIONS))
    parser.add_argument("--first", type=int, default=10311)
    parser.add_argument("--tables", type=int, default=1)
    parser.add_argument(
        "--seeds", default=None, help="table numbers, comma-separated, instead of --first/--tables"
    )
    parser.add_argument("--weights", type=Path, default=None)
    parser.add_argument("--name", default=None)
    a = parser.parse_args()
    module, cls = SOLUTIONS[a.solution]
    factory = getattr(importlib.import_module(module), cls)
    solution = factory(a.weights) if a.weights else factory()
    seeds = [int(x) for x in a.seeds.split(",")] if a.seeds else list(range(a.first, a.first + a.tables))
    name = a.name or f"{a.solution}-{len(seeds)}-tables"
    path = FILMS / f"{name}.mp4"
    film = Film(path, f"{solution.name}")
    with MoveItLink() as link:
        for seed in seeds:
            film_table(solution, seed, link, film, ARM_BUDGET)
    film.close()
    print("wrote", path, f"{film.frames / FPS:.0f} s")


if __name__ == "__main__":
    main()
