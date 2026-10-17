"""The decision in front of the policy: which kind of answer to give, and at which glass.

## What this is, and the measurement it comes from

Problem 4's teacher gives four kinds of answer, and four of every five are a
move to see from somewhere else rather than anything that touches a glass. A
single network fitted to copy the teacher has to produce both kinds from one
output, and fitting minimises the average distance to the teacher's answer, so
wherever the picture does not say which kind was wanted it produces something
between them. Something between a look and a push is a look. That is why the
first held-out walk of this solution freed no glasses at all: it had learned the
teacher's travelling, which is most of the data, and not its pushing, which is
the part that changes the table.

This file is the first half of the answer to that. **One small model decides
what kind of answer to give and which glass to give it at, and the chunked
policy then draws only that.** Two models, each with one job, instead of one
model with two jobs that it has to average.

## What it is shown and what it says

It is shown exactly what the policy is shown, minus the decision itself: the
picture from the camera on the arm, the readings of the glasses that picture
caught, and three numbers the solution keeps about its own behaviour on this
table -- how many answers it has given, how many since it last touched a glass,
and how far the jaw has travelled since then.

Those three matter more than they look. A solution shown one picture at a time
cannot tell "I have just arrived" from "I have been all the way round and there
is nothing to do", and saying when a table is finished is part of the job in
problem 4. The teacher's own rule is that it has walked the whole ring since its
last push; these three numbers are what a model can learn that from, and they
are facts about the solution and not about the table.

It says two things. The **kind** is one of four: go and look, probe a glass with
a five-millimetre shove, push a glass at the task, or say the table is finished.
The **slot** is which of the glasses in the picture the answer is aimed at, in
the order the readings are laid out, with one extra value meaning "none of
them", which is what a look and a finish are aimed at.

## How it is fitted

On the teacher's own decisions, from the same demonstrations the policy is
fitted on: ``collect.py`` writes down which kind each of the teacher's answers
was and which glass it was aimed at. The loss is the ordinary one for a choice
between named things -- cross-entropy -- added over the two heads, and the
measurement printed at the end is how often each head agrees with the teacher on
tables the fit never saw.

It is small by design: a few convolutions over the picture, the numbers joined
on at the end, and two linear heads. A fit takes minutes rather than the hour
the chunked policy takes, which is what makes it cheap to try at all.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import readings
import torch
from torch import nn

HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "weights"

# The fit. A batch of sixty-four and a few thousand steps is minutes on this
# machine's graphics chip, and the accuracy printed at the end stops improving
# well before the end of it.
STEPS = 4_000
BATCH = 64
LEARNING_RATE = 3e-4

# How many channels each convolution keeps. Four of them halve the picture each
# time, so a 192-pixel picture arrives at the heads as a 12 by 12 grid.
CHANNELS = (16, 32, 64, 64)


def where_to_run() -> str:
    """The fastest device this machine has, which is Apple's Metal here."""
    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


class Gate(nn.Module):
    """The two-headed decision: which kind of answer, and which glass it is aimed at."""

    def __init__(self, numbers: int = readings.GATE_WIDTH) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        was = 3
        for channels in CHANNELS:
            layers += [nn.Conv2d(was, channels, 3, stride=2, padding=1), nn.ReLU()]
            was = channels
        self.seeing = nn.Sequential(*layers, nn.AdaptiveAvgPool2d(1), nn.Flatten())
        self.joining = nn.Sequential(
            nn.Linear(was + numbers, 128), nn.ReLU(), nn.Linear(128, 128), nn.ReLU()
        )
        self.kinds = nn.Linear(128, len(readings.KINDS))
        self.slots = nn.Linear(128, readings.GLASSES + 1)

    def forward(self, pictures: torch.Tensor, numbers: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        joined = self.joining(torch.cat([self.seeing(pictures), numbers], dim=1))
        return self.kinds(joined), self.slots(joined)


class Decider:
    """A fitted gate, asked one look at a time.

    It holds the device and the scaling so that a caller hands it the picture
    the camera rendered and the numbers ``readings`` builds, exactly as the
    chunked policy is called, and nothing about torch leaks into the run.
    """

    def __init__(self, net: Gate, device: str, shrink) -> None:
        self.net = net.to(device).eval()
        self.device = device
        self.shrink = shrink

    @classmethod
    def load(cls, path: Path, shrink, device: str | None = None) -> Decider:
        where = device or where_to_run()
        net = Gate()
        net.load_state_dict(torch.load(path, map_location=where))
        return cls(net, where, shrink)

    def decide(self, picture: np.ndarray, numbers: np.ndarray) -> tuple[int, int]:
        """The kind of answer to give, and the slot of the glass to give it at."""
        with torch.no_grad():
            kinds, slots = self.net(self._picture(picture), self._numbers(numbers))
        return int(kinds.argmax(1)), int(slots.argmax(1))

    def _picture(self, picture: np.ndarray) -> torch.Tensor:
        small = self.shrink(picture)
        array = np.asarray(small, dtype=np.float32) / 255.0
        return torch.from_numpy(array.transpose(0, 3, 1, 2)).to(self.device)

    def _numbers(self, numbers: np.ndarray) -> torch.Tensor:
        return torch.from_numpy(np.asarray(numbers, dtype=np.float32)[None]).to(self.device)


def fit(
    pictures: np.ndarray,
    numbers: np.ndarray,
    decisions: np.ndarray,
    seed: int,
    steps: int = STEPS,
    batch: int = BATCH,
) -> tuple[Gate, list[float]]:
    """One fit of the gate on the teacher's decisions. Returns it and its loss curve.

    The mixture is left exactly as the teacher gave it, which is the opposite of
    what ``train.py`` does for the chunked policy, and the difference is the
    point. The policy has to *draw* a push, so it needs to see pushes as often as
    looks or the average of its material swamps them. The gate has to *choose*
    between the kinds, so how often each kind really happens is part of what it
    is being asked to learn.
    """
    device = where_to_run()
    torch.manual_seed(seed)
    net = Gate(numbers.shape[1]).to(device)
    net.train()
    optimiser = torch.optim.AdamW(net.parameters(), lr=LEARNING_RATE)
    loss_of = nn.CrossEntropyLoss()
    rng = np.random.default_rng(seed)
    curve, running, clock = [], [], time.time()
    for step in range(steps):
        rows = rng.integers(0, len(decisions), size=batch)
        shown = torch.from_numpy(pictures[rows].astype(np.float32).transpose(0, 3, 1, 2) / 255.0)
        told = torch.from_numpy(numbers[rows])
        kinds, slots = net(shown.to(device), told.to(device))
        wanted = torch.from_numpy(decisions[rows]).to(device)
        loss = loss_of(kinds, wanted[:, 0]) + loss_of(slots, wanted[:, 1])
        loss.backward()
        optimiser.step()
        optimiser.zero_grad(set_to_none=True)
        running.append(float(loss.detach()))
        if (step + 1) % max(1, steps // 10) == 0:
            curve.append(round(float(np.mean(running)), 4))
            running = []
            print(
                f"  gate {seed} step {step + 1}/{steps}: loss {curve[-1]:.3f}, "
                f"{(time.time() - clock) / 60:.1f} min",
                flush=True,
            )
    return net, curve


def how_often_right(
    net: Gate, pictures: np.ndarray, numbers: np.ndarray, decisions: np.ndarray, batch: int = 128
) -> dict:
    """How often each head agrees with the teacher, over a whole set.

    Reported per kind as well as over everything, because the kinds are very
    unequal: a gate that answered "look" to everything would be right four times
    in five and useless, and only the per-kind figures show that.
    """
    device = next(net.parameters()).device
    net.eval()
    kinds = np.empty(len(decisions), dtype=np.int64)
    slots = np.empty(len(decisions), dtype=np.int64)
    with torch.no_grad():
        for at in range(0, len(decisions), batch):
            shown = pictures[at : at + batch].astype(np.float32).transpose(0, 3, 1, 2) / 255.0
            said, slot = net(
                torch.from_numpy(shown).to(device), torch.from_numpy(numbers[at : at + batch]).to(device)
            )
            kinds[at : at + batch] = said.argmax(1).cpu().numpy()
            slots[at : at + batch] = slot.argmax(1).cpu().numpy()
    net.train()
    right = {
        "kind_right": round(float((kinds == decisions[:, 0]).mean()), 3),
        "slot_right": round(float((slots == decisions[:, 1]).mean()), 3),
    }
    for kind, name in enumerate(readings.KINDS):
        wanted = decisions[:, 0] == kind
        if not wanted.any():
            continue
        right[f"{name}_found"] = round(float((kinds[wanted] == kind).mean()), 3)
        aimed = wanted & (decisions[:, 1] != readings.NO_GLASS)
        if aimed.any():
            right[f"{name}_slot_right"] = round(float((slots[aimed] == decisions[aimed, 1]).mean()), 3)
    return right


def saved(seed: int) -> Path:
    """Where a fitted gate goes, beside the chunked policy's own weights."""
    return WEIGHTS / f"gate-{seed}.pt"
