"""Run the trained policy, or the scripted expert, in Gazebo, on one of ten fixed runs or all of them.

Each run is one block and one target. The ten are the first ten episodes of
the MuJoCo evaluation (seeds 1,000,000 to 1,000,009), so the two simulators
can be compared run by run. Each has its own irregular block, start, turn
and target, and none of them was ever in the training data.

    pixi run python -m pick_place.gazebo.run --run 3 --gui
    pixi run python -m pick_place.gazebo.run --run all
    pixi run python -m pick_place.gazebo.run --run 3 --driver expert
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

from ..env import random_episode
from ..evaluate import EPISODE_SECONDS, FIRST_UNSEEN_SEED
from ..expert import run as run_expert
from ..settings import FPS, SUCCESS_RADIUS
from .env import GazeboEnv, write_world
from .sim import GazeboSim

RUNS = {n: FIRST_UNSEEN_SEED + n - 1 for n in range(1, 11)}
DEFAULT_POLICY = Path("outputs/act/checkpoints/015000/pretrained_model")


def outcome(env: GazeboEnv, lifted: bool) -> str:
    if env.succeeded():
        return "on target"
    if not lifted:
        return "never lifted"
    if env.block_up()[2] < 0.99:
        return "tipped"
    if env.gripper_reading() >= 0.2:
        return "still holding"
    return "placed off"


def play(
    run: int, driver: str, policy_path: Path, gui: bool, action_steps: int | None, verbose: bool
) -> dict:
    seed = RUNS[run]
    episode = random_episode(seed)
    world = write_world(episode, Path("data/gazebo") / f"run-{run}")
    print(
        f"run {run} (seed {seed}): {len(episode.block.outline)}-sided block, starting Gazebo...", flush=True
    )
    with GazeboSim(world, gui=gui, verbose=verbose) as sim:
        if gui:
            # Time for the window to open and show the scene before anything moves.
            time.sleep(8.0)
        env = GazeboEnv(episode, sim)
        start = episode.block.thickness / 2
        lifted = False
        pace = 1 / FPS if gui else 0.0
        steps = run_expert(env) if driver == "expert" else run_policy(env, policy_path, action_steps)
        for _ in steps:
            tick = time.monotonic()
            lifted = lifted or env.block_centre()[2] > start + 0.02
            # With a window open, run no faster than real time, so it can be watched.
            while time.monotonic() - tick < pace:
                time.sleep(0.001)
        result = {
            "run": run,
            "seed": seed,
            "outcome": outcome(env, lifted),
            "distance_mm": env.distance_to_target() * 1000,
        }
        if gui:
            time.sleep(3.0)
    return result


def run_policy(env: GazeboEnv, policy_path: Path, action_steps: int | None):
    """The trained policy's episode, one control step per iteration, as ``evaluate.py`` runs it in MuJoCo."""
    import torch

    from ..evaluate import load_policy
    from ..record import TASK

    policy, preprocess, postprocess = load_policy(policy_path, "cpu", action_steps)
    policy.reset()
    for _ in range(EPISODE_SECONDS * FPS):
        observation = {
            "observation.state": torch.from_numpy(env.state()),
            "observation.environment_state": torch.from_numpy(env.environment_state()),
            "task": TASK,
        }
        with torch.inference_mode():
            action = postprocess(policy.select_action(preprocess(observation)))
        env.step(action.squeeze(0).cpu().numpy())
        yield


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--run", default="1", help="which run, 1 to 10, or all")
    parser.add_argument("--driver", choices=("policy", "expert"), default="policy")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY, help="a pretrained_model folder")
    parser.add_argument("--gui", action="store_true", help="open Gazebo's window and run in real time")
    parser.add_argument("--action-steps", type=int, default=None, help="as in evaluate.py")
    parser.add_argument("--verbose", action="store_true", help="show Gazebo's own messages")
    args = parser.parse_args()

    runs = list(RUNS) if args.run == "all" else [int(args.run)]
    results = []
    for run in runs:
        result = play(run, args.driver, args.policy, args.gui, args.action_steps, args.verbose)
        results.append(result)
        print(f"run {run}: {result['outcome']}, {result['distance_mm']:.1f} mm from the target", flush=True)

    if len(results) > 1:
        print(f"\n{args.driver} in Gazebo      outcome          distance to target")
        for r in results:
            print(f"  run {r['run']:>2} (seed {r['seed']})  {r['outcome']:<15} {r['distance_mm']:7.1f} mm")
        hits = sum(r["outcome"] == "on target" for r in results)
        distances = np.array([r["distance_mm"] for r in results])
        print(
            f"\n  {hits}/{len(results)} on target (within {SUCCESS_RADIUS * 1000:.0f} mm); "
            f"median distance {np.median(distances):.1f} mm"
        )


if __name__ == "__main__":
    main()
