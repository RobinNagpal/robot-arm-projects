"""Film an episode from beside the table, for checking by eye what the arm did."""

from __future__ import annotations

from pathlib import Path

import cv2
import mujoco
import numpy as np

WIDTH, HEIGHT = 640, 480


class Filmer:
    def __init__(self, model: mujoco.MjModel):
        self.renderer = mujoco.Renderer(model, HEIGHT, WIDTH)
        self.camera = mujoco.MjvCamera()
        self.camera.lookat[:] = [0.42, 0.0, 0.1]
        self.camera.distance = 1.35
        self.camera.azimuth = 160
        self.camera.elevation = -30
        self.frames: list[np.ndarray] = []

    def capture(self, data: mujoco.MjData, caption: str = "") -> None:
        self.renderer.update_scene(data, self.camera)
        frame = self.renderer.render()[:, :, ::-1].copy()
        if caption:
            cv2.putText(
                frame, caption, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA
            )
        self.frames.append(frame)

    def save(self, path: Path, fps: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (WIDTH, HEIGHT))
        for frame in self.frames:
            writer.write(frame)
        writer.release()
        self.renderer.close()
