"""Solution 5: learn by trying, with a small budget.

``python reinforcement_learning.py train --iterations 15 --workers 8 --steps 20``

The model is told nothing about how to push. It is put in front of tables, asked
to choose a push, and told afterwards how it did. Over a few thousand pushes it
works out which choices were rewarded. This is reinforcement learning in its
plainest form -- PPO, with one network that both chooses and estimates how good
the table is -- and the point of running it here is to learn what it does with
very little experience, not to win.

**What it chooses.** The same thing as the other learned solutions: which glass,
which way, how far, and the six settings handed to MoveIt. MoveIt makes the move.

**What it is paid.** For each push:

* +1 for every glass the push made pickable, minus one for every glass it made
  unpickable;
* +0.5 for each centimetre of total room the table gained, so that a push that
  frees nothing yet but loosens the table is still better than one that does
  nothing;
* -3 if a glass went over, and the table ends there, as it does in the cell;
* -0.5 if MoveIt could not plan the push, because a refused push costs the arm
  nothing but costs the run a turn;
* -0.01 for every second of arm time;
* when it says "finished": +1 if every glass has room, -2 if one does not.

**What it sees.** The boxes. For training, they are the simulator's glasses with
errors added of about the size the box model makes (2 mm in position, 1.5 mm in
radius and 6 mm in height), because reading a picture twice per push would triple
the cost of every push and the box model's errors are the only thing the pictures
add. The model is judged with the real box model, on pictures.

**How it runs.** The learner starts several worker processes, each with its own
MoveIt and its own table, hands each the current network, and gathers what they
tried. Then it improves the network on all of it and does it again.
"""

from __future__ import annotations

import argparse
import json
import pickle
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from examiner.motion.push_motions import Box
from shared.learning import table_and_push_encoding as F
from shared.learning.learned_networks import PushPolicy
from shared.turn_by_turn_loop import AS_NEEDED, Done, Refused, TurnByTurn

HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "weights"
SCRATCH = HERE / "data" / "rl"

NOISE = {"x": 0.002, "r": 0.0015, "h": 0.006}
MAX_PUSHES = 4

# The pay, in one place so the docs can quote it.
PAY = {
    "glass": 1.0,
    "room_per_cm": 0.5,
    "topple": -3.0,
    "refused": -0.5,
    "second": -0.01,
    "right_stop": 1.0,
    "wrong_stop": -2.0,
}


def noisy(boxes: list[Box], rng: random.Random) -> list[Box]:
    return [
        Box(
            b.x + rng.gauss(0, NOISE["x"]),
            b.y + rng.gauss(0, NOISE["x"]),
            max(0.015, b.radius + rng.gauss(0, NOISE["r"])),
            max(0.03, b.height + rng.gauss(0, NOISE["h"])),
            b.foot,
        )
        for b in boxes
    ]


def new_policy() -> PushPolicy:
    net = PushPolicy()
    # Start from "push gently, from the middle of every range, sideways to the
    # line to the nearest neighbour": the last layer is small and its bias says
    # that. The first two numbers are an angle measured from the direction away
    # from the neighbour, and (0, 1) is a quarter turn from it. Sideways because
    # that is where the arm can go: measured over 1,949 random pushes, a push
    # straight away from a neighbour was never possible (the hand would have to
    # come down in the gap between the two), and one at a right angle to it was
    # possible a third of the time.
    last = net.push[-1]
    nn.init.normal_(last.weight, 0.0, 0.02)
    last.bias.data = torch.tensor([0.0, 1.0, 0.5, 0.5, 0.3, 0.5, 0.5, 0.5, 0.5])
    return net


# --------------------------------------------------------------------- acting


def act(net: PushPolicy, boxes: list[Box], greedy: bool, rng: np.random.Generator | None = None):
    """Choose a push. Returns (glass or SLOTS for finished, raw numbers, log probability, value)."""
    rows, mask = F.table_tensor(boxes)
    rows_t, mask_t = torch.tensor(rows)[None], torch.tensor(mask)[None]
    with torch.no_grad():
        logits, push, value = net(rows_t, mask_t)
    dist = torch.distributions.Categorical(logits=logits[0])
    glass = int(logits[0].argmax()) if greedy else int(dist.sample())
    log_p = float(dist.log_prob(torch.tensor(glass)))
    chosen = push[0, min(glass, F.SLOTS - 1)]
    if greedy:
        raw = chosen
    else:
        std = net.spread.exp()
        raw = torch.distributions.Normal(chosen, std).sample()
        if glass < F.SLOTS:
            log_p += float(torch.distributions.Normal(chosen, std).log_prob(raw).sum())
    return glass, raw.numpy(), log_p, float(value[0])


# -------------------------------------------------------------------- workers


def pay(before: list[Box], after: list[Box], pushed, seconds: float, toppled: bool) -> float:
    reward = PAY["glass"] * (F.pickable_count(after) - F.pickable_count(before))
    reward += PAY["room_per_cm"] * 100 * (F.shortfall(before) - F.shortfall(after))
    reward += PAY["second"] * seconds
    if toppled:
        reward += PAY["topple"]
    return reward


def rollout(weights: Path, first: int, steps: int, out: Path, worker: int, greedy: bool = False) -> None:
    from examiner.examining import one_table_cell as C
    from examiner.motion.moveit_connection import MoveItLink

    net = new_policy()
    net.load_state_dict(torch.load(weights, weights_only=True))
    net.eval()
    random.seed(first * 31 + worker)
    py = random.Random(first * 31 + worker)
    rng = np.random.default_rng(first * 31 + worker)
    transitions = []
    episodes = []
    seed = first
    with MoveItLink(domain=worker) as link:
        while len(transitions) < steps:
            cell = C.ArmCell(seed, link, camera=False)
            seed += 1
            score = 0.0
            try:
                for _ in range(MAX_PUSHES):
                    truth = _truth(cell)
                    boxes = noisy(truth, py)
                    rows, mask = F.table_tensor(boxes)
                    glass, raw, log_p, value = act(net, boxes, greedy, rng)
                    stop = glass >= F.SLOTS or glass >= len(boxes)
                    if stop:
                        crowded = F.pickable_count(truth) < len(truth)
                        reward = PAY["wrong_stop"] if crowded else PAY["right_stop"]
                        done = True
                    else:
                        before = truth
                        seconds_before = cell.arm_seconds
                        result = cell.push(boxes, F.relative_request(glass, raw, boxes))
                        if result.ok:
                            after = _truth(cell)
                            topple = cell.toppled() > 0
                            reward = pay(before, after, result, cell.arm_seconds - seconds_before, topple)
                            done = topple
                        else:
                            reward, done, topple = PAY["refused"], False, False
                    transitions.append(
                        {
                            "rows": rows,
                            "mask": mask,
                            "glass": glass,
                            "raw": raw,
                            "log_p": log_p,
                            "value": value,
                            "reward": reward,
                            "done": done,
                        }
                    )
                    score += reward
                    if done:
                        break
                if transitions and not transitions[-1]["done"]:
                    transitions[-1]["done"] = True  # the table's four pushes are used up
            finally:
                cell.close()
            episodes.append(score)
    with open(out, "wb") as handle:
        pickle.dump({"transitions": transitions, "episodes": episodes}, handle)


def _truth(cell) -> list[Box]:
    simulator = cell.simulator
    boxes = []
    for i, glass in enumerate(simulator.glasses):
        x, y = simulator.position(i)
        o = glass.outline
        boxes.append(
            Box(float(x), float(y), float(o.max_diameter / 2), float(o.total_height), float(o.radius[0]))
        )
    return boxes


# -------------------------------------------------------------------- learner


def advantages(transitions: list[dict], gamma: float = 0.97, lam: float = 0.95):
    adv = np.zeros(len(transitions), dtype=np.float32)
    last = 0.0
    for t in reversed(range(len(transitions))):
        tr = transitions[t]
        nxt = 0.0 if tr["done"] or t == len(transitions) - 1 else transitions[t + 1]["value"]
        delta = tr["reward"] + gamma * nxt - tr["value"]
        last = delta + (0.0 if tr["done"] else gamma * lam * last)
        adv[t] = last
    returns = adv + np.array([tr["value"] for tr in transitions], dtype=np.float32)
    return adv, returns


def update(
    net: PushPolicy, optimiser, transitions: list[dict], epochs: int = 6, batch: int = 64, clip: float = 0.2
) -> dict:
    adv, ret = advantages(transitions)
    adv = (adv - adv.mean()) / (adv.std() + 1e-6)
    rows = torch.tensor(np.stack([t["rows"] for t in transitions]))
    mask = torch.tensor(np.stack([t["mask"] for t in transitions]))
    glass = torch.tensor([t["glass"] for t in transitions])
    raw = torch.tensor(np.stack([t["raw"] for t in transitions]), dtype=torch.float32)
    old = torch.tensor([t["log_p"] for t in transitions])
    adv_t, ret_t = torch.tensor(adv), torch.tensor(ret)
    n = len(transitions)
    stats = {}
    for _ in range(epochs):
        order = torch.randperm(n)
        for k in range(0, n, batch):
            idx = order[k : k + batch]
            logits, push, value = net(rows[idx], mask[idx])
            dist = torch.distributions.Categorical(logits=logits)
            log_p = dist.log_prob(glass[idx])
            pushed = glass[idx] < F.SLOTS
            chosen = push[torch.arange(len(idx)), glass[idx].clamp(max=F.SLOTS - 1)]
            normal = torch.distributions.Normal(chosen, net.spread.exp())
            log_p = log_p + normal.log_prob(raw[idx]).sum(1) * pushed
            ratio = (log_p - old[idx]).exp()
            a = adv_t[idx]
            policy_loss = -torch.min(ratio * a, ratio.clamp(1 - clip, 1 + clip) * a).mean()
            value_loss = nn.functional.mse_loss(value, ret_t[idx])
            entropy = dist.entropy().mean()
            loss = policy_loss + 0.5 * value_loss - 0.03 * entropy
            optimiser.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            optimiser.step()
            stats = {"policy": float(policy_loss), "value": float(value_loss), "entropy": float(entropy)}
    return stats


def train(
    iterations: int,
    workers: int,
    steps: int,
    seed_start: int = 3000,
    tag: str = "reinforcement-v4",
    resume: bool = False,
    epochs: int = 6,
    minibatch: int = 64,
    lr: float = 3e-4,
) -> list[dict]:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    WEIGHTS.mkdir(exist_ok=True)
    torch.manual_seed(0)
    net = new_policy()
    optimiser = torch.optim.Adam(net.parameters(), lr)
    curve = []
    seed = seed_start
    started = time.perf_counter()
    total_steps = 0
    done_before = 0
    if resume and (HERE / "results" / f"{tag}-curve.json").exists():
        # Picks up from the last saved iteration: the weights are kept, the
        # optimiser's running averages are not, and start afresh.
        curve = json.loads((HERE / "results" / f"{tag}-curve.json").read_text())
        net.load_state_dict(torch.load(WEIGHTS / f"{tag}.pt", weights_only=True))
        done_before, total_steps = len(curve), curve[-1]["steps"]
        seed = seed_start + 40 * workers * done_before
        started -= curve[-1]["minutes"] * 60
    for it in range(done_before, iterations):
        weights = SCRATCH / "current.pt"
        torch.save(net.state_dict(), weights)
        children = []
        for w in range(workers):
            out = SCRATCH / f"rollout-{w}.pkl"
            out.unlink(missing_ok=True)
            children.append(
                (
                    out,
                    subprocess.Popen(
                        [
                            sys.executable,
                            __file__,
                            "work",
                            "--weights",
                            str(weights),
                            "--first",
                            str(seed),
                            "--steps",
                            str(steps),
                            "--out",
                            str(out),
                            "--worker",
                            str(w),
                        ]
                    ),
                )
            )
            seed += 40
        transitions, episodes = [], []
        for out, child in children:
            child.wait()
            if out.exists():
                with open(out, "rb") as handle:
                    got = pickle.load(handle)
                transitions += got["transitions"]
                episodes += got["episodes"]
        net.train()
        stats = update(net, optimiser, transitions, epochs=epochs, batch=minibatch)
        net.eval()
        total_steps += len(transitions)
        pushes = [t for t in transitions if t["glass"] < F.SLOTS]
        row = {
            "iteration": it + 1,
            "steps": total_steps,
            "episodes": len(episodes),
            "mean_return": float(np.mean(episodes)),
            "refused_share": float(
                np.mean(
                    [
                        t["reward"] <= PAY["refused"] + 1e-9 and t["reward"] > PAY["refused"] - 1e-9
                        for t in pushes
                    ]
                )
            )
            if pushes
            else 0.0,
            "topple_share": float(np.mean([t["reward"] < -2.0 for t in pushes])) if pushes else 0.0,
            "finished_share": float(np.mean([t["glass"] >= F.SLOTS for t in transitions])),
            **stats,
            "minutes": round((time.perf_counter() - started) / 60, 1),
        }
        curve.append(row)
        print(json.dumps(row), flush=True)
        torch.save(net.state_dict(), WEIGHTS / f"{tag}.pt")
        (HERE / "results").mkdir(exist_ok=True)
        (HERE / "results" / f"{tag}-curve.json").write_text(json.dumps(curve, indent=1))
    return curve


# ------------------------------------------------------------------ the solution


class Learner(TurnByTurn):
    name = "reinforcement learning (limited training)"
    looking = AS_NEEDED  # it reads the boxes, so one picture that shows every glass is enough

    def __init__(self, weights: Path | None = None) -> None:
        self.net = new_policy()
        self.net.load_state_dict(torch.load(weights or WEIGHTS / "reinforcement-v4.pt", weights_only=True))
        self.net.eval()

    def begin(self) -> None:
        self.refused = Refused()
        self.last = None

    def decide(self, look):
        boxes = list(look.boxes)
        if not boxes:
            return Done("no glass in view")
        if look.refused and self.last is not None:
            self.refused.add(boxes, self.last)
        rows, mask = F.table_tensor(boxes)
        for k in self.refused.among(boxes):
            if k < F.SLOTS:
                mask[k] = False
        with torch.no_grad():
            logits, push, _ = self.net(torch.tensor(rows)[None], torch.tensor(mask)[None])
        choice = int(logits[0].argmax())
        if choice >= F.SLOTS or not mask.any():
            return Done("the policy says the table is finished")
        self.last = choice
        return F.relative_request(choice, push[0, choice].numpy(), boxes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("train", "work"))
    parser.add_argument("--iterations", type=int, default=15)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--first", type=int, default=3000)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--worker", type=int, default=0)
    parser.add_argument("--tag", default="reinforcement-v4")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--epochs", type=int, default=6, help="passes over each round of experience")
    parser.add_argument("--minibatch", type=int, default=64)
    parser.add_argument("--lr", type=float, default=3e-4)
    a = parser.parse_args()
    if a.mode == "work":
        rollout(a.weights, a.first, a.steps, a.out, a.worker)
    else:
        train(
            a.iterations,
            a.workers,
            a.steps,
            tag=a.tag,
            resume=a.resume,
            epochs=a.epochs,
            minibatch=a.minibatch,
            lr=a.lr,
        )


if __name__ == "__main__":
    main()
