"""Run the learned pipeline on the held-out scenes, and score it.

The same scenes, pictures and scorecard as problem-2-programmed/run.py, so the
two results files can be set side by side.

    pixi run python run.py              # 50 held-out scenes
    pixi run python run.py --scenes 5 --show
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch

import models
import pipeline
import render
from scoring import Scorecard
from train import WEIGHTS


def load():
    nets = {"top_net": models.TopNet(), "ranker": models.Ranker(), "side_net": models.SideNet()}
    for name, net in nets.items():
        net.load_state_dict(torch.load(WEIGHTS / f"{name}.pt"))
    return nets["top_net"], nets["ranker"], nets["side_net"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", type=int, default=50)
    parser.add_argument("--show", action="store_true", help="print each glass")
    arguments = parser.parse_args()
    top_net, ranker, side_net = load()
    card = Scorecard()

    for seed in range(render.TEST_SEEDS, render.TEST_SEEDS + arguments.scenes):
        glasses = render.scene(seed)
        top = render.render(glasses, render.top_pose())
        found = pipeline.find_glasses(top, top_net)
        matches = card.found(glasses, top, [f.pixels for f in found], [(f.seen.x, f.seen.y) for f in found])

        for item, index in zip(found, matches, strict=True):
            if index is None:
                continue
            others = [f.seen for f in found if f is not item]
            ranked = pipeline.rank_views(item.seen, others, ranker)
            if not ranked:
                card.handed_over("no allowed place")
                continue
            score, angle = ranked[0]
            if score < pipeline.MIN_SCORE:
                card.handed_over("every place doubted")
                continue

            def pose_for(a, item=item):
                return render.side_pose(item.seen.x, item.seen.y, a)

            card.view(glasses, index, angle, [a for _, a in ranked], pose_for, render.render)
            side = render.render(glasses, pose_for(angle))
            height, width = card.measured(pipeline.measure(side, side_net), glasses[index])
            if arguments.show:
                glass = glasses[index]
                print(
                    f"seed {seed} {glass.kind:20s} {glass.total_height * 1000:5.0f} mm tall  "
                    f"view score {score:.2f}  height {1000 * height:+6.1f} mm  width {1000 * width:4.1f} mm"
                )

    card.report(arguments.scenes, Path(__file__).parent / "results.json")


if __name__ == "__main__":
    main()
