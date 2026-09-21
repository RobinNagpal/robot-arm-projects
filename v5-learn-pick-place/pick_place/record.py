"""Record the scripted expert's demonstrations as a LeRobot dataset.

Each episode is a new block and target, from its own seed. The expert's run
is played out in full first, and only saved if the block ended on the target,
so the dataset holds only good demonstrations.

    pixi run python -m pick_place.record --episodes 200 --out data/pick-place
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

import numpy as np
from lerobot.datasets.lerobot_dataset import LeRobotDataset

from .env import ACTION_NAMES, ENVIRONMENT_NAMES, STATE_NAMES, PickPlaceEnv, random_episode
from .expert import run
from .settings import FPS

TASK = "pick up the block and place it on the red target"
# Half the demonstrations have the arm pushed off course while it moves, by
# about 0.02 rad per joint, which is 1 to 2 cm at the fingertips: the size of
# the policy's own mistakes before it was trained on pushed demonstrations.
NOISE = 0.02
NOISY_SHARE = 0.5
REPO_ID = "local/pick-place"

FEATURES = {
    "observation.state": {"dtype": "float32", "shape": (len(STATE_NAMES),), "names": STATE_NAMES},
    "observation.environment_state": {
        "dtype": "float32",
        "shape": (len(ENVIRONMENT_NAMES),),
        "names": ENVIRONMENT_NAMES,
    },
    "action": {"dtype": "float32", "shape": (len(ACTION_NAMES),), "names": ACTION_NAMES},
}


def play(seed: int, noise: float) -> tuple[list[dict], bool]:
    """The expert's episode for ``seed``, as frames, and whether it put the block on the target.

    Each frame is recorded just before its command is executed: what the
    policy would see at that moment, and the move from there to the
    expert's clean command.
    """
    env = PickPlaceEnv(random_episode(seed))
    frames = []
    for command in run(env, noise, seed):
        frames.append(
            {
                "observation.state": env.state(),
                "observation.environment_state": env.environment_state(),
                "action": env.relative(command),
                "task": TASK,
            }
        )
    return frames, env.succeeded()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--episodes", type=int, default=200, help="how many good demonstrations to keep")
    parser.add_argument("--out", type=Path, default=Path("data/pick-place"))
    parser.add_argument("--first-seed", type=int, default=0)
    parser.add_argument(
        "--noise",
        type=float,
        default=NOISE,
        help="how far to push the arm off course while it moves, radians; 0 for clean demonstrations",
    )
    parser.add_argument(
        "--noisy-share", type=float, default=NOISY_SHARE, help="share of episodes that are pushed"
    )
    args = parser.parse_args()

    if args.out.exists():
        shutil.rmtree(args.out)
    dataset = LeRobotDataset.create(
        repo_id=REPO_ID, fps=FPS, features=FEATURES, root=args.out, robot_type="ur5e", use_videos=False
    )
    seed, kept, dropped, lengths = args.first_seed, 0, [], []
    while kept < args.episodes:
        noisy = random.Random(seed).random() < args.noisy_share
        frames, ok = play(seed, args.noise if noisy else 0.0)
        if ok:
            for frame in frames:
                dataset.add_frame(frame)
            dataset.save_episode()
            kept += 1
            lengths.append(len(frames))
            if kept % 25 == 0:
                print(f"{kept}/{args.episodes} episodes", flush=True)
        else:
            dropped.append(seed)
        seed += 1
    dataset.finalize()
    print(
        f"kept {kept} episodes, {sum(lengths)} frames ({np.mean(lengths) / FPS:.1f} s each on average) "
        f"into {args.out}; dropped {len(dropped)} where the expert missed: seeds {dropped}"
    )


if __name__ == "__main__":
    main()
