"""Solution 3 in the full-arm cell: copy the pushes that worked.

The model reads the boxes the box model found and answers, in one go, with which
glass to push, which way, how far, and the six settings to hand MoveIt. It is not
told how to choose them. It is shown pushes that were made in the cell and worked,
and trained to answer the same way.

**Who the teacher is.** There is no hand-written teacher here. The pushes were
made at random, the cell scored each one, and the ones kept as demonstrations are
the ones that MoveIt could plan, that did not tip a glass, and that left the table
with more room than it had. The simulator is the expert: a demonstration is a push
it approved. This is the cheapest honest teacher, and its weakness is plain: it
can only show pushes that a random draw happened to find.

**What "finished" is taught from.** A table with every glass already pickable is
shown with the answer "finished", because the same network has to know when to
stop, and a network that only ever saw pushes would never say so.

Training is a plain supervised loss: a cross entropy on which glass (or
finished), and a squared error on the push, taken only at the glass that was
chosen. The glasses are shuffled every time they are used, so the network cannot
learn that "slot 0" means anything.
"""

from __future__ import annotations

import time
from pathlib import Path

import features as F
import numpy as np
import torch
from geometry import SAFE  # noqa: F401
from nets import PushPolicy
from solving import AS_NEEDED, Done, TurnByTurn
from torch import nn

WEIGHTS = Path(__file__).resolve().parent / "weights"


def demonstrations(records: list[dict], least_gain_mm: float = 4.0) -> tuple[list, int]:
    """(rows, mask, glass, action) for every push worth copying, and how many finished-tables there were."""
    demos, done = [], 0
    for r in records:
        before = F.boxes_of(r["before"])
        rows, mask = F.table_tensor(before)
        if all(g["pickable"] for g in r["before"]):
            demos.append((rows, mask, F.SLOTS, np.zeros(F.ACTION_WIDTH, np.float32)))  # the table is finished
            done += 1
            continue
        o = F.outcome(r)
        if not o["feasible"] or o["topple"]:
            continue
        # Worth copying: it freed a glass, or took real room off the table
        # without disturbing anything else much.
        if o["gain"] >= 1 or (o["eased"] >= least_gain_mm and o["disturbed"] < 0.01 and o["moved"] > 0.01):
            demos.append((rows, mask, r["request"]["glass"], F.action_vector(F.request_of(r))))
    return demos, done


def lessons(rows: list[dict]) -> tuple[list, int]:
    """(rows, mask, glass, action) for every turn of the search in ``teach.py``, and how many said "finished".

    A push the search made is copied unless it tipped a glass after all, which the
    search's tries can miss, because a try and the real push are not quite the same
    motion. A turn on which the search stopped is copied as "finished", and that
    includes tables that still had glasses short of room: the search tried thirty
    pushes there and none was worth making.
    """
    demos, done = [], 0
    for row in rows:
        table, mask = F.table_tensor(F.boxes_of(row["before"]))
        if row["request"] is None:
            demos.append((table, mask, F.SLOTS, np.zeros(F.ACTION_WIDTH, np.float32)))
            done += 1
        elif not row.get("toppled") and row["request"]["glass"] < F.SLOTS:
            demos.append((table, mask, row["request"]["glass"], F.action_vector(F.request_of(row))))
    return demos, done


def train(demos: list, epochs: int = 300, seed: int = 0, log=lambda *a: print(*a, flush=True)) -> PushPolicy:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = PushPolicy()
    optimiser = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-4)
    rows = torch.tensor(np.stack([d[0] for d in demos]))
    mask = torch.tensor(np.stack([d[1] for d in demos]))
    glass = torch.tensor([d[2] for d in demos])
    action = torch.tensor(np.stack([d[3] for d in demos]))
    n = len(demos)
    started = time.perf_counter()
    for epoch in range(epochs):
        order = rng.permutation(n)
        total = 0.0
        for k in range(0, n, 64):
            idx = order[k : k + 64]
            r, m, g, a = rows[idx].clone(), mask[idx].clone(), glass[idx].clone(), action[idx]
            # Shuffle the glasses, and the answer with them.
            for b in range(len(idx)):
                perm = torch.randperm(F.SLOTS)
                inverse = torch.argsort(perm)
                r[b], m[b] = r[b][perm], m[b][perm]
                if g[b] < F.SLOTS:
                    g[b] = inverse[g[b]]
            logits, push, _ = net(r, m)
            choice = nn.functional.cross_entropy(logits, g)
            real = g < F.SLOTS
            chosen = push[torch.arange(len(idx)), g.clamp(max=F.SLOTS - 1)]
            fit = ((chosen - a) ** 2).mean(1)
            fit = (fit * real).sum() / real.sum().clamp(min=1)
            loss = choice + 2.0 * fit
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            total += float(loss) * len(idx)
        if log and (epoch % 50 == 49 or epoch == epochs - 1):
            log(f"  epoch {epoch + 1}/{epochs}: loss {total / n:.3f}, {time.perf_counter() - started:.0f} s")
    return net.eval()


class Imitation(TurnByTurn):
    name = "imitation (copies the pushes that worked)"
    looking = AS_NEEDED  # it reads the boxes, so one picture that shows every glass is enough

    def __init__(self, weights: Path | None = None) -> None:
        self.net = PushPolicy()
        self.net.load_state_dict(torch.load(weights or WEIGHTS / "imitation.pt", weights_only=True))
        self.net.eval()
        self.refused: set[int] = set()

    def begin(self) -> None:
        self.refused = set()
        self.last = None

    @torch.no_grad()
    def decide(self, look):
        boxes = list(look.boxes)
        if not boxes:
            return Done("no glass in view")
        if look.refused and getattr(self, "last", None) is not None:
            self.refused.add(self.last)
        rows, mask = F.table_tensor(boxes)
        logits, push, _ = self.net(torch.tensor(rows)[None], torch.tensor(mask)[None])
        scores = logits[0].clone()
        for k in self.refused:
            if k < F.SLOTS:
                scores[k] = -1e9
        choice = int(scores.argmax())
        if choice == F.SLOTS or F.pickable_count(boxes) == len(boxes):
            return Done(
                "every glass has room"
                if F.pickable_count(boxes) == len(boxes)
                else "the model says the table is finished"
            )
        self.last = choice
        return F.request_from(choice, push[0, choice].numpy())


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("records", nargs="*")
    parser.add_argument("--lessons", nargs="*", default=[], help="turns of the search, from teach.py")
    parser.add_argument("--repeat", type=int, default=1, help="how many times each lesson is shown per pass")
    parser.add_argument(
        "--stop-repeat", type=int, help="the same for lessons that say 'finished' (default: --repeat)"
    )
    parser.add_argument("--epochs", type=int, default=300)
    parser.add_argument("--tag", default="imitation")
    a = parser.parse_args()
    records = F.load_records(*a.records)
    demos, finished = demonstrations(records) if records else ([], 0)
    print(f"{len(records)} pushes -> {len(demos)} demonstrations ({finished} of them 'finished')")
    taught, stops = lessons(F.load_records(*a.lessons)) if a.lessons else ([], 0)
    print(f"{len(taught)} lessons from the search ({stops} of them 'finished'), each shown {a.repeat} times")
    # Most lessons say "finished", so shown as often as the pushes they teach the policy to stop everywhere.
    stop_repeat = a.repeat if a.stop_repeat is None else a.stop_repeat
    demos += [d for d in taught if d[2] != F.SLOTS] * a.repeat + [
        d for d in taught if d[2] == F.SLOTS
    ] * stop_repeat
    net = train(demos, a.epochs)
    WEIGHTS.mkdir(exist_ok=True)
    torch.save(net.state_dict(), WEIGHTS / f"{a.tag}.pt")
    (Path(__file__).resolve().parent / "results").mkdir(exist_ok=True)
    (Path(__file__).resolve().parent / "results" / f"{a.tag}-training.json").write_text(
        json.dumps(
            {
                "pushes": len(records),
                "demonstrations": len(demos),
                "finished": finished,
                "lessons": len(taught),
                "lessons_finished": stops,
                "repeat": a.repeat,
                "stop_repeat": stop_repeat,
                "epochs": a.epochs,
            },
            indent=1,
        )
    )
