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

from examiner.motion.push_motions import GlassBox
from shared.learning import table_and_push_encoding
from shared.learning.learned_networks import PushPolicyNetwork
from shared.turn_by_turn_loop import LOOK_ONLY_AS_NEEDED, RefusedGlasses, TableFinished, TurnByTurnSolution

THIS_FOLDER = Path(__file__).resolve().parent
WEIGHTS_FOLDER = THIS_FOLDER / "weights"
ROLLOUT_FOLDER = THIS_FOLDER / "data" / "rl"

BOX_NOISE = {"x": 0.002, "r": 0.0015, "h": 0.006}
PUSHES_PER_TRAINING_TABLE = 4

# The pay, in one place so the docs can quote it.
REWARDS = {
    "glass": 1.0,
    "room_per_cm": 0.5,
    "topple": -3.0,
    "refused": -0.5,
    "second": -0.01,
    "right_stop": 1.0,
    "wrong_stop": -2.0,
}


def with_box_model_noise(boxes: list[GlassBox], rng: random.Random) -> list[GlassBox]:
    return [
        GlassBox(
            box.x + rng.gauss(0, BOX_NOISE["x"]),
            box.y + rng.gauss(0, BOX_NOISE["x"]),
            max(0.015, box.radius + rng.gauss(0, BOX_NOISE["r"])),
            max(0.03, box.height + rng.gauss(0, BOX_NOISE["h"])),
            box.foot,
        )
        for box in boxes
    ]


def new_push_policy() -> PushPolicyNetwork:
    network = PushPolicyNetwork()
    # Start from "push gently, from the middle of every range, sideways to the
    # line to the nearest neighbour": the last layer is small and its bias says
    # that. The first two numbers are an angle measured from the direction away
    # from the neighbour, and (0, 1) is a quarter turn from it. Sideways because
    # that is where the arm can go: measured over 1,949 random pushes, a push
    # straight away from a neighbour was never possible (the hand would have to
    # come down in the gap between the two), and one at a right angle to it was
    # possible a third of the time.
    last_layer = network.push[-1]
    nn.init.normal_(last_layer.weight, 0.0, 0.02)
    last_layer.bias.data = torch.tensor([0.0, 1.0, 0.5, 0.5, 0.3, 0.5, 0.5, 0.5, 0.5])
    return network


# --------------------------------------------------------------------- acting


def choose_push_to_try(
    network: PushPolicyNetwork, boxes: list[GlassBox], greedy: bool, rng: np.random.Generator | None = None
):
    """Choose a push. Returns (glass or GLASS_SLOTS for finished, raw numbers, log probability, value)."""
    rows, mask = table_and_push_encoding.encode_table(boxes)
    rows_tensor, mask_tensor = torch.tensor(rows)[None], torch.tensor(mask)[None]
    with torch.no_grad():
        logits, push_for_each_glass, value = network(rows_tensor, mask_tensor)
    glass_distribution = torch.distributions.Categorical(logits=logits[0])
    glass = int(logits[0].argmax()) if greedy else int(glass_distribution.sample())
    log_probability = float(glass_distribution.log_prob(torch.tensor(glass)))
    chosen_push = push_for_each_glass[0, min(glass, table_and_push_encoding.GLASS_SLOTS - 1)]
    if greedy:
        push_numbers = chosen_push
    else:
        spread = network.spread.exp()
        push_numbers = torch.distributions.Normal(chosen_push, spread).sample()
        if glass < table_and_push_encoding.GLASS_SLOTS:
            log_probability += float(
                torch.distributions.Normal(chosen_push, spread).log_prob(push_numbers).sum()
            )
    return glass, push_numbers.numpy(), log_probability, float(value[0])


# -------------------------------------------------------------------- workers


def reward_for_push(
    before: list[GlassBox], after: list[GlassBox], pusher_result, arm_seconds: float, toppled: bool
) -> float:
    reward = REWARDS["glass"] * (
        table_and_push_encoding.count_pickable_boxes(after)
        - table_and_push_encoding.count_pickable_boxes(before)
    )
    reward += (
        REWARDS["room_per_cm"]
        * 100
        * (
            table_and_push_encoding.total_room_shortfall(before)
            - table_and_push_encoding.total_room_shortfall(after)
        )
    )
    reward += REWARDS["second"] * arm_seconds
    if toppled:
        reward += REWARDS["topple"]
    return reward


def collect_rollouts(
    weights: Path,
    first_table: int,
    transitions_wanted: int,
    output_file: Path,
    worker_number: int,
    greedy: bool = False,
) -> None:
    from examiner.examining import one_table_cell
    from examiner.motion.moveit_connection import MoveItConnection

    network = new_push_policy()
    network.load_state_dict(torch.load(weights, weights_only=True))
    network.eval()
    random.seed(first_table * 31 + worker_number)
    python_rng = random.Random(first_table * 31 + worker_number)
    numpy_rng = np.random.default_rng(first_table * 31 + worker_number)
    transitions = []
    episodes = []
    table_number = first_table
    with MoveItConnection(ros_domain=worker_number) as moveit:
        while len(transitions) < transitions_wanted:
            cell = one_table_cell.OneTableCell(table_number, moveit, with_wrist_camera=False)
            table_number += 1
            table_return = 0.0
            try:
                for _ in range(PUSHES_PER_TRAINING_TABLE):
                    true_boxes = _true_boxes(cell)
                    boxes = with_box_model_noise(true_boxes, python_rng)
                    rows, mask = table_and_push_encoding.encode_table(boxes)
                    glass, push_numbers, log_probability, value = choose_push_to_try(
                        network, boxes, greedy, numpy_rng
                    )
                    says_finished = glass >= table_and_push_encoding.GLASS_SLOTS or glass >= len(boxes)
                    if says_finished:
                        crowded = table_and_push_encoding.count_pickable_boxes(true_boxes) < len(true_boxes)
                        reward = REWARDS["wrong_stop"] if crowded else REWARDS["right_stop"]
                        done = True
                    else:
                        before = true_boxes
                        seconds_before = cell.arm_seconds
                        pusher_result = cell.push_glass(
                            boxes,
                            table_and_push_encoding.decode_push_relative_to_neighbour(
                                glass, push_numbers, boxes
                            ),
                        )
                        if pusher_result.made:
                            after = _true_boxes(cell)
                            toppled = cell.count_toppled_glasses() > 0
                            reward = reward_for_push(
                                before, after, pusher_result, cell.arm_seconds - seconds_before, toppled
                            )
                            done = toppled
                        else:
                            reward, done, toppled = REWARDS["refused"], False, False
                    transitions.append(
                        {
                            "rows": rows,
                            "mask": mask,
                            "glass": glass,
                            "raw": push_numbers,
                            "log_p": log_probability,
                            "value": value,
                            "reward": reward,
                            "done": done,
                        }
                    )
                    table_return += reward
                    if done:
                        break
                if transitions and not transitions[-1]["done"]:
                    transitions[-1]["done"] = True  # the table's four pushes are used up
            finally:
                cell.close()
            episodes.append(table_return)
    with open(output_file, "wb") as output:
        pickle.dump({"transitions": transitions, "episodes": episodes}, output)


def _true_boxes(cell) -> list[GlassBox]:
    simulator = cell.simulator
    boxes = []
    for i, glass in enumerate(simulator.glasses):
        x, y = simulator.position(i)
        outline = glass.outline
        boxes.append(
            GlassBox(
                float(x),
                float(y),
                float(outline.max_diameter / 2),
                float(outline.total_height),
                float(outline.radius[0]),
            )
        )
    return boxes


# -------------------------------------------------------------------- learner


def advantages_and_returns(transitions: list[dict], gamma: float = 0.97, smoothing: float = 0.95):
    advantages = np.zeros(len(transitions), dtype=np.float32)
    running = 0.0
    for index in reversed(range(len(transitions))):
        transition = transitions[index]
        next_value = (
            0.0 if transition["done"] or index == len(transitions) - 1 else transitions[index + 1]["value"]
        )
        surprise = transition["reward"] + gamma * next_value - transition["value"]
        running = surprise + (0.0 if transition["done"] else gamma * smoothing * running)
        advantages[index] = running
    returns = advantages + np.array([transition["value"] for transition in transitions], dtype=np.float32)
    return advantages, returns


def ppo_update(
    network: PushPolicyNetwork,
    optimiser,
    transitions: list[dict],
    epochs: int = 6,
    batch_size: int = 64,
    clip_range: float = 0.2,
) -> dict:
    advantages, returns = advantages_and_returns(transitions)
    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-6)
    rows = torch.tensor(np.stack([t["rows"] for t in transitions]))
    mask = torch.tensor(np.stack([t["mask"] for t in transitions]))
    glass = torch.tensor([t["glass"] for t in transitions])
    raw = torch.tensor(np.stack([t["raw"] for t in transitions]), dtype=torch.float32)
    old_log_probability = torch.tensor([t["log_p"] for t in transitions])
    advantages_tensor, returns_tensor = torch.tensor(advantages), torch.tensor(returns)
    count = len(transitions)
    losses = {}
    for _ in range(epochs):
        order = torch.randperm(count)
        for batch_start in range(0, count, batch_size):
            batch = order[batch_start : batch_start + batch_size]
            logits, push_for_each_glass, value = network(rows[batch], mask[batch])
            glass_distribution = torch.distributions.Categorical(logits=logits)
            log_probability = glass_distribution.log_prob(glass[batch])
            is_push = glass[batch] < table_and_push_encoding.GLASS_SLOTS
            chosen_push = push_for_each_glass[
                torch.arange(len(batch)), glass[batch].clamp(max=table_and_push_encoding.GLASS_SLOTS - 1)
            ]
            push_distribution = torch.distributions.Normal(chosen_push, network.spread.exp())
            log_probability = log_probability + push_distribution.log_prob(raw[batch]).sum(1) * is_push
            ratio = (log_probability - old_log_probability[batch]).exp()
            batch_advantages = advantages_tensor[batch]
            policy_loss = -torch.min(
                ratio * batch_advantages, ratio.clamp(1 - clip_range, 1 + clip_range) * batch_advantages
            ).mean()
            value_loss = nn.functional.mse_loss(value, returns_tensor[batch])
            entropy = glass_distribution.entropy().mean()
            loss = policy_loss + 0.5 * value_loss - 0.03 * entropy
            optimiser.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(network.parameters(), 1.0)
            optimiser.step()
            losses = {"policy": float(policy_loss), "value": float(value_loss), "entropy": float(entropy)}
    return losses


def train_with_ppo(
    iterations: int,
    worker_count: int,
    steps: int,
    seed_start: int = 3000,
    tag: str = "reinforcement-v4",
    resume: bool = False,
    epochs: int = 6,
    minibatch: int = 64,
    learning_rate: float = 3e-4,
) -> list[dict]:
    ROLLOUT_FOLDER.mkdir(parents=True, exist_ok=True)
    WEIGHTS_FOLDER.mkdir(exist_ok=True)
    torch.manual_seed(0)
    network = new_push_policy()
    optimiser = torch.optim.Adam(network.parameters(), learning_rate)
    learning_curve = []
    next_table = seed_start
    started = time.perf_counter()
    transitions_so_far = 0
    iterations_done = 0
    if resume and (THIS_FOLDER / "results" / f"{tag}-curve.json").exists():
        # Picks up from the last saved iteration: the weights are kept, the
        # optimiser's running averages are not, and start afresh.
        learning_curve = json.loads((THIS_FOLDER / "results" / f"{tag}-curve.json").read_text())
        network.load_state_dict(torch.load(WEIGHTS_FOLDER / f"{tag}.pt", weights_only=True))
        iterations_done, transitions_so_far = len(learning_curve), learning_curve[-1]["steps"]
        next_table = seed_start + 40 * worker_count * iterations_done
        started -= learning_curve[-1]["minutes"] * 60
    for iteration in range(iterations_done, iterations):
        current_weights = ROLLOUT_FOLDER / "current.pt"
        torch.save(network.state_dict(), current_weights)
        running_workers = []
        for worker_number in range(worker_count):
            output_file = ROLLOUT_FOLDER / f"rollout-{worker_number}.pkl"
            output_file.unlink(missing_ok=True)
            running_workers.append(
                (
                    output_file,
                    subprocess.Popen(
                        [
                            sys.executable,
                            __file__,
                            "work",
                            "--weights",
                            str(current_weights),
                            "--first",
                            str(next_table),
                            "--steps",
                            str(steps),
                            "--out",
                            str(output_file),
                            "--worker",
                            str(worker_number),
                        ]
                    ),
                )
            )
            next_table += 40
        transitions, episodes = [], []
        for output_file, process in running_workers:
            process.wait()
            if output_file.exists():
                with open(output_file, "rb") as handle:
                    collected = pickle.load(handle)
                transitions += collected["transitions"]
                episodes += collected["episodes"]
        network.train()
        losses = ppo_update(network, optimiser, transitions, epochs=epochs, batch_size=minibatch)
        network.eval()
        transitions_so_far += len(transitions)
        push_transitions = [
            transition
            for transition in transitions
            if transition["glass"] < table_and_push_encoding.GLASS_SLOTS
        ]
        curve_row = {
            "iteration": iteration + 1,
            "steps": transitions_so_far,
            "episodes": len(episodes),
            "mean_return": float(np.mean(episodes)),
            "refused_share": float(
                np.mean(
                    [
                        transition["reward"] <= REWARDS["refused"] + 1e-9
                        and transition["reward"] > REWARDS["refused"] - 1e-9
                        for transition in push_transitions
                    ]
                )
            )
            if push_transitions
            else 0.0,
            "topple_share": float(np.mean([transition["reward"] < -2.0 for transition in push_transitions]))
            if push_transitions
            else 0.0,
            "finished_share": float(
                np.mean(
                    [transition["glass"] >= table_and_push_encoding.GLASS_SLOTS for transition in transitions]
                )
            ),
            **losses,
            "minutes": round((time.perf_counter() - started) / 60, 1),
        }
        learning_curve.append(curve_row)
        print(json.dumps(curve_row), flush=True)
        torch.save(network.state_dict(), WEIGHTS_FOLDER / f"{tag}.pt")
        (THIS_FOLDER / "results").mkdir(exist_ok=True)
        (THIS_FOLDER / "results" / f"{tag}-curve.json").write_text(json.dumps(learning_curve, indent=1))
    return learning_curve


# ------------------------------------------------------------------ the solution


class ReinforcementLearningSolution(TurnByTurnSolution):
    name = "reinforcement learning (limited training)"
    looking_mode = LOOK_ONLY_AS_NEEDED  # it reads the boxes, so one picture that shows every glass is enough

    def __init__(self, weights: Path | None = None) -> None:
        self.policy_network = new_push_policy()
        self.policy_network.load_state_dict(
            torch.load(weights or WEIGHTS_FOLDER / "reinforcement-v4.pt", weights_only=True)
        )
        self.policy_network.eval()

    def start_new_table(self) -> None:
        self.refused_glasses = RefusedGlasses()
        self.last_requested_glass = None

    def decide_turn(self, observation):
        boxes = list(observation.boxes)
        if not boxes:
            return TableFinished("no glass in view")
        if observation.last_push_refusal_reason and self.last_requested_glass is not None:
            self.refused_glasses.remember(boxes, self.last_requested_glass)
        rows, mask = table_and_push_encoding.encode_table(boxes)
        for refused_index in self.refused_glasses.indices_in_look(boxes):
            if refused_index < table_and_push_encoding.GLASS_SLOTS:
                mask[refused_index] = False
        with torch.no_grad():
            logits, push_for_each_glass, _ = self.policy_network(
                torch.tensor(rows)[None], torch.tensor(mask)[None]
            )
        chosen = int(logits[0].argmax())
        if chosen >= table_and_push_encoding.GLASS_SLOTS or not mask.any():
            return TableFinished("the policy says the table is finished")
        self.last_requested_glass = chosen
        return table_and_push_encoding.decode_push_relative_to_neighbour(
            chosen, push_for_each_glass[0, chosen].numpy(), boxes
        )


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
    arguments = parser.parse_args()
    if arguments.mode == "work":
        collect_rollouts(arguments.weights, arguments.first, arguments.steps, arguments.out, arguments.worker)
    else:
        train_with_ppo(
            arguments.iterations,
            arguments.workers,
            arguments.steps,
            tag=arguments.tag,
            resume=arguments.resume,
            epochs=arguments.epochs,
            minibatch=arguments.minibatch,
            learning_rate=arguments.lr,
        )


if __name__ == "__main__":
    main()
