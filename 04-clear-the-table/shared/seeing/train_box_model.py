"""Train the box model and measure it: ``python train_box_model.py TRAIN.pkl TEST.pkl [epochs]``.

It is measured on pictures it was not trained on, against the simulator's own
sizes and positions: how many glasses it finds, how many boxes it invents, and
how far out the boxes are.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

from examiner.examining import one_table_cell
from examiner.examining.one_table_cell import viewing_joint_angles
from examiner.motion.moveit_connection import ARM_COLLISION_MESHES, write_arm_urdf_if_missing
from examiner.simulation import table_draw
from examiner.simulation.arm_and_table_simulator import ArmAndTableSimulator
from shared.seeing import box_model

torch.set_num_threads(8)


def measure_box_model(model: box_model.BoxModel, examples: list[box_model.BoxTrainingExample]) -> dict:
    """Match each detection to the nearest labelled glass, within 25 mm on the table."""
    found = missed = invented = 0
    errors = {"position_mm": [], "radius_mm": [], "height_mm": [], "foot_mm": []}
    both_views = viewing_joint_angles()
    hand_by_heading = {}
    # Rebuild the camera pose of each view once; the pictures were taken from it.
    simulator = ArmAndTableSimulator(
        0,
        table_draw.draw_table(0),
        urdf=write_arm_urdf_if_missing(),
        meshes=ARM_COLLISION_MESHES,
        start_joint_angles=both_views[0],
    )
    for view, view_joint_angles in zip(one_table_cell.VIEW_WAYPOINTS, both_views, strict=True):
        simulator.set_joint_angles(view_joint_angles)
        hand_by_heading[round(view.heading, 3)] = simulator.fingertips_waypoint()
    for example in examples:
        hand = hand_by_heading[min(hand_by_heading, key=lambda heading: abs(heading - example.heading))]
        picture = torch.from_numpy(example.image).float() / 255.0
        # ``boxes_in_picture`` takes a full-size picture; the stored one is already shrunk, so it is
        # fed to the network straight.
        network_input = torch.cat([picture, box_model.camera_heading_planes(example.heading)]).unsqueeze(0)
        with torch.no_grad():
            heat, offset, size = model.network(network_input)
        heat = heat.sigmoid()[0, 0]
        neighbourhood_peak = torch.nn.functional.max_pool2d(heat[None, None], 3, 1, 1)[0, 0]
        detections = []
        for cell_row, cell_column in torch.nonzero(
            (heat == neighbourhood_peak) & (heat > model.PEAK_THRESHOLD)
        ).tolist():
            row = (cell_row + float(offset[0, 0, cell_row, cell_column])) * box_model.PIXELS_PER_GRID_CELL * 2
            column = (
                (cell_column + float(offset[0, 1, cell_row, cell_column]))
                * box_model.PIXELS_PER_GRID_CELL
                * 2
            )
            radius, height, foot = (size[0, :, cell_row, cell_column] * box_model.SIZE_UNITS).tolist()
            detections.append((*box_model.pixel_to_table(hand, row, column), radius, height, foot))
        true_glasses = [
            (*box_model.pixel_to_table(hand, row, column), radius, height, foot)
            for row, column, radius, height, foot in example.glasses
        ]
        matched = set()
        for detection in detections:
            nearest, nearest_index = 1e9, None
            for index, truth_glass in enumerate(true_glasses):
                distance = np.hypot(detection[0] - truth_glass[0], detection[1] - truth_glass[1])
                if index not in matched and distance < nearest:
                    nearest, nearest_index = distance, index
            if nearest_index is not None and nearest < 0.025:
                matched.add(nearest_index)
                truth_glass = true_glasses[nearest_index]
                errors["position_mm"].append(1000 * nearest)
                errors["radius_mm"].append(1000 * (detection[2] - truth_glass[2]))
                errors["height_mm"].append(1000 * (detection[3] - truth_glass[3]))
                errors["foot_mm"].append(1000 * (detection[4] - truth_glass[4]))
                found += 1
            else:
                invented += 1
        missed += len(true_glasses) - len(matched)
    true_count = found + missed
    summary = {
        "pictures": len(examples),
        "glasses": true_count,
        "found": found,
        "missed": missed,
        "invented": invented,
        "recall": found / max(true_count, 1),
        "precision": found / max(found + invented, 1),
    }
    for name, values in errors.items():
        values = np.array(values)
        summary[name] = {
            "median_abs": float(np.median(np.abs(values))),
            "mean": float(values.mean()),
            "p90_abs": float(np.percentile(np.abs(values), 90)),
        }
    return summary


if __name__ == "__main__":
    train_path, test_path = Path(sys.argv[1]), Path(sys.argv[2])
    epochs = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    weights_file = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    train_set, test_set = (
        box_model.load_training_examples(train_path),
        box_model.load_training_examples(test_path),
    )
    print(f"{len(train_set)} training pictures, {len(test_set)} test pictures, {epochs} epochs", flush=True)
    started = time.perf_counter()
    network = box_model.train_box_detector(train_set, test_set, epochs=epochs)
    model = box_model.BoxModel(network)
    model.save(weights_file)
    result = measure_box_model(model, test_set)
    result["train_seconds"] = round(time.perf_counter() - started)
    result["train_pictures"] = len(train_set)
    print(json.dumps(result, indent=1))
