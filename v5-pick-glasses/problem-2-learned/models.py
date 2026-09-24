"""The three learned parts, and how each is trained.

1. TopNet   — overhead depth picture in, per pixel: is it glass, and which way
              is the middle of its glass. Pixels that vote for the same middle
              are one glass, which is what separates two glasses that touch in
              the picture.
2. Ranker   — the numbers in viewpoints.FEATURES in, the chance this side
              picture is unspoiled out. It only orders places geometry allowed.
3. SideNet  — side depth picture in, the glass's height and its width at 16
              fractions of that height out.

All small enough to train on a laptop CPU in minutes from 200 pictures.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn
from work_cell.table.layout import TABLE_TOP_Z

from render import HEIGHT, STANDOFF, TOP_HEIGHT, WIDTH, Picture, project
from scoring import FRACTIONS
from viewpoints import FEATURES

DEVICE = "mps" if torch.backends.mps.is_available() else "cpu"

# Pictures go into the networks at half size. A glass is still 20-odd pixels
# across from above, and training is four times quicker.
SHRINK = 2
SMALL = (HEIGHT // SHRINK, WIDTH // SHRINK)

# Offsets to a glass's middle are stored divided by this, so they sit near 1.
VOTE_SCALE = 25.0

# SideNet's outputs are divided by these, for the same reason.
HEIGHT_SCALE, WIDTH_SCALE = 0.25, 0.10


def _block(into: int, out: int, stride: int = 1, dilation: int = 1) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(into, out, 3, stride, padding=dilation, dilation=dilation),
        nn.BatchNorm2d(out),
        nn.ReLU(inplace=True),
    )


# ------------------------------------------------------------------ TopNet


def top_input(picture: Picture) -> np.ndarray:
    """Height-like channel plus where each pixel is in the frame.

    Where the pixel is matters: from above, a rim leans outwards from the
    middle of the picture, more for a taller glass, so the way to a glass's
    middle depends on where in the frame it is seen.
    """
    depth = picture.depth[::SHRINK, ::SHRINK]
    near = np.where(np.isfinite(depth), (TOP_HEIGHT - depth) / 0.25, 0.0)
    rows, columns = np.indices(SMALL)
    return np.stack([near, rows / SMALL[0] * 2 - 1, columns / SMALL[1] * 2 - 1]).astype(np.float32)


def top_target(picture: Picture, glasses) -> np.ndarray:
    """Per pixel: glass or not, and the offset to its rim's middle."""
    ids = picture.ids[::SHRINK, ::SHRINK]
    target = np.zeros((3, *SMALL), dtype=np.float32)
    target[0] = ids > 0
    rows, columns = np.indices(SMALL)
    for index, glass in enumerate(glasses):
        column, row = project(picture.camera_to_world, [glass.x, glass.y, TABLE_TOP_Z + glass.total_height])
        mine = ids == index + 1
        target[1][mine] = (column / SHRINK - columns[mine]) / VOTE_SCALE
        target[2][mine] = (row / SHRINK - rows[mine]) / VOTE_SCALE
    return target


class TopNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.at_full = nn.Sequential(_block(3, 16), _block(16, 16))
        self.at_half = nn.Sequential(_block(16, 32, 2), _block(32, 32))
        self.at_quarter = nn.Sequential(
            _block(32, 64, 2), _block(64, 64, dilation=2), _block(64, 64, dilation=4)
        )
        self.up_half = _block(64 + 32, 32)
        self.up_full = _block(32 + 16, 16)
        self.head = nn.Conv2d(16, 3, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        full = self.at_full(x)
        half = self.at_half(full)
        quarter = self.at_quarter(half)
        up = nn.functional.interpolate(quarter, size=half.shape[-2:])
        up = self.up_half(torch.cat([up, half], 1))
        up = nn.functional.interpolate(up, size=full.shape[-2:])
        return self.head(self.up_full(torch.cat([up, full], 1)))


def top_loss(out: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    glass = target[:, 0]
    found = nn.functional.binary_cross_entropy_with_logits(out[:, 0], glass)
    offset = (out[:, 1:] - target[:, 1:]).abs().sum(1)
    return found + (offset * glass).sum() / glass.sum().clamp(min=1)


# ------------------------------------------------------------------ Ranker


class Ranker(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(len(FEATURES), 32), nn.ReLU(), nn.Linear(32, 32), nn.ReLU(), nn.Linear(32, 1)
        )
        # Features are standardised with the training set's own spread,
        # stored with the weights so that running uses the same numbers.
        self.register_buffer("mean", torch.zeros(len(FEATURES)))
        self.register_buffer("spread", torch.ones(len(FEATURES)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net((x - self.mean) / self.spread).squeeze(-1)


# ----------------------------------------------------------------- SideNet


def side_input(picture: Picture) -> np.ndarray:
    """Distance from the standoff, with nothing-there set to far away."""
    depth = picture.depth[::SHRINK, ::SHRINK]
    return np.clip(np.where(np.isfinite(depth), (depth - STANDOFF) / 0.15, 2.0), -2, 2)[None].astype(
        np.float32
    )


def side_target(glass) -> np.ndarray:
    widths = 2.0 * np.interp(FRACTIONS * glass.total_height, glass.height, glass.radius)
    return np.concatenate([[glass.total_height / HEIGHT_SCALE], widths / WIDTH_SCALE]).astype(np.float32)


class SideNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Sequential(
            _block(1, 16, 2), _block(16, 32, 2), _block(32, 64, 2), _block(64, 64, 2)
        )
        size = 64 * ((SMALL[0] + 15) // 16) * ((SMALL[1] + 15) // 16)
        self.head = nn.Sequential(
            nn.Flatten(), nn.Dropout(0.2), nn.Linear(size, 128), nn.ReLU(), nn.Linear(128, 1 + len(FRACTIONS))
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.features(x))


def side_output(out: np.ndarray) -> tuple[float, np.ndarray]:
    """Height in metres, and widths in metres at FRACTIONS of it."""
    return float(out[0] * HEIGHT_SCALE), out[1:] * WIDTH_SCALE


# --------------------------------------------------------------- training


def fit(
    model: nn.Module, inputs, targets, loss, *, epochs: int, flip: bool = False, batch: int = 16
) -> list[float]:
    """Plain Adam over the whole set. Returns the loss per epoch.

    ``flip`` mirrors pictures left to right as they are drawn, which doubles
    a small set for free: a mirrored side view is still a true side view.
    """
    model.to(DEVICE).train()
    inputs, targets = torch.as_tensor(inputs), torch.as_tensor(targets)
    optimiser = torch.optim.Adam(model.parameters(), lr=2e-3)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, epochs)
    history = []
    for _ in range(epochs):
        order, total = torch.randperm(len(inputs)), 0.0
        for start in range(0, len(inputs), batch):
            pick = order[start : start + batch]
            x, y = inputs[pick].to(DEVICE), targets[pick].to(DEVICE)
            if flip and torch.rand(1).item() < 0.5:
                x = x.flip(-1)
            optimiser.zero_grad()
            value = loss(model(x), y)
            value.backward()
            optimiser.step()
            total += value.item() * len(pick)
        schedule.step()
        history.append(total / len(inputs))
    return history


def predict(model: nn.Module, inputs: np.ndarray) -> np.ndarray:
    model.to(DEVICE).eval()
    with torch.no_grad():
        return model(torch.as_tensor(inputs).to(DEVICE)).cpu().numpy()
