"""Solution 4 in the full-arm cell: learn what a push does, then search for a good one.

Imitation copies pushes. This solution learns something different: a stand-in for
the cell. Given a table and a push -- which glass, which way, how far, and the six
settings handed to MoveIt -- the model says whether MoveIt could plan it, whether a
glass would go over, where the pushed glass would end up, how much it would knock
the others about, and how long the arm would take. Then it chooses a push the way a
person would with a model of the cell: imagine many pushes, score what each would
leave, and make the best.

**Why this suits the two learned jobs.** Where a glass should go (job 1) and what
to tell MoveIt so that it does not tip (job 2) are one search here. The settings
are part of the push the search varies, and the model has learned from the cell
that a fast, high stroke tips glasses, so the search finds slow, low ones on its own.

**Five models, not one.** A single model is wrong in places and the search is
good at finding the places where it is wrong in its own favour: it picks the push
the model is most optimistic about, which is often the push it has seen least.
Five networks started from different weights agree where they have data and
disagree where they do not, and the search is penalised by how much they disagree.
"""

from __future__ import annotations

import math
import random
import time
from pathlib import Path

import features as F
import numpy as np
import torch
from nets import WorldModel
from pusher import Box
from torch import nn

from contract import Done

WEIGHTS = Path(__file__).resolve().parent / "weights"
MODELS = 5
MOVE, TIME = 0.05, 10.0  # scales that keep every target near one


def samples(records: list[dict]):
    rows, masks, glass, action, target, valid = [], [], [], [], [], []
    for r in records:
        r_, m_ = F.table_tensor(F.boxes_of(r["before"]))
        o = F.outcome(r)
        k = r["request"]["glass"]
        rows.append(r_)
        masks.append(m_)
        glass.append(k)
        action.append(F.action_vector(F.request_of(r)))
        # feasible, topple, along, across, disturbance, seconds, gain, room eased, success
        target.append(
            [
                float(o["feasible"]),
                float(o["topple"]),
                o["moved"] / MOVE,
                _signed_across(r) / MOVE,
                o["disturbed"] / MOVE,
                o["seconds"] / TIME,
                float(np.clip(o["gain"], -2, 2)),
                float(np.clip(o["eased"], -40, 40)) / 20.0,
                float(o["feasible"] and not o["topple"] and o["gain"] >= 1),
            ]
        )
        valid.append(o["feasible"])

    def t(a, dt=torch.float32):
        return torch.tensor(np.stack(a) if isinstance(a[0], np.ndarray) else a, dtype=dt)

    return t(rows), t(masks, torch.bool), t(glass, torch.long), t(action), t(target), t(valid, torch.bool)


def _signed_across(r: dict) -> float:
    """Sideways drift of the pushed glass: positive to the left of the push."""
    if not r["feasible"]:
        return 0.0
    k, q = r["request"]["glass"], r["request"]
    u = (math.cos(q["heading"]), math.sin(q["heading"]))
    d = (r["after"][k]["x"] - r["before"][k]["x"], r["after"][k]["y"] - r["before"][k]["y"])
    return -d[0] * u[1] + d[1] * u[0]


def loss_of(net: WorldModel, rows, mask, glass, action, target, valid):
    out = net(rows, mask, glass, action)
    feasible = nn.functional.binary_cross_entropy_with_logits(out[:, 0], target[:, 0])
    # Whether a push works is learned from every push, because most are failures
    # and a model shown only the successes could not tell a good push from a bad one.
    success = nn.functional.binary_cross_entropy_with_logits(out[:, 8], target[:, 8])
    if valid.any():
        topple = nn.functional.binary_cross_entropy_with_logits(out[valid, 1], target[valid, 1])
        regress = nn.functional.smooth_l1_loss(out[valid][:, 2:8], target[valid][:, 2:8])
    else:
        topple = regress = out.sum() * 0
    total = feasible + topple + regress + success
    return total, (float(feasible), float(topple), float(regress), float(success))


def train(
    records: list[dict], epochs: int = 150, seed: int = 0, log=lambda *a: print(*a, flush=True)
) -> list[WorldModel]:
    data = samples(records)
    n = len(records)
    split = int(0.9 * n)
    order = np.random.default_rng(seed).permutation(n)
    train_idx, held_idx = order[:split], order[split:]
    nets = []
    for m in range(MODELS):
        torch.manual_seed(seed * 100 + m)
        net = WorldModel()
        optimiser = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-4)
        rng = np.random.default_rng(seed * 100 + m)
        started = time.perf_counter()
        for _ in range(epochs):
            # Each model sees a different bootstrap of the data, so they differ where data is thin.
            sample = rng.choice(train_idx, len(train_idx))
            for k in range(0, len(sample), 128):
                idx = sample[k : k + 128]
                batch = [d[idx] for d in data]
                loss, _ = loss_of(net, *batch)
                optimiser.zero_grad()
                loss.backward()
                optimiser.step()
        net.eval()
        with torch.no_grad():
            held, parts = loss_of(net, *[d[held_idx] for d in data])
        if log:
            log(
                f"  model {m + 1}/{MODELS}: held-out loss {float(held):.3f} (feasible {parts[0]:.3f}, "
                f"topple {parts[1]:.3f}, move {parts[2]:.3f}, works {parts[3]:.3f}), "
                f"{time.perf_counter() - started:.0f} s"
            )
        nets.append(net)
    return nets


class PlanningSolution:
    name = "world model (imagines pushes, makes the best)"

    # What a topple costs, how far the five models' disagreement is distrusted, and what a
    # second of arm time costs, all in units of "probability that the push works". Below
    # THRESHOLD the table is left as it is. A push MoveIt refuses costs the arm nothing, so
    # a push that is only possible one time in five is still worth asking for if it would
    # be worth making. Set by looking at the pushes the models liked on tables below the
    # held-out line, and nowhere else.
    TOPPLE, DOUBT, SECOND = 1.0, 0.5, 0.002
    THRESHOLD = 0.1
    # How many pushes the search imagines: first drawn the way round two drew its informed
    # pushes, then the best few shaken a little, twice.
    POOL, ELITES, SHAKES, ROUNDS = 320, 24, 10, 2

    def __init__(self, weights: Path | None = None, seed: int = 0) -> None:
        state = torch.load(weights or WEIGHTS / "world-models.pt", weights_only=True)
        self.nets = []
        for s in state:
            net = WorldModel()
            net.load_state_dict(s)
            self.nets.append(net.eval())
        self.rng = random.Random(seed)

    def begin(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.refused: set[int] = set()
        self.last = None

    @torch.no_grad()
    def imagine(self, boxes: list[Box], glass: np.ndarray, action: np.ndarray):
        rows, mask = F.table_tensor(boxes)
        n = len(glass)
        r = torch.tensor(rows)[None].expand(n, -1, -1)
        m = torch.tensor(mask)[None].expand(n, -1)
        outs = torch.stack(
            [net(r, m, torch.tensor(glass), torch.tensor(action, dtype=torch.float32)) for net in self.nets]
        )
        return outs

    def score(self, boxes: list[Box], glass: np.ndarray, action: np.ndarray):
        """How good each imagined push is, and the probabilities it was built from.

        A push is worth the chance that it works -- MoveIt plans it, no glass goes over and
        a glass is given room -- less the chance that it plans and tips a glass, less a
        charge for how far the five models disagree about it, less a charge for arm time.
        """
        outs = self.imagine(boxes, glass, action)
        works = torch.sigmoid(outs[:, :, 8])
        feasible = torch.sigmoid(outs[:, :, 0]).mean(0).numpy()
        topple = torch.sigmoid(outs[:, :, 1]).mean(0).numpy()
        seconds = outs.mean(0)[:, 5].numpy() * TIME
        total = (
            works.mean(0).numpy()
            - self.TOPPLE * feasible * topple
            - self.DOUBT * works.std(0).numpy()
            - self.SECOND * feasible * seconds
        )
        return total, feasible, topple

    def candidates(self, boxes: list[Box], usable: list[int]) -> list:
        """Pushes worth imagining: each would, if it went as asked, leave its glass with room.

        These are drawn by ``collect_pushes.informed_request``, which uses problem 3's own two
        tests -- the hand fits between the glasses, and the glass ends with room. Nothing
        here says whether the arm can make the push, or whether the glass would tip: the
        models are asked that. If the geometry finds nothing, nothing is imagined.
        """
        import collect_pushes as CP

        pool = []
        for _ in range(self.POOL * 3):
            request = CP.informed_request(self.rng, boxes, tries=40)
            if request is not None and request.glass in usable:
                pool.append(request)
            if len(pool) >= self.POOL:
                break
        return pool

    def shaken(self, request, boxes: list[Box]):
        """The same push, a little different: the direction, the distance and every setting nudged."""
        vector = F.action_vector(request).copy()
        angle = math.atan2(vector[1], vector[0]) + self.rng.gauss(0.0, 0.12)
        vector[0], vector[1] = math.cos(angle), math.sin(angle)
        vector[2:] = np.clip(vector[2:] + np.array([self.rng.gauss(0.0, 0.1) for _ in vector[2:]]), 0.0, 1.0)
        return F.request_from(request.glass, vector)

    def search(self, boxes: list[Box], usable: list[int]):
        """Imagine a pool of pushes, keep the best few, shake them, and repeat.

        Returns (score, glass, push numbers) of the best push imagined, or a score of minus
        infinity when the geometry offers nothing to imagine.
        """
        pool = self.candidates(boxes, usable)
        best = (-math.inf, 0, np.zeros(F.ACTION_WIDTH, dtype=np.float32))
        for _ in range(self.ROUNDS + 1):
            if not pool:
                break
            glass = np.array([r.glass for r in pool])
            action = np.stack([F.action_vector(r) for r in pool])
            scores, _, _ = self.score(boxes, glass, action)
            order = np.argsort(-scores)
            if scores[order[0]] > best[0]:
                best = (float(scores[order[0]]), int(glass[order[0]]), action[order[0]].copy())
            elites = [pool[i] for i in order[: self.ELITES]]
            pool = []
            for request in elites:
                for _ in range(self.SHAKES):
                    nudged = self.shaken(request, boxes)
                    if F.hand_clear(boxes, nudged.glass, nudged.heading, nudged.travel):
                        pool.append(nudged)
        return best

    def decide(self, look):
        boxes = list(look.boxes)
        if not boxes:
            return Done("no glass in view")
        if look.refused and self.last is not None:
            self.refused.add(self.last)
        if F.pickable_count(boxes) == len(boxes):
            return Done("every glass has room")
        usable = [k for k in range(len(boxes)) if k not in self.refused and k < F.SLOTS]
        if not usable:
            return Done("nothing left that can be pushed")
        best = self.search(boxes, usable)
        if best[0] <= self.THRESHOLD:
            return Done("no push the model expects to work")
        self.last = best[1]
        return F.request_from(best[1], best[2])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("records", nargs="+")
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--tag", default="world-models")
    a = parser.parse_args()
    records = F.load_records(*a.records)
    print(f"{len(records)} pushes")
    nets = train(records, a.epochs)
    WEIGHTS.mkdir(exist_ok=True)
    torch.save([n.state_dict() for n in nets], WEIGHTS / f"{a.tag}.pt")
