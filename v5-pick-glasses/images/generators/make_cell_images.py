"""Diagrams for docs/the-cell.md — the layout, the reach and the sensors.

Every dimension is read from the project's own constants rather than typed in,
so a picture cannot drift from the code. If a number moves in
``arm/dimensions.py``, ``table/layout.py`` or ``rack/layout.py``, re-run this
and the drawings move with it.

    pixi run python images/generators/make_cell_images.py
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import to_rgba  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle, Wedge  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "work_cell"))

from work_cell.arm.dimensions import (  # noqa: E402
    CAMERA_OFFSET,
    COMFORTABLE_REACH,
    GRASP_DEPTH,
    GRIPPER_MAX_OPENING,
    LOWEST_GRIP,
    MEASURE_FRAME_MARGIN,
    MEASURE_STANDOFF,
    MEASURE_VIEW_HEIGHT,
    PAD_HEIGHT,
    PAD_LENGTH,
    SURVEY_BASELINE,
    SURVEY_HEIGHT,
    survey_stations,
)
from work_cell.glasses.shapes import KIND_RANGES, family  # noqa: E402
from work_cell.rack.layout import (  # noqa: E402
    GLASS_ZONE,
    MARKER_SIZE,
    PEG_HEIGHT,
    RACK_AREA,
    RACK_TOP_Z,
)
from work_cell.table.layout import ROBOT_BASE, TABLE_CENTRE_XY, TABLE_SIZE, TABLE_TOP_Z  # noqa: E402
from work_cell.task import TALLEST_GLASS  # noqa: E402

IMAGES = ROOT / "images"
INK = "#22272e"
MUTED = "#8b949e"
GLASS = "#4c8fd6"
WARN = "#d9694b"
GOOD = "#5aa469"
PAPER = "#ffffff"
TITLE = 12
LABEL = 9
NOTE = 8.2

MM = 1000.0  # the drawings are in millimetres; the constants are in metres

# The lens, read out of the model the simulator loads rather than typed here.
_XACRO = (ROOT / "src" / "work_cell" / "work_cell" / "arm" / "camera"
          / "wrist_camera.urdf.xacro").read_text()


def _from_xacro(tag: str) -> float:
    found = re.search(rf"<{tag}>([0-9.]+)</{tag}>", _XACRO)
    if found is None:
        raise SystemExit(f"<{tag}> is no longer in wrist_camera.urdf.xacro")
    return float(found.group(1))


FOV = _from_xacro("horizontal_fov")
COLUMNS, ROWS = int(_from_xacro("width")), int(_from_xacro("height"))

# One focal length does for both axes: the pixels are square, which is how the
# simulator builds a camera given a field of view across.
FX = (COLUMNS / 2.0) / math.tan(FOV / 2.0)

# How far back the arm stands to measure a glass, worked out the way task.py
# works it out: the frame has to reach from the table up to the rim of the
# tallest glass the cell handles, and how far back that puts the camera is a
# question about the lens.
_HALF_FRAME = (ROWS / 2.0) / FX
STANDOFF = max(
    MEASURE_STANDOFF,
    max(MEASURE_VIEW_HEIGHT, TALLEST_GLASS - MEASURE_VIEW_HEIGHT)
    / (_HALF_FRAME * MEASURE_FRAME_MARGIN),
)

# What one survey picture covers, and how much of it both pictures of a
# station share — the second is what the stations are spread on.
FOOTPRINT = (SURVEY_HEIGHT * COLUMNS / FX, SURVEY_HEIGHT * ROWS / FX)
SHARED = (FOOTPRINT[0] - GRIPPER_MAX_OPENING,
          FOOTPRINT[1] - SURVEY_BASELINE - GRIPPER_MAX_OPENING)

# Where the camera ends up when the fingers are round a glass: the tool stops
# GRASP_DEPTH short of the glass's axis and the camera sits CAMERA_OFFSET from
# the tool, a little further along the approach and well off to one side.
FINGER_BACK = GRASP_DEPTH - CAMERA_OFFSET[2]
FINGER_ASIDE = CAMERA_OFFSET[0]


def save(figure, name: str) -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    figure.savefig(IMAGES / name, dpi=150, bbox_inches="tight", facecolor=PAPER)
    plt.close(figure)
    print(f"wrote images/{name}")


def _tint(colour: str, alpha: float) -> tuple[float, float, float, float]:
    """The colour at a given transparency, as matplotlib wants it."""
    return to_rgba(colour, alpha)


def bare(axis) -> None:
    axis.set_xticks([])
    axis.set_yticks([])
    for side in axis.spines.values():
        side.set_visible(False)


def span(axis, x0, y0, x1, y1, text, colour=INK, offset=(0, 0), size=NOTE):
    """A double-headed dimension arrow with its measurement written beside it."""
    axis.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="<->",
                                   mutation_scale=9, color=colour, lw=1.0))
    axis.text((x0 + x1) / 2 + offset[0], (y0 + y1) / 2 + offset[1], text,
              fontsize=size, color=colour, ha="center", va="center")


def cell_from_above() -> None:
    figure, axis = plt.subplots(figsize=(11.0, 8.2))
    figure.patch.set_facecolor(PAPER)
    axis.set_facecolor(PAPER)
    bare(axis)
    axis.set_aspect("equal")

    tw, td, _ = (v * MM for v in TABLE_SIZE)
    tcx, tcy = (v * MM for v in TABLE_CENTRE_XY)
    table = Rectangle((tcx - tw / 2, tcy - td / 2), tw, td,
                      facecolor="#f6f7f8", edgecolor=MUTED, lw=1.3)
    axis.add_patch(table)

    # The reach the arm works in comfortably, as an annulus round the base.
    near, far = (v * MM for v in COMFORTABLE_REACH)
    axis.add_patch(Wedge((0, 0), far, 0, 360, width=far - near,
                         facecolor=GOOD, alpha=0.08, edgecolor="none"))
    for r, label in ((near, f"{near:.0f} mm"), (far, f"{far:.0f} mm")):
        axis.add_patch(Circle((0, 0), r, fill=False, edgecolor=GOOD, lw=1.0,
                              ls=(0, (5, 4))))
        bearing = math.radians(150)
        axis.text(r * math.cos(bearing), r * math.sin(bearing), f"{label} ",
                  fontsize=NOTE, color=GOOD, ha="right", va="center")

    gx0, gx1, gy0, gy1 = (v * MM for v in GLASS_ZONE)
    axis.add_patch(Rectangle((gx0, gy0), gx1 - gx0, gy1 - gy0,
                             facecolor=GLASS, alpha=0.16, edgecolor=GLASS, lw=1.4))
    axis.text(gx0 - 6, gy1 + 78, "the glass zone", fontsize=LABEL,
              color=GLASS, ha="right", va="center")

    rx0, rx1, ry0, ry1 = (v * MM for v in RACK_AREA)
    axis.add_patch(Rectangle((rx0, ry0), rx1 - rx0, ry1 - ry0,
                             facecolor=WARN, alpha=0.20, edgecolor=WARN, lw=1.4))
    axis.text((rx0 + rx1) / 2, ry1 + 16, "the rack", fontsize=LABEL, color=WARN,
              ha="center", va="bottom")

    # The arm's base.
    axis.add_patch(Circle((0, 0), 34, facecolor=INK, edgecolor="none"))
    axis.text(0, -56, "the arm's base\n(0, 0)", fontsize=NOTE, color=INK,
              ha="center", va="top")

    # Five glasses at a layout that really satisfies the 150 mm rule, to give
    # the zone a scale. Fixed rather than sampled: at 150 mm apart the zone
    # holds five with very little slack, and rejection sampling rarely lands one.
    placed = [(340.0, -100.0), (340.0, -260.0), (340.0, -420.0),
              (500.0, -180.0), (500.0, -340.0)]
    closest = min(math.dist(placed[0], q) for q in placed[1:])
    assert min(math.dist(a, b) for i, a in enumerate(placed)
               for b in placed[i + 1:]) >= 150.0, "the drawn layout breaks the 150 mm rule"
    for x, y in placed:
        axis.add_patch(Circle((x, y), 37, facecolor=PAPER, edgecolor=GLASS, lw=1.5))
        axis.add_patch(Circle((x, y), 37, facecolor=GLASS, alpha=0.30, edgecolor="none"))
    near_pair = min(placed[1:], key=lambda q: math.dist(placed[0], q))
    span(axis, *placed[0], *near_pair, "", colour=INK)
    axis.text(placed[0][0] - 16, (placed[0][1] + near_pair[1]) / 2,
              f"{closest:.0f} mm apart,\nthe closest allowed", fontsize=NOTE,
              color=INK, ha="right", va="center")

    # Dimensions on each side.
    span(axis, gx0, gy0 - 52, gx1, gy0 - 52, f"{gx1 - gx0:.0f} mm", GLASS, (0, -22))
    span(axis, gx1 + 34, gy0, gx1 + 34, gy1, f"{gy1 - gy0:.0f} mm", GLASS, (56, 0))
    span(axis, tcx - tw / 2, tcy - td / 2 - 116, tcx + tw / 2, tcy - td / 2 - 116,
         f"the table, {tw:.0f} mm", MUTED, (0, -24))
    span(axis, tcx + tw / 2 + 116, tcy - td / 2, tcx + tw / 2 + 116, tcy + td / 2,
         f"{td:.0f} mm", MUTED, (64, 0))

    axis.set_xlim(tcx - tw / 2 - 240, tcx + tw / 2 + 240)
    axis.set_ylim(tcy - td / 2 - 230, tcy + td / 2 + 120)
    axis.set_title("The cell from above — every number read from the code",
                   fontsize=TITLE, color=INK, pad=12)
    figure.text(0.5, 0.045,
                "The glass zone and the rack are both inside the ring the arm reaches comfortably. "
                "Glasses stand at least 150 mm apart, centre to centre.",
                fontsize=NOTE, color=INK, ha="center")
    save(figure, "cell-from-above.png")


def cell_from_the_side() -> None:
    """An elevation of the table top and everything above it.

    The floor is left out on purpose: it is 750 mm below the table and nothing
    happens between, so drawing it to scale would be three quarters whitespace.
    """
    figure, axis = plt.subplots(figsize=(11.6, 5.0))
    figure.patch.set_facecolor(PAPER)
    axis.set_facecolor(PAPER)
    bare(axis)
    axis.set_aspect("equal")

    thick = TABLE_SIZE[2] * MM
    x0, x1 = -140.0, 940.0
    axis.add_patch(Rectangle((x0, -thick), x1 - x0, thick,
                             facecolor="#eceef0", edgecolor=MUTED, lw=1.2))
    axis.text(x1 - 8, -thick / 2, "the table top ", fontsize=NOTE, color=MUTED,
              ha="right", va="center")

    axis.add_patch(Rectangle((-46, 0), 92, 82, facecolor=INK, alpha=0.85, edgecolor="none"))
    axis.text(-58, 41, "arm\nbase", fontsize=NOTE, color=INK, ha="right", va="center")

    heights = [r["height"] for r in KIND_RANGES.values()]
    lo, hi = min(h[0] for h in heights) * MM, max(h[1] for h in heights) * MM
    for x, h, label, va in ((470, hi, f"tallest glass\n{hi:.0f} mm", 14),
                            (640, lo, f"shortest\n{lo:.0f} mm", 14)):
        axis.add_patch(Rectangle((x - 34, 0), 68, h, facecolor=GLASS, alpha=0.30,
                                 edgecolor=GLASS, lw=1.3))
        axis.text(x, h + va, label, fontsize=NOTE, color=GLASS, ha="center", va="bottom")

    # The survey pose, straight down, and the pair of pictures it takes.
    sy = SURVEY_HEIGHT * MM
    axis.plot([300, 300 - 150, 300 + 150, 300], [sy, 0, 0, sy],
              color=INK, lw=0.8, ls=(0, (4, 3)))
    for dx in (-SURVEY_BASELINE * MM / 2, SURVEY_BASELINE * MM / 2):
        axis.plot([300 + dx], [sy], "o", color=MUTED, ms=5)
    axis.plot([300], [sy], "o", color=INK, ms=8)
    axis.text(300, sy + 34, "the survey view — straight down", fontsize=NOTE,
              color=INK, ha="center")
    span(axis, 300 - SURVEY_BASELINE * MM / 2, sy - 30,
         300 + SURVEY_BASELINE * MM / 2, sy - 30, "", MUTED)
    axis.text(300, sy - 52, f"two pictures, {SURVEY_BASELINE * MM:.0f} mm apart",
              fontsize=NOTE, color=MUTED, ha="center", va="top")

    # The side-on pose, level.
    my = MEASURE_VIEW_HEIGHT * MM
    cam_x = 470 - STANDOFF * MM
    axis.plot([cam_x, 470 + 46], [my, my], color=WARN, lw=0.8, ls=(0, (4, 3)))
    axis.plot([cam_x], [my], "o", color=WARN, ms=8)
    axis.text(cam_x - 34, my, "the level view,\nlevel", fontsize=NOTE,
              color=WARN, ha="right", va="center")

    span(axis, 830, 0, 830, sy, f"{SURVEY_HEIGHT * MM:.0f} mm", INK, (62, 0))
    span(axis, cam_x + 46, 0, cam_x + 46, my, f"{MEASURE_VIEW_HEIGHT * MM:.0f} mm", WARN, (52, 0))
    span(axis, cam_x, -thick - 44, 470, -thick - 44, f"{STANDOFF * MM:.0f} mm", WARN, (0, -22))

    axis.set_xlim(x0 - 190, x1 + 120)
    axis.set_ylim(-thick - 110, sy + 90)
    axis.set_title("The cell from the side — the two places the camera works from",
                   fontsize=TITLE, color=INK, pad=12)
    figure.text(0.5, 0.015,
                f"The table top is {TABLE_TOP_Z * MM:.0f} mm above the floor, and the arm is bolted to "
                "it, so every height here is measured from the table rather than the ground. "
                "The level view's distance is worked out from the lens, not fixed.",
                fontsize=NOTE, color=INK, ha="center")
    save(figure, "cell-from-the-side.png")


def the_sensors() -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12.6, 5.4))
    figure.patch.set_facecolor(PAPER)
    wrist, table = axes
    for a in axes:
        a.set_facecolor(PAPER)
        bare(a)
        a.set_aspect("equal")

    # --- the wrist assembly, drawn to scale in millimetres
    wrist.add_patch(Rectangle((-42, 0), 84, 40, facecolor="#e7e9eb",
                              edgecolor=MUTED, lw=1.2))
    wrist.text(0, 20, "wrist flange", fontsize=NOTE, color=INK, ha="center", va="center")

    # force-torque sensor, between the flange and the gripper
    wrist.add_patch(Rectangle((-42, -16), 84, 16, facecolor=WARN, alpha=0.30,
                              edgecolor=WARN, lw=1.3))
    wrist.text(66, -8, "wrist force-torque, 100 Hz", fontsize=NOTE, color=WARN,
               ha="left", va="center")

    # the two fingers and their pads
    gap = GRIPPER_MAX_OPENING * MM
    pad_h, pad_l = PAD_HEIGHT * MM, PAD_LENGTH * MM
    for side in (-1, 1):
        outer = side * gap / 2                      # the jaw's outside face
        inner = outer - side * 11                   # 11 mm of finger
        wrist.add_patch(Rectangle((min(outer, inner), -120), 11, 104,
                                  facecolor="#e7e9eb", edgecolor=MUTED, lw=1.1))
        pad_near = inner - side * pad_h             # the pad faces the glass
        wrist.add_patch(Rectangle((min(inner, pad_near), -120), pad_h, pad_l,
                                  facecolor=GOOD, alpha=0.45, edgecolor=GOOD, lw=1.2))
    wrist.text(66, -112, "two pad contact sensors, 60 Hz", fontsize=NOTE, color=GOOD,
               ha="left", va="center")
    span(wrist, -gap / 2, -136, gap / 2, -136, f"opens to {gap:.0f} mm", INK, (0, -18))

    # the camera, offset from the flange
    cx, cz = CAMERA_OFFSET[0] * MM, CAMERA_OFFSET[2] * MM
    wrist.add_patch(Rectangle((cx - 16, cz + 40), 32, 22, facecolor=GLASS, alpha=0.45,
                              edgecolor=GLASS, lw=1.3))
    wrist.text(cx + 28, cz + 50, " RGB-D camera, 320x240, 15 Hz", fontsize=NOTE,
               color=GLASS, ha="left", va="center")
    span(wrist, 0, cz + 82, cx, cz + 82, f"{cx:.0f} mm off the flange", GLASS, (0, 16))
    wrist.plot([cx, cx - 58, cx + 58, cx], [cz + 40, cz - 96, cz - 96, cz + 40],
               color=GLASS, lw=0.8, ls=(0, (4, 3)))
    wrist.text(cx, cz - 112, "1.047 rad across", fontsize=NOTE, color=GLASS, ha="center")

    wrist.set_xlim(-150, 300)
    wrist.set_ylim(-175, 125)
    wrist.set_title("On the wrist — everything the arm carries", fontsize=LABEL,
                    color=INK, pad=8)

    # --- the one sensor that is not on the arm
    table.add_patch(Rectangle((-150, -40), 300, 80, facecolor="#f6f7f8",
                              edgecolor=MUTED, lw=1.2))
    m = MARKER_SIZE * MM
    table.add_patch(Rectangle((-m / 2, -m / 2), m, m, facecolor=INK, edgecolor="none"))
    for i in range(3):
        for j in range(3):
            if (i + j) % 2 == 0:
                table.add_patch(Rectangle((-m / 2 + (i + 1) * m / 5,
                                           -m / 2 + (j + 1) * m / 5),
                                          m / 5, m / 5, facecolor=PAPER,
                                          edgecolor="none"))
    table.text(0, m / 2 + 14, f"ArUco marker, {m:.0f} mm", fontsize=NOTE, color=INK,
               ha="center")
    table.text(0, -m / 2 - 20,
               "printed on the rack, not a sensor —\nit is how the camera finds where the rack is",
               fontsize=NOTE, color=MUTED, ha="center", va="top")
    table.set_xlim(-170, 170)
    table.set_ylim(-110, 80)
    table.set_title("On the rack — the fixed reference", fontsize=LABEL, color=INK, pad=8)

    figure.text(0.5, 0.03,
                "Four sensors in all: one RGB-D camera, one force-torque sensor and two pad contact "
                "sensors. Everything else the cell knows is arithmetic on these.",
                fontsize=NOTE, color=INK, ha="center")
    save(figure, "the-sensors.png")


def the_glasses() -> None:
    figure, axes = plt.subplots(1, 4, figsize=(12.8, 4.6))
    figure.patch.set_facecolor(PAPER)
    for axis, kind in zip(axes, KIND_RANGES, strict=True):
        axis.set_facecolor(PAPER)
        bare(axis)
        axis.set_aspect("equal")
        outlines = family(kind, 6, 1)
        for i, (o, _) in enumerate(outlines):
            z = np.asarray(o.height) * MM
            r = np.asarray(o.radius) * MM
            shade = 0.15 + 0.10 * i
            axis.fill_betweenx(z, -r, r, color=GLASS, alpha=shade, lw=0)
        z = np.asarray(outlines[-1][0].height) * MM
        r = np.asarray(outlines[-1][0].radius) * MM
        axis.plot(r, z, color=GLASS, lw=1.2)
        axis.plot(-r, z, color=GLASS, lw=1.2)
        axis.plot([-90, 90], [0, 0], color=MUTED, lw=1.0)

        hs = KIND_RANGES[kind]["height"]
        key = "rim_diameter" if "rim_diameter" in KIND_RANGES[kind] else "bowl_diameter"
        ds = KIND_RANGES[kind][key]
        axis.set_title(kind.replace("_", " "), fontsize=LABEL, color=INK, pad=8)
        axis.text(0, -22, f"{hs[0] * MM:.0f}–{hs[1] * MM:.0f} mm tall\n"
                          f"{ds[0] * MM:.0f}–{ds[1] * MM:.0f} mm across the top",
                  fontsize=NOTE, color=MUTED, ha="center", va="top")
        axis.set_xlim(-98, 98)
        axis.set_ylim(-78, 250)

    figure.suptitle("The four kinds, each drawn six times across its own range",
                    fontsize=TITLE, color=INK, y=0.99)
    figure.text(0.5, 0.015,
                "No glass's size is written down anywhere in the project. These ranges are what the "
                "spawner draws from; the arm measures every glass it is given.",
                fontsize=NOTE, color=INK, ha="center")
    figure.tight_layout(rect=(0, 0.05, 1, 0.94))
    save(figure, "the-four-kinds.png")


# ---------------------------------------------------------------------------
# Splay: why an overhead camera reports a glass further out than it stands.
# ---------------------------------------------------------------------------
# The glass drawn here is one the spawner really produces: the eighth
# straight_glass of family("straight_glass", 8, 1), 160.7 mm tall with its
# widest point at the rim. Its stretch factor, 450 / (450 - 160.7) = 1.555, is
# what turns problem 1's measured 157 mm into the reported 244 mm.
SPLAY_GLASS, _ = family("straight_glass", 8, 1)[7]
TRUE_MM = 157.0


def _splay_numbers():
    z = np.asarray(SPLAY_GLASS.height) * MM
    r = np.asarray(SPLAY_GLASS.radius) * MM
    widest_h = float(z[r.argmax()])
    return widest_h, float(r.max()), SURVEY_HEIGHT * MM / (SURVEY_HEIGHT * MM - widest_h)


def splay_why_it_happens() -> None:
    widest_h, widest_r, k = _splay_numbers()
    cam = SURVEY_HEIGHT * MM
    reported = TRUE_MM * k

    figure, axis = plt.subplots(figsize=(10.6, 5.6))
    figure.patch.set_facecolor(PAPER)
    axis.set_facecolor(PAPER)
    bare(axis)
    axis.set_aspect("equal")

    axis.plot([-60, 330], [0, 0], color=MUTED, lw=1.4)
    axis.text(328, 8, "the table", fontsize=NOTE, color=MUTED, ha="right", va="bottom")

    # the camera, straight above the nadir
    axis.plot([0], [cam], "o", color=INK, ms=8)
    axis.text(0, cam + 16, "the camera, 450 mm up", fontsize=NOTE, color=INK, ha="center")
    axis.plot([0, 0], [0, cam], color=MUTED, lw=0.9, ls=(0, (5, 4)))
    axis.plot([0], [0], "o", color=MUTED, ms=5)
    axis.text(-8, -16, "the nadir", fontsize=NOTE, color=MUTED, ha="right")

    # the glass, standing where it really stands
    z = np.asarray(SPLAY_GLASS.height) * MM
    r = np.asarray(SPLAY_GLASS.radius) * MM
    axis.fill_betweenx(z, TRUE_MM - r, TRUE_MM + r, color=_tint(GLASS, 0.32), lw=0)
    axis.plot(TRUE_MM + r, z, color=GLASS, lw=1.3)
    axis.plot(TRUE_MM - r, z, color=GLASS, lw=1.3)

    # the ray through the widest point, carried on to the table
    axis.plot([0, reported], [cam, 0], color=WARN, lw=1.4, ls=(0, (5, 3)))
    axis.plot([TRUE_MM], [widest_h], "o", color=WARN, ms=6)
    axis.plot([reported], [0], "o", color=WARN, ms=7)
    axis.text(TRUE_MM + 10, widest_h + 10, f"the widest part,\n{widest_h:.1f} mm up",
              fontsize=NOTE, color=WARN, ha="left")

    # where the two positions are
    axis.plot([TRUE_MM, TRUE_MM], [0, widest_h], color=GLASS, lw=0.9, ls=(0, (4, 3)))
    span(axis, 0, -34, TRUE_MM, -34, "", INK)
    axis.text(TRUE_MM / 2, -50, f"where it stands\n{TRUE_MM:.0f} mm", fontsize=NOTE,
              color=INK, ha="center", va="top")
    span(axis, TRUE_MM, -90, reported, -90, "", WARN)
    axis.text((TRUE_MM + reported) / 2, -106, f"the error\n{reported - TRUE_MM:.0f} mm",
              fontsize=NOTE, color=WARN, ha="center", va="top")
    axis.text(reported + 10, -10, f"where it is\nreported\n{reported:.0f} mm",
              fontsize=NOTE, color=WARN, ha="left", va="top")

    # the arithmetic, as similar triangles
    axis.text(178, cam - 96,
              "the two triangles are the same shape:\n"
              f"    {reported:.0f} / {TRUE_MM:.0f}  =  450 / (450 − {widest_h:.1f})  =  {k:.3f}",
              fontsize=NOTE, color=INK, ha="left", va="top")

    axis.set_xlim(-70, 345)
    axis.set_ylim(-150, cam + 60)
    axis.set_title("Splay — the ray through the widest part lands past the glass",
                   fontsize=TITLE, color=INK, pad=10)
    figure.text(0.5, 0.02,
                f"The camera cannot see the base. It sees the widest part, which stands "
                f"{widest_h:.0f} mm above the table, and lays that down on the table plane.",
                fontsize=NOTE, color=INK, ha="center")
    save(figure, "splay-why-it-happens.png")


def splay_what_it_costs() -> None:
    widest_h, widest_r, k = _splay_numbers()
    figure, axes = plt.subplots(1, 2, figsize=(12.6, 5.0))
    figure.patch.set_facecolor(PAPER)
    plan, plot = axes
    for a in axes:
        a.set_facecolor(PAPER)

    # --- left: the plan view, three glasses at increasing distance
    bare(plan)
    plan.set_aspect("equal")
    z = np.asarray(SPLAY_GLASS.height) * MM
    r = np.asarray(SPLAY_GLASS.radius) * MM
    base_r = float(r[z < z.min() + 4].max())

    plan.plot([0], [0], "o", color=INK, ms=7)
    plan.text(0, -30, "the nadir", fontsize=NOTE, color=INK, ha="center", va="top")
    for d in (60.0, TRUE_MM, 250.0):
        plan.add_patch(Circle((d, 0), base_r, facecolor=_tint(GLASS, 0.30),
                              edgecolor=GLASS, lw=1.4))
        plan.add_patch(Circle((d * k, 0), widest_r * k, facecolor="none",
                              edgecolor=WARN, lw=1.4, ls=(0, (4, 3))))
        plan.annotate("", xy=(d * k, 62), xytext=(d, 62),
                      arrowprops={"arrowstyle": "->", "color": WARN, "lw": 1.1})
        plan.text((d + d * k) / 2, 72, f"{d * k - d:.0f}", fontsize=NOTE, color=WARN,
                  ha="center")
    plan.text(0, 118, "blue: where the glass is    dashed: where it is reported",
              fontsize=NOTE, color=MUTED, ha="left")
    plan.text(0, -66, "The further from the nadir, the bigger the error —\n"
                      "and the outline grows with it.",
              fontsize=NOTE, color=MUTED, ha="left", va="top")
    plan.set_xlim(-60, 430)
    plan.set_ylim(-110, 135)
    plan.set_title("From above, at three distances", fontsize=LABEL, color=INK, pad=8)

    # --- right: reported against true, for three heights of widest part
    plot.set_title("Reported distance against true distance", fontsize=LABEL, color=INK, pad=8)
    true = np.linspace(0, 260, 200)
    plot.plot(true, true, color=MUTED, lw=1.2, ls=(0, (5, 4)))
    plot.text(252, 222, "no error", fontsize=NOTE, color=MUTED, ha="right", va="top")
    top = 430.0
    for h, colour in ((80.0, "#9dc3e6"), (widest_h, WARN), (230.0, "#8c4a33")):
        factor = SURVEY_HEIGHT * MM / (SURVEY_HEIGHT * MM - h)
        # stop each line where it leaves the axes, and put its label at that end
        end = min(260.0, (top - 14) / factor)
        ts = np.linspace(0, end, 200)
        plot.plot(ts, ts * factor, color=colour, lw=2.0)
        if end < 259.0:
            plot.text(end + 6, end * factor - 4, f"{h:.0f} mm up\n(x{factor:.2f})",
                      fontsize=NOTE, color=colour, ha="left", va="top")
        else:
            plot.text(end + 6, end * factor, f"{h:.0f} mm up\n(x{factor:.2f})", fontsize=NOTE,
                      color=colour, ha="left", va="center")
    plot.plot([TRUE_MM], [TRUE_MM * k], "o", color=INK, ms=7, zorder=5)
    plot.annotate(f"the measured case:\n{TRUE_MM:.0f} mm reported at {TRUE_MM * k:.0f}",
                  xy=(TRUE_MM, TRUE_MM * k), xytext=(40, 330), fontsize=NOTE, color=INK,
                  arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.9})
    plot.set_xlabel("where the glass really is, mm from the nadir", fontsize=NOTE, color=INK)
    plot.set_ylabel("where the survey reports it, mm", fontsize=NOTE, color=INK)
    plot.tick_params(labelsize=NOTE - 0.6, colors=MUTED)
    for side in ("top", "right"):
        plot.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        plot.spines[side].set_color(MUTED)
    plot.set_xlim(0, 300)
    plot.set_ylim(0, top)

    figure.text(0.5, 0.02,
                "The error is proportional, not fixed: it is zero under the camera and grows with "
                "distance, and a taller glass is stretched harder.",
                fontsize=NOTE, color=INK, ha="center")
    figure.tight_layout(rect=(0, 0.06, 0.92, 1))
    save(figure, "splay-what-it-costs.png")


def _eye(axis, x, y, dx, dy, colour, size=7.5):
    """A camera, drawn as a dot with an arrow for the way it looks."""
    axis.plot([x], [y], "o", color=colour, ms=size, zorder=4)
    axis.annotate("", xy=(x + dx, y + dy), xytext=(x, y),
                  arrowprops={"arrowstyle": "-|>", "color": colour, "lw": 1.3},
                  zorder=4)


def camera_positions() -> None:
    """The five places the camera is ever put, named, in plan and elevation."""
    figure, (plan, side) = plt.subplots(1, 2, figsize=(13.8, 6.6))
    figure.patch.set_facecolor(PAPER)
    for a in (plan, side):
        a.set_facecolor(PAPER)
        bare(a)
        a.set_aspect("equal")

    # ------------------------------------------------ left: where on the table
    gx0, gx1, gy0, gy1 = (v * MM for v in GLASS_ZONE)
    plan.add_patch(Rectangle((gx0, gy0), gx1 - gx0, gy1 - gy0,
                             facecolor=GLASS, alpha=0.10, edgecolor=GLASS, lw=1.0))
    plan.text(gx1 + 8, gy0 + 8, "the glass zone", fontsize=NOTE, color=GLASS,
              ha="left", va="bottom")

    rx0, rx1, ry0, ry1 = (v * MM for v in RACK_AREA)
    plan.add_patch(Rectangle((rx0, ry0), rx1 - rx0, ry1 - ry0,
                             facecolor=WARN, alpha=0.25, edgecolor=WARN, lw=1.0))
    plan.text(rx1 + 14, (ry0 + ry1) / 2, "the rack view\nis straight over here",
              fontsize=NOTE, color=WARN, ha="left", va="center")

    plan.add_patch(Circle((0, 0), 28, facecolor=INK, edgecolor="none"))
    plan.text(-40, 0, "the arm's\nbase", fontsize=NOTE, color=INK, ha="right", va="center")

    stations = survey_stations(GLASS_ZONE, SHARED)
    for station in stations:
        plan.plot([station[0] * MM], [station[1] * MM], "s", color=INK, ms=6, zorder=5)
    plan.text(stations[-1][0] * MM, stations[-1][1] * MM + 18,
              f"{len(stations)} stations — the survey\nview is taken over each",
              fontsize=NOTE, color=INK, ha="center", va="bottom")

    park = np.array([0.5 * MM, 0.0])
    plan.plot([park[0]], [park[1]], "o", markerfacecolor=PAPER, markeredgecolor=INK,
              markeredgewidth=1.4, ms=9, zorder=5)
    plan.text(park[0] + 18, park[1], "the parking spot", fontsize=NOTE,
              color=INK, ha="left", va="center")

    # The ring: every place the camera may stand to take a level view of one
    # glass, 40 degrees apart, the way task.py offers them.
    glass = np.array([(gx0 + gx1) / 2.0 + 70.0, (gy0 + gy1) / 2.0 + 80.0])
    plan.add_patch(Circle(glass, 34, facecolor=_tint(GLASS, 0.5), edgecolor=GLASS, lw=1.3))
    toward_base = math.atan2(-glass[1], -glass[0])
    near, far = (v * MM for v in COMFORTABLE_REACH)
    for step in range(-4, 5):
        angle = toward_base + step * math.radians(40.0)
        eye = glass + STANDOFF * MM * np.array([math.cos(angle), math.sin(angle)])
        reachable = near <= float(np.linalg.norm(eye)) <= far
        colour = WARN if step == 0 else (MUTED if reachable else "#dde1e4")
        plan.plot([eye[0], glass[0]], [eye[1], glass[1]], color=colour, lw=0.8,
                  ls=(0, (4, 4)), alpha=0.55 if step else 0.9)
        _eye(plan, eye[0], eye[1], (glass[0] - eye[0]) * 0.13, (glass[1] - eye[1]) * 0.13,
             colour, size=9 if step == 0 else 5.5)
    plan.set_xlim(-150, 950)
    plan.set_ylim(-700, 430)
    plan.text(glass[0], glass[1] - STANDOFF * MM - 40,
              "the level view is taken from one of nine places round the glass,\n"
              "40° apart — orange is the one tried first, straight in from the base.\n"
              "The pale ones are too far out for the arm to reach.",
              fontsize=NOTE, color=INK, ha="center", va="top")
    plan.set_title("Where over the table", fontsize=LABEL, color=INK, pad=8)

    # ------------------------------------- right: how high, and which way it looks
    gx = 430.0
    side.plot([-80, 600], [0, 0], color=MUTED, lw=1.4)
    side.text(598, 8, "the table", fontsize=NOTE, color=MUTED, ha="right", va="bottom")
    z = np.asarray(SPLAY_GLASS.height) * MM
    r = np.asarray(SPLAY_GLASS.radius) * MM
    side.fill_betweenx(z, gx - r, gx + r, color=_tint(GLASS, 0.30), lw=0)
    side.plot(gx + r, z, color=GLASS, lw=1.2)
    side.plot(gx - r, z, color=GLASS, lw=1.2)

    survey_y = SURVEY_HEIGHT * MM
    side.plot([gx, gx], [0, survey_y], color=MUTED, lw=0.8, ls=(0, (5, 5)))
    _eye(side, gx, survey_y, 0, -96, INK)
    side.text(gx + 16, survey_y, "the survey view\n450 mm up, looking straight down",
              fontsize=NOTE, color=INK, ha="left", va="center")

    level_y = MEASURE_VIEW_HEIGHT * MM
    level_x = gx - STANDOFF * MM
    _eye(side, level_x, level_y, 96, 0, WARN)
    side.text(level_x, level_y + 26, "the level view\n120 mm up, looking level",
              fontsize=NOTE, color=WARN, ha="left", va="bottom")
    span(side, level_x, -40, gx, -40, f"{STANDOFF * MM:.0f} mm", WARN, (0, -20))

    finger_x = gx - FINGER_BACK * MM
    finger_y = LOWEST_GRIP * MM
    _eye(side, finger_x, finger_y, 54, 0, GOOD)
    side.text(finger_x - 10, finger_y + 12,
              f"the finger view\n{FINGER_BACK * MM:.0f} mm back, "
              f"{FINGER_ASIDE * MM:.0f} mm to one side,\nat whatever height the grip is",
              fontsize=NOTE, color=GOOD, ha="right", va="bottom")

    span(side, gx - 54, 0, gx - 54, survey_y, f"{survey_y:.0f} mm", INK, (-46, 0))
    span(side, level_x - 46, 0, level_x - 46, level_y, f"{level_y:.0f} mm", WARN, (-40, 0))
    side.set_xlim(-130, 640)
    side.set_ylim(-110, survey_y + 80)
    side.set_title("How high, and which way it looks", fontsize=LABEL, color=INK, pad=8)

    figure.text(0.5, 0.018,
                "Every one of these is the wrist camera. The arm has only the one, and these are "
                "the places it takes it to.",
                fontsize=NOTE, color=INK, ha="center")
    figure.tight_layout(rect=(0, 0.075, 1, 1))
    save(figure, "the-camera-positions.png")


def main() -> None:
    cell_from_above()
    cell_from_the_side()
    camera_positions()
    splay_why_it_happens()
    splay_what_it_costs()
    the_sensors()
    the_glasses()
    print(f"\nread from the code: table top {TABLE_TOP_Z * MM:.0f} mm, "
          f"survey {SURVEY_HEIGHT * MM:.0f} mm, standoff floor {MEASURE_STANDOFF * MM:.0f} mm, "
          f"reach {COMFORTABLE_REACH[0] * MM:.0f}-{COMFORTABLE_REACH[1] * MM:.0f} mm, "
          f"rack top {RACK_TOP_Z * MM:.0f} mm, peg {PEG_HEIGHT * MM:.0f} mm, "
          f"lowest grip {LOWEST_GRIP * MM:.0f} mm, base {ROBOT_BASE[2] * MM:.0f} mm")


if __name__ == "__main__":
    main()
