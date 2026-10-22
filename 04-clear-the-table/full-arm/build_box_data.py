"""Make the box model's pictures and answer keys: ``python build_box_data.py FIRST COUNT OUT``.

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

import arm_camera
import cell as C
import mujoco
import seeing
from arm_bench import ArmBench
from moveit_link import GENERATED, MESHES, generate_urdf

import tables
from partners import in_zone

VIEW_FILE = GENERATED / "views.json"


def view_joint_sets() -> list[list[float]]:
    """Joint angles of both viewing poses; see ``cell.view_joint_sets``."""
    return C.view_joint_sets()


def scatter(bench: ArmBench, rng: random.Random) -> None:
    """Put the glasses at random places in the zone, none touching another."""
    placed: list[tuple[float, float, float]] = []
    for i, glass in enumerate(bench.glasses):
        width = glass.outline.max_diameter
        for _ in range(300):
            x = rng.uniform(0.32, 0.64)
            y = rng.uniform(-0.44, -0.08)
            if in_zone(x, y) and all(
                math.dist((x, y), (qx, qy)) > (width + qw) / 2 + 0.004 for qx, qy, qw in placed
            ):
                placed.append((x, y, width))
                address = bench.model.jnt_qposadr[bench.model.body_jntadr[bench.bodies[i]]]
                bench.data.qpos[address : address + 3] = [x, y, bench.data.qpos[address + 2]]
                break
    bench.data.qvel[:] = 0.0
    mujoco.mj_forward(bench.model, bench.data)
    bench._settle()


def build(first: int, count: int, scattered: bool = True) -> list[seeing.Example]:
    joints = view_joint_sets()
    urdf = generate_urdf()
    out: list[seeing.Example] = []
    started = time.perf_counter()
    for k, seed in enumerate(range(first, first + count)):
        for variant in (0, 1) if scattered else (0,):
            bench = ArmBench(seed, tables.table(seed), urdf=urdf, meshes=MESHES, start=joints[0])
            if variant:
                scatter(bench, random.Random(seed * 7 + 1))
            camera = arm_camera.ArmCamera(bench)
            for q in joints:
                bench.set_joints(q)
                jaw = bench.tcp()
                out.append(seeing.example(camera.view(jaw), jaw, bench))
            camera.close()
        if (k + 1) % 25 == 0:
            print(
                f"  {k + 1}/{count} tables, {len(out)} pictures, {time.perf_counter() - started:.0f} s",
                flush=True,
            )
    return out


if __name__ == "__main__":
    first, count, out = int(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    seeing.save_examples(build(first, count), out)
    print("wrote", out)
