"""The box model: a picture from the wrist in, a box round each glass out.

MoveIt plans round boxes, so before it can be asked for a safe motion somebody
has to say where the glasses are and how big. In problem 4 that was problem 2's
measurement pipeline, handed over as numbers. Here it is a network that reads
the wrist camera's picture, which is what a cell without a measurement pipeline
would have.

**How it works.** It is a small fully convolutional detector in the style of
CenterNet. The picture is reduced to a grid of cells four pixels on a side.
For each cell the network says three things: how likely it is that the foot of
a glass stands in that cell, where in the cell, and how big the glass is --
the radius where it is widest, the height and the radius of its foot. A glass
is a peak in the first map. Its position on the table is not learned at all:
the pixel of its foot is turned into a point on the table by following the
camera's ray down to the table top, which is geometry, so the network does not
have to learn the camera.

**What the labels are, and what they are not.** The simulator knows every
glass. The labels are its answers for the glasses that are at least half
visible in the picture, the same rule problem 4 uses for what a look can hand
over. The network sees none of that when it runs, only the picture, and what it
returns is judged against the simulator's sizes on pictures it was not trained
on.

Two things are worth knowing about the sizes. The radius is the radius at the
widest point, which is what a box must cover; the box is as wide there as
anywhere, so it is wider than the glass is where the hand meets it. And the
foot radius is returned only because the tipping rule needs it; MoveIt does not.
"""

from __future__ import annotations

import math
import pickle
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn
from work_cell.table.layout import TABLE_TOP_Z

from examiner.motion.push_motions import GlassBox
from examiner.simulation import wrist_camera

THIS_FOLDER = Path(__file__).resolve().parent
WEIGHTS_FOLDER = THIS_FOLDER / "weights"
NETWORK_INPUT_PIXELS = 192  # the picture is shrunk to this many pixels on a side
PIXELS_PER_GRID_CELL = 4  # one network cell is this many input pixels wide
GRID_CELLS_PER_SIDE = NETWORK_INPUT_PIXELS // PIXELS_PER_GRID_CELL
PICTURE_PIXELS = wrist_camera.WRIST_VIEW_SIZE[0]  # 384


# ------------------------------------------------------------------ geometry


def pixel_to_table(hand, row: float, column: float) -> tuple[float, float]:
    """Where on the table top the camera's ray through a pixel lands.

    It is the inverse of ``wrist_camera.table_point_to_pixel``.
    """
    eye, forward, right, up = wrist_camera._lens_axes(hand)
    edge = math.tan(math.radians(wrist_camera.WRIST_VIEW_FOVY_DEG) / 2)
    across_picture = 2.0 * (column + 0.5) / PICTURE_PIXELS - 1.0
    up_picture = 1.0 - 2.0 * (row + 0.5) / PICTURE_PIXELS
    direction = forward + across_picture * edge * right + up_picture * edge * up
    distance_to_table = (TABLE_TOP_Z - eye[2]) / direction[2]
    point = eye + distance_to_table * direction
    return float(point[0]), float(point[1])


def shrink_picture(picture: np.ndarray) -> torch.Tensor:
    """384x384x3 uint8 to a 3x192x192 float tensor, by averaging 2x2 pixels."""
    pixels = torch.from_numpy(picture).float().div_(255.0).permute(2, 0, 1)
    return nn.functional.avg_pool2d(pixels, 2)


def camera_heading_planes(heading: float) -> torch.Tensor:
    """Two constant planes saying which way the camera points, so one network serves both viewing places."""
    return torch.stack(
        [
            torch.full((NETWORK_INPUT_PIXELS, NETWORK_INPUT_PIXELS), math.cos(heading)),
            torch.full((NETWORK_INPUT_PIXELS, NETWORK_INPUT_PIXELS), math.sin(heading)),
        ]
    )


# --------------------------------------------------------------------- labels


@dataclass
class BoxTrainingExample:
    image: np.ndarray  # 3 x 192 x 192, uint8
    heading: float
    glasses: np.ndarray  # n x 5: row, col (in 384-pixel units), radius, height, foot radius


def true_boxes_in_picture(simulator, hand) -> np.ndarray:
    """The simulator's answers for the glasses at least half visible from ``jaw``."""
    readings = list(simulator.look())
    visible_ids = {s.id for s in wrist_camera.glasses_the_camera_can_see(hand, readings)}
    glass_rows = []
    for i, glass in enumerate(simulator.glasses):
        if i not in visible_ids:
            continue
        x, y = simulator.position(i)
        row, column = wrist_camera.table_point_to_pixel(hand, float(x), float(y), 0.0)
        if not (0 <= row < PICTURE_PIXELS and 0 <= column < PICTURE_PIXELS):
            continue
        outline = glass.outline
        glass_rows.append(
            [row, column, outline.max_diameter / 2, outline.total_height, float(outline.radius[0])]
        )
    return np.array(glass_rows, dtype=np.float32).reshape(-1, 5)


def make_training_example(picture: np.ndarray, hand, simulator) -> BoxTrainingExample:
    return BoxTrainingExample(
        (shrink_picture(picture) * 255).byte().numpy(), hand.heading, true_boxes_in_picture(simulator, hand)
    )


# -------------------------------------------------------------------- network


def _convolution_block(channels_in: int, channels_out: int, stride: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(channels_in, channels_out, 3, stride, 1, bias=False),
        nn.BatchNorm2d(channels_out),
        nn.ReLU(inplace=True),
        nn.Conv2d(channels_out, channels_out, 3, 1, 1, bias=False),
        nn.BatchNorm2d(channels_out),
        nn.ReLU(inplace=True),
    )


class BoxDetectorNetwork(nn.Module):
    """Picture to a grid of glass detections. About half a million weights."""

    def __init__(self) -> None:
        super().__init__()
        self.down = nn.Sequential(
            _convolution_block(5, 24, 2),
            _convolution_block(24, 48, 2),
            _convolution_block(48, 64, 1),
            _convolution_block(64, 96, 1),
        )
        self.context = nn.Sequential(
            nn.Conv2d(96, 96, 3, 1, 2, dilation=2),
            nn.ReLU(inplace=True),
            nn.Conv2d(96, 96, 3, 1, 4, dilation=4),
            nn.ReLU(inplace=True),
        )
        self.heat = nn.Conv2d(96, 1, 1)
        self.offset = nn.Conv2d(96, 2, 1)
        self.size = nn.Conv2d(96, 3, 1)

    def forward(self, pictures: torch.Tensor):
        features = self.down(pictures)
        features = features + self.context(features)
        return self.heat(features), self.offset(features).sigmoid(), self.size(features)


# Sizes are regressed in these units so that every output is of order one.
SIZE_UNITS = torch.tensor([0.05, 0.2, 0.04])


def _training_targets(examples: list[BoxTrainingExample]):
    count = len(examples)
    heat = torch.zeros(count, 1, GRID_CELLS_PER_SIDE, GRID_CELLS_PER_SIDE)
    mask = torch.zeros(count, GRID_CELLS_PER_SIDE, GRID_CELLS_PER_SIDE, dtype=torch.bool)
    offset = torch.zeros(count, 2, GRID_CELLS_PER_SIDE, GRID_CELLS_PER_SIDE)
    size = torch.zeros(count, 3, GRID_CELLS_PER_SIDE, GRID_CELLS_PER_SIDE)
    ys, xs = torch.meshgrid(
        torch.arange(GRID_CELLS_PER_SIDE).float(), torch.arange(GRID_CELLS_PER_SIDE).float(), indexing="ij"
    )
    for index, example in enumerate(examples):
        for row, col, radius, height, foot in example.glasses:
            grid_row, grid_column = (
                row / PICTURE_PIXELS * GRID_CELLS_PER_SIDE,
                col / PICTURE_PIXELS * GRID_CELLS_PER_SIDE,
            )
            cell_row, cell_column = (
                min(GRID_CELLS_PER_SIDE - 1, int(grid_row)),
                min(GRID_CELLS_PER_SIDE - 1, int(grid_column)),
            )
            sigma = 1.2
            bump = torch.exp(-((ys - cell_row) ** 2 + (xs - cell_column) ** 2) / (2 * sigma**2))
            heat[index, 0] = torch.maximum(heat[index, 0], bump)
            mask[index, cell_row, cell_column] = True
            offset[index, :, cell_row, cell_column] = torch.tensor(
                [grid_row - cell_row, grid_column - cell_column]
            )
            size[index, :, cell_row, cell_column] = torch.tensor([radius, height, foot]) / SIZE_UNITS
    return heat, mask, offset, size


def network_input_batch(examples: list[BoxTrainingExample]) -> torch.Tensor:
    return torch.stack(
        [
            torch.cat(
                [torch.from_numpy(example.image).float() / 255.0, camera_heading_planes(example.heading)]
            )
            for example in examples
        ]
    )


def detector_loss(
    network: BoxDetectorNetwork, examples: list[BoxTrainingExample]
) -> tuple[torch.Tensor, dict]:
    predicted_heat, predicted_offset, predicted_size = network(network_input_batch(examples))
    heat, mask, offset, size = _training_targets(examples)
    peak_chance = predicted_heat.sigmoid().clamp(1e-4, 1 - 1e-4)
    # The focal loss CenterNet uses: peaks are rare, so plain cross entropy
    # would be won by predicting nothing anywhere.
    is_peak = heat.eq(1.0).float()
    peak_loss = -(((1 - peak_chance) ** 2) * torch.log(peak_chance) * is_peak).sum()
    background_loss = -(
        ((1 - heat) ** 4) * (peak_chance**2) * torch.log(1 - peak_chance) * (1 - is_peak)
    ).sum()
    peak_count = is_peak.sum().clamp(min=1)
    focal_loss = (peak_loss + background_loss) / peak_count
    cell_has_glass = mask.unsqueeze(1)
    offset_loss = (
        nn.functional.l1_loss(predicted_offset, offset, reduction="none") * cell_has_glass
    ).sum() / (cell_has_glass.sum() * 2).clamp(min=1)
    size_loss = (nn.functional.l1_loss(predicted_size, size, reduction="none") * cell_has_glass).sum() / (
        cell_has_glass.sum() * 3
    ).clamp(min=1)
    total_loss = focal_loss + offset_loss + 2.0 * size_loss
    return total_loss, {"focal": float(focal_loss), "offset": float(offset_loss), "size": float(size_loss)}


def train_box_detector(
    examples: list[BoxTrainingExample],
    held_out: list[BoxTrainingExample],
    epochs: int = 30,
    batch_size: int = 16,
    seed: int = 0,
    log=print,
) -> BoxDetectorNetwork:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    network = BoxDetectorNetwork()
    optimiser = torch.optim.AdamW(network.parameters(), 2e-3, weight_decay=1e-4)
    total_steps = epochs * math.ceil(len(examples) / batch_size)
    learning_rate_schedule = torch.optim.lr_scheduler.OneCycleLR(optimiser, 2e-3, total_steps=total_steps)
    started = time.perf_counter()
    for epoch in range(epochs):
        network.train()
        order = rng.permutation(len(examples))
        epoch_losses = []
        for batch_start in range(0, len(order), batch_size):
            batch = [examples[start] for start in order[batch_start : batch_start + batch_size]]
            loss, loss_parts = detector_loss(network, batch)
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            learning_rate_schedule.step()
            epoch_losses.append(float(loss))
        if log and (epoch % 5 == 4 or epoch == epochs - 1):
            network.eval()
            with torch.no_grad():
                held_out_loss = (
                    float(
                        np.mean(
                            [
                                float(detector_loss(network, held_out[start : start + 16])[0])
                                for start in range(0, len(held_out), 16)
                            ]
                        )
                    )
                    if held_out
                    else float("nan")
                )
            log(
                f"  epoch {epoch + 1}/{epochs}: train loss {np.mean(epoch_losses):.3f}, "
                f"held-out loss {held_out_loss:.3f}, {time.perf_counter() - started:.0f} s"
            )
    network.eval()
    return network


# ------------------------------------------------------------------ inference


class BoxModel:
    """The trained network, as the cell uses it: a picture and where it was taken from, boxes out."""

    PEAK_THRESHOLD = 0.35

    def __init__(self, network: BoxDetectorNetwork) -> None:
        self.network = network.eval()

    @staticmethod
    def load(path: Path | None = None) -> BoxModel:
        network = BoxDetectorNetwork()
        network.load_state_dict(torch.load(path or WEIGHTS_FOLDER / "box-net.pt", weights_only=True))
        return BoxModel(network)

    def save(self, path: Path | None = None) -> None:
        WEIGHTS_FOLDER.mkdir(exist_ok=True)
        torch.save(self.network.state_dict(), path or WEIGHTS_FOLDER / "box-net.pt")

    @torch.no_grad()
    def boxes_in_picture(self, picture: np.ndarray, hand) -> list[GlassBox]:
        network_input = torch.cat([shrink_picture(picture), camera_heading_planes(hand.heading)]).unsqueeze(0)
        heat, offset, size = self.network(network_input)
        heat = heat.sigmoid()[0, 0]
        # A peak is a cell that is the largest in its 3x3 neighbourhood.
        neighbourhood_peak = nn.functional.max_pool2d(heat[None, None], 3, 1, 1)[0, 0]
        boxes = []
        for cell_row, cell_column in torch.nonzero(
            (heat == neighbourhood_peak) & (heat > self.PEAK_THRESHOLD)
        ).tolist():
            row = (cell_row + float(offset[0, 0, cell_row, cell_column])) * PIXELS_PER_GRID_CELL * 2
            column = (cell_column + float(offset[0, 1, cell_row, cell_column])) * PIXELS_PER_GRID_CELL * 2
            radius, height, foot = (size[0, :, cell_row, cell_column] * SIZE_UNITS).tolist()
            table_x, table_y = pixel_to_table(hand, row, column)
            boxes.append(GlassBox(table_x, table_y, max(radius, 0.015), max(height, 0.03), max(foot, 0.01)))
        return boxes


def save_training_examples(examples: list[BoxTrainingExample], path: Path) -> None:
    path.parent.mkdir(exist_ok=True)
    with open(path, "wb") as handle:
        pickle.dump(examples, handle)


class _UnpicklerForOldModuleNames(pickle.Unpickler):
    """Reads examples saved under older names.

    The examples were first saved when this file was a plain module called ``seeing``, and
    their class was then called ``Example``. Both are mapped to the names used now.
    """

    def find_class(self, module: str, name: str):
        module = __name__ if module in ("seeing", __name__) else module
        name = "BoxTrainingExample" if module == __name__ and name == "Example" else name
        return super().find_class(module, name)


def load_training_examples(path: Path) -> list[BoxTrainingExample]:
    with open(path, "rb") as handle:
        return _UnpicklerForOldModuleNames(handle).load()
