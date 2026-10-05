"""Which processor the models here run on, and saying so out loud.

This is an Apple silicon Mac. PyTorch reaches its GPU through a backend named
MPS, which sits where CUDA would sit on a machine with an NVIDIA card. There is
no NVIDIA card here, so the choice is MPS or the CPU and nothing else, and
asking for CUDA would only fail.

The choice is announced because it is the difference between a training run of
minutes and one of hours. A run that falls back to the CPU without saying so
looks like a run that is simply slow, and the log of a finished run should not
leave that to be guessed at.
"""

from __future__ import annotations

import torch

_announced = False


def pick() -> torch.device:
    """MPS when this machine has it, the CPU otherwise. Says which, once."""
    global _announced
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    if not _announced:
        print(f"running on {describe(device)}")
        _announced = True
    return device


def describe(device: torch.device) -> str:
    """One line naming the device, for a log or a report."""
    if device.type == "mps":
        return "the GPU through MPS, which shares its memory with the CPU"
    return "the CPU, because MPS is not available here"
