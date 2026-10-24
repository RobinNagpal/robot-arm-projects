"""Film a solution clearing tables with the whole arm.

``python film_solution.py SOLUTION --first 10004 --tables 1``

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

import av
import cv2
import mujoco
import numpy as np

from examiner.examining.table_examiner import ARM_SECONDS_FOR_TABLE_LIST, SimulatedExaminer
from examiner.motion.moveit_connection import MoveItConnection
from examiner.tools.evaluate_solution import SOLUTIONS

FILM_SIZE = (720, 1080)  # rows, columns
FPS = 30
SPEED = 3.0
FILMS_FOLDER = Path(__file__).resolve().parents[2] / "videos"


class SideCamera:
    def __init__(self, simulator) -> None:
        # The world's offscreen buffer is 640 by 480 unless it is told otherwise.
        simulator.model.vis.global_.offheight, simulator.model.vis.global_.offwidth = FILM_SIZE
        self.renderer = mujoco.Renderer(simulator.model, *FILM_SIZE)
        self.free_camera = mujoco.MjvCamera()
        self.free_camera.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.free_camera.lookat[:] = (0.42, -0.24, 0.90)
        self.free_camera.distance = 1.55
        self.free_camera.azimuth = 128.0
        self.free_camera.elevation = -24.0

    def render_frame(self, simulator) -> np.ndarray:
        self.renderer.update_scene(simulator.data, self.free_camera)
        return self.renderer.render().copy()


class FilmWriter:
    def __init__(self, film_file: Path, title: str) -> None:
        film_file.parent.mkdir(parents=True, exist_ok=True)
        self.container = av.open(str(film_file), "w")
        self.stream = self.container.add_stream("libx264", rate=FPS)
        self.stream.width, self.stream.height, self.stream.pix_fmt = FILM_SIZE[1], FILM_SIZE[0], "yuv420p"
        self.stream.options = {"crf": "26"}
        self.title = title
        self.status_line = ""
        self.frames = 0

    def write(self, picture: np.ndarray, extra_text: str = "") -> None:
        picture = np.ascontiguousarray(picture)
        for text, baseline, text_scale in ((self.title, 36, 0.9), (self.status_line + extra_text, 72, 0.7)):
            cv2.putText(
                picture,
                text,
                (24, baseline),
                cv2.FONT_HERSHEY_SIMPLEX,
                text_scale,
                (20, 20, 20),
                4,
                cv2.LINE_AA,
            )
            cv2.putText(
                picture,
                text,
                (24, baseline),
                cv2.FONT_HERSHEY_SIMPLEX,
                text_scale,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
        frame = av.VideoFrame.from_ndarray(picture, format="rgb24")
        for packet in self.stream.encode(frame):
            self.container.mux(packet)
        self.frames += 1

    def close(self) -> None:
        for packet in self.stream.encode():
            self.container.mux(packet)
        self.container.close()


def film_one_table(
    solution, table_number: int, moveit, film_writer: FilmWriter, arm_seconds_given: float
) -> None:
    physics_steps_per_frame = max(1, round(SPEED / (FPS * 0.002)))
    counter = {"steps": 0}
    watched = {}

    def watch_attempt(attempt) -> None:
        cell = SimulatedExaminer.cell_behind_attempt(attempt)
        camera = SideCamera(cell.simulator)
        watched.update(cell=cell, camera=camera)

        def film_frame(simulator) -> None:
            counter["steps"] += 1
            if counter["steps"] % physics_steps_per_frame == 0:
                film_writer.write(
                    camera.render_frame(simulator),
                    f"   arm time {simulator.arm_seconds:5.0f} s   glasses the gripper could pick: "
                    f"{cell.pickable_glass_count()} of {cell.glass_count()}",
                )

        cell.simulator.after_each_physics_step.append(film_frame)

    film_writer.status_line = f"table {table_number}"
    result = SimulatedExaminer(moveit, arm_seconds_given).run_solution_on_table(
        solution, table_number, prepare=watch_attempt
    )
    # The last picture is held for two seconds, with what happened.
    ending = (
        f"   {result.pickable_at_start} -> {result.pickable_at_end} of {result.glass_count} pickable, "
        f"{result.ended_by}"
    )
    # A table can end because a glass went over, and then ``ended_by`` already says so.
    if result.glasses_toppled and "went over" not in result.ended_by:
        ending += f", {result.glasses_toppled} glass went over"
    print(f"table {table_number}:{ending}", flush=True)
    last_picture = watched["camera"].render_frame(watched["cell"].simulator)
    for _ in range(2 * FPS):
        film_writer.write(last_picture.copy(), ending)


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
    arguments = parser.parse_args()
    module_name, factory_name = SOLUTIONS[arguments.solution]
    make_solution = getattr(importlib.import_module(module_name), factory_name)
    solution = make_solution(arguments.weights) if arguments.weights else make_solution()
    table_numbers = (
        [int(number) for number in arguments.seeds.split(",")]
        if arguments.seeds
        else list(range(arguments.first, arguments.first + arguments.tables))
    )
    name = arguments.name or f"{arguments.solution}-{len(table_numbers)}-tables"
    film_file = FILMS_FOLDER / f"{name}.mp4"
    film_writer = FilmWriter(film_file, f"{solution.name}")
    with MoveItConnection() as moveit:
        for table_number in table_numbers:
            film_one_table(solution, table_number, moveit, film_writer, ARM_SECONDS_FOR_TABLE_LIST)
    film_writer.close()
    print("wrote", film_file, f"{film_writer.frames / FPS:.0f} s")


if __name__ == "__main__":
    main()
