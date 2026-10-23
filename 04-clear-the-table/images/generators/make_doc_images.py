"""The pictures for docs/. Run from 04-clear-the-table with ``pixi run python``.

    pixi run python images/generators/make_images.py

Each picture shows one thing, and every number on one is read off the files the
solutions write, not typed in.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PROBLEM = ROOT
sys.path.insert(0, str(PROBLEM))
sys.path.insert(0, str(PROBLEM / "work-cell"))
sys.path.insert(0, str(PROBLEM / "from-problem-3" / "bench"))
OUT = ROOT / "images"
OUT.mkdir(parents=True, exist_ok=True)

from examiner.simulation import wrist_camera  # noqa: E402
from shared.learning import table_and_push_encoding as F  # noqa: E402

INK, BLUE, ORANGE, GREY = "#222222", "#2b6cb0", "#dd6b20", "#9aa5b1"


def records(*names):
    return F.load_records(*[PROBLEM / "shared" / "learning" / "data" / n for n in names])


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=INK)
    ax.yaxis.label.set_color(INK)
    ax.xaxis.label.set_color(INK)


def views_and_boxes():
    """The same table from the two viewing places, with the boxes the network found."""
    from examiner.examining import one_table_cell as C
    from shared.seeing import box_model
    from examiner.simulation import table_draw
    from examiner.simulation.arm_and_table_simulator import ArmSimulator
    from examiner.motion.moveit_connection import MESHES, generate_urdf

    joints = C.view_joint_sets()
    model = box_model.BoxModel.load()
    seed = 10001
    simulator = ArmSimulator(seed, table_draw.table(seed), urdf=generate_urdf(), meshes=MESHES, start=joints[0])
    camera = wrist_camera.ArmCamera(simulator)
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.8))
    for ax, view, q, title in zip(axes, C.VIEWS, joints, ("from the first place", "from the second place"), strict=True):
        simulator.set_joints(q)
        jaw = simulator.tcp()
        picture = camera.view(jaw)
        ax.imshow(picture)
        for box in model.detect(picture, jaw):
            # The box's eight corners, each followed through the camera, and the
            # rectangle that holds them: that is how much of the picture the box covers.
            corners = [
                wrist_camera.to_pixel(jaw, box.x + sx * box.radius, box.y + sy * box.radius, z)
                for sx in (-1, 1)
                for sy in (-1, 1)
                for z in (0.0, box.height)
            ]
            rows = [c[0] for c in corners]
            cols = [c[1] for c in corners]
            ax.add_patch(plt.Rectangle((min(cols), min(rows)), max(cols) - min(cols), max(rows) - min(rows), fill=False, ec=ORANGE, lw=2))
        ax.set_title(title, color=INK, fontsize=11, pad=10)
        ax.axis("off")
    plt.tight_layout()
    plt.savefig(OUT / "two-views-and-boxes.png", dpi=110)
    plt.close()
    camera.close()


def heading_feasible():
    rs = records("pushes-round1.jsonl")
    bins = [0.0, 0.4, 0.8, 1.2, 1.6, 2.0, 2.4, 2.8, math.pi + 1e-9]
    shares, counts = [], []
    for lo, hi in zip(bins, bins[1:]):
        sel = []
        for r in rs:
            boxes = F.boxes_of(r["before"])
            if len(boxes) < 2:
                continue
            k = r["request"]["glass"]
            off = abs((r["request"]["heading"] - F.away_angle(boxes, k) + math.pi) % (2 * math.pi) - math.pi)
            if lo <= off < hi:
                sel.append(r["feasible"])
        shares.append(100 * np.mean(sel) if sel else 0)
        counts.append(len(sel))
    fig, ax = plt.subplots(figsize=(7.5, 4))
    xs = np.arange(len(shares))
    ax.bar(xs, shares, color=BLUE)
    for x, s, n in zip(xs, shares, counts):
        ax.text(x, s + 1, f"{s:.0f}%\nn={n}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{math.degrees(a):.0f}–{math.degrees(min(b, math.pi)):.0f}°" for a, b in zip(bins, bins[1:])], fontsize=8)
    ax.set_xlabel("push direction, measured from straight away from the nearest neighbour")
    ax.set_ylabel("pushes MoveIt could plan (%)")
    ax.set_ylim(0, 60)
    style(ax)
    plt.tight_layout()
    plt.savefig(OUT / "feasible-by-direction.png", dpi=110)
    plt.close()


def topple_by_kind():
    rs = records("pushes-round1.jsonl", "pushes-round2.jsonl")
    fe = [r for r in rs if r["feasible"]]
    kinds = ["straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass"]
    shares = [100 * np.mean([F.outcome(r)["topple"] for r in fe if r["before"][r["request"]["glass"]]["kind"] == k]) for k in kinds]
    counts = [sum(1 for r in fe if r["before"][r["request"]["glass"]]["kind"] == k) for k in kinds]
    fig, ax = plt.subplots(figsize=(7, 4))
    xs = np.arange(len(kinds))
    ax.bar(xs, shares, color=[BLUE, ORANGE, ORANGE, ORANGE])
    for x, s, n in zip(xs, shares, counts):
        ax.text(x, s + 1.5, f"{s:.0f}%\nn={n}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(xs)
    ax.set_xticklabels([k.replace("_glass", "").replace("_", " ") for k in kinds])
    ax.set_ylabel("pushes that tipped the glass (%)")
    ax.set_ylim(0, 105)
    style(ax)
    plt.tight_layout()
    plt.savefig(OUT / "topple-by-kind.png", dpi=110)
    plt.close()


def topple_by_height():
    rs = records("pushes-round1.jsonl", "pushes-round2.jsonl")
    fe = [r for r in rs if r["feasible"]]
    edges = [0.075, 0.092, 0.108, 0.125 + 1e-9]
    shares, counts = [], []
    for lo, hi in zip(edges, edges[1:]):
        sel = [F.outcome(r)["topple"] for r in fe if lo <= r["request"]["settings"]["push_height"] < hi]
        shares.append(100 * np.mean(sel))
        counts.append(len(sel))
    fig, ax = plt.subplots(figsize=(6, 4))
    xs = np.arange(3)
    ax.bar(xs, shares, color=BLUE)
    for x, s, n in zip(xs, shares, counts):
        ax.text(x, s + 1.5, f"{s:.0f}%\nn={n}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{1000 * a:.0f}–{1000 * min(b, 0.125):.0f} mm" for a, b in zip(edges, edges[1:])])
    ax.set_xlabel("how high the middle of the hand rode during the stroke")
    ax.set_ylabel("pushes that tipped the glass (%)")
    ax.set_ylim(0, 90)
    style(ax)
    plt.tight_layout()
    plt.savefig(OUT / "topple-by-height.png", dpi=110)
    plt.close()


def learning_curve(tag: str = "reinforcement-v4", name: str = "reinforcement-curve.png"):
    curve = json.loads((PROBLEM / "05-reinforcement-learning" / "results" / f"{tag}-curve.json").read_text())
    fig, ax = plt.subplots(figsize=(7, 4))
    xs = [c["steps"] for c in curve]
    ax.plot(xs, [100 * c["refused_share"] for c in curve], color=ORANGE, marker="o", ms=3, label="pushes MoveIt could not plan")
    ax.plot(xs, [100 * c["topple_share"] for c in curve], color=BLUE, marker="o", ms=3, label="pushes that tipped a glass")
    ax.set_xlabel("pushes tried so far")
    ax.set_ylabel("share of the pushes in that round (%)")
    ax.legend(frameon=False, fontsize=9)
    style(ax)
    plt.tight_layout()
    plt.savefig(OUT / name, dpi=110)
    plt.close()


if __name__ == "__main__":
    which = sys.argv[1:] or ["views", "heading", "kind", "height", "curve"]
    if "views" in which:
        views_and_boxes()
    if "heading" in which:
        heading_feasible()
    if "kind" in which:
        topple_by_kind()
    if "height" in which:
        topple_by_height()
    if "curve" in which:
        learning_curve()
    print("wrote pictures to", OUT)
