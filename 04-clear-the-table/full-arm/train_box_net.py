"""Train the box model and measure it: ``python train_box_net.py TRAIN.pkl TEST.pkl [epochs]``.

It is measured on pictures it was not trained on, against the simulator's own
sizes and positions: how many glasses it finds, how many boxes it invents, and
how far out the boxes are.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import arm_camera  # noqa: F401  (replaces the camera mounting)
import cell as C
import numpy as np
import seeing
import torch
from arm_bench import ArmBench
from build_box_data import view_joint_sets
from moveit_link import MESHES, generate_urdf

import tables

torch.set_num_threads(8)


def measure(model: seeing.BoxModel, examples: list[seeing.Example]) -> dict:
    """Match each detection to the nearest labelled glass, within 25 mm on the table."""
    found = missed = invented = 0
    errors = {"position_mm": [], "radius_mm": [], "height_mm": [], "foot_mm": []}
    joints = view_joint_sets()
    jaws = {}
    # Rebuild the camera pose of each view once; the pictures were taken from it.
    bench = ArmBench(0, tables.table(0), urdf=generate_urdf(), meshes=MESHES, start=joints[0])
    for view, q in zip(C.VIEWS, joints, strict=True):
        bench.set_joints(q)
        jaws[round(view.heading, 3)] = bench.tcp()
    for ex in examples:
        jaw = jaws[min(jaws, key=lambda h: abs(h - ex.heading))]
        picture = torch.from_numpy(ex.image).float() / 255.0
        # ``detect`` takes a full-size picture; the stored one is already shrunk, so feed it straight in.
        x = torch.cat([picture, seeing.view_channels(ex.heading)]).unsqueeze(0)
        with torch.no_grad():
            heat, offset, size = model.net(x)
        heat = heat.sigmoid()[0, 0]
        top = torch.nn.functional.max_pool2d(heat[None, None], 3, 1, 1)[0, 0]
        detections = []
        for iy, ix in torch.nonzero((heat == top) & (heat > model.THRESHOLD)).tolist():
            row = (iy + float(offset[0, 0, iy, ix])) * seeing.STRIDE * 2
            col = (ix + float(offset[0, 1, iy, ix])) * seeing.STRIDE * 2
            radius, height, foot = (size[0, :, iy, ix] * seeing.SIZE_SCALE).tolist()
            detections.append((*seeing.pixel_to_table(jaw, row, col), radius, height, foot))
        truth = [(*seeing.pixel_to_table(jaw, r, c), rad, h, f) for r, c, rad, h, f in ex.glasses]
        used = set()
        for d in detections:
            best, where = 1e9, None
            for k, t in enumerate(truth):
                gap = np.hypot(d[0] - t[0], d[1] - t[1])
                if k not in used and gap < best:
                    best, where = gap, k
            if where is not None and best < 0.025:
                used.add(where)
                t = truth[where]
                errors["position_mm"].append(1000 * best)
                errors["radius_mm"].append(1000 * (d[2] - t[2]))
                errors["height_mm"].append(1000 * (d[3] - t[3]))
                errors["foot_mm"].append(1000 * (d[4] - t[4]))
                found += 1
            else:
                invented += 1
        missed += len(truth) - len(used)
    total = found + missed
    summary = {
        "pictures": len(examples),
        "glasses": total,
        "found": found,
        "missed": missed,
        "invented": invented,
        "recall": found / max(total, 1),
        "precision": found / max(found + invented, 1),
    }
    for name, values in errors.items():
        a = np.array(values)
        summary[name] = {
            "median_abs": float(np.median(np.abs(a))),
            "mean": float(a.mean()),
            "p90_abs": float(np.percentile(np.abs(a), 90)),
        }
    return summary


if __name__ == "__main__":
    train_path, test_path = Path(sys.argv[1]), Path(sys.argv[2])
    epochs = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    out = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    train_set, test_set = seeing.load_examples(train_path), seeing.load_examples(test_path)
    print(f"{len(train_set)} training pictures, {len(test_set)} test pictures, {epochs} epochs", flush=True)
    started = time.perf_counter()
    net = seeing.train(train_set, test_set, epochs=epochs)
    model = seeing.BoxModel(net)
    model.save(out)
    result = measure(model, test_set)
    result["train_seconds"] = round(time.perf_counter() - started)
    result["train_pictures"] = len(train_set)
    print(json.dumps(result, indent=1))
