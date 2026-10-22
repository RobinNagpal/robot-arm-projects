"""The forward model: a push in, what it will do out.

A small network, trained ``ENSEMBLE`` times from different starting weights on
the same pushes. Where the copies agree, the model has seen pushes like this
one; where they disagree, it has not. The search uses that disagreement: it
takes the *worst* of the copies' topple chances rather than their average, so a
push the model is unsure about counts as a risky one.

This is problem 3's solution 4's ``model.py`` with two changes, both forced by
how little data problem 4 can afford to collect. Problem 3 collected fifteen
thousand pushes, because a push there costs nothing but laptop time. Here the
arm has to drive round the table and look before it can push at all, so the
set is a tenth of the size -- see ``collect.py``. So the network is half as
wide and there are three copies rather than five.

The loss carries a mask, which problem 3's did not need. There, every look saw
the whole table, so every push had a label for every glass. Here a glass can be
out of the picture when the push is looked at, and a missing label is not a
label of zero: a push whose neighbour was not seen again has to teach the model
nothing about that neighbour rather than teach it that nothing moved.
"""

from __future__ import annotations

import encoding
import numpy as np
import torch
from torch import nn

ENSEMBLE = 3
HIDDEN = 128


class PushNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(encoding.INPUTS, HIDDEN), nn.SiLU(),
            nn.Linear(HIDDEN, HIDDEN), nn.SiLU(),
            nn.Linear(HIDDEN, HIDDEN), nn.SiLU(),
            nn.Linear(HIDDEN, encoding.OUTPUTS),
        )  # fmt: skip
        # Inputs are standardised with the training set's own spread, kept with
        # the weights so that running uses the numbers training used.
        self.register_buffer("mean", torch.zeros(encoding.INPUTS))
        self.register_buffer("spread", torch.ones(encoding.INPUTS))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net((x - self.mean) / self.spread)


def loss(
    out: torch.Tensor, y: torch.Tensor, mask: torch.Tensor, x: torch.Tensor, topple_weight: float
) -> torch.Tensor:
    """Movement error where there is a movement to learn, plus the one yes-or-no guess.

    A slot counts only when it holds a glass *and* that glass was measured
    again after the push. Toppling is the rare answer and the one a mistake is
    unaffordable in, so it is weighted up until the two sides count the same.
    """
    moves = encoding.MOVES
    here = mask[:, :moves].clone()
    here[:, 2:] *= encoding.present(x).repeat_interleave(2, 1)
    move = (
        nn.functional.smooth_l1_loss(out[:, :moves], y[:, :moves], reduction="none", beta=0.1) * here
    ).sum() / here.sum().clamp(min=1.0)
    toppled = nn.functional.binary_cross_entropy_with_logits(
        out[:, encoding.TOPPLED],
        y[:, encoding.TOPPLED],
        pos_weight=torch.tensor(topple_weight, device=out.device),
    )
    return move + toppled


def fit(
    net: PushNet,
    x: np.ndarray,
    y: np.ndarray,
    mask: np.ndarray,
    *,
    epochs: int,
    seed: int,
    topple_weight: float,
) -> list[float]:
    """Plain AdamW with a cosine schedule. Returns the loss per epoch."""
    torch.manual_seed(seed)
    for layer in net.net:
        if isinstance(layer, nn.Linear):
            layer.reset_parameters()
    x_t, y_t, mask_t = (torch.as_tensor(array) for array in (x, y, mask))
    optimiser = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, epochs)
    history = []
    net.train()
    for _ in range(epochs):
        order, total = torch.randperm(len(x_t)), 0.0
        for start in range(0, len(x_t), 256):
            pick = order[start : start + 256]
            optimiser.zero_grad()
            value = loss(net(x_t[pick]), y_t[pick], mask_t[pick], x_t[pick], topple_weight)
            value.backward()
            optimiser.step()
            total += value.item() * len(pick)
        schedule.step()
        history.append(total / len(x_t))
    return history


class Ensemble:
    """``ENSEMBLE`` copies of the model, asked together."""

    def __init__(self, nets: list[PushNet]) -> None:
        self.nets = [net.eval() for net in nets]

    def predict(self, x: np.ndarray) -> np.ndarray:
        """(copies, rows, outputs), raw: movements scaled, the yes-or-no as a logit."""
        with torch.no_grad():
            x_t = torch.as_tensor(x)
            return np.stack([net(x_t).numpy() for net in self.nets])

    def save(self, folder) -> None:
        folder.mkdir(parents=True, exist_ok=True)
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

    @classmethod
    def untrained(cls) -> Ensemble:
        """Copies at their starting weights, for a test that needs a model but not a trained one."""
        return cls([PushNet() for _ in range(ENSEMBLE)])


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
