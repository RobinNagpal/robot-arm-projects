"""Pictures for solution 3 — move the camera.

Nine diagrams, each carrying a different point:

    03-two-difficulties.png       separation and viewpoint are not one problem
    03-the-fixed-sweep.png        the three-station sweep the cell already runs
    03-occlusion-as-geometry.png  the wedge test, before any motion planner
    hidden-three-tests.png            reach, line of sight and path, on one plan view
    03-bound-then-score.png       filter first, or score first and let the planner reject
    03-the-budget.png             extra looks against the tens-of-seconds ceiling
    03-no-viewpoint.png           the object with nowhere to look from
    03-hidden-from-above.png      a glass covered by a taller one, from three nadirs
    hidden-moving-the-camera.png   a glass behind another, and the step that frees it

The last two project real glass outlines, taken from ``work_cell.glasses.shapes``,
through the cell's own camera. A standing glass is a circle only in its
footprint, which neither of the two views ever sees straight on.

Run from the project root:

    pixi run python images/generators/02-segment-glasses/make_hidden_tests_images.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from diagram_style import (
    GLASS,
    GOOD,
    INK,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    SHORT_A,
    TALL_A,
    TITLE_SIZE,
    WARN,
    bare,
    new,
    save,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import Arc, Circle, Polygon, Rectangle, Wedge

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import build  # noqa: E402

# ---------------------------------------------------------------- the cell

BASE = np.array([0.0, 0.0])
REACH_NEAR, REACH_FAR = 0.30, 0.78
ZONE = (0.32, 0.64, -0.44, -0.08)
STANDOFF = 0.380
SURVEY_HEIGHT = 0.450
BASELINE = 0.120
FX = 277.1
TALLEST = 0.260
PICTURE = (0.520, 0.390)        # what one survey picture covers, in metres
SHARED = (0.425, 0.175)         # the part of it both pictures of a station share
STATIONS_Y = (-0.3526, -0.2600, -0.1674)
STATION_X = 0.480
WIDEST = 0.105                  # the widest footprint the cell handles
RADIUS = WIDEST / 2.0

PALE = "#dfe4ea"
FAINT = "#eef1f4"

# The arrangement every plan view in this document uses. Five objects in the
# zone, none nearer than 150 mm to another, which is the closest the problem
# allows them to stand.
SCENE = {
    "A": np.array([0.40, -0.30]),
    "B": np.array([0.52, -0.39]),
    "C": np.array([0.32, -0.16]),
    "D": np.array([0.58, -0.14]),
    "E": np.array([0.64, -0.30]),
}


# ------------------------------------------------------------- the geometry



FRAME = (320, 240)              # the wrist camera's picture, in pixels
VIEW_HEIGHT = 120.0             # mm above the table, the height the level look is taken from
SURVEY_MM = SURVEY_HEIGHT * 1000.0
CANVAS = (520, 475)             # a drawing canvas, in those same pixels
NADIR_ON_CANVAS = (185, 105)    # where the point below the camera sits on it

def half_width(radius: float, distance: float) -> float:
    """Half the angle an object of this radius fills, seen from this far away."""
    return math.atan2(radius, distance)


def separation(eye, first, second) -> float:
    """The angle at ``eye`` between the directions to two points."""
    to_first = np.asarray(first, dtype=float) - np.asarray(eye, dtype=float)
    to_second = np.asarray(second, dtype=float) - np.asarray(eye, dtype=float)
    turn = to_first[0] * to_second[1] - to_first[1] * to_second[0]
    return abs(math.atan2(float(turn), float(np.dot(to_first, to_second))))


def shares_the_frame(eye, target, other, radius: float = RADIUS) -> bool:
    """Would ``other`` land on top of ``target`` in a picture taken from ``eye``?

    Judged as an angle at the camera, which is what decides whether two
    silhouettes touch. Not as a distance from the line of sight: an object well
    off to the side but twice as far away covers the same part of the frame.
    """
    range_target = float(np.linalg.norm(np.asarray(target) - np.asarray(eye)))
    range_other = float(np.linalg.norm(np.asarray(other) - np.asarray(eye)))
    if range_target <= 0.0 or range_other <= 0.0:
        return True
    limit = half_width(radius, range_target) + half_width(radius, range_other)
    return separation(eye, target, other) < limit


def wedge_half_angle(spacing: float, radius: float = RADIUS) -> float:
    """Half the angle of the blocked wedge two objects this far apart cast.

    Far from the pair, the angle between them at the camera shrinks as
    ``spacing * sin(theta) / distance`` and the two angular half-widths as
    ``2 * radius / distance``. The distance cancels, so whether they overlap
    depends only on the direction: ``sin(theta) < 2 * radius / spacing``.
    """
    return math.asin(min(1.0, 2.0 * radius / spacing))


def candidates(target, others, *, step_deg: float = 40.0, count: int = 9, radius: float = RADIUS):
    """The places the camera could stand to measure ``target``, in the cell's own order.

    ``count`` directions spaced ``step_deg`` apart, centred on the line back to
    the arm's base, because that is the direction with the least reach in it.
    Each one carries the two facts arithmetic can settle: whether the standoff
    point is inside the working annulus, and which other objects would share
    the picture.
    """
    toward_base = math.atan2(BASE[1] - target[1], BASE[0] - target[0])
    rows = []
    for step in range(count):
        offset = step - (count - 1) / 2.0
        angle = toward_base + math.radians(step_deg * offset)
        eye = target + np.array([math.cos(angle), math.sin(angle)]) * STANDOFF
        out = float(np.linalg.norm(eye - BASE))
        rows.append(
            {
                "step": offset,
                "angle": angle,
                "eye": eye,
                "reach": out,
                "in_reach": REACH_NEAR <= out <= REACH_FAR,
                "blockers": [
                    name for name, place in others if shares_the_frame(eye, target, place, radius)
                ],
            }
        )
    return rows


def others_of(name: str, scene=None):
    scene = SCENE if scene is None else scene
    return [(other, place) for other, place in scene.items() if other != name]


def clear_arc(name: str, scene=None, *, step: float = 0.25) -> float:
    """How many degrees of an object's standoff ring pass both arithmetic tests."""
    scene = SCENE if scene is None else scene
    target = scene[name]
    rest = others_of(name, scene)
    total = 0.0
    for degrees in np.arange(0.0, 360.0, step):
        angle = math.radians(degrees)
        eye = target + np.array([math.cos(angle), math.sin(angle)]) * STANDOFF
        out = float(np.linalg.norm(eye - BASE))
        if REACH_NEAR <= out <= REACH_FAR and not any(
            shares_the_frame(eye, target, place) for _, place in rest
        ):
            total += step
    return total


def survivors(rows) -> list:
    return [row for row in rows if row["in_reach"] and not row["blockers"]]


# ----------------------------------------------------------- drawing helpers


def titles(figure, axes, labels, colours=None, *, heading: str | None = None) -> None:
    """Panel titles on one line, whatever the panels' aspect ratios do to their boxes.

    ``set_title`` hangs the title off the axes box, and an equal-aspect plan
    view has a shorter box than the plot beside it, so the two titles come out
    at different heights. Reading the boxes back once the layout is settled and
    placing the text in figure coordinates keeps them level.
    """
    figure.canvas.draw()
    boxes = [axis.get_position() for axis in axes]
    top = max(box.y1 for box in boxes)
    colours = colours or [INK] * len(labels)
    for box, label, colour in zip(boxes, labels, colours, strict=True):
        figure.text(
            (box.x0 + box.x1) / 2.0, top + 0.035, label,
            ha="center", va="bottom", fontsize=TITLE_SIZE, color=colour,
        )
    if heading:
        figure.text(
            0.5, top + 0.125, heading,
            ha="center", va="bottom", fontsize=TITLE_SIZE + 1, color=INK,
        )


def note(axis, x, y, text, *, colour=INK, ha="left", va="top", mono=False):
    """A block of text that stays readable over a shaded drawing."""
    return axis.text(
        x, y, text, ha=ha, va=va, color=colour, fontsize=NOTE_SIZE,
        family="monospace" if mono else None, zorder=12,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 2.4},
    )


def plan_axes(axis, xlim, ylim) -> None:
    axis.set_xlim(*xlim)
    axis.set_ylim(*ylim)
    axis.set_aspect("equal")
    bare(axis)


def plot_axes(axis) -> None:
    axis.tick_params(labelsize=NOTE_SIZE, colors=INK)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)
    axis.set_axisbelow(True)


def draw_base(axis, *, dx=0.0, dy=-0.055, ha="center") -> None:
    axis.add_patch(Circle(BASE, 0.028, facecolor=INK, edgecolor="none", zorder=9))
    axis.text(
        BASE[0] + dx, BASE[1] + dy, "arm base", ha=ha, va="top" if dy < 0 else "bottom",
        fontsize=NOTE_SIZE, color=INK, zorder=9,
    )


def draw_zone(axis) -> None:
    axis.add_patch(
        Rectangle(
            (ZONE[0], ZONE[2]), ZONE[1] - ZONE[0], ZONE[3] - ZONE[2],
            facecolor="none", edgecolor=MUTED, linestyle=":", linewidth=1.0, zorder=2,
        )
    )


def draw_annulus(axis) -> None:
    for radius, text in ((REACH_NEAR, "300 mm"), (REACH_FAR, "780 mm")):
        axis.add_patch(
            Arc(BASE, 2 * radius, 2 * radius, theta1=-92.0, theta2=26.0,
                edgecolor=MUTED, linewidth=1.1, linestyle="--", zorder=2)
        )
        angle = math.radians(-84.0)
        note(
            axis, radius * math.cos(angle), radius * math.sin(angle) - 0.008, text,
            colour=MUTED, ha="center", va="top",
        )


def draw_objects(axis, *, highlight: str | None = None, scene=None) -> None:
    for name, place in (SCENE if scene is None else scene).items():
        face = GLASS if name == highlight else PALE
        axis.add_patch(Circle(place, RADIUS, facecolor=face, edgecolor=INK, linewidth=1.0, zorder=6))
        axis.text(
            place[0], place[1], name, ha="center", va="center", zorder=7,
            fontsize=LABEL_SIZE, color=INK, fontweight="bold",
        )


def ring_status(axis, name: str, *, radius: float = STANDOFF, scene=None) -> None:
    """The standoff ring round one object, coloured by what each direction fails.

    Sampled with the same two tests the filter uses, so the picture and the
    arithmetic cannot disagree.
    """
    scene = SCENE if scene is None else scene
    target = scene[name]
    rest = others_of(name, scene)
    runs: list[tuple[str, list[float]]] = []
    for degrees in np.arange(0.0, 360.5, 1.0):
        angle = math.radians(degrees)
        eye = target + np.array([math.cos(angle), math.sin(angle)]) * radius
        out = float(np.linalg.norm(eye - BASE))
        if not REACH_NEAR <= out <= REACH_FAR:
            kind = "reach"
        elif any(shares_the_frame(eye, target, place) for _, place in rest):
            kind = "blocked"
        else:
            kind = "clear"
        if runs and runs[-1][0] == kind:
            runs[-1][1].append(degrees)
        else:
            runs.append((kind, [degrees]))
    colours = {"reach": MUTED, "blocked": WARN, "clear": GOOD}
    for kind, degrees in runs:
        arc = np.array([
            target + np.array([math.cos(math.radians(d)), math.sin(math.radians(d))]) * radius
            for d in degrees
        ])
        axis.plot(arc[:, 0], arc[:, 1], color=colours[kind], linewidth=5.0, solid_capstyle="butt",
                  alpha=0.9 if kind == "clear" else 0.5, zorder=3)


def camera(axis, eye, look_at, *, colour=INK, size: float = 0.028, label: str | None = None) -> None:
    """A little wedge for the camera, pointing the way it looks."""
    direction = np.asarray(look_at, dtype=float) - np.asarray(eye, dtype=float)
    angle = math.degrees(math.atan2(direction[1], direction[0]))
    axis.add_patch(Wedge(eye, size, angle - 30.0, angle + 30.0, facecolor=colour,
                         edgecolor="none", zorder=9))
    axis.add_patch(Circle(eye, size * 0.42, facecolor=colour, edgecolor="none", zorder=10))
    if label:
        axis.text(eye[0], eye[1] + size + 0.014, label, ha="center", va="bottom",
                  fontsize=NOTE_SIZE, color=colour, zorder=10)


def silhouette_strip(axis, x0, y0, width, height, shapes, caption) -> None:
    """A little inset standing for the picture the camera would get."""
    axis.add_patch(Rectangle((x0, y0), width, height, facecolor="#f4f6f9",
                             edgecolor=MUTED, linewidth=0.8))
    for shape in shapes:
        axis.add_patch(Polygon(shape, facecolor=WARN, alpha=0.55, edgecolor="none"))
    axis.text(x0 + width / 2, y0 - 0.012, caption, ha="center", va="top",
              fontsize=NOTE_SIZE, color=INK)


# ------------------------------------------------- 1. the two difficulties


def three_tests() -> None:
    figure, axes = new(14.2, 6.8, columns=2)
    left, right = axes

    plan_axes(left, (-0.34, 1.06), (-0.88, 0.28))
    draw_annulus(left)
    draw_zone(left)
    draw_base(left, dx=-0.042, dy=0.0, ha="right")
    ring_status(left, "A")
    draw_objects(left, highlight="A")
    rows = candidates(SCENE["A"], others_of("A"))
    for row in rows:
        if not row["in_reach"]:
            colour, marker, size = INK, "x", 8
        elif row["blockers"]:
            colour, marker, size = WARN, "o", 7
        else:
            colour, marker, size = GOOD, "*", 15
        left.plot([row["eye"][0]], [row["eye"][1]], marker=marker, markersize=size, color=colour,
                  markeredgecolor=colour if marker == "x" else "white",
                  markeredgewidth=1.6 if marker == "x" else 0.8, zorder=10)
        if marker == "*":
            left.plot([row["eye"][0], SCENE["A"][0]], [row["eye"][1], SCENE["A"][1]],
                      color=GOOD, linewidth=1.2, zorder=5)
    note(
        left, -0.33, 0.27,
        "The ring is every direction round A, 380 mm out.\n"
        "grey    the standoff point falls outside 300-780 mm\n"
        "red     another object would share the picture\n"
        "green   clear on both counts\n"
        "x o *   the nine directions the cell actually tries",
        colour=INK, mono=True,
    )

    bare(right)
    right.set_xlim(0, 1)
    right.set_ylim(0, 1)
    header = (
        f"{'facing':>7}  {'standoff point':>18}  {'reach':>6}  "
        f"{'in reach':>8}  shares frame with"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        blockers = ", ".join(row["blockers"]) if row["blockers"] else "-"
        lines.append(
            f"{math.degrees(row['angle']) % 360:6.1f}  "
            f"({row['eye'][0]:+.3f}, {row['eye'][1]:+.3f})  "
            f"{row['reach'] * 1000:5.0f}  "
            f"{'yes' if row['in_reach'] else 'NO':>8}  {blockers}"
        )
    right.text(0.0, 0.99, "\n".join(lines), fontsize=NOTE_SIZE, family="monospace",
               color=INK, ha="left", va="top", linespacing=1.7)
    kept = survivors(rows)
    right.text(
        0.0, 0.52,
        f"9 candidates  ->  {sum(1 for r in rows if r['in_reach'])} inside the annulus  "
        f"->  {len(kept)} with a clear line of sight",
        fontsize=LABEL_SIZE, color=GOOD, ha="left", va="top",
    )
    best = min(kept, key=lambda row: abs(row["step"]))
    right.text(
        0.0, 0.43,
        "Test three is the one arithmetic cannot answer: can the arm get\n"
        "there without carrying an elbow over something? That is the motion\n"
        "planner, and it is asked about the two survivors in order, least\n"
        f"turn first — {math.degrees(best['angle']) % 360:.1f} degrees, then the other.",
        fontsize=NOTE_SIZE, color=INK, ha="left", va="top",
    )
    right.text(
        0.0, 0.24,
        "The two directions nearest the A-to-B line are 303.1 and 343.1\n"
        "degrees. Both stand the camera 867 mm out, so the reach test kills\n"
        "them and the occlusion test never sees them. The cheapest test runs\n"
        "first, and the three tests stay independent of one another.",
        fontsize=NOTE_SIZE, color=MUTED, ha="left", va="top",
    )

    titles(
        figure, axes,
        ["Nine candidate poses for object A", "The same nine, written out"],
        heading=(
            "Three independent tests: inside the reach, a clear line of sight, "
            "and a path the arm can fly"
        ),
    )
    save(figure, "hidden-three-tests.png")


# ----------------------------------------------------- 5. bound, then score


def _no_viewpoint_rate(step_deg: float, count: int, radius: float, *, trials: int = 600) -> float:
    """Share of objects with no usable viewpoint, over arrangements drawn in the zone."""
    generator = random.Random(11)
    seen = stranded = drawn = 0
    while drawn < trials:
        wanted = generator.choice((4, 5, 6))
        places: list[np.ndarray] = []
        for _ in range(200):
            if len(places) == wanted:
                break
            point = np.array([generator.uniform(ZONE[0], ZONE[1]), generator.uniform(ZONE[2], ZONE[3])])
            if all(float(np.linalg.norm(point - other)) >= 0.150 for other in places):
                places.append(point)
        if len(places) < wanted:
            continue
        drawn += 1
        named = [(str(index), place) for index, place in enumerate(places)]
        for index, place in enumerate(places):
            seen += 1
            rest = [row for row in named if row[0] != str(index)]
            if not survivors(candidates(place, rest, step_deg=step_deg, count=count, radius=radius)):
                stranded += 1
    return 100.0 * stranded / seen


def glass_outline(height_mm: float, rim_mm: float, base_fraction: float = 0.45):
    """One of the project's own outlines, at a size inside the kind's own range."""
    return build(
        "tapered_glass",
        height=height_mm / 1000.0,
        rim_diameter=rim_mm / 1000.0,
        base_fraction=base_fraction,
    )


TALL = glass_outline(*TALL_A)     # 225 mm tall, 102 mm across the rim
SHORT = glass_outline(*SHORT_A)   # 95 mm tall, 67 mm across the rim


def profile(outline) -> tuple[np.ndarray, np.ndarray]:
    """The outline's heights and radii, in millimetres."""
    return np.asarray(outline.height) * 1000.0, np.asarray(outline.radius) * 1000.0


def topdown(glasses, size=CANVAS, centre=NADIR_ON_CANVAS) -> np.ndarray:
    """Straight down from 450 mm, with the nadir at ``centre``.

    Each horizontal slice of the glass stays a circle, but it slides away from
    the nadir and grows as it rises, because it is nearer the lens than the
    table is. So a glass images as a teardrop pointing away from the nadir.
    """
    width, height = size
    mask = np.zeros((height, width), np.uint8)
    for gx, gy, outline in glasses:
        z, r = profile(outline)
        for zi, ri in zip(z, r, strict=True):
            away = SURVEY_MM - zi
            cv2.circle(
                mask,
                (int(round(centre[0] + FX * gx / away)), int(round(centre[1] + FX * gy / away))),
                max(1, int(round(FX * ri / away))), 255, -1,
            )
    return mask


def sideon(glasses, size=FRAME) -> np.ndarray:
    """Level, from 120 mm up, the pose the shape measurement is taken from.

    ``gy`` is the distance along the way the camera is looking and ``gx`` the
    offset across it. A horizontal circle seen edge-on is a line, so the
    silhouette is the band between the left and right walls of the profile.
    """
    width, height = size
    mask = np.zeros((height, width), np.uint8)
    for gx, gy, outline in glasses:
        z, r = profile(outline)
        for zi, ri in zip(z, r, strict=True):
            row = int(round(height / 2 - FX * (zi - VIEW_HEIGHT) / gy))
            left = int(round(width / 2 + FX * (gx - ri) / gy))
            right = int(round(width / 2 + FX * (gx + ri) / gy))
            if 0 <= row < height:
                cv2.line(mask, (max(0, left), row), (min(width - 1, right), row), 255, 1)
    return mask


def paint(axis, region: np.ndarray, colour: str, alpha: float = 1.0) -> None:
    """Lay one mask over a picture panel in one colour."""
    rgba = np.zeros((*region.shape, 4), float)
    rgba[region > 0] = to_rgba(colour, alpha)
    axis.imshow(rgba, interpolation="nearest", zorder=3)


def edge(axis, mask: np.ndarray, colour: str, width: float = 1.1, style="-") -> None:
    axis.contour(mask.astype(float), [0.5], colors=[colour], linewidths=width,
                 linestyles=style, zorder=5)


def picture_panel(axis, size, *, frame: bool = True, centre=None) -> None:
    """A panel holding one projected picture, with the real frame marked on it."""
    width, height = size
    bare(axis)
    axis.set_xlim(0, width)
    axis.set_ylim(height, 0)
    axis.set_aspect("equal")
    if frame:
        cx, cy = centre
        axis.add_patch(
            Rectangle((cx - FRAME[0] / 2, cy - FRAME[1] / 2), FRAME[0], FRAME[1],
                      facecolor="none", edgecolor=MUTED, linewidth=1.1, linestyle="--", zorder=6)
        )


def bisect(test, low: float, high: float, tolerance: float = 0.05) -> float:
    """The smallest value in [low, high] at which ``test`` turns true.

    Used to put a number on each threshold the text quotes, rather than
    quoting the nearest value on a coarse sweep.
    """
    while high - low > tolerance:
        middle = (low + high) / 2.0
        if test(middle):
            high = middle
        else:
            low = middle
    return high


def footprint(axis, place, rim_mm: float, base_fraction: float = 0.45, *, colour=GLASS) -> None:
    """A glass on a plan view: the circle it stands on, and the rim over it."""
    axis.add_patch(Circle(tuple(place), rim_mm / 2.0 * base_fraction, facecolor=colour,
                          edgecolor=INK, linewidth=1.0, alpha=0.85, zorder=6))
    axis.add_patch(Circle(tuple(place), rim_mm / 2.0, facecolor="none", edgecolor=INK,
                          linewidth=0.8, linestyle=":", zorder=6))


# ----------------------------------------- 8. hidden from straight above


def level_camera(near_at, far_at, azimuth_deg: float):
    """Where the two glasses sit in the camera's own frame.

    The camera stands at the 380 mm standoff from the near glass, 120 mm up,
    looking level at it. ``azimuth_deg`` is how far round the near glass it has
    stepped from the direction that lines the two glasses up.
    """
    angle = math.radians(azimuth_deg)
    eye = near_at + STANDOFF * 1000.0 * np.array([-math.sin(angle), -math.cos(angle)])
    forward = (near_at - eye) / float(np.linalg.norm(near_at - eye))
    across = np.array([forward[1], -forward[0]])
    return eye, [(float((place - eye) @ across), float((place - eye) @ forward))
                 for place in (near_at, far_at)]


def hidden_from_the_side() -> None:
    """Plain line-of-sight blocking, and the step round that undoes it.

    No splay is needed here. The near glass's outline simply covers the far
    one's, and because the near glass is the nearer of the two it is magnified,
    so it covers a far glass much taller than itself.
    """
    near_at = np.array([0.0, 0.0])
    far_at = np.array([0.0, 300.0])

    def shot(azimuth_deg, near=TALL, far=SHORT):
        _, (gn, gf) = level_camera(near_at, far_at, azimuth_deg)
        only_near = sideon([(gn[0], gn[1], near)])
        only_far = sideon([(gf[0], gf[1], far)])
        both = sideon([(gn[0], gn[1], near), (gf[0], gf[1], far)])
        extra = (both > 0) & (only_near == 0)
        patches, _ = cv2.connectedComponents((both > 0).astype(np.uint8))
        return {"both": both, "only_far": only_far, "extra": extra,
                "added": int(extra.sum()), "alone": int((only_far > 0).sum()),
                "patches": patches - 1, "near": gn, "far": gf}

    in_line = shot(0.0)
    stepped = shot(19.8)
    reversed_pair = shot(0.0, near=SHORT, far=TALL)
    for name, s in (("in line", in_line), ("19.8 deg round", stepped),
                    ("short in front of tall", reversed_pair)):
        print(f"    {name:24s}: the far glass adds {s['added']:5d} px of its {s['alone']:5d}, "
              f"{s['patches']} patch(es)")

    first = bisect(lambda turn: shot(turn)["added"] > 0, 0.0, 15.0)
    apart = bisect(lambda turn: shot(turn)["patches"] > 1, 10.0, 30.0)

    def still_refused(turn: float) -> bool:
        _, (near_xy, far_xy) = level_camera(near_at, far_at, turn)
        between = abs(math.atan2(*near_xy[::-1]) - math.atan2(*far_xy[::-1]))
        limit = (half_width(TALL_A[1] / 2.0, float(np.hypot(*near_xy)))
                 + half_width(SHORT_A[1] / 2.0, float(np.hypot(*far_xy))))
        return between < limit

    refuses_to = bisect(lambda turn: not still_refused(turn), 10.0, 40.0)
    print(f"    the far glass shows its first pixel after a {first:.1f} degree step round, comes "
          f"clear of the near one at {apart:.1f}, and test two refuses everything up to "
          f"{refuses_to:.1f}")

    figure, axes = new(17.2, 5.4, columns=4)
    plan, *pictures = axes

    # --- the plan view -----------------------------------------------------
    plan_axes(plan, (-455.0, 455.0), (-510.0, 570.0))
    for place, size_mm, label in ((near_at, TALL_A, "the near glass,\n225 mm tall,\n102 across"),
                                  (far_at, SHORT_A, "the far glass,\n95 mm tall,\n67 across")):
        footprint(plan, place, size_mm[1])
        note(plan, place[0] + size_mm[1] / 2 + 18.0, place[1], label, colour=INK,
             ha="left", va="center")
    plan.annotate("", xy=(-115.0, far_at[1]), xytext=(-115.0, near_at[1]),
                  arrowprops={"arrowstyle": "<->", "color": GOOD, "linewidth": 1.2}, zorder=7)
    note(plan, -123.0, 150.0, "300 mm", colour=GOOD, ha="right", va="center")
    for azimuth, colour, label, dx, ha in ((0.0, WARN, "in line with the pair", 34.0, "left"),
                                           (19.8, GOOD, "19.8 degrees round", -34.0, "right")):
        eye, (gn, gf) = level_camera(near_at, far_at, azimuth)
        camera(plan, eye, near_at, colour=colour, size=24.0)
        note(plan, eye[0] + dx, eye[1], label, colour=colour, ha=ha, va="center")
        for place, size_mm in ((near_at, TALL_A), (far_at, SHORT_A)):
            span = place - eye
            distance = float(np.linalg.norm(span))
            heading = math.atan2(span[1], span[0])
            for sign in (-1.0, 1.0):
                angle = heading + sign * half_width(size_mm[1] / 2.0, distance)
                plan.plot([eye[0], eye[0] + math.cos(angle) * distance * 1.06],
                          [eye[1], eye[1] + math.sin(angle) * distance * 1.06],
                          color=colour, linewidth=0.9, alpha=0.8, zorder=3)
    plan.add_patch(
        Arc(tuple(near_at), 2 * STANDOFF * 1000.0, 2 * STANDOFF * 1000.0,
            theta1=250.0, theta2=292.0, edgecolor=MUTED, linewidth=1.0, linestyle="--", zorder=2)
    )
    note(plan, -450.0, 565.0,
         "The camera stands 380 mm back from the near\n"
         "glass, 120 mm up, looking level. That is the\n"
         "pose the shape measurement needs anyway.",
         colour=INK)
    note(plan, 450.0, -505.0,
         "The step is round the pair, not away from it:\n"
         "standing further back changes nothing here.",
         colour=GOOD, ha="right", va="bottom")

    # --- the three pictures ------------------------------------------------
    stories = (
        (in_line, "in line: the far glass is gone", WARN),
        (stepped, "19.8 degrees round: it is back", GOOD),
        (reversed_pair, "the short glass in front: it keeps the top", GOOD),
    )
    for axis, (s, _, colour) in zip(pictures, stories, strict=True):
        picture_panel(axis, FRAME, frame=False)
        axis.add_patch(Rectangle((0, 0), FRAME[0] - 1, FRAME[1] - 1, facecolor="#f7f8fa",
                                 edgecolor=MUTED, linewidth=1.0, zorder=0))
        paint(axis, s["both"], GLASS, 0.34)
        paint(axis, s["extra"], GOOD, 0.7)
        edge(axis, s["only_far"], WARN, 1.1, ":")
        wording = ("not one pixel of it" if s["added"] == 0 else f"{s['added']} pixels of it")
        axis.text(
            8, FRAME[1] - 8,
            f"dotted red: where the far glass is\n{wording} reaches the picture, "
            f"out of {s['alone']}\nthe picture holds {s['patches']} patch"
            f"{'' if s['patches'] == 1 else 'es'}",
            ha="left", va="bottom", fontsize=NOTE_SIZE, color=colour, zorder=8,
        )

    titles(
        figure, axes,
        ["Where the two glasses stand"] + [label for _, label, _ in stories],
        [INK] + [colour for _, _, colour in stories],
        heading=(
            "Looking level: no splay is needed, the near outline simply covers the far one, "
            "and the cure is a step round rather than a step out"
        ),
    )
    save(figure, "hidden-moving-the-camera.png")


def main() -> None:
    three_tests()
    hidden_from_the_side()


if __name__ == "__main__":
    main()
