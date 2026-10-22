"""Film the scripted expert, and draw what the camera found, to check both by eye.

For each seed it writes a video of the expert's episode, and a picture from
the overhead camera with the located outline, centre of mass and grasp drawn
on it next to the true ones.

    pixi run python -m pick_place.view --seeds 0 1 2
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
import mujoco
import numpy as np

from .env import PickPlaceEnv, random_episode
from .expert import run
from .settings import CAMERA, FPS
from .shapes import rotate
from .video import Filmer


def film_expert(seed: int, out: Path) -> bool:
    env = PickPlaceEnv(random_episode(seed))
    filmer = Filmer(env.model)
    for step, _ in enumerate(run(env)):
        filmer.capture(env.data, f"scripted expert  seed {seed}  t={step / FPS:4.1f}s")
    filmer.save(out, FPS)
    return env.succeeded()


def draw_located(seed: int, out: Path) -> None:
    """The overhead picture: true outline in green, located one in yellow, grasp as a red line."""
    env = PickPlaceEnv(random_episode(seed))
    renderer = mujoco.Renderer(env.model, CAMERA.height, CAMERA.width)
    camera = env.model.camera("overhead").id
    renderer.update_scene(env.data, camera)
    picture = renderer.render()[:, :, ::-1].copy()
    renderer.close()
    pos, mat = env.data.cam_xpos[camera], env.data.cam_xmat[camera].reshape(3, 3)
    top = env.episode.block.thickness

    def pixel(x: float, y: float, z: float) -> tuple[int, int]:
        local = mat.T @ (np.array([x, y, z]) - pos)
        f = (CAMERA.height / 2) / math.tan(math.radians(CAMERA.fovy) / 2)
        return int(round(CAMERA.width / 2 + f * local[0] / -local[2])), int(
            round(CAMERA.height / 2 - f * local[1] / -local[2])
        )

    block = env.data.body("block")
    yaw = math.atan2(block.xmat[3], block.xmat[0])
    true_outline = [(block.xpos[0] + x, block.xpos[1] + y) for x, y in rotate(env.episode.block.outline, yaw)]
    located = env.located
    found_outline = [(located.x + x, located.y + y) for x, y in located.outline]
    for outline, colour in ((true_outline, (0, 200, 0)), (found_outline, (0, 220, 255))):
        points = np.array([pixel(x, y, top) for x, y in outline], np.int32)
        cv2.polylines(picture, [points], True, colour, 1, cv2.LINE_AA)
    cv2.circle(picture, pixel(block.xipos[0], block.xipos[1], top), 4, (0, 200, 0), -1)
    cv2.drawMarker(picture, pixel(located.x, located.y, top), (0, 220, 255), cv2.MARKER_CROSS, 12, 2)
    g = located.grasp
    half = g.width / 2 + 0.01
    ends = [(g.x + s * half * math.cos(g.phi), g.y + s * half * math.sin(g.phi)) for s in (-1, 1)]
    cv2.line(picture, pixel(*ends[0], top), pixel(*ends[1], top), (0, 0, 255), 2, cv2.LINE_AA)
    cv2.drawMarker(picture, pixel(*env.place_point[:2], 0.0), (255, 0, 255), cv2.MARKER_TILTED_CROSS, 12, 2)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), picture)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--out", type=Path, default=Path("figures/expert"))
    args = parser.parse_args()
    for seed in args.seeds:
        ok = film_expert(seed, args.out / f"expert-seed-{seed}.mp4")
        draw_located(seed, args.out / f"located-seed-{seed}.png")
        print(f"seed {seed}: {'on target' if ok else 'missed'}; video and picture in {args.out}/")


if __name__ == "__main__":
    main()
