"""The small networks the learned solutions are made of.

Two networks, both reading a table as a set of glasses.

``PushPolicy`` answers "which glass, and how": a score for each glass, one more
score for "the table is finished", and for each glass the push that would be made
if it were chosen. Imitation trains it by copying pushes that worked and
reinforcement learning trains it by trying pushes and being scored.

``WorldModel`` answers "what would happen": given a table and a push, whether
MoveIt could plan it, whether a glass would go over, where the pushed glass would
end up, how much the neighbours would be disturbed, and how long the arm would
take. The solution that plans by search uses it as its stand-in for the cell.

Both start from the same encoder, a two-layer transformer over the glasses. A
transformer is used for one reason: a table has no order, and attention is the
usual way to make a network indifferent to the order of its inputs.
"""

from __future__ import annotations

import torch
from features import ACTION_WIDTH, GLASS_WIDTH, SLOTS
from torch import nn


class TableEncoder(nn.Module):
    def __init__(self, width: int = 64, layers: int = 2, heads: int = 4) -> None:
        super().__init__()
        self.embed = nn.Sequential(nn.Linear(GLASS_WIDTH, width), nn.ReLU(), nn.Linear(width, width))
        self.summary = nn.Parameter(torch.zeros(1, 1, width))  # one more token that reads the whole table
        block = nn.TransformerEncoderLayer(
            width, heads, 2 * width, dropout=0.0, batch_first=True, norm_first=True
        )
        self.encoder = nn.TransformerEncoder(block, layers, enable_nested_tensor=False)
        self.width = width

    def forward(self, rows: torch.Tensor, mask: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Per-glass vectors (B, SLOTS, width) and one for the whole table (B, width)."""
        tokens = self.embed(rows)
        tokens = torch.cat([self.summary.expand(len(rows), -1, -1), tokens], dim=1)
        padding = torch.cat([torch.zeros(len(rows), 1, dtype=torch.bool), ~mask], dim=1)
        out = self.encoder(tokens, src_key_padding_mask=padding)
        return out[:, 1:], out[:, 0]


class PushPolicy(nn.Module):
    """Which glass, and what push for it."""

    def __init__(self, width: int = 64) -> None:
        super().__init__()
        self.encoder = TableEncoder(width)
        self.choice = nn.Linear(width, 1)  # a score per glass
        self.finished = nn.Linear(width, 1)  # a score for "the table is finished"
        self.push = nn.Sequential(nn.Linear(width, width), nn.ReLU(), nn.Linear(width, ACTION_WIDTH))
        self.spread = nn.Parameter(
            torch.full((ACTION_WIDTH,), -1.2)
        )  # log standard deviation, for the reinforcement learner
        self.value = nn.Sequential(nn.Linear(width, width), nn.ReLU(), nn.Linear(width, 1))

    def forward(self, rows: torch.Tensor, mask: torch.Tensor):
        tokens, summary = self.encoder(rows, mask)
        scores = self.choice(tokens).squeeze(-1).masked_fill(~mask, -1e9)
        logits = torch.cat([scores, self.finished(summary)], dim=1)  # the last column is "finished"
        return logits, self.push(tokens), self.value(summary).squeeze(-1)


class WorldModel(nn.Module):
    """What a push would do.

    Nine heads: whether MoveIt could plan it, whether a glass would go over, how far the
    pushed glass would move along the push and across it, how much the others would be
    disturbed, how long the arm would take, how many glasses it would make pickable, how
    much room it would take off the table, and whether the push would work: planned, no
    glass over, and at least one glass given room.
    """

    OUTPUTS = 9

    def __init__(self, width: int = 64) -> None:
        super().__init__()
        self.encoder = TableEncoder(width)
        self.action = nn.Sequential(nn.Linear(ACTION_WIDTH, width), nn.ReLU())
        self.head = nn.Sequential(
            nn.Linear(3 * width, 2 * width),
            nn.ReLU(),
            nn.Linear(2 * width, 2 * width),
            nn.ReLU(),
            nn.Linear(2 * width, self.OUTPUTS),
        )

    def forward(self, rows, mask, glass, action):
        tokens, summary = self.encoder(rows, mask)
        chosen = tokens[torch.arange(len(rows)), glass]
        return self.head(torch.cat([chosen, summary, self.action(action)], dim=1))


__all__ = ["PushPolicy", "TableEncoder", "WorldModel", "SLOTS"]
