"""The forward model: a push in, what it will do out.

Problem 3's network (03-push-glasses-apart/04-a-world-model/model.py), resized for the wider input.
A small MLP trained ENSEMBLE times from different starts; where the copies
disagree the model has not seen a push like this one, and the planner takes
the worst copy's topple chance rather than the average.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

import push_features as features

ENSEMBLE = 5
HIDDEN = 256


class PushNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(features.INPUTS, HIDDEN), nn.SiLU(),
            nn.Linear(HIDDEN, HIDDEN), nn.SiLU(),
            nn.Linear(HIDDEN, HIDDEN), nn.SiLU(),
            nn.Linear(HIDDEN, features.OUTPUTS),
        )  # fmt: skip
        self.register_buffer("mean", torch.zeros(features.INPUTS))
        self.register_buffer("spread", torch.ones(features.INPUTS))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net((x - self.mean) / self.spread)


def loss(out: torch.Tensor, y: torch.Tensor, x: torch.Tensor, topple_weight: float) -> torch.Tensor:
    """Movement error where there is a glass to move, plus the two yes-or-no guesses."""
    moves = 2 + 2 * features.OTHERS
    there = torch.ones_like(y[:, :moves])
    there[:, 2:] = features.present(x).repeat_interleave(2, 1)
    move = (nn.functional.smooth_l1_loss(out[:, :moves], y[:, :moves], reduction="none", beta=0.1)
            * there).sum() / there.sum()  # fmt: skip
    toppled = nn.functional.binary_cross_entropy_with_logits(
        out[:, features.TOPPLED], y[:, features.TOPPLED], pos_weight=torch.tensor(topple_weight)
    )
    blocked = nn.functional.binary_cross_entropy_with_logits(out[:, features.BLOCKED], y[:, features.BLOCKED])
    return move + toppled + blocked


def fit(
    net: PushNet, x: np.ndarray, y: np.ndarray, *, epochs: int, seed: int, topple_weight: float
) -> list[float]:
    torch.manual_seed(seed)
    for layer in net.net:
        if isinstance(layer, nn.Linear):
            layer.reset_parameters()
    x_t, y_t = torch.as_tensor(x), torch.as_tensor(y)
    optimiser = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, epochs)
    history = []
    net.train()
    for _ in range(epochs):
        order, total = torch.randperm(len(x_t)), 0.0
        for start in range(0, len(x_t), 512):
            pick = order[start : start + 512]
            optimiser.zero_grad()
            value = loss(net(x_t[pick]), y_t[pick], x_t[pick], topple_weight)
            value.backward()
            optimiser.step()
            total += value.item() * len(pick)
        schedule.step()
        history.append(total / len(x_t))
    return history


class Ensemble:
    def __init__(self, nets: list[PushNet]) -> None:
        self.nets = [net.eval() for net in nets]

    def predict(self, x: np.ndarray) -> np.ndarray:
        """(copies, rows, outputs), raw: movements scaled, yes-or-no as logits."""
        with torch.no_grad():
            x_t = torch.as_tensor(x)
            return np.stack([net(x_t).numpy() for net in self.nets])

    def save(self, folder) -> None:
        folder.mkdir(exist_ok=True)
        for i, net in enumerate(self.nets):
            torch.save(net.state_dict(), folder / f"push_net_{i}.pt")

    @classmethod
    def load(cls, folder) -> Ensemble:
        nets = []
        for i in range(ENSEMBLE):
            net = PushNet()
            net.load_state_dict(torch.load(folder / f"push_net_{i}.pt"))
            nets.append(net)
        return cls(nets)


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
