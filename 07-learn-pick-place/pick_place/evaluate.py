"""Run a trained policy on episodes it never saw, and count how often the block lands on the target.

The seeds start far above any the dataset was recorded from, so every block
shape, start and target here is new to the policy. The scripted expert runs
on the same seeds too, as the score to compare against.

    pixi run python -m pick_place.evaluate --policy outputs/act/checkpoints/last/pretrained_model
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from lerobot.configs.policies import PreTrainedConfig
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.policies.factory import make_pre_post_processors

from .env import PickPlaceEnv, random_episode
from .expert import run
from .record import TASK
from .settings import FPS
from .video import Filmer

FIRST_UNSEEN_SEED = 1_000_000
# The expert's longest episodes take about 12 s. The policy gets a little
# longer, and is judged on where the block is when time runs out.
EPISODE_SECONDS = 16


def load_policy(path: Path, device: str = "cpu", action_steps: int | None = None):
    """The trained policy, and the steps that scale its inputs and unscale its outputs."""
    config = PreTrainedConfig.from_pretrained(path)
    config.device = device
    # ACT's temporal ensembling, which averages overlapping chunks, is left
    # out on purpose: the actions are moves from where the joints are when
    # each chunk is predicted, and averaging moves from different starting
    # points put the block further off (20% success against 47%).
    if action_steps is not None:
        config.n_action_steps = action_steps
    policy = ACTPolicy.from_pretrained(path, config=config)
    policy.to(device)
    preprocess, postprocess = make_pre_post_processors(
        policy.config,
        pretrained_path=str(path),
        preprocessor_overrides={"device_processor": {"device": device}},
    )
    return policy, preprocess, postprocess


def run_policy(policy, preprocess, postprocess, seed: int, film: Path | None) -> tuple[bool, float]:
    env = PickPlaceEnv(random_episode(seed))
    policy.reset()
    filmer = Filmer(env.model) if film else None
    for step in range(EPISODE_SECONDS * FPS):
        observation = {
            "observation.state": torch.from_numpy(env.state()),
            "observation.environment_state": torch.from_numpy(env.environment_state()),
            "task": TASK,
        }
        with torch.inference_mode():
            action = postprocess(policy.select_action(preprocess(observation)))
        env.step(action.squeeze(0).cpu().numpy())
        if filmer:
            filmer.capture(env.data, f"ACT policy  seed {seed}  t={step / FPS:4.1f}s")
    if filmer:
        filmer.save(film, FPS)
    return env.succeeded(), env.distance_to_target()


def run_expert(seed: int) -> tuple[bool, float]:
    env = PickPlaceEnv(random_episode(seed))
    for _ in run(env):
        pass
    return env.succeeded(), env.distance_to_target()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--policy", type=Path, required=True, help="a pretrained_model folder from training")
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--first-seed", type=int, default=FIRST_UNSEEN_SEED)
    parser.add_argument("--videos", type=int, default=3, help="film this many of the episodes")
    parser.add_argument("--video-dir", type=Path, default=Path("figures/evaluate"))
    # The CPU by default: every reported score was measured on it, and the
    # model is small enough that the simulation, not the model, takes the time.
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--action-steps",
        type=int,
        default=None,
        help="how many steps of each predicted chunk to carry out before asking again "
        "(default: what the policy was trained with)",
    )
    args = parser.parse_args()

    policy, preprocess, postprocess = load_policy(args.policy, args.device, args.action_steps)

    results = {"policy": [], "expert": []}
    for i in range(args.episodes):
        seed = args.first_seed + i
        film = args.video_dir / f"policy-seed-{seed}.mp4" if i < args.videos else None
        ok, distance = run_policy(policy, preprocess, postprocess, seed, film)
        results["policy"].append((ok, distance))
        results["expert"].append(run_expert(seed))
        print(f"seed {seed}: policy {'ok  ' if ok else 'MISS'} {distance * 1000:6.1f} mm", flush=True)

    print()
    print(f"{args.episodes} unseen episodes    success    distance to target, mm (median / 90th percentile)")
    for name, rows in results.items():
        oks = [ok for ok, _ in rows]
        d = np.array([distance for _, distance in rows]) * 1000
        print(
            f"  {name:<22} {sum(oks):3d}/{len(oks)} ({100 * np.mean(oks):3.0f}%)"
            f"    {np.median(d):5.1f} / {np.percentile(d, 90):5.1f}"
        )
    if args.videos:
        print(f"\nvideos of the first {min(args.videos, args.episodes)} in {args.video_dir}/")


if __name__ == "__main__":
    main()
