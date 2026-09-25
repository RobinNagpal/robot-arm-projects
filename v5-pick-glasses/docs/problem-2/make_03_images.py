"""Pictures for solution 3 — move the camera.

Seven diagrams, each carrying a different point:

    03-two-difficulties.png       separation and viewpoint are not one problem
    03-the-fixed-sweep.png        the three-station sweep the cell already runs
    03-occlusion-as-geometry.png  the wedge test, before any motion planner
    03-three-tests.png            reach, line of sight and path, on one plan view
    03-bound-then-score.png       filter first, or score first and let the planner reject
    03-the-budget.png             extra looks against the tens-of-seconds ceiling
    03-no-viewpoint.png           the object with nowhere to look from

Run from the project root:

    pixi run python docs/problem-2/make_03_images.py
"""

from __future__ import annotations

import math
import random

import numpy as np
from diagram_style import (
    GLASS,
    GOOD,
    INK,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    TITLE_SIZE,
    WARN,
    bare,
    new,
    save,
)
from matplotlib.patches import Arc, Circle, Polygon, Rectangle, Wedge

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


def two_difficulties() -> None:
    figure, axes = new(13.8, 5.8, columns=3)
    left, middle, right = axes

    # --- seen from the side: the two silhouettes overlap -------------------
    plan_axes(left, (0.0, 0.66), (-0.22, 0.50))
    left.plot([0.02, 0.64], [0.0, 0.0], color=INK, linewidth=1.6, zorder=5)
    eye = np.array([0.12, SURVEY_HEIGHT])
    spans = []
    for x0, name in ((0.2075, "A"), (0.3575, "B")):
        box = [(x0, 0.0), (x0 + WIDEST, 0.0), (x0 + WIDEST, TALLEST), (x0, TALLEST)]
        left.add_patch(Polygon(box, facecolor=PALE, edgecolor=INK, linewidth=1.0, zorder=6))
        left.text(x0 + WIDEST / 2, TALLEST / 2, name, ha="center", va="center",
                  fontsize=LABEL_SIZE, fontweight="bold", zorder=7)
        angles = [math.degrees(math.atan2(corner[1] - eye[1], corner[0] - eye[0])) for corner in box]
        spans.append((min(angles), max(angles)))
        left.add_patch(Wedge(eye, 0.60, min(angles), max(angles), facecolor=GLASS,
                             alpha=0.16, edgecolor="none", zorder=1))
    overlap = (max(spans[0][0], spans[1][0]), min(spans[0][1], spans[1][1]))
    left.add_patch(Wedge(eye, 0.60, overlap[0], overlap[1], facecolor=WARN, alpha=0.40,
                         edgecolor="none", zorder=2))
    camera(left, eye, eye + np.array([0.15, -0.45]), colour=INK, label="camera, 450 mm up")
    note(left, 0.65, 0.46, f"the two fans overlap\nby {overlap[1] - overlap[0]:.0f} degrees",
         colour=WARN, ha="right")
    silhouette_strip(
        left, 0.09, -0.180, 0.48, 0.080,
        [[(0.14, -0.172), (0.14, -0.110), (0.52, -0.110), (0.52, -0.172)]],
        "the picture: one patch, wider than any\nobject this cell handles",
    )

    # --- seen from above: clustering separates them ------------------------
    plan_axes(middle, (0.26, 0.70), (-0.54, -0.10))
    generator = random.Random(4)
    for name in ("A", "B"):
        place = SCENE[name]
        cloud = []
        for _ in range(110):
            angle = generator.uniform(0.0, 2 * math.pi)
            radius = RADIUS * math.sqrt(generator.uniform(0.0, 1.0))
            cloud.append(place + np.array([math.cos(angle), math.sin(angle)]) * radius)
        cloud = np.array(cloud)
        middle.scatter(cloud[:, 0], cloud[:, 1], s=2.6, color=GLASS, alpha=0.8, zorder=3)
        middle.add_patch(Circle(place, RADIUS, facecolor="none", edgecolor=GOOD,
                                linewidth=1.8, zorder=5))
        middle.text(place[0] - RADIUS - 0.014, place[1], name, ha="right", va="center",
                    fontsize=LABEL_SIZE, fontweight="bold", color=GOOD)
    middle.annotate(
        "", xy=tuple(SCENE["B"]), xytext=tuple(SCENE["A"]),
        arrowprops={"arrowstyle": "<->", "color": INK, "linewidth": 1.0},
    )
    note(middle, 0.478, -0.330, "150 mm apart", colour=INK, va="center")
    note(
        middle, 0.48, -0.520,
        "Two circles, two positions,\ntwo widths. The merge in\npanel 1 is answered.",
        colour=GOOD, ha="center", va="bottom",
    )

    # --- and the side-on view is still blocked -----------------------------
    plan_axes(right, (0.05, 0.95), (-0.66, 0.36))
    target, blocker = SCENE["A"], SCENE["B"]
    for place, name in ((target, "A"), (blocker, "B")):
        right.add_patch(Circle(place, RADIUS, facecolor=PALE, edgecolor=INK, linewidth=1.0, zorder=6))
        right.text(place[0], place[1], name, ha="center", va="center",
                   fontsize=LABEL_SIZE, fontweight="bold", zorder=7)
    stand = np.array([0.314, 0.070])
    camera(right, stand, target, colour=WARN)
    for place in (target, blocker):
        distance = float(np.linalg.norm(place - stand))
        heading = math.atan2(*(place - stand)[::-1])
        for sign in (-1.0, 1.0):
            angle = heading + sign * half_width(RADIUS, distance)
            right.plot(
                [stand[0], stand[0] + math.cos(angle) * 0.46],
                [stand[1], stand[1] + math.sin(angle) * 0.46],
                color=WARN, linewidth=0.9, alpha=0.75, zorder=3,
            )
    note(
        right, 0.94, 0.35,
        "The camera stands 380 mm back from A,\n"
        "level, 120 mm above the table — the pose\n"
        "the profile step needs. B is 11.0 degrees\n"
        "off that line of sight, and two silhouettes\n"
        "this far away meet at 13.8.",
        colour=INK, ha="right",
    )
    silhouette_strip(
        right, 0.19, -0.575, 0.46, 0.080,
        [[(0.25, -0.567), (0.25, -0.512), (0.33, -0.502), (0.43, -0.507), (0.53, -0.527),
          (0.53, -0.567)]],
        "the outline: two objects, one silhouette",
    )
    note(
        right, 0.94, -0.10,
        "No cleverness applied to\nthis picture produces A's\n"
        "outline against the table.\nThe camera has to move.",
        colour=WARN, ha="right", va="top",
    )

    titles(
        figure, axes,
        [
            "1. From the sweep: they merge",
            "2. On the table: they separate",
            "3. The side-on view: still blocked",
        ],
        [INK, GOOD, WARN],
        heading="Separating objects and finding a viewpoint are two difficulties, not one",
    )
    save(figure, "03-two-difficulties.png")


# ------------------------------------------------------ 2. the fixed sweep


def fixed_sweep() -> None:
    figure, axes = new(13.4, 5.8, columns=2)
    left, right = axes

    plan_axes(left, (-0.12, 0.92), (-0.74, 0.16))
    draw_base(left, dy=-0.050)
    for index, y in enumerate(STATIONS_Y, start=1):
        centre = np.array([STATION_X, y])
        left.add_patch(
            Rectangle(
                (centre[0] - PICTURE[0] / 2, centre[1] - PICTURE[1] / 2), PICTURE[0], PICTURE[1],
                facecolor=GLASS, alpha=0.05, edgecolor=GLASS, linewidth=0.7, linestyle=":", zorder=1,
            )
        )
        left.add_patch(
            Rectangle(
                (centre[0] - SHARED[0] / 2, centre[1] - SHARED[1] / 2), SHARED[0], SHARED[1],
                facecolor=GLASS, alpha=0.14, edgecolor=GLASS, linewidth=1.1, zorder=2,
            )
        )
        left.plot([centre[0]], [centre[1]], marker="o", markersize=5, color=INK, zorder=7)
        note(left, centre[0] + 0.022, centre[1], f"station {index}", colour=INK, va="center")
    left.add_patch(
        Rectangle(
            (ZONE[0], ZONE[2]), ZONE[1] - ZONE[0], ZONE[3] - ZONE[2],
            facecolor="none", edgecolor=INK, linewidth=1.5, zorder=4,
        )
    )
    note(
        left, -0.11, 0.14,
        "dotted   what one picture covers, 520 x 390 mm\n"
        "shaded   the 425 x 175 mm both pictures share\n"
        "heavy    the zone that has to be covered",
        colour=INK, mono=True,
    )
    gap = (STATIONS_Y[2] - STATIONS_Y[0]) / 2.0
    note(
        left, 0.40, -0.72,
        f"Stations {gap * 1000:.0f} mm apart in y, shared strip {SHARED[1] * 1000:.0f} mm deep: "
        f"{100 * (1 - gap / SHARED[1]):.0f} per cent\noverlap, so nothing lands only on an edge.",
        colour=MUTED, ha="center", va="bottom",
    )

    plan_axes(right, (0.00, 0.90), (-0.13, 0.54))
    right.plot([0.02, 0.88], [0.0, 0.0], color=INK, linewidth=1.6, zorder=5)
    right.text(0.82, -0.010, "the table top", ha="center", va="top", fontsize=NOTE_SIZE, color=INK)
    left_x, width = 0.40, 0.075
    right.add_patch(Rectangle((left_x, 0.0), width, TALLEST, facecolor=PALE, edgecolor=INK, zorder=6))
    right.text(left_x + width / 2, TALLEST + 0.014, "a 260 mm object", ha="center", va="bottom",
               fontsize=NOTE_SIZE, color=INK)
    top = np.array([left_x + width, TALLEST])
    landings = []
    for offset, colour, name in ((-BASELINE / 2, INK, "picture 1"), (BASELINE / 2, GLASS, "picture 2")):
        eye = np.array([left_x + width / 2 + offset, SURVEY_HEIGHT])
        camera(right, eye, eye + np.array([0.0, -0.1]), colour=colour, size=0.020)
        right.text(eye[0], eye[1] + 0.030, name, ha="center", va="bottom",
                   fontsize=NOTE_SIZE, color=colour)
        landing = eye + (top - eye) * (eye[1] / (eye[1] - top[1]))
        landings.append(landing[0])
        right.plot([eye[0], landing[0]], [eye[1], 0.0], color=colour, linewidth=1.0,
                   linestyle="--", zorder=4)
        right.plot([landing[0]], [0.0], marker="v", markersize=6, color=colour, zorder=7)
    right.annotate(
        "", xy=(landings[0], -0.050), xytext=(landings[1], -0.050),
        arrowprops={"arrowstyle": "<->", "color": WARN, "linewidth": 1.1},
    )
    right.text(
        (landings[0] + landings[1]) / 2, -0.062,
        f"{abs(landings[0] - landings[1]) * 1000:.0f} mm apart on the table", ha="center", va="top",
        fontsize=NOTE_SIZE, color=WARN,
    )
    note(
        right, 0.01, 0.255,
        "One picture lays the top of\n"
        "the object down on the table\n"
        "in the wrong place, and cannot\n"
        "say how far wrong. Move the\n"
        f"camera {BASELINE * 1000:.0f} mm and that point\n"
        f"moves {abs(landings[0] - landings[1]) * 1000:.0f} mm. That ratio is\n"
        "the height.",
        colour=INK,
    )
    note(
        right, 0.88, 0.165,
        f"At {SURVEY_HEIGHT * 1000:.0f} mm one pixel covers\n"
        f"{SURVEY_HEIGHT / FX * 1000:.2f} mm of table.",
        colour=MUTED, ha="right",
    )

    titles(
        figure, axes,
        ["Three stations, six pictures, seen from above", "Why each station takes two pictures"],
        heading="The fixed sweep: what the cell already does before any of this starts",
    )
    save(figure, "03-the-fixed-sweep.png")


# ----------------------------------------------- 3. occlusion as geometry


def occlusion_as_geometry() -> None:
    figure, axes = new(14.6, 5.2, columns=3)
    left, middle, right = axes

    # --- the angular test at one pose -------------------------------------
    plan_axes(left, (-0.02, 0.70), (-0.40, 0.32))
    target = np.array([0.58, 0.02])
    blocker = np.array([0.46, -0.035])
    eye = np.array([0.04, 0.0])
    for place, name, face in ((target, "A, the target", GLASS), (blocker, "B", PALE)):
        left.add_patch(Circle(place, RADIUS, facecolor=face, edgecolor=INK, linewidth=1.0, zorder=6))
        left.text(place[0], place[1] + RADIUS + 0.012, name, ha="center", va="bottom",
                  fontsize=NOTE_SIZE, color=INK, zorder=7)
    camera(left, eye, target, colour=INK, label="camera")
    headings = []
    for place, colour in ((target, GLASS), (blocker, MUTED)):
        span = place - eye
        distance = float(np.linalg.norm(span))
        heading = math.atan2(span[1], span[0])
        headings.append(math.degrees(heading))
        for sign in (-1.0, 1.0):
            angle = heading + sign * half_width(RADIUS, distance)
            left.plot([eye[0], eye[0] + math.cos(angle) * distance * 1.14],
                      [eye[1], eye[1] + math.sin(angle) * distance * 1.14],
                      color=colour, linewidth=1.0, zorder=3)
    between = math.degrees(separation(eye, target, blocker))
    limit = math.degrees(
        half_width(RADIUS, float(np.linalg.norm(target - eye)))
        + half_width(RADIUS, float(np.linalg.norm(blocker - eye)))
    )
    left.add_patch(Arc(eye, 0.66, 0.66, theta1=min(headings), theta2=max(headings),
                       edgecolor=WARN, linewidth=1.6, zorder=4))
    note(
        left, 0.0, -0.22,
        f"angle between the centres   {between:4.1f} deg\n"
        f"sum of the two half-widths  {limit:4.1f} deg\n"
        f"{between:.1f} is under {limit:.1f}: the two touch",
        colour=WARN, mono=True,
    )
    note(left, 0.0, 0.31, "Four multiplications and two\narctangents. No picture, no\nplanner, no motion.",
         colour=MUTED)

    # --- the wedge --------------------------------------------------------
    plan_axes(middle, (-0.40, 0.46), (-0.43, 0.43))
    here, there = np.array([0.0, 0.0]), np.array([0.150, 0.0])
    half = math.degrees(wedge_half_angle(0.150))
    for centre in (0.0, 180.0):
        middle.add_patch(
            Wedge(here, 0.64, centre - half, centre + half,
                  facecolor=WARN, alpha=0.15, edgecolor=WARN, linewidth=0.8, zorder=1)
        )
    ring = np.array([
        [math.cos(math.radians(a)) * STANDOFF, math.sin(math.radians(a)) * STANDOFF]
        for a in range(0, 361, 3)
    ])
    middle.plot(ring[:, 0], ring[:, 1], color=MUTED, linewidth=1.0, linestyle="--", zorder=3)
    for place, name in ((here, "A"), (there, "B")):
        middle.add_patch(Circle(place, RADIUS, facecolor=PALE, edgecolor=INK, zorder=6))
        middle.text(place[0], place[1], name, ha="center", va="center",
                    fontsize=LABEL_SIZE, fontweight="bold", zorder=7)
    middle.add_patch(Arc(here, 0.46, 0.46, theta1=0.0, theta2=half,
                         edgecolor=WARN, linewidth=1.4, zorder=4))
    note(middle, 0.255, 0.120, f"{half:.1f} deg", colour=WARN)
    note(middle, -0.39, -0.42, "the 380 mm\nstandoff ring", colour=MUTED, va="bottom")
    note(
        middle, 0.03, 0.42,
        f"Two objects 150 mm apart put {2 * half:.0f} degrees\n"
        f"of the ring out of use — {100 * 2 * half / 360:.0f} per cent of it —\n"
        "and that is one neighbour.",
        colour=INK, ha="center",
    )

    # --- how the wedge narrows with spacing -------------------------------
    spacings = np.linspace(0.150, 0.420, 200)
    for radius, colour, label in (
        (0.105 / 2, WARN, "105 mm footprints"),
        (0.075 / 2, GLASS, "75 mm footprints"),
        (0.045 / 2, GOOD, "45 mm footprints"),
    ):
        blocked = [200.0 * math.degrees(wedge_half_angle(s, radius)) / 360.0 for s in spacings]
        right.plot(spacings * 1000, blocked, color=colour, linewidth=1.9, label=label)
    right.axvline(150, color=MUTED, linewidth=1.0, linestyle=":")
    right.text(154, 27.2, "the closest two objects\nmay ever stand",
               fontsize=NOTE_SIZE, color=MUTED, va="top")
    right.set_xlabel("how far apart the two objects stand (mm)", fontsize=NOTE_SIZE, color=INK)
    right.set_ylabel("per cent of the standoff ring blocked", fontsize=NOTE_SIZE, color=INK)
    right.set_ylim(0, 28)
    right.set_xlim(142, 420)
    plot_axes(right)
    right.grid(axis="y", color="#e8ebef", linewidth=0.8)
    right.legend(fontsize=NOTE_SIZE, frameon=False, loc="upper right")

    titles(
        figure, axes,
        ["The test at one camera pose", "Every pose it rejects, at once", "What one neighbour costs"],
        heading="Occlusion is geometry, not image processing: on a table it is a wedge test",
    )
    save(figure, "03-occlusion-as-geometry.png")


# ---------------------------------------------------------- 4. three tests


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
    save(figure, "03-three-tests.png")


# ----------------------------------------------------- 5. bound, then score


def bound_then_score() -> None:
    total = in_reach = clear = 0
    for name in SCENE:
        rows = candidates(SCENE[name], others_of(name))
        total += len(rows)
        in_reach += sum(1 for row in rows if row["in_reach"])
        clear += len(survivors(rows))
    unreachable = total - in_reach
    blocked = in_reach - clear

    figure, axes = new(13.6, 6.4, columns=2)
    for axis in axes:
        bare(axis)
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)

    def funnel(axis, stages, *, accent) -> None:
        top, height, step = 0.92, 0.106, 0.150
        for index, (label, count, cost) in enumerate(stages):
            bottom = top - height
            axis.add_patch(Rectangle((0.02, bottom), 0.60, height, facecolor=FAINT,
                                     edgecolor="none", zorder=1))
            axis.add_patch(Rectangle((0.02, bottom), 0.60 * count / total, height,
                                     facecolor=accent, alpha=0.30, edgecolor=accent,
                                     linewidth=1.0, zorder=2))
            axis.text(0.035, bottom + height / 2, label, fontsize=NOTE_SIZE, color=INK,
                      va="center", zorder=3)
            axis.text(0.655, bottom + height / 2, f"{count}", fontsize=LABEL_SIZE, color=accent,
                      va="center", ha="right", fontweight="bold", zorder=3)
            axis.text(0.69, bottom + height / 2, cost, fontsize=NOTE_SIZE, color=MUTED,
                      va="center", ha="left", zorder=3)
            if index < len(stages) - 1:
                axis.annotate(
                    "", xy=(0.10, bottom - step + height), xytext=(0.10, bottom),
                    arrowprops={"arrowstyle": "-|>", "color": MUTED, "linewidth": 1.0},
                )
            top -= step

    funnel(
        axes[0],
        [
            ("every direction round every object", total, "free"),
            ("inside 300-780 mm?", in_reach, "a square root each"),
            ("line of sight clear?", clear, "a wedge test per pair"),
            ("score what is left, best first", clear, "a sort"),
            ("ask the motion planner, in that order", clear, "the expensive call"),
        ],
        accent=GOOD,
    )
    axes[0].text(
        0.02, 0.09,
        f"The planner is asked about {clear} poses at most, and every one of them\n"
        "is worth flying to. Whatever it answers is useful: a refusal means\n"
        "there is no path, not that the picture would have been wrong.",
        fontsize=NOTE_SIZE, color=GOOD, ha="left", va="bottom",
    )

    funnel(
        axes[1],
        [
            ("every direction round every object", total, "free"),
            ("score all of them", total, "a sort"),
            ("ask the motion planner, best first", total, f"the expensive call, {total} times"),
            (f"it refuses the {unreachable} out of reach", unreachable, "slow, but at least it is a no"),
            (f"it accepts the {blocked} that are blocked", blocked, "nothing errors"),
        ],
        accent=WARN,
    )
    axes[1].text(
        0.02, 0.09,
        "The planner has no opinion about lines of sight, so it says yes to\n"
        f"all {blocked} blocked poses. The cell gets slow, and then it returns a\n"
        "confident measurement of two objects reported as one.",
        fontsize=NOTE_SIZE, color=WARN, ha="left", va="bottom",
    )

    titles(
        figure, axes,
        ["Bound, then score", "Score, then let the planner reject"],
        [GOOD, WARN],
        heading="The structural point: filter with arithmetic before spending anything",
    )
    save(figure, "03-bound-then-score.png")


# ---------------------------------------------------------------- 6. budget


def budget() -> None:
    figure, axes = new(13.6, 5.6, columns=2)
    left, right = axes

    rows = [
        ("the sweep alone: 3 stations", 3, 0, GLASS),
        ("+ 2 extra looks", 3, 2, GOOD),
        ("+ 4 extra looks (the cap)", 3, 4, GOOD),
        ("+ 6 extra looks", 3, 6, WARN),
        ("2 looks for each of 5 objects", 3, 10, WARN),
    ]
    positions = list(range(len(rows)))[::-1]
    for position, (_, sweep, extra, colour) in zip(positions, rows, strict=True):
        left.barh(position, sweep, color=GLASS, alpha=0.75, height=0.54, edgecolor="none")
        left.barh(position, extra, left=sweep, color=colour, alpha=0.40, height=0.54, edgecolor=colour)
        left.text(sweep + extra + 0.2, position, f"{sweep + extra}", va="center",
                  fontsize=NOTE_SIZE, color=INK)
    left.set_yticks(positions)
    left.set_yticklabels([row[0] for row in rows], fontsize=NOTE_SIZE, color=INK)
    left.set_xlabel("station-equivalents: one move, one settle, two pictures",
                    fontsize=NOTE_SIZE, color=INK)
    left.set_xlim(0, 16.2)
    plot_axes(left)
    left.grid(axis="x", color="#e8ebef", linewidth=0.8)
    left.set_ylim(-0.62, 5.05)
    for units, seconds in ((15, 4), (10, 6), (7.5, 8)):
        left.axvline(units, color=WARN, linewidth=1.1, linestyle="--", alpha=0.85)
        left.text(units, 3.34, f"{seconds} s", color=WARN, fontsize=NOTE_SIZE,
                  ha="center", va="bottom",
                  bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.6})
    left.text(
        15.9, 5.0, "dashed: where 60 seconds falls, if one\nstation-equivalent costs 8, 6 or 4 seconds",
        color=WARN, fontsize=NOTE_SIZE, ha="right", va="top",
    )

    units = np.arange(0, 16.01, 0.1)
    for seconds, colour in ((4.0, GOOD), (6.0, GLASS), (8.0, WARN)):
        right.plot(units, units * seconds, color=colour, linewidth=1.9,
                   label=f"one unit takes {seconds:.0f} s")
    right.axhline(60, color=INK, linewidth=1.2, linestyle="--")
    right.text(0.3, 62, 'the top of "tens of seconds"', fontsize=NOTE_SIZE, color=INK)
    right.axvspan(3, 7, color=GOOD, alpha=0.10)
    right.text(5, 116, "the sweep plus\nthe 4-look cap", ha="center", fontsize=NOTE_SIZE, color=GOOD)
    right.axvline(9, color=WARN, linewidth=1.0, linestyle=":")
    right.text(9.4, 116, "6 looks: over the ceiling\nunless a unit turns out\nto be at the cheap end",
               fontsize=NOTE_SIZE, color=WARN, va="top")
    right.set_xlabel("station-equivalents in the run", fontsize=NOTE_SIZE, color=INK)
    right.set_ylabel("survey time (s)", fontsize=NOTE_SIZE, color=INK)
    right.set_xlim(0, 16)
    right.set_ylim(0, 128)
    plot_axes(right)
    right.grid(color="#e8ebef", linewidth=0.8)
    right.legend(fontsize=NOTE_SIZE, frameon=False, loc="lower right")

    titles(
        figure, axes,
        ["Where 60 seconds runs out", "What one unit costs is the number to measure"],
        heading="The budget: the survey is three stations, and the cap is four extra looks",
    )
    save(figure, "03-the-budget.png")


# ----------------------------------------------------------- 7. no viewpoint


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


def no_viewpoint() -> None:
    figure, axes = new(15.6, 6.4, columns=3)
    left, middle, right = axes

    # --- E, in the arrangement the rest of the document uses ---------------
    plan_axes(left, (-0.10, 1.24), (-1.02, 0.32))
    draw_annulus(left)
    draw_zone(left)
    draw_base(left, dy=-0.050)
    ring_status(left, "E")
    draw_objects(left, highlight="E")
    rows = candidates(SCENE["E"], others_of("E"))
    for row in rows:
        colour, marker = (INK, "x") if not row["in_reach"] else (WARN, "o")
        left.plot([row["eye"][0]], [row["eye"][1]], marker=marker, markersize=8, color=colour,
                  markeredgecolor=colour if marker == "x" else "white",
                  markeredgewidth=1.6 if marker == "x" else 0.8, zorder=10)
    widths = "  ".join(f"{name} {clear_arc(name):.0f}" for name in SCENE)
    middle_of_gap = math.radians(144.6)
    left.annotate(
        "", xy=tuple(SCENE["E"] + np.array([math.cos(middle_of_gap), math.sin(middle_of_gap)]) * STANDOFF),
        xytext=(0.20, 0.02),
        arrowprops={"arrowstyle": "->", "color": GOOD, "linewidth": 1.2},
    )
    note(
        left, -0.09, 0.30,
        f"{sum(1 for r in rows if not r['in_reach'])} of the nine fall outside the annulus\n"
        f"{sum(1 for r in rows if r['in_reach'] and r['blockers'])} of the nine are blocked\n"
        f"but {clear_arc('E'):.0f} degrees of the ring are clear",
        colour=INK, mono=True,
    )
    note(
        left, 0.19, 0.03,
        "10 degrees of clear ring —\nthe nine directions step over it",
        colour=GOOD, ha="left", va="bottom",
    )
    note(
        left, 0.30, -1.00,
        f"Clear arc per object, in degrees:\n  {widths}\n"
        "Nine directions sit 40 apart, so only an arc\n"
        "wider than 40 is certain to be hit.",
        colour=MUTED, va="bottom", mono=True,
    )

    # --- and an arrangement where there is nothing to refine towards -------
    boxed = {
        "P": np.array([0.324, -0.308]),
        "Q": np.array([0.539, -0.100]),
        "R": np.array([0.628, -0.376]),
        "S": np.array([0.481, -0.278]),
        "T": np.array([0.473, -0.434]),
    }
    plan_axes(middle, (-0.10, 1.24), (-1.02, 0.32))
    draw_annulus(middle)
    draw_zone(middle)
    draw_base(middle, dy=-0.050)
    ring_status(middle, "S", scene=boxed)
    draw_objects(middle, highlight="S", scene=boxed)
    note(
        middle, -0.09, 0.30,
        f"S stands {float(np.linalg.norm(boxed['S'] - BASE)) * 1000:.0f} mm out, "
        "four neighbours round it.\n"
        f"Clear arc on its ring: {clear_arc('S', boxed):.0f} degrees.\n"
        "No grid, however fine, finds a viewpoint here.",
        colour=INK, mono=True,
    )
    note(
        middle, 0.30, -1.00,
        "This is the handover to problem 3.\n"
        "S is reported with its reason, and something\n"
        "has to move before the question is asked again.",
        colour=WARN, va="bottom",
    )

    # --- how often it happens, and what the grid has to do with it ---------
    grids = ((40.0, 9), (20.0, 17), (10.0, 33), (5.0, 65))
    xs = list(range(len(grids)))
    for radius, colour, label in (
        (0.105 / 2, WARN, "105 mm footprints"),
        (0.075 / 2, GLASS, "75 mm footprints"),
        (0.045 / 2, GOOD, "45 mm footprints"),
    ):
        rates = [_no_viewpoint_rate(step, count, radius) for step, count in grids]
        right.plot(xs, rates, marker="o", markersize=5, color=colour, linewidth=1.9, label=label)
        for x, rate in zip(xs, rates, strict=True):
            right.text(x, rate + 1.8, f"{rate:.0f}%", fontsize=NOTE_SIZE, color=colour, ha="center")
    right.set_xticks(xs)
    right.set_xticklabels([f"{count}\n({step:.0f} deg apart)" for step, count in grids])
    right.set_xlim(-0.3, len(grids) - 0.7)
    right.set_xlabel("how many directions round each object are tried", fontsize=NOTE_SIZE, color=INK)
    right.set_ylabel("objects with no usable viewpoint (%)", fontsize=NOTE_SIZE, color=INK)
    right.set_ylim(0, 54)
    plot_axes(right)
    right.grid(axis="y", color="#e8ebef", linewidth=0.8)
    right.legend(fontsize=NOTE_SIZE, frameon=False, loc="upper right")
    right.text(
        0.0, -0.20,
        "600 arrangements of four to six objects drawn in the zone,\n"
        "150 mm apart or more, counted with the same two tests. Most of\n"
        "the drop is the grid, not the geometry — but it never reaches zero.",
        transform=right.transAxes, ha="left", va="top", fontsize=NOTE_SIZE, color=MUTED,
    )

    titles(
        figure, axes,
        [
            "E: stranded by the grid, not the geometry",
            "S: boxed in, and no grid helps",
            "How often, and what makes it rarer",
        ],
        [INK, WARN, INK],
        heading="The limit: an object with no usable viewpoint is a result, and the handover to problem 3",
    )
    save(figure, "03-no-viewpoint.png")


def main() -> None:
    two_difficulties()
    fixed_sweep()
    occlusion_as_geometry()
    three_tests()
    bound_then_score()
    budget()
    no_viewpoint()


if __name__ == "__main__":
    main()
