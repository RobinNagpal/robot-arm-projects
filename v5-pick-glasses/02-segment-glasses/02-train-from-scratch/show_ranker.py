"""Save pictures of what the Ranker is taught, and of what it answers.

    pixi run python show_ranker.py train   # one place per training scene: its 7 numbers, and the right answer
    pixi run python show_ranker.py test    # each glass of the held-out scenes: all 24 places, scored

Each gets a .png to look at and a .json with the numbers, in saved/ranker/.
``train`` also writes all-examples.csv, the whole training set as one table.
Nothing here trains anything: ``test`` uses the weights that ``make train``
left.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

import cv2
import models
import numpy as np
import pipeline
import torch
import train
import viewpoints
from drawing import WHITE, above, beside, foot, grey, panel, tag, write
from viewpoints import BEHIND, FEATURES, Seen
from work_cell.arm.dimensions import COMFORTABLE_REACH
from work_cell.glasses.perception import NotMeasurable
from work_cell.rack.layout import GLASS_ZONE
from work_cell.table.layout import ROBOT_BASE, TABLE_CENTRE_XY, TABLE_SIZE

import render
import scoring
from render import HORIZONTAL_FOV, STANDOFF

SAVED = Path(__file__).parent / "saved" / "ranker"

# The plan of the table is drawn this many pixels each way.
MAP = 720

# The plan has to hold every place a camera could stand: a standoff out from
# any edge of the glass zone, and the arm's base.
_x_low, _x_high, _y_low, _y_high = GLASS_ZONE
_out = STANDOFF + 0.06
LOW = np.array([min(_x_low - _out, ROBOT_BASE[0] - 0.06), min(_y_low - _out, ROBOT_BASE[1] - 0.06)])
HIGH = np.array([max(_x_high + _out, ROBOT_BASE[0] + 0.06), max(_y_high + _out, ROBOT_BASE[1] + 0.06)])
SCALE = MAP / float((HIGH - LOW).max())

# One colour per value the Ranker is given, in the order of FEATURES.
# Blue-green-red, as OpenCV wants them.
COLOURS = dict(
    zip(
        FEATURES,
        [
            (0, 165, 255),
            (0, 255, 255),
            (90, 90, 255),
            (255, 90, 255),
            (255, 255, 0),
            (90, 255, 90),
            (255, 170, 70),
        ],
        strict=True,
    )
)

MEANINGS = dict(
    zip(
        FEATURES,
        [
            "metres from the arm's base to the camera",
            "+1 when the camera looks away from the arm's base, -1 when it looks back at it",
            "metres of room, sideways, between the target and the nearest glass in front of it. 0.300: none",
            "the same, for the nearest glass behind the target",
            "how many other glasses are inside the camera's view (ringed)",
            "the target's own radius, metres",
            "metres from the target to the glass nearest to it, in any direction",
        ],
        strict=True,
    )
)

VETOES = {
    "out of reach": (150, 150, 150),
    "a glass in the way": (0, 140, 255),
    "camera too close to a glass": (255, 90, 255),
}

# Side pictures are drawn this big: beside the plan when there is one of
# them, and four to a row when there is one per place.
LARGE, SMALL_ = (480, 360), (360, 270)
PER_ROW = 4


# ------------------------------------------------------------ the plan


def _at(x: float, y: float) -> tuple[int, int]:
    """Where a point on the table is in the plan.

    Turned the way the overhead picture is: away from the arm is up.
    """
    return round((HIGH[1] - y) * SCALE), round((HIGH[0] - x) * SCALE)


def _line(image: np.ndarray, start, end, colour, thick: int = 1) -> None:
    cv2.line(image, _at(*start), _at(*end), colour, thick, cv2.LINE_AA)


def room(target: Seen, others: list[Seen]) -> np.ndarray:
    """The table, the arm's reach and the glasses, from above. The target is white."""
    image = np.full((MAP, MAP, 3), 16, np.uint8)
    (x, y), (long, wide) = TABLE_CENTRE_XY, TABLE_SIZE[:2]
    cv2.rectangle(image, _at(x + long / 2, y + wide / 2), _at(x - long / 2, y - wide / 2), (44, 44, 44), -1)
    cv2.rectangle(image, _at(_x_high, _y_high), _at(_x_low, _y_low), (95, 95, 95), 1)
    write(image, "glass zone", _at(_x_high + 0.025, _y_high), (120, 120, 120), 0.4)

    base = _at(ROBOT_BASE[0], ROBOT_BASE[1])
    for reach in COMFORTABLE_REACH:
        cv2.circle(image, base, round(reach * SCALE), (130, 100, 70), 1, cv2.LINE_AA)
    write(image, "the camera must stand between the two blue rings", (8, MAP - 10), (150, 120, 90), 0.4)
    cv2.rectangle(image, (base[0] - 6, base[1] - 6), (base[0] + 6, base[1] + 6), (130, 100, 70), -1)
    write(image, "arm base", (base[0] + 10, base[1] + 5), (150, 120, 90), 0.4)

    for other in others:
        cv2.circle(
            image, _at(other.x, other.y), round(other.radius * SCALE), (125, 125, 125), -1, cv2.LINE_AA
        )
    cv2.circle(image, _at(target.x, target.y), round(target.radius * SCALE), WHITE, -1, cv2.LINE_AA)
    return image


def annotate(image: np.ndarray, target: Seen, others: list[Seen], angle: float) -> None:
    """Draw one camera place on the plan, and where each of the 7 values is on it.

    The values themselves come from viewpoints.features; this only finds the
    lengths they are and numbers them 1 to 7 in the order of FEATURES.
    """
    place = viewpoints.camera_place(target, angle)
    toward = -np.array([math.cos(angle), math.sin(angle)])
    normal = np.array([toward[1], -toward[0]])
    middle, base = np.array([target.x, target.y]), np.asarray(ROBOT_BASE[:2], dtype=float)
    far = STANDOFF + BEHIND

    def label(feature: str, at: np.ndarray) -> None:
        tag(image, str(FEATURES.index(feature) + 1), _at(*at), COLOURS[feature])

    # What the camera sees: the edges of its view, its line of sight, and
    # the strip along it that the target fills.
    for side in (-1, 1):
        half = side * HORIZONTAL_FOV / 2
        ray = math.cos(half) * toward + math.sin(half) * normal
        _line(image, place, place + ray * far / math.cos(half), COLOURS["others_in_frame"])
        edge = place + side * target.radius * normal
        _line(image, edge, edge + toward * far, (105, 105, 105))
    _line(image, place, place + toward * far, WHITE)
    label("others_in_frame", place + ray * 0.75 * far)

    nearest = {"gap_in_front": None, "gap_behind": None}
    for other in others:
        offset = np.array([other.x, other.y]) - place
        along, across = offset @ toward, offset @ normal
        gap = abs(across) - other.radius - target.radius
        zone = "gap_in_front" if 0.0 < along < STANDOFF else "gap_behind" if along < far else None
        if along > 0.0 and zone and (nearest[zone] is None or gap < nearest[zone][0]):
            nearest[zone] = (gap, along, across, other)
        if along > 0.0 and math.atan2(abs(across), along) < HORIZONTAL_FOV / 2:
            ring = round(other.radius * SCALE) + 4
            cv2.circle(image, _at(other.x, other.y), ring, COLOURS["others_in_frame"], 1, cv2.LINE_AA)
    for zone, closest in nearest.items():
        if closest:
            _, along, across, other = closest
            side = 1.0 if across >= 0 else -1.0
            start = place + along * toward + side * target.radius * normal
            end = place + along * toward + side * (abs(across) - other.radius) * normal
            _line(image, start, end, COLOURS[zone], 3)
            label(zone, (start + end) / 2 + 0.015 * toward)

    _line(image, base, place, COLOURS["reach"])
    label("reach", (base + place) / 2)
    cv2.arrowedLine(image, _at(*base), _at(*middle), COLOURS["facing_base"], 1, cv2.LINE_AA, tipLength=0.04)
    label("facing_base", base + 0.35 * (middle - base))
    _line(image, middle, middle - toward * target.radius, COLOURS["radius"], 3)
    label("radius", middle - toward * target.radius * 0.5 - normal * 0.02)
    neighbour = min(others, key=lambda o: math.dist((target.x, target.y), (o.x, o.y)))
    _line(image, middle, (neighbour.x, neighbour.y), COLOURS["nearest_neighbour"])
    label("nearest_neighbour", (middle + [neighbour.x, neighbour.y]) / 2)

    cv2.circle(image, _at(*place), 6, WHITE, -1, cv2.LINE_AA)
    cv2.arrowedLine(image, _at(*place), _at(*(place + 0.07 * toward)), WHITE, 2, cv2.LINE_AA, tipLength=0.4)
    tag(image, "camera", _at(*(place - 0.035 * toward + 0.02 * normal)))


def feature_lines(values: np.ndarray) -> list[tuple]:
    """The 7 values, one line each, to go under a plan that annotate() drew on."""
    lines = []
    for number, (feature, value) in enumerate(zip(FEATURES, values, strict=True), start=1):
        shown = f"{value:.0f}" if feature == "others_in_frame" else f"{value:+.3f}"
        lines.append((COLOURS[feature], f"{number}  {feature} = {shown}.  {MEANINGS[feature]}"))
    return lines


# ---------------------------------------------------- the side pictures


def side_picture(picture: render.Picture, index: int, size: tuple[int, int]) -> np.ndarray:
    """A side depth picture: nearer is brighter, nothing there is black.

    The target's own pixels are tinted green. That is the simulator's
    knowledge, put in for the reader; the arm is never told it.
    """
    # The same band of distances SideNet is given, so both show the same thing.
    value = np.clip(np.where(np.isfinite(picture.depth), (picture.depth - STANDOFF) / 0.15, 2.0), -2, 2)
    image = grey((2.0 - value) / 4.0)
    mine = picture.ids == index + 1
    image[mine] = image[mine] * [0.55, 1.0, 0.55]
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA)


def judge(glasses: list, index: int, target: Seen, angle: float):
    """Take the side picture from one place, and the simulator's verdict on it.

    (picture, picture with the target alone, unspoiled or not, why in words.)
    """
    pose = render.side_pose(target.x, target.y, angle)
    side, alone = render.render(glasses, pose), render.render([glasses[index]], pose)
    good = scoring.is_good(side, alone)
    try:
        height, width = scoring.profile_error(scoring.silhouette(side), scoring.silhouette(alone))
        why = (
            f"with the other glasses there it measures {1000 * abs(height):.1f} mm off in height "
            f"(limit {1000 * scoring.GOOD_HEIGHT:.0f}) and {1000 * width:.1f} mm off in width "
            f"(limit {1000 * scoring.GOOD_WIDTH:.0f})"
        )
    except NotMeasurable:
        why = "with the other glasses there it could not be measured at all"
    return side, alone, good, why


def place_number(angle: float) -> int:
    return round(angle / (2 * math.pi / viewpoints.DIRECTIONS)) % viewpoints.DIRECTIONS


def _given(values: np.ndarray) -> dict:
    return {feature: round(float(value), 3) for feature, value in zip(FEATURES, values, strict=True)}


# ------------------------------------------------------- the two pictures


def taught(count: int):
    """Each training example: (name, picture, record). The same ones train.py draws."""
    rng = random.Random(0)
    for seed in range(count):
        glasses = render.scene(seed)
        picked = train.pick_view(glasses, seed, rng)
        if picked is None:
            continue
        index, target, others, angle = picked
        values = viewpoints.features(target, others, angle)
        side, alone, good, why = judge(glasses, index, target, angle)

        plan = room(target, others)
        annotate(plan, target, others, angle)
        pictures = beside(
            panel("the table from above. 1 to 7: where each value given to the Ranker is", plan),
            above(
                panel("the side picture from there. green: the target", side_picture(side, index, LARGE)),
                panel("the same place, with the target alone", side_picture(alone, index, LARGE)),
            ),
        )
        how = "the most crowded allowed place" if seed % 2 else "a random allowed place"
        lines = [
            f"scene {seed}: glass {index + 1} of {len(glasses)}, place {place_number(angle)} of "
            f"{viewpoints.DIRECTIONS}, picked as {how}",
            *feature_lines(values),
            f"true answer: {int(good)}, {'unspoiled' if good else 'spoiled'}. {why}",
        ]
        record = {
            "scene": seed,
            "glass": index + 1,
            "place": place_number(angle),
            "angle_degrees": round(math.degrees(angle)),
            "picked_as": how,
            "given_to_ranker": _given(values),
            "true_answer": {"unspoiled": int(good), "why": why},
        }
        yield f"scene-{seed:05d}", above(pictures, foot(lines, pictures.shape[1])), record


def _score_colour(score: float) -> tuple[int, int, int]:
    """Red at 0, yellow at a half, green at 1."""
    return (0, round(255 * min(1.0, 2 * score)), round(255 * min(1.0, 2 * (1 - score))))


def answered(seed: int, top_net, ranker):
    """Each glass of one held-out scene: (name, picture, record).

    All 24 places round it: which the geometry vetoes, the Ranker's score for
    the rest, and the side picture from each of those with the simulator's
    verdict on it.
    """
    glasses = render.scene(seed)
    found = pipeline.find_glasses(render.render(glasses, render.top_pose()), top_net)
    for number, item in enumerate(found, start=1):
        target, others = item.seen, [f.seen for f in found if f is not item]
        middle = np.array([target.x, target.y])
        index = min(range(len(glasses)), key=lambda i: math.dist((glasses[i].x, glasses[i].y), middle))
        ranked = pipeline.rank_views(target, others, ranker)
        scores = {place_number(angle): score for score, angle in ranked}
        best = place_number(ranked[0][1]) if ranked else None

        plan, places, views = room(target, others), [], []
        for place, angle in enumerate(viewpoints.angles()):
            spot = viewpoints.camera_place(target, angle)
            outward = _at(*(spot + 0.05 * (spot - middle) / STANDOFF))
            why_not = viewpoints.veto(target, others, angle)
            record = {"place": place, "angle_degrees": round(math.degrees(angle)), "allowed": why_not is None}
            if why_not:
                record["vetoed_because"] = why_not
                cv2.drawMarker(plan, _at(*spot), VETOES[why_not], cv2.MARKER_TILTED_CROSS, 10, 1, cv2.LINE_AA)
                write(plan, str(place), (outward[0] - 6, outward[1] + 4), VETOES[why_not], 0.4)
            else:
                score = scores[place]
                side, _, good, why = judge(glasses, index, target, angle)
                record |= {
                    "given_to_ranker": _given(viewpoints.features(target, others, angle)),
                    "ranker_said": {"score": round(score, 3)},
                    "true_answer": {"unspoiled": int(good), "why": why},
                    "chosen": place == best,
                }
                cv2.circle(plan, _at(*spot), 7, _score_colour(score), -1, cv2.LINE_AA)
                if place == best:
                    cv2.circle(plan, _at(*spot), 11, WHITE, 2, cv2.LINE_AA)
                write(plan, f"{place}: {score:.2f}", (outward[0] - 22, outward[1] + 4), WHITE, 0.4)
                title = f"place {place}: score {score:.2f}. truly {'unspoiled' if good else 'SPOILED'}"
                views.append((score, panel(title, side_picture(side, index, SMALL_))))
            places.append(record)

        if best is None:
            decision = "no place is allowed: the glass is handed to problem 3"
        elif scores[best] < pipeline.MIN_SCORE:
            decision = (
                f"the best place, {best}, scores {scores[best]:.2f}, under {pipeline.MIN_SCORE}: "
                "the glass is handed to problem 3"
            )
        else:
            decision = (
                f"the best place, {best}, scores {scores[best]:.2f}: the side picture is taken from there"
            )

        lines = [
            f"scene {seed}, glass {number} of {len(found)} found. {decision}",
            *[(colour, f"cross: vetoed, {why_not}") for why_not, colour in VETOES.items()],
            (
                _score_colour(1.0),
                "dot: allowed. red 0, yellow 0.5, green 1 is the Ranker's score. white ring: the best",
            ),
        ]
        top = [panel("the 24 places round the target. dots: allowed, with the score. crosses: vetoed", plan)]
        if best is not None:
            angle = viewpoints.angles()[best]
            close = room(target, others)
            annotate(close, target, others, angle)
            top.append(
                panel(f"the best place, {best}. 1 to 7: where each value given to the Ranker is", close)
            )
            lines += feature_lines(viewpoints.features(target, others, angle))

        views = [view for _, view in sorted(views, key=lambda pair: -pair[0])]
        rows = [beside(*views[start : start + PER_ROW]) for start in range(0, len(views), PER_ROW)]
        picture = above(beside(*top), *rows)
        record = {
            "scene": seed,
            "glass": number,
            "target": {"x": round(target.x, 3), "y": round(target.y, 3), "radius": round(target.radius, 3)},
            "decision": decision,
            "places": places,
        }
        yield f"scene-{seed:05d}-glass-{number}", above(picture, foot(lines, picture.shape[1])), record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("which", choices=["train", "test"])
    parser.add_argument("--scenes", type=int, help="how many; 200 for train and 50 for test if not given")
    arguments = parser.parse_args()
    folder = SAVED / arguments.which
    folder.mkdir(parents=True, exist_ok=True)

    if arguments.which == "train":
        drawn = taught(arguments.scenes or 200)
    else:
        top_net, ranker = models.TopNet(), models.Ranker()
        top_net.load_state_dict(torch.load(train.WEIGHTS / "top_net.pt"))
        ranker.load_state_dict(torch.load(train.WEIGHTS / "ranker.pt"))
        seeds = range(render.TEST_SEEDS, render.TEST_SEEDS + (arguments.scenes or 50))
        drawn = (one for seed in seeds for one in answered(seed, top_net, ranker))

    records = []
    for name, image, record in drawn:
        cv2.imwrite(str(folder / f"{name}.png"), image)
        (folder / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n")
        records.append(record)

    if arguments.which == "train":
        with (folder / "all-examples.csv").open("w", newline="") as file:
            table = csv.writer(file)
            table.writerow(["scene", "glass", "place", *FEATURES, "unspoiled"])
            for record in records:
                given, answer = record["given_to_ranker"], record["true_answer"]
                table.writerow(
                    [record["scene"], record["glass"], record["place"], *given.values(), answer["unspoiled"]]
                )
    print(f"{len(records)} pictures saved to {folder}")


if __name__ == "__main__":
    main()
