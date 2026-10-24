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

from examiner.examining import one_table_cell
from examiner.motion.moveit_connection import ARM_COLLISION_MESHES, write_arm_urdf_if_missing
from examiner.simulation import table_draw, wrist_camera
from examiner.simulation.arm_and_table_simulator import ArmAndTableSimulator
from examiner.simulation.taken_from_problem_3 import in_zone
from shared.seeing import box_model


def scatter_glasses_at_random(simulator: ArmAndTableSimulator, rng: random.Random) -> None:
    """Put the glasses at random places in the zone, none touching another."""
    placed: list[tuple[float, float, float]] = []
    for i, glass in enumerate(simulator.glasses):
        width = glass.outline.max_diameter
        for _ in range(300):
            x = rng.uniform(0.32, 0.64)
            y = rng.uniform(-0.44, -0.08)
            if in_zone(x, y) and all(
                math.dist((x, y), (other_x, other_y)) > (width + other_width) / 2 + 0.004
                for other_x, other_y, other_width in placed
            ):
                placed.append((x, y, width))
                address = simulator.model.jnt_qposadr[simulator.model.body_jntadr[simulator.bodies[i]]]
                simulator.data.qpos[address : address + 3] = [x, y, simulator.data.qpos[address + 2]]
                break
    simulator.data.qvel[:] = 0.0
    mujoco.mj_forward(simulator.model, simulator.data)
    simulator._settle()


def make_training_examples(
    first_table: int, table_count: int, also_scattered: bool = True
) -> list[box_model.BoxTrainingExample]:
    both_views = one_table_cell.viewing_joint_angles()
    urdf = write_arm_urdf_if_missing()
    examples: list[box_model.BoxTrainingExample] = []
    started = time.perf_counter()
    for done, seed in enumerate(range(first_table, first_table + table_count)):
        for scatter_this_one in (0, 1) if also_scattered else (0,):
            simulator = ArmAndTableSimulator(
                seed,
                table_draw.draw_table(seed),
                urdf=urdf,
                meshes=ARM_COLLISION_MESHES,
                start_joint_angles=both_views[0],
            )
            if scatter_this_one:
                scatter_glasses_at_random(simulator, random.Random(seed * 7 + 1))
            camera = wrist_camera.WristCameraRenderer(simulator)
            for view_joint_angles in both_views:
                simulator.set_joint_angles(view_joint_angles)
                hand = simulator.fingertips_waypoint()
                examples.append(box_model.make_training_example(camera.render_picture(hand), hand, simulator))
            camera.close()
        if (done + 1) % 25 == 0:
            print(
                f"  {done + 1}/{table_count} tables, {len(examples)} pictures, "
                f"{time.perf_counter() - started:.0f} s",
                flush=True,
            )
    return examples


if __name__ == "__main__":
    first_table, table_count, output_file = int(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    box_model.save_training_examples(make_training_examples(first_table, table_count), output_file)
    print("wrote", output_file)
