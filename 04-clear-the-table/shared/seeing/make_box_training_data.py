"""Make the box model's pictures and answer keys: ``python make_box_training_data.py FIRST COUNT OUT``.

Each table is photographed from both viewing places, once as drawn and, for some,
once with the glasses scattered at random, because the tables the arm meets later
in a run are not the tables as drawn: they are tables with a glass pushed.
"""

from __future__ import annotations

import math
import random
import sys
import time
from pathlib import Path

import mujoco

from examiner.examining import one_table_cell as C
from examiner.motion.moveit_connection import MESHES, generate_urdf
from examiner.simulation import table_draw, wrist_camera
from examiner.simulation.arm_and_table_simulator import ArmSimulator
from examiner.simulation.taken_from_problem_3 import in_zone
from shared.seeing import box_model


def scatter(simulator: ArmSimulator, rng: random.Random) -> None:
    """Put the glasses at random places in the zone, none touching another."""
    placed: list[tuple[float, float, float]] = []
    for i, glass in enumerate(simulator.glasses):
        width = glass.outline.max_diameter
        for _ in range(300):
            x = rng.uniform(0.32, 0.64)
            y = rng.uniform(-0.44, -0.08)
            if in_zone(x, y) and all(
                math.dist((x, y), (qx, qy)) > (width + qw) / 2 + 0.004 for qx, qy, qw in placed
            ):
                placed.append((x, y, width))
                address = simulator.model.jnt_qposadr[simulator.model.body_jntadr[simulator.bodies[i]]]
                simulator.data.qpos[address : address + 3] = [x, y, simulator.data.qpos[address + 2]]
                break
    simulator.data.qvel[:] = 0.0
    mujoco.mj_forward(simulator.model, simulator.data)
    simulator._settle()


def build(first: int, count: int, scattered: bool = True) -> list[box_model.Example]:
    joints = C.view_joint_sets()
    urdf = generate_urdf()
    out: list[box_model.Example] = []
    started = time.perf_counter()
    for k, seed in enumerate(range(first, first + count)):
        for variant in (0, 1) if scattered else (0,):
            simulator = ArmSimulator(seed, table_draw.table(seed), urdf=urdf, meshes=MESHES, start=joints[0])
            if variant:
                scatter(simulator, random.Random(seed * 7 + 1))
            camera = wrist_camera.ArmCamera(simulator)
            for q in joints:
                simulator.set_joints(q)
                jaw = simulator.tcp()
                out.append(box_model.example(camera.view(jaw), jaw, simulator))
            camera.close()
        if (k + 1) % 25 == 0:
            print(
                f"  {k + 1}/{count} tables, {len(out)} pictures, {time.perf_counter() - started:.0f} s",
                flush=True,
            )
    return out


if __name__ == "__main__":
    first, count, out = int(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    box_model.save_examples(build(first, count), out)
    print("wrote", out)
