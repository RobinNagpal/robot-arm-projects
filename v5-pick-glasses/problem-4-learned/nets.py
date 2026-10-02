"""The picture models: two reused from problem 2, one widened, one new.

1. TopNet   — problem 2's, unchanged. Overhead depth picture in; per pixel,
              is it glass and which way is the middle of its glass.
2. Ranker   — problem 2's, unchanged. Seven numbers about one camera place
              in; the chance the side picture from there is clean.
3. SideNet  — problem 2's, with a second head. Side depth picture in; the
              height, the width at 16 levels, and now **the kind** as well.
4. GripNet  — new. The same side picture in; whether the glass can be held,
              how high up, and how far apart the pads are when they touch.

TopNet and the Ranker are imported from problem-2-learned/models.py as they
are. SideNet's picture half is the same layers as problem 2's; only the heads
on the end differ.

All of them train on a laptop in a few minutes from 200 tables.
"""

from __future__ import annotations

import numpy as np
import torch
from models import (  # problem-2-learned
    DEVICE,
    HEIGHT_SCALE,
    SMALL,
    WIDTH_SCALE,
    Ranker,
    TopNet,
    _block,
    fit,
    predict,
    side_input,
    side_target,
    top_input,
    top_loss,
    top_target,
)
from torch import nn

from bench import KINDS
from scoring import FRACTIONS

__all__ = [
    "DEVICE", "FRACTIONS", "KINDS", "GripNet", "Ranker", "SideNet", "TopNet",
    "fit", "predict", "side_input", "side_target", "top_input", "top_loss", "top_target",
]  # fmt: skip

# Grip height and opening are divided by these so they sit near 1, the same
# trick as SideNet's height and widths.
GRIP_HEIGHT_SCALE = HEIGHT_SCALE
OPENING_SCALE = WIDTH_SCALE / 4

# How much the kind counts against the shape in SideNet's loss. The shape's
# error is a few hundredths in scaled units; a wrong kind costs about one.
KIND_WEIGHT = 0.2


def _features() -> nn.Sequential:
    """The picture half shared by SideNet and GripNet: four strided layers."""
    return nn.Sequential(_block(1, 16, 2), _block(16, 32, 2), _block(32, 64, 2), _block(64, 64, 2))


_FLAT = 64 * ((SMALL[0] + 15) // 16) * ((SMALL[1] + 15) // 16)


# ----------------------------------------------------------------- SideNet


class SideNet(nn.Module):
    """Height and 16 widths, as problem 2's, plus four kind scores."""

    def __init__(self) -> None:
        super().__init__()
        self.features = _features()
        self.trunk = nn.Sequential(nn.Flatten(), nn.Dropout(0.2), nn.Linear(_FLAT, 128), nn.ReLU())
        self.shape = nn.Linear(128, 1 + len(FRACTIONS))
        self.kind = nn.Linear(128, len(KINDS))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        shared = self.trunk(self.features(x))
        return torch.cat([self.shape(shared), self.kind(shared)], 1)


def side_kind_target(glass) -> np.ndarray:
    """17 shape numbers as problem 2 has them, then the kind's index."""
    return np.concatenate([side_target(glass), [KINDS.index(glass.kind)]]).astype(np.float32)


def side_loss(out: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    shape = (out[:, :17] - target[:, :17]).abs().mean()
    kind = nn.functional.cross_entropy(out[:, 17:], target[:, 17].long())
    return shape + KIND_WEIGHT * kind


def side_output(out: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """Height in metres, widths in metres at FRACTIONS of it, and the chance of each kind."""
    scores = out[17:] - out[17:].max()
    chances = np.exp(scores) / np.exp(scores).sum()
    return float(out[0] * HEIGHT_SCALE), out[1:17] * WIDTH_SCALE, chances


# ----------------------------------------------------------------- GripNet


class GripNet(nn.Module):
    """Can it be held; if so, how high up and how wide the pads are when they touch."""

    def __init__(self) -> None:
        super().__init__()
        self.features = _features()
        self.head = nn.Sequential(
            nn.Flatten(), nn.Dropout(0.2), nn.Linear(_FLAT, 128), nn.ReLU(), nn.Linear(128, 3)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.features(x))


def grip_target(grip) -> np.ndarray:
    """(holdable, height scaled, opening scaled), from tables.TrueGrip."""
    return np.array(
        [float(grip.holdable), grip.height / GRIP_HEIGHT_SCALE, grip.opening / OPENING_SCALE],
        dtype=np.float32,
    )


def grip_loss(out: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Holdable or not, everywhere; where, only for glasses that can be held."""
    holdable = target[:, 0]
    decide = nn.functional.binary_cross_entropy_with_logits(out[:, 0], holdable)
    where = ((out[:, 1:] - target[:, 1:]).abs().sum(1) * holdable).sum() / holdable.sum().clamp(min=1)
    return decide + where


def grip_output(out: np.ndarray) -> tuple[float, float, float]:
    """The chance it can be held, the grip height and the opening, in metres."""
    return float(1 / (1 + np.exp(-out[0]))), float(out[1] * GRIP_HEIGHT_SCALE), float(out[2] * OPENING_SCALE)
