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
from pusher import Box
from torch import nn
from work_cell.table.layout import TABLE_TOP_Z

import wrist

HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "weights"
INPUT = 192  # the picture is shrunk to this many pixels on a side
STRIDE = 4  # one network cell is this many input pixels wide
GRID = INPUT // STRIDE
FULL = wrist.WRIST_VIEW_SIZE[0]  # 384


# ------------------------------------------------------------------ geometry


def pixel_to_table(jaw, row: float, col: float) -> tuple[float, float]:
    """Where on the table top the camera's ray through a pixel lands. The inverse of ``wrist.to_pixel``."""
    eye, forward, right, up = wrist._axes(jaw)
    edge = math.tan(math.radians(wrist.WRIST_VIEW_FOVY_DEG) / 2)
    across = 2.0 * (col + 0.5) / FULL - 1.0
    upward = 1.0 - 2.0 * (row + 0.5) / FULL
    direction = forward + across * edge * right + upward * edge * up
    reach = (TABLE_TOP_Z - eye[2]) / direction[2]
    point = eye + reach * direction
    return float(point[0]), float(point[1])


def shrink(picture: np.ndarray) -> torch.Tensor:
    """384x384x3 uint8 to a 3x192x192 float tensor, by averaging 2x2 pixels."""
    x = torch.from_numpy(picture).float().div_(255.0).permute(2, 0, 1)
    return nn.functional.avg_pool2d(x, 2)


def view_channels(heading: float) -> torch.Tensor:
    """Two constant planes saying which way the camera points, so one network serves both viewing places."""
    return torch.stack(
        [torch.full((INPUT, INPUT), math.cos(heading)), torch.full((INPUT, INPUT), math.sin(heading))]
    )


# --------------------------------------------------------------------- labels


@dataclass
class Example:
    image: np.ndarray  # 3 x 192 x 192, uint8
    heading: float
    glasses: np.ndarray  # n x 5: row, col (in 384-pixel units), radius, height, foot radius


def label(bench, jaw) -> np.ndarray:
    """The simulator's answers for the glasses at least half visible from ``jaw``."""
    readings = list(bench.look())
    visible = {s.id for s in wrist.in_picture(jaw, readings)}
    rows = []
    for i, glass in enumerate(bench.glasses):
        if i not in visible or i in bench.taken:
            continue
        x, y = bench.position(i)
        r, c = wrist.to_pixel(jaw, float(x), float(y), 0.0)
        if not (0 <= r < FULL and 0 <= c < FULL):
            continue
        outline = glass.outline
        rows.append([r, c, outline.max_diameter / 2, outline.total_height, float(outline.radius[0])])
    return np.array(rows, dtype=np.float32).reshape(-1, 5)


def example(picture: np.ndarray, jaw, bench) -> Example:
    return Example((shrink(picture) * 255).byte().numpy(), jaw.heading, label(bench, jaw))


# -------------------------------------------------------------------- network


def _block(cin: int, cout: int, stride: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(cin, cout, 3, stride, 1, bias=False),
        nn.BatchNorm2d(cout),
        nn.ReLU(inplace=True),
        nn.Conv2d(cout, cout, 3, 1, 1, bias=False),
        nn.BatchNorm2d(cout),
        nn.ReLU(inplace=True),
    )


class BoxNet(nn.Module):
    """Picture to a grid of glass detections. About half a million weights."""

    def __init__(self) -> None:
        super().__init__()
        self.down = nn.Sequential(_block(5, 24, 2), _block(24, 48, 2), _block(48, 64, 1), _block(64, 96, 1))
        self.context = nn.Sequential(
            nn.Conv2d(96, 96, 3, 1, 2, dilation=2),
            nn.ReLU(inplace=True),
            nn.Conv2d(96, 96, 3, 1, 4, dilation=4),
            nn.ReLU(inplace=True),
        )
        self.heat = nn.Conv2d(96, 1, 1)
        self.offset = nn.Conv2d(96, 2, 1)
        self.size = nn.Conv2d(96, 3, 1)

    def forward(self, x: torch.Tensor):
        h = self.down(x)
        h = h + self.context(h)
        return self.heat(h), self.offset(h).sigmoid(), self.size(h)


# Sizes are regressed in these units so that every output is of order one.
SIZE_SCALE = torch.tensor([0.05, 0.2, 0.04])


def _targets(batch: list[Example]):
    n = len(batch)
    heat = torch.zeros(n, 1, GRID, GRID)
    mask = torch.zeros(n, GRID, GRID, dtype=torch.bool)
    offset = torch.zeros(n, 2, GRID, GRID)
    size = torch.zeros(n, 3, GRID, GRID)
    ys, xs = torch.meshgrid(torch.arange(GRID).float(), torch.arange(GRID).float(), indexing="ij")
    for b, ex in enumerate(batch):
        for row, col, radius, height, foot in ex.glasses:
            fy, fx = row / FULL * GRID, col / FULL * GRID
            iy, ix = min(GRID - 1, int(fy)), min(GRID - 1, int(fx))
            sigma = 1.2
            bump = torch.exp(-((ys - iy) ** 2 + (xs - ix) ** 2) / (2 * sigma**2))
            heat[b, 0] = torch.maximum(heat[b, 0], bump)
            mask[b, iy, ix] = True
            offset[b, :, iy, ix] = torch.tensor([fy - iy, fx - ix])
            size[b, :, iy, ix] = torch.tensor([radius, height, foot]) / SIZE_SCALE
    return heat, mask, offset, size


def batch_input(batch: list[Example]) -> torch.Tensor:
    return torch.stack(
        [torch.cat([torch.from_numpy(ex.image).float() / 255.0, view_channels(ex.heading)]) for ex in batch]
    )


def loss_of(net: BoxNet, batch: list[Example]) -> tuple[torch.Tensor, dict]:
    heat_hat, offset_hat, size_hat = net(batch_input(batch))
    heat, mask, offset, size = _targets(batch)
    p = heat_hat.sigmoid().clamp(1e-4, 1 - 1e-4)
    # The focal loss CenterNet uses: peaks are rare, so plain cross entropy
    # would be won by predicting nothing anywhere.
    positive = heat.eq(1.0).float()
    pos_loss = -(((1 - p) ** 2) * torch.log(p) * positive).sum()
    neg_loss = -(((1 - heat) ** 4) * (p**2) * torch.log(1 - p) * (1 - positive)).sum()
    count = positive.sum().clamp(min=1)
    focal = (pos_loss + neg_loss) / count
    m = mask.unsqueeze(1)
    off = (nn.functional.l1_loss(offset_hat, offset, reduction="none") * m).sum() / (m.sum() * 2).clamp(min=1)
    siz = (nn.functional.l1_loss(size_hat, size, reduction="none") * m).sum() / (m.sum() * 3).clamp(min=1)
    total = focal + off + 2.0 * siz
    return total, {"focal": float(focal), "offset": float(off), "size": float(siz)}


def train(
    examples: list[Example],
    held_out: list[Example],
    epochs: int = 30,
    batch: int = 16,
    seed: int = 0,
    log=print,
) -> BoxNet:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = BoxNet()
    optimiser = torch.optim.AdamW(net.parameters(), 2e-3, weight_decay=1e-4)
    steps = epochs * math.ceil(len(examples) / batch)
    schedule = torch.optim.lr_scheduler.OneCycleLR(optimiser, 2e-3, total_steps=steps)
    started = time.perf_counter()
    for epoch in range(epochs):
        net.train()
        order = rng.permutation(len(examples))
        running = []
        for k in range(0, len(order), batch):
            chunk = [examples[i] for i in order[k : k + batch]]
            loss, parts = loss_of(net, chunk)
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            schedule.step()
            running.append(float(loss))
        if log and (epoch % 5 == 4 or epoch == epochs - 1):
            net.eval()
            with torch.no_grad():
                held = (
                    float(
                        np.mean(
                            [
                                float(loss_of(net, held_out[i : i + 16])[0])
                                for i in range(0, len(held_out), 16)
                            ]
                        )
                    )
                    if held_out
                    else float("nan")
                )
            log(
                f"  epoch {epoch + 1}/{epochs}: train loss {np.mean(running):.3f}, "
                f"held-out loss {held:.3f}, {time.perf_counter() - started:.0f} s"
            )
    net.eval()
    return net


# ------------------------------------------------------------------ inference


class BoxModel:
    """The trained network, as the cell uses it: a picture and where it was taken from, boxes out."""

    THRESHOLD = 0.35

    def __init__(self, net: BoxNet) -> None:
        self.net = net.eval()

    @staticmethod
    def load(path: Path | None = None) -> BoxModel:
        net = BoxNet()
        net.load_state_dict(torch.load(path or WEIGHTS / "box-net.pt", weights_only=True))
        return BoxModel(net)

    def save(self, path: Path | None = None) -> None:
        WEIGHTS.mkdir(exist_ok=True)
        torch.save(self.net.state_dict(), path or WEIGHTS / "box-net.pt")

    @torch.no_grad()
    def detect(self, picture: np.ndarray, jaw) -> list[Box]:
        x = torch.cat([shrink(picture), view_channels(jaw.heading)]).unsqueeze(0)
        heat, offset, size = self.net(x)
        heat = heat.sigmoid()[0, 0]
        # A peak is a cell that is the largest in its 3x3 neighbourhood.
        top = nn.functional.max_pool2d(heat[None, None], 3, 1, 1)[0, 0]
        boxes = []
        for iy, ix in torch.nonzero((heat == top) & (heat > self.THRESHOLD)).tolist():
            row = (iy + float(offset[0, 0, iy, ix])) * STRIDE * 2
            col = (ix + float(offset[0, 1, iy, ix])) * STRIDE * 2
            radius, height, foot = (size[0, :, iy, ix] * SIZE_SCALE).tolist()
            x_t, y_t = pixel_to_table(jaw, row, col)
            boxes.append(Box(x_t, y_t, max(radius, 0.015), max(height, 0.03), max(foot, 0.01)))
        return boxes


def save_examples(examples: list[Example], path: Path) -> None:
    path.parent.mkdir(exist_ok=True)
    with open(path, "wb") as handle:
        pickle.dump(examples, handle)


def load_examples(path: Path) -> list[Example]:
    with open(path, "rb") as handle:
        return pickle.load(handle)
