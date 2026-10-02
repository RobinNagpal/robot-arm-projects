"""Pictures and JSON of what each model is taught, and of what it answers.

Writes into saved/, which is not in git. Trains nothing; uses weights/.

    pixi run python show.py top train      # TopNet: the training tables
    pixi run python show.py top test       # TopNet: held-out tables, what it found
    pixi run python show.py ranker train
    pixi run python show.py ranker test
    pixi run python show.py side train     # SideNet: shape and kind
    pixi run python show.py side test
    pixi run python show.py grip train     # GripNet: where to hold it
    pixi run python show.py grip test
    pixi run python show.py push train     # the push model: collected pushes
    pixi run python show.py push test      # its predictions on unseen tables
    pixi run python show.py run            # every step of the tables run.py --trace wrote

Add --count 10 for a quick look. Each .png has a .json beside it with the
same numbers written out.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import cv2
import numpy as np
from models import SHRINK, VOTE_SCALE  # problem-2-learned
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import TABLE_TOP_Z

import nets
import pipeline as p2  # problem-2-learned
import push_features as features
import render
import scoring
import tables
import train
import viewpoints
from collect import DATA
from drawing import WHITE, above, beside, foot, grid, panel, tag, write  # problem-2-learned
from push_model import Ensemble, sigmoid

SAVED = Path(__file__).parent / "saved"

# BGR, one per kind, and grey for a glass not measured.
COLOURS = {
    "straight_glass": (230, 160, 60),
    "tapered_glass": (90, 200, 90),
    "stemmed_glass": (200, 90, 200),
    "short_stemmed_glass": (40, 150, 240),
    features.NOT_MEASURED: (150, 150, 150),
}
TRUE, SAID = (90, 220, 90), (40, 160, 255)
ZOOM = 2


def short(kind: str) -> str:
    return kind.replace("_glass", "").replace("_", "-")


def big(image: np.ndarray, zoom: int = ZOOM) -> np.ndarray:
    return cv2.resize(image, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_NEAREST)


def heat(values: np.ndarray, low: float, high: float) -> np.ndarray:
    scaled = np.clip((values - low) / (high - low), 0, 1)
    return cv2.applyColorMap((scaled * 255).astype(np.uint8), cv2.COLORMAP_VIRIDIS)


def save(folder: Path, name: str, image: np.ndarray, data: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(folder / f"{name}.png"), image)
    (folder / f"{name}.json").write_text(json.dumps(data, indent=1, default=float) + "\n")


def draw_scene(seed: int):
    spawned = tables.scene(seed)
    return spawned, tables.to_render(spawned, [g.position[:2] for g in spawned])


# ----------------------------------------------------------------- the plan


class Plan:
    """The glass zone from above, as a flat drawing. ``margin`` is how much table to show round it."""

    def __init__(self, scale: float = 1250, margin: float = 0.09) -> None:
        x0, x1, y0, y1 = GLASS_ZONE
        self.SCALE = scale
        self.x0, self.y1 = x0 - margin, y1 + margin
        self.size = (int((y1 - y0 + 2 * margin) * scale), int((x1 - x0 + 2 * margin) * scale))

    def px(self, x: float, y: float) -> tuple[int, int]:
        """Far from the arm is up the picture; the arm's left is left."""
        return int((self.y1 - y) * self.SCALE), int(self.size[1] - (x - self.x0) * self.SCALE)

    def blank(self) -> np.ndarray:
        image = np.full((self.size[1], self.size[0], 3), 40, np.uint8)
        x0, x1, y0, y1 = GLASS_ZONE
        cv2.rectangle(image, self.px(x1, y1), self.px(x0, y0), (90, 90, 90), 1)
        return image

    def glass(self, image, x, y, width, colour, text="", filled=False) -> None:
        r = max(2, int(width / 2 * self.SCALE))
        cv2.circle(image, self.px(x, y), r, colour, -1 if filled else 2, cv2.LINE_AA)
        if text:
            c = self.px(x, y)
            write(image, text, (c[0] - 4 * len(text), c[1] + 4), WHITE, 0.4)

    def arrow(self, image, start, end, colour, thickness=2) -> None:
        cv2.arrowedLine(image, self.px(*start), self.px(*end), colour, thickness, cv2.LINE_AA, tipLength=0.25)


# ----------------------------------------------------------------- TopNet


def top_train(count: int) -> None:
    out = SAVED / "top-net" / "train"
    for seed in range(count):
        spawned, glasses = draw_scene(seed)
        top = render.render(glasses, render.top_pose())
        given, target = nets.top_input(top), nets.top_target(top, glasses)
        angle = np.arctan2(target[2], target[1])
        hue = ((angle + math.pi) / (2 * math.pi) * 179).astype(np.uint8)
        colour = cv2.cvtColor(
            np.stack([hue, np.full_like(hue, 255), (target[0] * 255).astype(np.uint8)], -1), cv2.COLOR_HSV2BGR
        )
        arrows = heat(given[0], 0, 1)
        rows, columns = np.nonzero(target[0])
        for r, c in list(zip(rows, columns, strict=True))[::23]:
            tip = (int(c + target[1, r, c] * VOTE_SCALE), int(r + target[2, r, c] * VOTE_SCALE))
            cv2.arrowedLine(arrows, (int(c), int(r)), tip, WHITE, 1, tipLength=0.15)
        picks = _four_pixels(target)
        shown = heat(given[0], 0, 1)
        for r, c in picks:
            cv2.circle(shown, (c, r), 3, (0, 0, 255), 1)
        image = grid(
            [
                [
                    ("given: height above the table", big(shown)),
                    (
                        "answer 1: glass or not",
                        big(cv2.cvtColor((target[0] * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)),
                    ),
                ],
                [
                    ("answer 2: way to its middle, as colour", big(colour)),
                    ("answer 2, as arrows", big(arrows)),
                ],
            ]
        )
        image = np.vstack(
            [
                image,
                foot(
                    [
                        (
                            COLOURS[g.kind],
                            f"glass {i + 1}: {short(g.kind)}, {1000 * g.total_height:.0f} mm tall",
                        )
                        for i, g in enumerate(glasses)
                    ],
                    image.shape[1],
                ),
            ]
        )
        save(
            out,
            f"table-{seed:05d}",
            image,
            {
                "table": seed,
                "glasses": [
                    {"kind": g.kind, "x": g.x, "y": g.y, "height_mm": 1000 * g.total_height} for g in glasses
                ],
                "pixels": [
                    {
                        "row": int(r),
                        "column": int(c),
                        "given": given[:, r, c].tolist(),
                        "answer": {
                            "glass": bool(target[0, r, c]),
                            "to_middle_across": float(target[1, r, c] * VOTE_SCALE),
                            "to_middle_down": float(target[2, r, c] * VOTE_SCALE),
                        },
                    }
                    for r, c in picks
                ],
                "shapes": {"input": list(given.shape), "target": list(target.shape)},
            },
        )


def _four_pixels(target: np.ndarray) -> list[tuple[int, int]]:
    rows, columns = np.nonzero(target[0])
    rng = np.random.default_rng(0)
    on = [(int(rows[i]), int(columns[i])) for i in rng.choice(len(rows), 3, replace=False)]
    off_rows, off_columns = np.nonzero(target[0] == 0)
    i = len(off_rows) // 3
    return [*on, (int(off_rows[i]), int(off_columns[i]))]


def top_test(count: int) -> None:
    models = train.load()
    out = SAVED / "top-net" / "test"
    for seed in range(tables.TEST_SEEDS, tables.TEST_SEEDS + count):
        spawned, glasses = draw_scene(seed)
        top = render.render(glasses, render.top_pose())
        votes = p2.cast_votes(top, models["top_net"])
        found = p2.gather(top, votes)
        chance = 1 / (1 + np.exp(-votes.out[0]))
        landed = heat(nets.top_input(top)[0], 0, 1)
        for r, c in votes.landed[::5]:
            cv2.circle(landed, (int(c), int(r)), 0, (0, 0, 255), -1)
        for r, c in votes.middles:
            cv2.drawMarker(landed, (c, r), WHITE, cv2.MARKER_CROSS, 10, 1)
        plan = Plan()
        drawn = plan.blank()
        for g in glasses:
            plan.glass(drawn, g.x, g.y, 2 * g.max_radius, COLOURS[g.kind])
        for f in found:
            cv2.drawMarker(drawn, plan.px(f.seen.x, f.seen.y), WHITE, cv2.MARKER_TILTED_CROSS, 10, 2)
        image = beside(
            grid(
                [
                    [
                        ("given: height above the table", big(heat(nets.top_input(top)[0], 0, 1))),
                        ("TopNet: chance each pixel is glass", big(heat(chance, 0, 1))),
                    ],
                    [
                        ("where the votes landed; middles picked", big(landed)),
                        ("true glasses (rings), found (crosses)", drawn),
                    ],
                ]
            )
        )
        truth = [{"kind": g.kind, "x": g.x, "y": g.y, "width_mm": 2000 * g.max_radius} for g in glasses]
        said = [
            {"x": f.seen.x, "y": f.seen.y, "width_mm": 2000 * f.seen.radius, "pixels": len(f.pixels)}
            for f in found
        ]
        lines = [f"{len(glasses)} glasses on the table, {len(found)} found"]
        for f in found:
            near = min(glasses, key=lambda g: math.dist((g.x, g.y), (f.seen.x, f.seen.y)))
            lines.append(
                (
                    COLOURS[near.kind],
                    f"{short(near.kind)}: {1000 * math.dist((near.x, near.y), (f.seen.x, f.seen.y)):.1f} mm "
                    f"from its true place; width {2000 * f.seen.radius:.0f} mm, "
                    f"true {2000 * near.max_radius:.0f}",
                )
            )
        save(
            out,
            f"table-{seed}",
            above(image, foot(lines, image.shape[1])),
            {"table": seed, "truth": truth, "found": said},
        )


# ----------------------------------------------------------------- Ranker


# Wide enough to show a camera place: the camera stands STANDOFF back from its glass.
CAMERA_PLAN = {"scale": 650, "margin": render.STANDOFF + 0.03}


def _plan_view(glasses, index, angle) -> np.ndarray:
    plan = Plan(**CAMERA_PLAN)
    image = plan.blank()
    for i, g in enumerate(glasses):
        plan.glass(image, g.x, g.y, 2 * g.max_radius, COLOURS[g.kind], str(i + 1), filled=i == index)
    if angle is not None:
        eye = viewpoints.camera_place(viewpoints.seen(glasses[index]), angle)
        cv2.drawMarker(image, plan.px(*eye), WHITE, cv2.MARKER_SQUARE, 12, 2)
        cv2.line(image, plan.px(*eye), plan.px(glasses[index].x, glasses[index].y), WHITE, 1, cv2.LINE_AA)
    return image


def ranker_train(count: int) -> None:
    data = np.load(train.DATA / "pictures.npz")
    out = SAVED / "ranker" / "train"
    rows = []
    for n, ((seed, index, angle), values, clean) in enumerate(
        zip(data["which"], data["rank_x"], data["rank_y"], strict=True)
    ):
        seed, index = int(seed), int(index)
        named = dict(zip(viewpoints.FEATURES, values.tolist(), strict=True))
        rows.append(
            {
                "table": seed,
                "glass": index + 1,
                "angle_deg": math.degrees(angle),
                **named,
                "clean": bool(clean),
            }
        )
        if n >= count:
            continue
        _, glasses = draw_scene(seed)
        pose = render.side_pose(glasses[index].x, glasses[index].y, angle)
        side, alone = render.render(glasses, pose), render.render([glasses[index]], pose)
        image = beside(
            panel("the camera place, from above", _plan_view(glasses, index, angle)),
            panel("side picture from there", big(heat(nets.side_input(side)[0], -2, 2))),
            panel("the same, glass alone", big(heat(nets.side_input(alone)[0], -2, 2))),
        )
        lines = [f"{i + 1}. {k} = {v:.3f}" for i, (k, v) in enumerate(named.items())]
        lines.append((TRUE if clean else (0, 0, 255), f"true answer: {'clean' if clean else 'spoiled'}"))
        image = np.vstack([image, foot(lines, image.shape[1])])
        save(out, f"example-{n:04d}", image, rows[-1])
    import csv

    with open(out / "all-examples.csv", "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def ranker_test(count: int) -> None:
    models = train.load()
    out = SAVED / "ranker" / "test"
    vetoed = {
        "out of reach": (0, 0, 255),
        "camera too close to a glass": (0, 165, 255),
        "a glass in the way": (255, 0, 255),
    }
    for seed in range(tables.TEST_SEEDS, tables.TEST_SEEDS + count):
        _, glasses = draw_scene(seed)
        seen = [viewpoints.seen(g) for g in glasses]
        index = seed % len(glasses)
        target, others = seen[index], seen[:index] + seen[index + 1 :]
        plan = Plan(**CAMERA_PLAN)
        image = _plan_view(glasses, index, None)
        places, best = [], None
        for angle in viewpoints.angles():
            eye = plan.px(*viewpoints.camera_place(target, angle))
            reason = viewpoints.veto(target, others, angle)
            if reason:
                cv2.drawMarker(image, eye, vetoed[reason], cv2.MARKER_TILTED_CROSS, 9, 2)
                places.append({"angle_deg": math.degrees(angle), "vetoed": reason})
                continue
            score = float(
                sigmoid(nets.predict(models["ranker"], viewpoints.features(target, others, angle)[None]))[0]
            )
            cv2.circle(image, eye, 4, WHITE, -1)
            tag(image, f"{score:.2f}", (eye[0] + 6, eye[1] + 4))
            places.append({"angle_deg": math.degrees(angle), "score": score})
            if best is None or score > best[0]:
                best = (score, angle, eye)
        side_panels = []
        if best:
            cv2.circle(image, best[2], 9, (0, 255, 255), 2)
            pose = render.side_pose(target.x, target.y, best[1])
            side = render.render(glasses, pose)
            clean = scoring.is_good(side, render.render([glasses[index]], pose))
            side_panels = [
                panel(
                    f"best place's picture: {'clean' if clean else 'spoiled'}",
                    big(heat(nets.side_input(side)[0], -2, 2)),
                )
            ]
            for p in places:
                p["chosen"] = "score" in p and p["angle_deg"] == math.degrees(best[1])
        picture = beside(panel(f"24 places round glass {index + 1}", image), *side_panels)
        lines = [(c, f"vetoed: {r}") for r, c in vetoed.items()] + [
            "white dot: allowed, with the Ranker's score"
        ]
        save(
            out,
            f"table-{seed}",
            np.vstack([picture, foot(lines, picture.shape[1])]),
            {"table": seed, "glass": index + 1, "kind": glasses[index].kind, "places": places},
        )


# ------------------------------------------------------- SideNet and GripNet


def _side_drawing(
    side_input: np.ndarray,
    glass_height: float,
    widths: np.ndarray,
    colour,
    picture: render.Picture,
    target: render.Glass,
    image: np.ndarray | None = None,
) -> np.ndarray:
    """The 17 shape numbers drawn on the side picture, at the glass's own place in it."""
    image = big(heat(side_input[0], -2, 2)) if image is None else image
    centre = np.array([target.x, target.y])

    def at(height: float, half: float, sign: float) -> tuple[int, int]:
        # A point on the glass's outline as the camera sees it: sideways across the view.
        pose = picture.camera_to_world
        right = pose[:3, 0][:2] / np.linalg.norm(pose[:3, 0][:2])
        c, r = render.project(pose, [*(centre + sign * half * right), TABLE_TOP_Z + height])
        # project() is in full-size pixels; the drawing is the half-size input, zoomed.
        return int(c * ZOOM / SHRINK), int(r * ZOOM / SHRINK)

    for fraction, width in zip(scoring.FRACTIONS, widths, strict=True):
        cv2.line(
            image,
            at(fraction * glass_height, width / 2, -1),
            at(fraction * glass_height, width / 2, 1),
            colour,
            1,
        )
    cv2.line(image, at(glass_height, 0.06, -1), at(glass_height, 0.06, 1), colour, 2)
    return image


def side_pictures(split: str, count: int):
    """(name, spawned glass, render glasses, index, angle, picture) for the side pictures to draw."""
    if split == "train":
        data = np.load(train.DATA / "pictures.npz")
        for n, (seed, index, angle) in enumerate(data["which"][:count]):
            spawned, glasses = draw_scene(int(seed))
            yield f"example-{n:04d}", spawned[int(index)], glasses, int(index), float(angle)
        return
    rng = random.Random(1)
    n = 0
    for seed in range(tables.TEST_SEEDS, tables.TEST_SEEDS + 200):
        spawned, glasses = draw_scene(seed)
        for index, angle in train.side_examples(glasses, seed, rng)[:1]:
            yield f"table-{seed}", spawned[index], glasses, index, angle
            n += 1
        if n >= count:
            return


def side_show(split: str, count: int) -> None:
    models = train.load() if split == "test" else None
    out = SAVED / "side-net" / split
    for name, _, glasses, index, angle in side_pictures(split, count):
        glass = glasses[index]
        picture = render.render(glasses, render.side_pose(glass.x, glass.y, angle))
        given = nets.side_input(picture)
        target = nets.side_kind_target(glass)
        true_h, true_w = target[0] * nets.HEIGHT_SCALE, target[1:17] * nets.WIDTH_SCALE
        panels = [
            panel("given: the side picture", big(heat(given[0], -2, 2))),
            panel("true: height, 16 widths", _side_drawing(given, true_h, true_w, TRUE, picture, glass)),
        ]
        data = {
            "made_as": glass.kind,
            "true": {
                "height_mm": 1000 * true_h,
                "widths_mm": (1000 * true_w).tolist(),
                "kind_index": int(target[17]),
            },
            "scaled_target": target.tolist(),
        }
        lines = [
            (COLOURS[glass.kind], f"true kind: {short(glass.kind)}   (kind index {int(target[17])})"),
            f"true height {1000 * true_h:.0f} mm; widths {', '.join(f'{1000 * w:.0f}' for w in true_w)} mm",
        ]
        if models:
            h, w, chances = nets.side_output(nets.predict(models["side_net"], given[None])[0])
            both = _side_drawing(given, true_h, true_w, TRUE, picture, glass)
            panels.append(
                panel(
                    "SideNet's (orange) over the truth",
                    _side_drawing(given, h, w, SAID, picture, glass, both),
                )
            )
            said = nets.KINDS[int(chances.argmax())]
            lines += [
                (
                    COLOURS[said],
                    f"SideNet: {short(said)}  "
                    + "  ".join(f"{short(k)} {c:.2f}" for k, c in zip(nets.KINDS, chances, strict=True)),
                ),
                f"SideNet height {1000 * h:.0f} mm ({1000 * (h - true_h):+.1f}); median width error "
                f"{1000 * np.median(np.abs(w - true_w)):.1f} mm",
            ]
            data["said"] = {
                "height_mm": 1000 * h,
                "widths_mm": (1000 * w).tolist(),
                "kind": said,
                "kind_chances": dict(zip(nets.KINDS, chances.tolist(), strict=True)),
            }
        image = beside(*panels)
        save(out, name, np.vstack([image, foot(lines, image.shape[1])]), data)


def _grip_drawing(picture, glass, height, opening, colour, image) -> np.ndarray:
    pose = picture.camera_to_world
    right = pose[:3, 0][:2] / np.linalg.norm(pose[:3, 0][:2])
    centre = np.array([glass.x, glass.y])
    ends = [
        render.project(pose, [*(centre + s * (opening / 2 + 0.006) * right), TABLE_TOP_Z + height])
        for s in (-1, 1)
    ]
    for (c, r), s in zip(ends, (-1, 1), strict=True):
        x, y = int(c * ZOOM / SHRINK), int(r * ZOOM / SHRINK)
        cv2.rectangle(image, (x - 6 * s - 3, y - 7), (x + 3 - 6 * s, y + 7), colour, -1)
    return image


def grip_show(split: str, count: int) -> None:
    models = train.load() if split == "test" else None
    out = SAVED / "grip-net" / split
    for name, spawned, glasses, index, angle in side_pictures(split, count):
        glass = glasses[index]
        picture = render.render(glasses, render.side_pose(glass.x, glass.y, angle))
        given = nets.side_input(picture)
        truth = tables.glass_grip(spawned)
        drawn = big(heat(given[0], -2, 2))
        if truth.holdable:
            _grip_drawing(picture, glass, truth.height, truth.opening, TRUE, drawn)
        lines = [
            (COLOURS[glass.kind], f"made as {short(glass.kind)}, {1000 * glass.total_height:.0f} mm tall"),
            (
                TRUE,
                f"the rule: grip {1000 * truth.height:.1f} mm up, pads {1000 * truth.opening:.1f} mm apart"
                if truth.holdable
                else f"the rule: cannot be held - {truth.reason[:90]}",
            ),
        ]
        data = {
            "made_as": glass.kind,
            "true": truth.__dict__,
            "scaled_target": nets.grip_target(truth).tolist(),
        }
        panels = [
            panel("given: the side picture", big(heat(given[0], -2, 2))),
            panel("true answer (green pads)", drawn),
        ]
        if models:
            hold, h, o = nets.grip_output(nets.predict(models["grip_net"], given[None])[0])
            said = drawn.copy()
            if hold >= 0.5:
                _grip_drawing(picture, glass, h, o, SAID, said)
            panels.append(panel("GripNet (orange pads)", said))
            lines.append(
                (
                    SAID,
                    f"GripNet: holdable chance {hold:.2f}; grip {1000 * h:.1f} mm up, pads {1000 * o:.1f} mm"
                    + (
                        f"  (off by {1000 * (h - truth.height):+.1f} mm in height, "
                        f"{1000 * (o - truth.opening):+.1f} mm in opening)"
                        if truth.holdable and hold >= 0.5
                        else ""
                    ),
                )
            )
            data["said"] = {"hold_chance": hold, "height_mm": 1000 * h, "opening_mm": 1000 * o}
        image = beside(*panels)
        save(out, name, np.vstack([image, foot(lines, image.shape[1])]), data)


# ------------------------------------------------------------- push model


def _decode(row: np.ndarray) -> dict:
    """One input row in millimetres and words."""
    k = len(features.LABELS)
    named = {
        "pushed_glass_kind": features.LABELS[int(row[:k].argmax())],
        "pushed_glass_height_mm": row[k] * 100,
        "pushed_glass_widest_mm": row[k + 1] * 100,
        "pushed_glass_foot_mm": row[k + 2] * 100,
        "push_offset_mm": row[k + 3] * 100,
        "push_travel_mm": row[k + 4] * 50,
        "others": [],
    }
    for slot in range(features.OTHERS):
        c = features._TARGET + slot * features._PER_OTHER
        if row[c + 4] == 0:
            continue
        named["others"].append(
            {
                "along_mm": row[c] * 100,
                "across_mm": row[c + 1] * 100,
                "widest_mm": row[c + 2] * 100,
                "height_mm": row[c + 3] * 100,
                "kind": features.LABELS[int(row[c + 5 : c + 5 + k].argmax())],
            }
        )
    return named


def _push_drawing(row: np.ndarray, real: np.ndarray, said: np.ndarray | None) -> np.ndarray:
    """The push in its own frame: the jaw moves up the picture, the pushed glass in the middle."""
    size, scale = 480, 1400
    image = np.full((size, size, 3), 40, np.uint8)
    middle = np.array([size // 2, size // 2 - 20])

    def px(along: float, across: float) -> tuple[int, int]:
        return int(middle[0] - across * scale), int(middle[1] - along * scale)

    named = _decode(row)
    glasses = [(0.0, 0.0, named["pushed_glass_widest_mm"] / 1000, named["pushed_glass_kind"])]
    glasses += [
        (o["along_mm"] / 1000, o["across_mm"] / 1000, o["widest_mm"] / 1000, o["kind"])
        for o in named["others"]
    ]
    for slot, (along, across, width, kind) in enumerate(glasses):
        cv2.circle(image, px(along, across), int(width / 2 * scale), COLOURS[kind], 2, cv2.LINE_AA)
        for moves, colour in ((real, TRUE), (said, SAID)):
            if moves is None:
                continue
            d = moves[2 * slot : 2 * slot + 2] * features.MOVE_SCALE
            if np.hypot(*d) > 0.001:
                cv2.arrowedLine(
                    image,
                    px(along, across),
                    px(along + d[0], across + d[1]),
                    colour,
                    2,
                    cv2.LINE_AA,
                    tipLength=0.3,
                )
    start = -(named["pushed_glass_widest_mm"] / 2000 + features.STANDOFF)
    offset = named["push_offset_mm"] / 1000
    cv2.arrowedLine(image, px(start - 0.05, offset), px(start, offset), WHITE, 3, cv2.LINE_AA, tipLength=0.3)
    write(image, "jaw", (px(start - 0.05, offset)[0] + 6, px(start - 0.05, offset)[1]), WHITE, 0.45)
    return image


def push_show(split: str, count: int) -> None:
    name = "pushes.npz" if split == "train" else "pushes_validation.npz"
    data = np.load(DATA / name)
    x, y = data["inputs"][:count], data["outputs"][:count]
    model = Ensemble.load(train.WEIGHTS) if split == "test" else None
    out = SAVED / "push-net" / split
    said_all = model.predict(x) if model else None
    examples = []
    for n in range(len(x)):
        said = said_all[:, n].mean(0) if model else None
        image = _push_drawing(x[n], y[n], said)
        named = _decode(x[n])
        lines = [
            (
                COLOURS[named["pushed_glass_kind"]],
                f"pushed: {short(named['pushed_glass_kind'])}, "
                f"{named['push_travel_mm']:.0f} mm push, {named['push_offset_mm']:+.0f} mm off centre",
            ),
            (
                TRUE,
                f"what happened (green): toppled {bool(y[n, features.TOPPLED])}, "
                f"blocked {bool(y[n, features.BLOCKED])}",
            ),
        ]
        example = {
            "input_numbers": x[n].tolist(),
            "output_numbers": y[n].tolist(),
            "input_named": named,
            "happened": {
                "pushed_glass_moved_mm": (y[n, :2] * 50).tolist(),
                "toppled": bool(y[n, features.TOPPLED]),
                "blocked": bool(y[n, features.BLOCKED]),
            },
        }
        if model:
            topple = float(sigmoid(said_all[:, n, features.TOPPLED]).max())
            lines.append(
                (
                    SAID,
                    f"the model (orange): topple chance {topple:.3f} (worst copy), blocked "
                    f"{float(sigmoid(said_all[:, n, features.BLOCKED]).mean()):.2f}",
                )
            )
            example["said"] = {
                "pushed_glass_moved_mm": (said[:2] * 50).tolist(),
                "topple_chance_worst_copy": topple,
            }
        lines.append("grey ring: a glass the model was told is not measured")
        picture = panel(f"push {n}, in the push's own frame (the jaw moves up)", image)
        save(out, f"push-{n:04d}", above(picture, foot(lines, 760)), example)
        examples.append(example)
    (out / "all-examples.json").write_text(json.dumps(examples, indent=1, default=float) + "\n")


# ------------------------------------------------------------------- runs


def run_show(count: int) -> None:
    for path in sorted((SAVED / "runs").glob("table-*.json"))[:count]:
        trace = json.loads(path.read_text())
        out = SAVED / "runs" / path.stem
        truth, steps = trace["glasses"], trace["steps"]
        kinds: dict[int, str] = {}
        refused: set[int] = set()
        plan = Plan()
        looks = [i for i, s in enumerate(steps) if s["step"] == "look"] + [len(steps)]
        for n, (here, after) in enumerate(zip(looks, looks[1:], strict=False)):
            look, then = steps[here], steps[here + 1 : after]
            lines = [f"look {n}: {len(look['found'])} glasses found"]
            for s in then:
                if s["step"] == "measure":
                    said, made = s["said"], truth[s["glass"]]["kind"]
                    kinds[s["glass"]] = said["kind"]
                    if s["refused"]:
                        refused.add(s["glass"])
                    lines.append(
                        (
                            COLOURS[said["kind"]],
                            f"glass {s['glass']} measured: SideNet {short(said['kind'])} "
                            f"(made as {short(made)}); "
                            f"GripNet holdable {said['hold_chance']:.2f}"
                            + (f"; refused: {s['refused'].split(' (')[0]}" if s["refused"] else ""),
                        )
                    )
                elif s["step"] == "refuse":
                    refused.add(s["glass"])
                    lines.append(f"glass {s['glass']} refused: {s['reason']}")

            image = plan.blank()
            for f in look["found"]:
                g = f["glass"]
                colour = COLOURS[kinds.get(g, features.NOT_MEASURED)] if g is not None else (0, 0, 255)
                plan.glass(image, f["x"], f["y"], f["widest_mm"] / 1000, colour, str(g))
                if g in refused:
                    cv2.drawMarker(
                        image, plan.px(f["x"], f["y"]), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 26, 2
                    )

            action = next((s for s in then if s["step"] in ("rack", "push")), None)
            if action and action["step"] == "push":
                f = next(f for f in look["found"] if f["glass"] == action["glass"])
                plan.arrow(image, (f["x"], f["y"]), action["aim"], WHITE)
                lines.append(
                    f"push glass {action['glass']} ({short(action['kind_given'])}) "
                    f"{action['travel_mm']:.0f} mm (arrow: where the model expects it to land); "
                    f"topple chance {action['topple_chance']:.3f}"
                )
            elif action:
                lines.append(
                    f"rack glass {action['glass']} in slot {action['slot']}, "
                    f"squeezed at {action['squeeze_n']:.0f} N"
                    + (", the slots beside it kept empty" if action["wide"] else "")
                )
            else:
                lines.append("nothing left worth doing; the table ends here")
            lines.append("red cross: refused, left standing")
            picture = panel(f"table {trace['table']}, look {n}", image)
            save(out, f"step-{n:02d}", above(picture, foot(lines, 1000)), {"look": look, "then": then})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", choices=("top", "ranker", "side", "grip", "push", "run"))
    parser.add_argument("split", nargs="?", choices=("train", "test"), default="train")
    parser.add_argument("--count", type=int, default=None)
    arguments = parser.parse_args()
    count = arguments.count
    if arguments.model == "top":
        (top_train if arguments.split == "train" else top_test)(
            count or (200 if arguments.split == "train" else 50)
        )
    elif arguments.model == "ranker":
        (ranker_train if arguments.split == "train" else ranker_test)(count or 50)
    elif arguments.model == "side":
        side_show(arguments.split, count or 50)
    elif arguments.model == "grip":
        grip_show(arguments.split, count or 50)
    elif arguments.model == "push":
        push_show(arguments.split, count or 20)
    else:
        run_show(count or 5)


if __name__ == "__main__":
    main()
