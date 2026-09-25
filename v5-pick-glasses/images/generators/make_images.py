"""Draw the pictures in this folder.

Every picture here is made by running the project's own functions and plotting
what comes back. Nothing is drawn by hand and nothing is illustrative. If a
grip point moves in `rules.py`, it moves in the picture the next time this is
run, which is the only way a diagram stays true.

    python images/generators/make_images.py

Needs matplotlib, which is not a dependency of the project itself.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "work_cell"))

from work_cell.arm.dimensions import (  # noqa: E402
    COMFORTABLE_REACH,
    FINGERTIP_OFFSET,
    GRASP_DEPTH,
    GRIPPER_MAX_OPENING,
    LOWEST_GRIP,
    PAD_HEIGHT,
    PAD_LENGTH,
    PLACE_CLEARANCE,
    SLIP_TEST_DEG,
    SURVEY_HEIGHT,
    TURNING_ROOM,
)
from work_cell.glasses import spec  # noqa: E402
from work_cell.glasses.detect import (  # noqa: E402
    LEAN_BAND,
    SHORT_STEM_FRACTION,
    TAPER_THRESHOLD_DEG,
    classify,
    wall_lean_deg,
)
from work_cell.glasses.force import (  # noqa: E402
    estimate_mass,
    required_force,
    starting_force,
)
from work_cell.glasses.profile import profile_from_outline  # noqa: E402
from work_cell.glasses.rules import NoGrip, find_grip  # noqa: E402
from work_cell.glasses.shapes import draw, family  # noqa: E402
from work_cell.rack.layout import (  # noqa: E402
    ARM_TILT_ACCURACY_DEG,
    PEG_HEIGHT,
    PEG_RADIUS,
    RACK_BASE_HEIGHT,
    SLOT_SPACING,
    rack_box,
    slots_from_marker,
    tilt_budget_deg,
)
from work_cell.table.layout import ROBOT_BASE, TABLE_TOP_Z  # noqa: E402

IMAGES = ROOT / "images"
INK = "#1b1b1f"
GLASS = "#4a7fb5"
GRIP = "#c8553d"
FAINT = "#9aa0a6"


def _style(ax, title: str) -> None:
    ax.set_title(title, fontsize=10, color=INK, pad=8)
    ax.tick_params(labelsize=8, colors=INK)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(FAINT)


def _save(fig, name: str) -> None:
    IMAGES.mkdir(exist_ok=True)
    fig.savefig(IMAGES / name, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote images/{name}")


def _silhouette(ax, profile, colour=GLASS) -> None:
    """One glass, as the outline the camera sees, in millimetres."""
    half = profile.width * 500.0
    up = profile.height * 1000.0
    ax.plot(half, up, color=colour, linewidth=1.6)
    ax.plot(-half, up, color=colour, linewidth=1.6)
    ax.fill_betweenx(up, -half, half, color=colour, alpha=0.12)


# --------------------------------------------------------------------------
# 1. The four kinds, with the grip each rule picks


def four_kinds() -> None:
    kinds = ["straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass"]
    fig, axes = plt.subplots(1, 4, figsize=(11, 4.2))

    for ax, name in zip(axes, kinds, strict=True):
        outline, _ = draw(name, random.Random(4))
        profile = profile_from_outline(outline)
        grip = find_grip(profile, spec.kind(name), gripper_max_opening=GRIPPER_MAX_OPENING)

        _silhouette(ax, profile)

        # The grip, as the pads really sit: as tall as a pad, as far apart as
        # the measurement said.
        height = grip.height * 1000.0
        opening = grip.opening * 1000.0
        pad = PAD_HEIGHT * 1000.0
        for side in (-1, 1):
            ax.add_patch(
                plt.Rectangle(
                    (side * opening / 2.0, height - pad / 2.0),
                    side * 4.0,
                    pad,
                    color=GRIP,
                )
            )
        # Off to the side and above, so it never lands on the axis label or
        # on the glass.
        ax.annotate(
            f"{opening:.0f} mm apart\n{height:.0f} mm up",
            xy=(opening / 2.0, height),
            xytext=(22, max(height + 26, 40)),
            fontsize=8,
            color=GRIP,
            arrowprops={"arrowstyle": "->", "color": GRIP, "linewidth": 0.8},
        )

        _style(ax, f"{name.replace('_', ' ')}\n{spec.kind(name).grip_rule}")
        ax.set_xlim(-70, 78)
        ax.set_ylim(0, 185)
        ax.set_aspect("equal")
        ax.set_xlabel("mm across", fontsize=8)

    axes[0].set_ylabel("mm up the glass", fontsize=8)
    fig.suptitle(
        "One rule per kind, applied to a measured profile. "
        "Every number on this picture was measured, not looked up.",
        fontsize=9,
        color=INK,
    )
    _save(fig, "grip-per-kind.png")


# --------------------------------------------------------------------------
# 2. Why the sizes cannot be written down


def a_family_of_wine_glasses() -> None:
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4.4))

    # Side by side, like a shelf. Overlaid they are a tangle; standing in a row
    # the differences in height, bowl and stem are the whole point.
    shelf = family("stemmed_glass", count=8, seed=1)
    step = 95.0
    for index, (outline, _) in enumerate(shelf):
        profile = profile_from_outline(outline)
        centre = index * step

        half = profile.width * 500.0
        up = profile.height * 1000.0
        left.plot(centre + half, up, color=GLASS, linewidth=1.2)
        left.plot(centre - half, up, color=GLASS, linewidth=1.2)
        left.fill_betweenx(up, centre - half, centre + half, color=GLASS, alpha=0.14)

        grip = find_grip(
            profile, spec.kind("stemmed_glass"), gripper_max_opening=GRIPPER_MAX_OPENING
        )
        left.plot(
            [centre - 22, centre + 22],
            [grip.height * 1000.0] * 2,
            color=GRIP,
            linewidth=1.8,
        )

    _style(left, "Eight wine glasses, all called the same thing")
    left.set_xlim(-55, (len(shelf) - 1) * step + 55)
    left.set_ylim(0, 240)
    left.set_aspect("equal")
    left.set_xticks([])
    left.set_ylabel("mm up the glass", fontsize=8)
    left.text(
        0.5,
        0.97,
        "the red mark is where the rule says to hold it",
        transform=left.transAxes,
        ha="center",
        va="top",
        fontsize=8,
        color=GRIP,
    )

    # The same twelve, as the two numbers a lookup table would have to hold.
    heights, grips = [], []
    for outline, _ in family("stemmed_glass", count=60, seed=1):
        profile = profile_from_outline(outline)
        try:
            grip = find_grip(
                profile, spec.kind("stemmed_glass"), gripper_max_opening=GRIPPER_MAX_OPENING
            )
        except NoGrip:
            continue
        heights.append(profile.total_height * 1000.0)
        grips.append(grip.height * 1000.0)

    right.scatter(heights, grips, s=14, color=GLASS, alpha=0.75)
    _style(right, "Where the stem is, against how tall the glass is")
    right.set_xlabel("glass height, mm", fontsize=8)
    right.set_ylabel("grip height, mm", fontsize=8)
    right.text(
        0.04,
        0.94,
        "A lookup table needs one row per glass.\n"
        "The rule needs one line, and covers all of them.",
        transform=right.transAxes,
        fontsize=8,
        va="top",
        color=INK,
    )
    _save(fig, "why-rules-not-sizes.png")


# --------------------------------------------------------------------------
# 3. The features a rule reads off a profile


def features_of_a_profile() -> None:
    outline, _ = draw("stemmed_glass", random.Random(4))
    profile = profile_from_outline(outline)
    kind = spec.kind("stemmed_glass")
    grip = find_grip(profile, kind, gripper_max_opening=GRIPPER_MAX_OPENING)

    fig, (shape, width) = plt.subplots(1, 2, figsize=(10, 4.6))

    _silhouette(shape, profile)
    widest = profile.widest_at * 1000.0
    waist = profile.waist_at() * 1000.0
    low, high = (v * 1000.0 for v in kind.band_for(profile.total_height))

    shape.axhspan(low, high, color=FAINT, alpha=0.18)
    shape.text(48, (low + high) / 2, "where the\nrule looks", fontsize=8, color=INK, va="center")
    for value, label, colour in ((widest, "widest", GLASS), (waist, "waist = the grip", GRIP)):
        shape.axhline(value, color=colour, linestyle="--", linewidth=1.0)
        shape.text(-58, value + 3, label, fontsize=8, color=colour)

    _style(shape, "The glass, and the two features the rule needs")
    shape.set_xlim(-60, 60)
    shape.set_ylim(0, 200)
    shape.set_aspect("equal")
    shape.set_ylabel("mm up the glass", fontsize=8)

    width.plot(profile.width * 1000.0, profile.height * 1000.0, color=GLASS, linewidth=1.6)
    width.axhline(widest, color=GLASS, linestyle="--", linewidth=1.0)
    width.axhline(waist, color=GRIP, linestyle="--", linewidth=1.0)
    width.plot(grip.opening * 1000.0, grip.height * 1000.0, "o", color=GRIP, markersize=6)
    width.annotate(
        f"the fingers are set to {grip.opening * 1000:.0f} mm\n"
        "because that is what the camera\nmeasured at this height",
        xy=(grip.opening * 1000.0, grip.height * 1000.0),
        xytext=(34, 22),
        fontsize=8,
        color=GRIP,
        arrowprops={"arrowstyle": "->", "color": GRIP, "linewidth": 0.9},
    )
    _style(width, "The same glass as a width for every height")
    width.set_xlabel("width, mm", fontsize=8)
    width.set_xlim(0, 100)
    width.set_ylim(0, 200)
    _save(fig, "profile-to-grip.png")


# --------------------------------------------------------------------------
# 4. Why the weight has to be measured


# Wall thickness is invisible from outside, so the estimate from the outline is
# wrong by roughly this much either way. It is the reason the glass gets weighed.
ESTIMATE_ERROR = 0.35


def the_estimate_is_not_enough() -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.6))

    kind = spec.kind("stemmed_glass")
    guessed, starting, low, high = [], [], [], []
    for outline, _ in family("stemmed_glass", count=30, seed=2):
        profile = profile_from_outline(outline)
        mass = estimate_mass(profile, kind)
        guessed.append(mass * 1000.0)
        starting.append(starting_force(profile, kind))
        low.append(required_force(mass * (1.0 - ESTIMATE_ERROR)))
        high.append(required_force(mass * (1.0 + ESTIMATE_ERROR)))

    order = np.argsort(guessed)
    guessed = np.array(guessed)[order]
    starting = np.array(starting)[order]
    low = np.array(low)[order]
    high = np.array(high)[order]

    ax.fill_between(
        guessed,
        low,
        high,
        color=GLASS,
        alpha=0.18,
        label=f"what it might really need (mass +/- {ESTIMATE_ERROR:.0%})",
    )
    ax.plot(guessed, starting, color=GLASS, linewidth=1.6, label="the squeeze the arm starts with")

    ax.axhline(kind.force_cap_n, color=GRIP, linewidth=1.2)
    ax.text(
        guessed[-1],
        kind.force_cap_n - 0.3,
        f"cap for a thin-walled glass: {kind.force_cap_n:.0f} N — above this it is refused",
        ha="right",
        va="top",
        fontsize=8,
        color=GRIP,
    )

    _style(ax, "Why the glass is weighed rather than trusted")
    ax.set_xlabel("estimated mass from the measured outline, g", fontsize=8)
    ax.set_ylabel("grip force, N", fontsize=8)
    ax.text(
        0.03,
        0.78,
        "The line is what the outline suggests.\n"
        "The band is where the answer really is, because\n"
        "wall thickness cannot be seen. Ten millimetres\n"
        "of lift on the wrist sensor collapses the band\n"
        "to a point.",
        transform=ax.transAxes,
        fontsize=8,
        va="top",
        color=INK,
    )
    ax.set_ylim(0, kind.force_cap_n + 1.2)
    ax.legend(fontsize=8, frameon=False, loc="lower right")
    _save(fig, "force-from-mass.png")


# --------------------------------------------------------------------------
# 5. The tilt budget, which decides whether a slot is enough


def tilt_budget() -> None:
    fig, ax = plt.subplots(figsize=(7, 4.4))
    heights = np.linspace(0.06, 0.26, 120)

    for width_mm, colour in ((60, GLASS), (75, "#6aa84f"), (90, GRIP)):
        budget = [tilt_budget_deg(width_mm / 1000.0, h) for h in heights]
        ax.plot(heights * 1000.0, budget, color=colour, linewidth=1.6, label=f"{width_mm} mm wide")

        doubled = [tilt_budget_deg(width_mm / 1000.0, h, spacing=2 * SLOT_SPACING) for h in heights]
        ax.plot(heights * 1000.0, doubled, color=colour, linewidth=1.0, linestyle=":")

    ax.axhline(ARM_TILT_ACCURACY_DEG, color=INK, linewidth=1.0)
    ax.text(
        62,
        ARM_TILT_ACCURACY_DEG + 0.4,
        f"what the arm can hold: {ARM_TILT_ACCURACY_DEG:.0f} deg",
        fontsize=8,
        color=INK,
    )

    _style(ax, "How much a glass may lean going into a slot")
    ax.set_xlabel("glass height, mm", fontsize=8)
    ax.set_ylabel("tilt budget, degrees", fontsize=8)
    ax.set_ylim(0, 32)
    ax.legend(
        fontsize=8,
        frameon=False,
        loc="upper right",
        title="solid: own slot   dotted: neighbour left empty",
    )
    ax.get_legend().get_title().set_fontsize(8)
    _save(fig, "tilt-budget.png")


# --------------------------------------------------------------------------
# 6. Classifying from the profile


def classification() -> None:
    fig, ax = plt.subplots(figsize=(7, 4.6))

    markers = {
        "straight_glass": "o",
        "tapered_glass": "s",
        "stemmed_glass": "^",
        "short_stemmed_glass": "D",
    }
    colours = {
        "straight_glass": GLASS,
        "tapered_glass": "#6aa84f",
        "stemmed_glass": GRIP,
        "short_stemmed_glass": "#8e7cc3",
    }

    for made_as in markers:
        for outline, _ in family(made_as, count=30, seed=5):
            profile = profile_from_outline(outline)
            called = classify(profile)
            if called is None:
                continue
            waist = profile.waist_at()
            fraction = 0.0 if waist is None else waist / profile.total_height
            lean = wall_lean_deg(profile)
            if lean is None:
                continue
            ax.scatter(
                lean,
                fraction,
                marker=markers[made_as],
                s=18,
                color=colours[called],
                alpha=0.75,
            )

    ax.axhline(SHORT_STEM_FRACTION, color=INK, linestyle="--", linewidth=1.0)
    ax.text(
        0.35,
        0.97,
        f"a waist above this line is a long stem,\nbelow it a short one ({SHORT_STEM_FRACTION})",
        transform=ax.transAxes,
        va="top",
        fontsize=8,
        color=INK,
    )
    ax.axvline(TAPER_THRESHOLD_DEG, color=INK, linestyle=":", linewidth=1.0)
    ax.text(
        0.42,
        0.20,
        "no waist at all, so the question is the lean:\n"
        f"upright to the left, tapered to the right ({TAPER_THRESHOLD_DEG:.0f} deg)",
        transform=ax.transAxes,
        fontsize=8,
        color=INK,
    )

    _style(ax, "Marker shape is how the glass was made; colour is what it was called")
    ax.set_xlabel("median lean of the lower wall, degrees", fontsize=8)
    ax.set_ylabel("waist height / glass height (0 = no waist)", fontsize=8)
    _save(fig, "classify-from-profile.png")


KIND_ORDER = ["straight_glass", "tapered_glass", "stemmed_glass", "short_stemmed_glass"]


def _a_glass_called(name: str):
    """The first generated glass of this kind that classify() also calls this kind.

    The picture is about how a kind is read off a profile, so it shows glasses
    the classifier reads correctly. The boundary cases are the scatter plot's
    job.
    """
    for seed in range(4, 200):
        outline, _ = draw(name, random.Random(seed))
        profile = profile_from_outline(outline)
        if classify(profile) == name:
            return profile
    raise RuntimeError(f"no generated {name} is called a {name}")


def three_questions() -> None:
    """The classifier as a flowchart, with the thresholds it really uses."""
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    question = {"boxstyle": "round,pad=0.5", "facecolor": "#eef3f8", "edgecolor": GLASS}
    answer = {"boxstyle": "round,pad=0.5", "facecolor": "#fbeee9", "edgecolor": GRIP}
    start = {"boxstyle": "round,pad=0.5", "facecolor": "white", "edgecolor": FAINT}

    boxes = {
        "start": (5.0, 9.3, "The measured profile\n(a width at every height)", start),
        "waist": (
            5.0,
            7.3,
            "1. Is there a waist?\nA narrow part with wider glass\nabove it and below it",
            question,
        ),
        "low": (
            2.3,
            4.6,
            f"2. Is the waist lower than\n{SHORT_STEM_FRACTION:.0%} of the glass's height?",
            question,
        ),
        "lean": (
            7.7,
            4.6,
            f"3. Does the lower wall lean\nmore than {TAPER_THRESHOLD_DEG:.0f} degrees?",
            question,
        ),
        "short": (1.1, 1.3, "short-stemmed\nglass", answer),
        "stemmed": (3.5, 1.3, "stemmed glass\n(wine glass)", answer),
        "tapered": (6.5, 1.3, "tapered\nglass", answer),
        "straight": (8.9, 1.3, "straight glass\n(tumbler)", answer),
    }
    for x, y, text, style in boxes.values():
        ax.text(x, y, text, ha="center", va="center", fontsize=9, color=INK, bbox=style)

    arrows = [
        ("start", "waist", ""),
        ("waist", "low", "yes"),
        ("waist", "lean", "no"),
        ("low", "short", "yes"),
        ("low", "stemmed", "no"),
        ("lean", "tapered", "yes"),
        ("lean", "straight", "no"),
    ]
    for source, target, label in arrows:
        x0, y0 = boxes[source][:2]
        x1, y1 = boxes[target][:2]
        ax.annotate(
            "",
            xy=(x1, y1 + 0.75),
            xytext=(x0, y0 - 0.8),
            arrowprops={"arrowstyle": "->", "color": INK, "linewidth": 1.0},
        )
        if label:
            ax.text((x0 + x1) / 2 + 0.15, (y0 + y1) / 2 + 0.1, label, fontsize=9, color=INK)

    ax.text(
        5.0,
        -0.2,
        "If there is too little glass to measure a lean, there is no answer, "
        "and the glass is left standing.",
        ha="center",
        fontsize=8,
        color=FAINT,
    )
    _save(fig, "three-questions.png")


# Where the labels go in the outline panels: clear of the widest glass drawn.
LABEL_X = 45


def four_kinds_named() -> None:
    """One glass of each kind, as an outline and as a profile, with the numbers that name it."""
    fig, axes = plt.subplots(2, 4, figsize=(12, 7.4))

    for column, name in enumerate(KIND_ORDER):
        profile = _a_glass_called(name)
        tall = profile.total_height * 1000.0
        waist = profile.waist_at()
        widest = profile.widest_at * 1000.0
        shape, curve = axes[0, column], axes[1, column]

        _silhouette(shape, profile)
        curve.plot(profile.width * 1000.0, profile.height * 1000.0, color=GLASS, linewidth=1.6)
        curve.plot(profile.width_at(profile.widest_at) * 1000.0, widest, "o", color=GLASS)
        curve.annotate("widest", (profile.width_at(profile.widest_at) * 1000.0, widest),
                       xytext=(-40, 6), textcoords="offset points", fontsize=8, color=GLASS)

        if waist is not None:
            up = waist * 1000.0
            share = waist / profile.total_height
            line = SHORT_STEM_FRACTION * tall
            for ax in (shape, curve):
                ax.axhline(up, color=GRIP, linewidth=1.2)
                ax.axhline(line, color=INK, linestyle="--", linewidth=0.8)
            # Labels to the right of the glass, the higher one above its line
            # and the lower one below, so two close lines never share a label.
            above, below = (up, line) if up > line else (line, up)
            for value, offset in ((above, 3), (below, -11)):
                is_waist = value == up
                shape.text(
                    LABEL_X,
                    value + offset,
                    f"waist, {share:.0%} up" if is_waist else f"the {SHORT_STEM_FRACTION:.0%} line",
                    fontsize=8,
                    color=GRIP if is_waist else INK,
                )
            curve.plot(profile.width_at(waist) * 1000.0, up, "o", color=GRIP)
            side = "below" if share < SHORT_STEM_FRACTION else "above"
            verdict = (
                f"a waist, {share:.0%} up the glass:\n"
                f"{side} the {SHORT_STEM_FRACTION:.0%} line"
            )
        else:
            lean = wall_lean_deg(profile)
            low, high = (fraction * tall for fraction in LEAN_BAND)
            for ax in (shape, curve):
                ax.axhspan(low, high, color=FAINT, alpha=0.25)
            shape.text(
                LABEL_X,
                (low + high) / 2,
                f"lean measured\nhere: {lean:.1f}°",
                fontsize=8,
                color=INK,
                va="center",
            )
            side = "more" if lean > TAPER_THRESHOLD_DEG else "less"
            verdict = (
                f"no waist; the lower wall\nleans {lean:.1f} degrees, "
                f"{side} than {TAPER_THRESHOLD_DEG:.0f}"
            )

        _style(shape, name.replace("_", " "))
        shape.set_xlim(-60, 110)
        shape.set_ylim(0, 200)
        shape.set_aspect("equal")
        shape.set_xlabel("mm across", fontsize=8)

        _style(curve, "")
        curve.set_xlim(0, 100)
        curve.set_ylim(0, 200)
        curve.set_xlabel(f"width, mm\n\n{verdict}", fontsize=8, color=INK)

    axes[0, 0].set_ylabel("the glass\n\nmm up", fontsize=8)
    axes[1, 0].set_ylabel("its profile: width at each height\n\nmm up", fontsize=8)
    fig.suptitle(
        "Top: the glass the camera saw. Bottom: the same glass as a width at every height. "
        "The marks are the numbers classify() decides on.",
        fontsize=9,
        color=INK,
    )
    fig.tight_layout()
    _save(fig, "four-kinds-named.png")


# --- what went wrong, and what was done about it -------------------------


def laying_a_glass_on_the_table() -> None:
    """Why one look from above puts a glass further away than it is."""
    height, camera = 0.151, SURVEY_HEIGHT
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6))

    for ax, pair in zip(axes, (False, True), strict=True):
        ax.plot([-0.05, 0.46], [0, 0], color=INK, lw=1.4)
        ax.text(-0.04, 0.008, "table", fontsize=7, color=INK, ha="left")

        glass = 0.24
        ax.add_patch(plt.Rectangle((glass - 0.031, 0), 0.062, height, facecolor=GLASS, alpha=0.30))
        ax.plot([glass, glass], [0, height], color=GLASS, lw=1.0)
        ax.text(
            glass, height + 0.012, "where it\nreally stands",
            fontsize=7, color=GLASS, ha="center",
        )

        eyes = [0.03] if not pair else [0.03, 0.12]
        eyes_fell: list[float] = []
        for index, eye in enumerate(eyes):
            ax.plot([eye], [camera], marker="v", color=INK, ms=7)
            # The ray that grazes the top of the glass, carried on to the table.
            fell = eye + (glass - eye) * camera / (camera - height)
            eyes_fell.append(fell)
            ax.plot([eye, fell], [camera, 0], color=GRIP, lw=1.0, ls="--")
            ax.plot([fell], [0], marker="o", color=GRIP, ms=5)
            if index == 0:
                ax.text(fell, -0.022, "where one look\nputs it", fontsize=7, color=GRIP, ha="center")

        if pair:
            ax.annotate(
                "", xy=(0.12, camera + 0.03), xytext=(0.03, camera + 0.03),
                arrowprops={"arrowstyle": "<->", "color": INK, "lw": 1.0},
            )
            ax.text(0.075, camera + 0.050, "a known step sideways", fontsize=7, color=INK, ha="center")
            ax.annotate(
                "", xy=(fell, -0.048), xytext=(eyes_fell[0], -0.048),
                arrowprops={"arrowstyle": "<->", "color": GRIP, "lw": 1.0},
            )
            ax.text(
                (eyes_fell[0] + fell) / 2, -0.062,
                "how far the mark moved",
                fontsize=7, color=GRIP, ha="center", va="top",
            )

        ax.set_xlim(-0.05, 0.50)
        ax.set_ylim(-0.11, camera + 0.10)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(
            "One look: too far out" if not pair else "Two looks: right place",
            fontsize=10, color=INK,
        )

    _save(fig, "one-look-two-looks.png")


def the_gripper_has_a_body() -> None:
    """Why a glass cannot be held close to the table."""
    body = 0.09
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.4))

    for ax, hold in zip(axes, (0.018, LOWEST_GRIP), strict=True):
        ax.plot([-0.02, 0.30], [0, 0], color=INK, lw=1.6)
        ax.add_patch(plt.Rectangle((0.20, 0), 0.062, 0.16, facecolor=GLASS, alpha=0.30))

        # The gripper comes in level, so its body sits across the grip height.
        clashes = hold - body / 2 < 0
        ax.add_patch(
            plt.Rectangle(
                (0.03, hold - body / 2), body, body,
                facecolor=GRIP if clashes else FAINT, alpha=0.35,
            )
        )
        ax.plot([0.03 + body, 0.20], [hold, hold], color=INK, lw=2.0)
        ax.text(0.155, hold + 0.008, "fingers", fontsize=7, color=INK, ha="center")
        ax.text(0.075, hold, "body", fontsize=7, color=INK, ha="center", va="center")

        ax.annotate(
            "", xy=(0.19, 0), xytext=(0.19, hold),
            arrowprops={"arrowstyle": "<->", "color": INK, "lw": 0.8},
        )
        ax.text(0.185, hold / 2, f"{hold * 1000:.0f} mm", fontsize=7, color=INK, ha="right", va="center")

        ax.set_xlim(-0.02, 0.30)
        ax.set_ylim(-0.06, 0.20)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(
            "Held too low: the body is through the table" if clashes
            else f"Held at {LOWEST_GRIP * 1000:.0f} mm: the body clears it",
            fontsize=10, color=GRIP if clashes else INK,
        )

    _save(fig, "the-gripper-has-a-body.png")


def the_rack_the_planner_saw() -> None:
    """The rack, and the box that was standing in for it."""
    marker = np.array([0.35, 0.355, TABLE_TOP_Z])
    slots = slots_from_marker(marker, np.pi / 2)
    centre, size, turned = rack_box(slots)

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.0))
    for ax, correct in zip(axes, (False, True), strict=True):
        for slot in slots:
            ax.plot([slot.centre[0]], [slot.centre[1]], marker="o", color=GLASS, ms=6)
        ax.plot(
            [slots[0].centre[0], slots[-1].centre[0]],
            [slots[0].centre[1], slots[-1].centre[1]],
            color=GLASS, lw=2.0, label="the rack, and its six slots",
        )

        if correct:
            corners = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]], dtype=float)
            corners = corners * np.array([size[0] / 2, size[1] / 2])
            drawn = (turned[:2, :2] @ corners.T).T + centre[:2]
        else:
            # What it used to be: the row's length laid out along y.
            half = np.array([SLOT_SPACING / 2, size[1] / 2])
            corners = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]], dtype=float) * half
            drawn = corners + centre[:2]

        ax.plot(drawn[:, 0], drawn[:, 1], color=INK if correct else GRIP, lw=1.4, ls="--",
                label="what the planner was told")
        ax.plot([ROBOT_BASE[0]], [ROBOT_BASE[1]], marker="s", color=INK, ms=7)
        ax.text(ROBOT_BASE[0], ROBOT_BASE[1] - 0.05, "arm", fontsize=7, color=INK, ha="center")

        ax.set_xlim(-0.15, 0.85)
        ax.set_ylim(-0.25, 0.75)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.legend(fontsize=7, loc="lower right", frameon=False)
        ax.set_title(
            "A slab across open table, at right angles to the rack" if not correct
            else "The box now lies along the row",
            fontsize=10, color=GRIP if not correct else INK,
        )

    _save(fig, "the-rack-the-planner-saw.png")


def which_way_is_down() -> None:
    """Why the wrist said every glass weighed nothing."""
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.plot([-0.05, 0.34], [0, 0], color=INK, lw=1.6)
    ax.add_patch(plt.Rectangle((0.22, 0), 0.062, 0.16, facecolor=GLASS, alpha=0.30))

    hold = 0.09
    ax.add_patch(plt.Rectangle((0.03, hold - 0.045), 0.09, 0.09, facecolor=FAINT, alpha=0.35))
    ax.plot([0.12, 0.22], [hold, hold], color=INK, lw=2.0)

    ax.annotate("", xy=(0.20, hold), xytext=(0.07, hold),
                arrowprops={"arrowstyle": "->", "color": GRIP, "lw": 1.6})
    ax.text(0.135, hold + 0.012, "the axis the gripper reaches along —\nthis is what was being read",
            fontsize=7, color=GRIP, ha="center")

    ax.annotate("", xy=(0.075, hold - 0.075), xytext=(0.075, hold - 0.005),
                arrowprops={"arrowstyle": "->", "color": INK, "lw": 1.6})
    ax.text(0.085, hold - 0.045, "the weight goes this way", fontsize=7, color=INK, va="center")

    ax.set_xlim(-0.05, 0.34)
    ax.set_ylim(-0.06, 0.22)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Reaching in level, the gripper's own axis carries none of the weight",
                 fontsize=10, color=INK)
    _save(fig, "which-way-is-down.png")


def the_turn_swings_the_arm() -> None:
    """Why where a glass is turned over decides whether it can be."""
    low, high = COMFORTABLE_REACH
    fig, ax = plt.subplots(figsize=(6.4, 4.2))

    for radius, label in ((low, "as close as it works"), (high, "as far as it reaches")):
        circle = plt.Circle((0, 0), radius, fill=False, color=FAINT, ls="--", lw=1.0)
        ax.add_patch(circle)
        ax.text(radius * 0.72, -radius * 0.72, label, fontsize=7, color=FAINT)

    parked = (
        (0.45, GRIP, "tool parked at 450 mm"),
        (TURNING_ROOM[0], GLASS, "glass parked at 500 mm"),
    )
    for glass_out, colour, name in parked:
        if colour is GRIP:
            grip_at = glass_out + FINGERTIP_OFFSET  # the old way: the tool was placed
            before, after = glass_out, glass_out + 2 * FINGERTIP_OFFSET
        else:
            grip_at = glass_out
            before, after = glass_out - FINGERTIP_OFFSET, glass_out + FINGERTIP_OFFSET
        y = -0.06 if colour is GRIP else 0.06
        ax.plot([before, after], [y, y], color=colour, lw=1.6)
        ax.plot([before, after], [y, y], marker="o", color=colour, ms=5, ls="none")
        ax.plot([grip_at], [y], marker="*", color=colour, ms=11)
        ax.text(after + 0.02, y, f"{after * 1000:.0f} mm" + ("  — past the arm" if after > high else ""),
                fontsize=7, color=colour, va="center")
        ax.text(before - 0.02, y, name, fontsize=7, color=colour, va="center", ha="right")

    ax.plot([0], [0], marker="s", color=INK, ms=8)
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.30, 0.30)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("A turn swings the tool a fingertip's length either side of the glass (star)",
                 fontsize=10, color=INK)
    _save(fig, "the-turn-swings-the-arm.png")


# --------------------------------------------------------------------------
# Step 6 approaches: why a held glass swings, and ways to turn it over


def _gripped(name: str, seed: int = 4):
    """A generated glass of this kind, and where the rules would hold it."""
    outline, _ = draw(name, random.Random(seed))
    profile = profile_from_outline(outline)
    grip = find_grip(profile, spec.kind(name), gripper_max_opening=GRIPPER_MAX_OPENING)
    return profile, grip


def _centre_of_mass(profile) -> float:
    """Height of the centre of mass, in metres, for an even wall and a solid base.

    The same shell that estimate_mass() weighs: the wall swept up the outline,
    plus a disc for the base. The thickness is the same everywhere, so it
    cancels. It is the estimate "from the outline" the doc talks about, and it
    is wrong by as much as a real glass's base is thicker than its wall.
    """
    radius = profile.width / 2.0
    ring = 2.0 * np.pi * radius
    wall = float(np.trapezoid(ring, profile.height))
    moment = float(np.trapezoid(ring * profile.height, profile.height))
    base = float(np.pi * radius[0] ** 2)
    return moment / (wall + base)


def _outline_polygon(profile) -> np.ndarray:
    """The side-on outline as a closed polygon, in millimetres, x across and y up."""
    half = profile.width * 500.0
    up = profile.height * 1000.0
    right = np.column_stack([half, up])
    left = np.column_stack([-half[::-1], up[::-1]])
    return np.vstack([right, left])


def _turned(points: np.ndarray, angle_deg: float, about: tuple[float, float]) -> np.ndarray:
    a = math.radians(angle_deg)
    turn = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    centre = np.asarray(about)
    return (points - centre) @ turn.T + centre


def _curved_arrow(ax, centre, radius, start_deg, end_deg, colour=INK) -> None:
    angles = np.radians(np.linspace(start_deg, end_deg, 40))
    xs = centre[0] + radius * np.cos(angles)
    ys = centre[1] + radius * np.sin(angles)
    ax.plot(xs[:-1], ys[:-1], color=colour, linewidth=1.3)
    ax.annotate("", xy=(xs[-1], ys[-1]), xytext=(xs[-3], ys[-3]),
                arrowprops={"arrowstyle": "->", "color": colour, "linewidth": 1.3})


def the_hinge() -> None:
    profile, grip = _gripped("straight_glass")
    r = grip.opening * 500.0
    g = grip.height * 1000.0
    pad_t = 4.0
    pad_h = PAD_HEIGHT * 1000.0
    pad_l = PAD_LENGTH * 1000.0
    tip = (FINGERTIP_OFFSET - GRASP_DEPTH) * 1000.0

    fig, (top, strong, weak) = plt.subplots(1, 3, figsize=(13, 4.8))

    # Seen from above: the glass is a circle, each flat pad meets it at a point.
    top.add_patch(plt.Circle((0, 0), r, color=GLASS, alpha=0.15))
    top.add_patch(plt.Circle((0, 0), r, fill=False, color=GLASS, linewidth=1.6))
    for side in (-1, 1):
        top.add_patch(plt.Rectangle((tip - pad_l, side * r if side > 0 else -r - pad_t),
                                    pad_l, pad_t, color=INK))
        top.add_patch(plt.Rectangle((-95, side * (r + pad_t) if side > 0 else -r - pad_t - 8),
                                    95 + tip, 8, color=FAINT, alpha=0.6))
        top.plot(0, side * r, "o", color=GRIP, markersize=7)
    top.plot([0, 0], [-r - 25, r + 25], color=GRIP, linestyle="--", linewidth=1.2)
    top.text(3, r + 18, "hinge: the line\nbetween the pads", fontsize=8, color=GRIP)
    top.annotate("", xy=(r + 30, -r - 20), xytext=(-90, -r - 20),
                 arrowprops={"arrowstyle": "->", "color": INK})
    top.text(-90, -r - 32, "the fingers reach along this line;\nthe wrist turns about it",
             fontsize=8, color=INK, va="top")
    top.text(-90, r + 24, "fingers", fontsize=8, color=FAINT)
    top.text(r + 4, 2, "each flat pad\ntouches the round\nglass at one spot",
             fontsize=8, color=GRIP)
    _style(top, "Seen from above")
    top.set_xlim(-100, 90)
    top.set_ylim(-r - 60, r + 45)
    top.set_aspect("equal")
    top.axis("off")

    # Looking down the fingers: the wrist turn. The pads are in the way of
    # the glass lagging behind.
    glass = _outline_polygon(profile)
    strong.fill(glass[:, 0], glass[:, 1], color=GLASS, alpha=0.15)
    strong.plot(glass[:, 0], glass[:, 1], color=GLASS, linewidth=1.6)
    for side in (-1, 1):
        x = side * r if side > 0 else -r - pad_t
        strong.add_patch(plt.Rectangle((x, g - pad_h / 2), pad_t, pad_h, color=INK))
    _curved_arrow(strong, (0, g), r + 22, 200, 110)
    for side in (-1, 1):
        strong.annotate("", xy=(side * r * 0.55, g + side * pad_h * 0.4),
                        xytext=(side * (r + 16), g + side * pad_h * 0.4),
                        arrowprops={"arrowstyle": "->", "color": GRIP, "linewidth": 1.4})
    strong.text(0, -22, "the pads push straight on the glass,\nso it turns with them",
                fontsize=8, color=GRIP, ha="center", va="top")
    _style(strong, "Turning across the fingers\n(the wrist turn): strong")
    strong.set_xlim(-90, 90)
    strong.set_ylim(-50, 130)
    strong.set_aspect("equal")
    strong.axis("off")

    # Looking along the hinge: tipping over the fingertips. Nothing but
    # friction on a short contact stops it.
    weak.fill(glass[:, 0], glass[:, 1], color=GLASS, alpha=0.15)
    weak.plot(glass[:, 0], glass[:, 1], color=GLASS, linewidth=1.6)
    weak.add_patch(plt.Rectangle((-95, g - 4), 95 + tip, 8, color=FAINT, alpha=0.6))
    weak.plot([0, 0], [g - pad_h / 2, g + pad_h / 2], color=GRIP, linewidth=4)
    weak.plot(0, g, "o", color=GRIP, markersize=6)
    _curved_arrow(weak, (0, g), r + 22, 70, -20)
    weak.text(0, -22, "only friction on this short contact\nstops the glass swinging",
              fontsize=8, color=GRIP, ha="center", va="top")
    weak.text(-90, g + 8, "finger", fontsize=8, color=FAINT)
    _style(weak, "Tipping over the fingertips\n(about the hinge): weak")
    weak.set_xlim(-100, 90)
    weak.set_ylim(-50, 130)
    weak.set_aspect("equal")
    weak.axis("off")

    _save(fig, "the-hinge.png")


def weight_and_the_hinge() -> None:
    fig, axes = plt.subplots(1, 4, figsize=(12, 4.8))
    cases = [("straight_glass", False), ("straight_glass", True),
             ("stemmed_glass", False), ("stemmed_glass", True)]
    for ax, (name, flipped) in zip(axes, cases, strict=True):
        profile, grip = _gripped(name)
        g = grip.height * 1000.0
        com = _centre_of_mass(profile) * 1000.0
        glass = _outline_polygon(profile)
        if flipped:
            glass = _turned(glass, 180.0, (0.0, g))
            com_y = 2 * g - com
        else:
            com_y = com
        ax.fill(glass[:, 0], glass[:, 1], color=GLASS, alpha=0.15)
        ax.plot(glass[:, 0], glass[:, 1], color=GLASS, linewidth=1.6)
        half = grip.opening * 500.0
        pad_h = PAD_HEIGHT * 1000.0
        for side in (-1, 1):
            ax.add_patch(plt.Rectangle((side * half if side > 0 else -half - 4, g - pad_h / 2),
                                       4, pad_h, color=GRIP))
        ax.axhline(g, color=GRIP, linestyle="--", linewidth=0.8)
        ax.plot(0, com_y, "o", color=INK, markersize=8)
        ax.plot(0, com_y, "+", color="white", markersize=8, markeredgewidth=1.5)
        # The weight pulls straight down, wherever the glass is turned.
        ax.annotate("", xy=(0, com_y - 18), xytext=(0, com_y),
                    arrowprops={"arrowstyle": "->", "color": INK})
        ax.text(half + 8, com_y, "centre of mass", fontsize=8, color=INK, va="center")
        ax.text(half + 8, g - 10, "grip", fontsize=8, color=GRIP, va="center")

        above = com_y > g
        gap = abs(com - g)
        verdict = (
            f"weight {gap:.0f} mm above the grip:\ntop-heavy, it can tip over"
            if above
            else f"weight {gap:.0f} mm below the grip:\nit hangs, and settles"
        )
        way = "upside down" if flipped else "upright"
        _style(ax, f"{name.replace('_', ' ')}, {way}")
        ax.set_xlabel(verdict, fontsize=8, color=INK)
        ax.set_xlim(-60, 100)
        ax.set_ylim(-130, 240)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for side in ("left", "bottom"):
            ax.spines[side].set_visible(False)

    fig.suptitle(
        "The grip is where the rules hold each glass. The centre of mass is estimated from "
        "the outline, assuming an even wall.",
        fontsize=9,
        color=INK,
    )
    _save(fig, "weight-and-the-hinge.png")


def pad_shapes() -> None:
    profile, grip = _gripped("straight_glass")
    r = grip.opening * 500.0
    fig, (flat, vee, tall) = plt.subplots(1, 3, figsize=(12, 4.2))

    def glass_from_above(ax):
        ax.add_patch(plt.Circle((0, 0), r, color=GLASS, alpha=0.15))
        ax.add_patch(plt.Circle((0, 0), r, fill=False, color=GLASS, linewidth=1.6))

    glass_from_above(flat)
    for side in (-1, 1):
        flat.add_patch(plt.Rectangle((-20, side * r if side > 0 else -r - 5), 40, 5, color=INK))
        flat.plot(0, side * r, "o", color=GRIP, markersize=8)
    _style(flat, "Flat pad: one contact each side")

    glass_from_above(vee)
    # A shallow V: two faces at 30 degrees, touching the circle where their
    # normals point at its centre.
    face = math.radians(30)
    for side in (-1, 1):
        apex = np.array([0.0, side * r / math.cos(face)])
        touches = [np.array([lr * r * math.sin(face), side * r * math.cos(face)]) for lr in (-1, 1)]
        groove = np.array([apex + 1.8 * (touches[0] - apex), apex, apex + 1.8 * (touches[1] - apex)])
        vee.plot(groove[:, 0], groove[:, 1], color=INK, linewidth=4, solid_joinstyle="miter")
        for point in touches:
            vee.plot(*point, "o", color=GRIP, markersize=8)
    _style(vee, "V-shaped pad: two contacts each side")

    for ax in (flat, vee):
        ax.set_xlim(-60, 60)
        ax.set_ylim(-r - 30, r + 30)
        ax.set_aspect("equal")
        ax.axis("off")

    # Side on: a taller pad means a longer contact line to resist tipping.
    for x, height, label in (
        (-35, PAD_HEIGHT * 1000.0, "short pad"),
        (35, 3 * PAD_HEIGHT * 1000.0, "tall pad"),
    ):
        tall.add_patch(plt.Rectangle((x - 20, 0), 40, 100, color=GLASS, alpha=0.15))
        tall.plot([x - 20, x - 20], [0, 100], color=GLASS, linewidth=1.6)
        tall.plot([x - 20, x - 20], [50 - height / 2, 50 + height / 2], color=GRIP, linewidth=5)
        tall.text(x - 20, -8, label, fontsize=8, color=INK, ha="center", va="top")
    tall.text(0, 112, "the red line is where pad meets glass:\nlonger resists tipping better",
              fontsize=8, color=GRIP, ha="center")
    _style(tall, "Seen from the side")
    tall.set_xlim(-75, 75)
    tall.set_ylim(-20, 130)
    tall.set_aspect("equal")
    tall.axis("off")

    _save(fig, "pad-shapes.png")


def ways_to_turn() -> None:
    profile, grip = _gripped("straight_glass")
    g = grip.height * 1000.0
    glass = _outline_polygon(profile)
    fig, (spot, curve, regrip) = plt.subplots(1, 3, figsize=(13, 4.6))

    def draw_at(ax, angle, offset, alpha, colour=GLASS):
        shape = _turned(glass, angle, (0.0, g)) + np.asarray(offset) - np.array([0.0, g])
        ax.fill(shape[:, 0], shape[:, 1], color=colour, alpha=alpha * 0.25)
        ax.plot(shape[:, 0], shape[:, 1], color=colour, linewidth=1.2, alpha=alpha)
        ax.plot(offset[0], offset[1], "o", color=GRIP, markersize=4, alpha=alpha)

    # On the spot: the grip point stays put and the glass turns about it.
    for step, angle in enumerate((0, 60, 120, 180)):
        draw_at(spot, angle, (0.0, 150.0), 0.3 + 0.7 * step / 3)
    _curved_arrow(spot, (0.0, 150.0), 130, 100, 250)
    spot.text(40, 250, "start: upright", fontsize=8, color=FAINT)
    spot.text(40, 40, "end: upside down", fontsize=8, color=INK)
    spot.text(0, 0, "the grip point stays still;\nthe glass turns about it",
              fontsize=8, color=INK, ha="center")
    _style(spot, "Turn the last wrist joint\n(in use)")

    # On a curve: the glass travels over an arc and turns as it goes.
    centre, radius = np.array([0.0, 120.0]), 120.0
    for step in range(5):
        share = step / 4
        at = centre + radius * np.array([-math.cos(math.pi * share), math.sin(math.pi * share)])
        draw_at(curve, -180.0 * share, at, 0.3 + 0.7 * share)
    arc = np.radians(np.linspace(180, 0, 60))
    curve.plot(centre[0] + radius * np.cos(arc), centre[1] + radius * np.sin(arc),
               color=FAINT, linestyle=":", linewidth=1.0)
    curve.text(0, -20, "it tips as it travels, and lands\nupside down, further along",
               fontsize=8, color=INK, ha="center")
    _style(curve, "Roll it over on a curve")

    # Put down and grip again: two quarter turns with a rest in between.
    table = 0.0
    for x, angle, label in ((-170, 0, "1. upright"), (0, 90, "2. on its side,\nin a cradle"),
                            (170, 180, "3. gripped again,\nupside down")):
        draw_at(regrip, angle, (x, 150.0), 1.0)
        regrip.text(x, table - 12, label, fontsize=8, color=INK, ha="center", va="top")
    for x in (-120, 60):
        regrip.annotate("", xy=(x + 50, 150), xytext=(x, 150),
                        arrowprops={"arrowstyle": "->", "color": INK})
    regrip.text(0, 280, "never more than a quarter turn in one grip",
                fontsize=8, color=INK, ha="center")
    _style(regrip, "Put it down and grip again")

    for ax in (spot, curve, regrip):
        ax.set_aspect("equal")
        ax.axis("off")
    spot.set_xlim(-160, 160)
    spot.set_ylim(-30, 300)
    curve.set_xlim(-230, 230)
    curve.set_ylim(-40, 320)
    regrip.set_xlim(-260, 260)
    regrip.set_ylim(-60, 300)
    _save(fig, "ways-to-turn.png")


def step_six_in_pictures() -> None:
    """The whole of step 6, side on, looking down the fingers, in six frames."""
    profile, grip = _gripped("straight_glass")
    g = grip.height * 1000.0
    half = grip.opening * 500.0
    pad_h = PAD_HEIGHT * 1000.0
    glass = _outline_polygon(profile)
    tall = profile.total_height * 1000.0
    base_top = RACK_BASE_HEIGHT * 1000.0
    peg = PEG_HEIGHT * 1000.0
    clearance = PLACE_CLEARANCE * 1000.0

    def pads(opening):
        return [
            np.array(
                [[x, g - pad_h / 2], [x + 4, g - pad_h / 2], [x + 4, g + pad_h / 2], [x, g + pad_h / 2]]
            )
                for x in (-opening - 4, opening)]

    def draw_held(ax, angle, lift, opening=half):
        """The glass and the pads, turned by ``angle`` about the grip and moved up by ``lift``."""
        shape = _turned(glass, angle, (0.0, g)) + np.array([0.0, lift])
        ax.fill(shape[:, 0], shape[:, 1], color=GLASS, alpha=0.2)
        ax.plot(shape[:, 0], shape[:, 1], color=GLASS, linewidth=1.5)
        for pad in pads(opening):
            turned = _turned(pad, angle, (0.0, g)) + np.array([0.0, lift])
            ax.fill(turned[:, 0], turned[:, 1], color=GRIP)

    def draw_rack(ax):
        ax.add_patch(plt.Rectangle((-80, 0), 160, base_top, color=FAINT, alpha=0.6))
        ax.add_patch(plt.Rectangle((-PEG_RADIUS * 1000, base_top), 2 * PEG_RADIUS * 1000, peg,
                                   color=FAINT))
        ax.text(-76, base_top / 2, "rack", fontsize=7, color=INK, va="center")

    fig, axes = plt.subplots(1, 6, figsize=(15, 4.6))
    # Upside down and turned about the grip, the rim sits (height - grip) below
    # the grip. These lifts put the rim where each frame says it is.
    rim_below_grip = tall - g
    over_slot = base_top + peg + clearance + rim_below_grip - g
    landed = base_top + rim_below_grip - g

    frames = [
        ("1. Carry it to the\nmiddle of the table", 0, 60.0, None),
        (f"2. Lean it {SLIP_TEST_DEG:.0f}°:\nhave the fingers crept shut?", SLIP_TEST_DEG, 60.0, None),
        (f"3. Turn the last wrist\njoint the other {180 - SLIP_TEST_DEG:.0f}°", 180, 60.0, None),
        ("4. Carry it over the slot,\nrim above the peg", 180, over_slot, "rack"),
        ("5. Come down 2 mm at a\ntime until it touches", 180, landed, "rack"),
        ("6. Rack has the weight?\nThen open and lift away", 180, landed, "open"),
    ]
    for ax, (title, angle, lift, extra) in zip(axes, frames, strict=True):
        if extra in ("rack", "open"):
            draw_rack(ax)
        draw_held(ax, angle, lift, opening=half + 12 if extra == "open" else half)
        _style(ax, title)
        ax.set_xlim(-85, 85)
        ax.set_ylim(-15, 230)
        ax.set_aspect("equal")
        ax.axis("off")

    # Frame 2: the pivot is the grip, and the lean is small enough to undo.
    _curved_arrow(axes[1], (0.0, g + 60.0), 70, 90, 90 + SLIP_TEST_DEG + 15)
    # Frame 3: the rest of the turn.
    _curved_arrow(axes[2], (0.0, g + 60.0), 70, 110, 260)
    # Frame 4: the gap between rim and peg top.
    rim = base_top + peg + clearance
    axes[3].annotate("", xy=(30, base_top + peg), xytext=(30, rim),
                     arrowprops={"arrowstyle": "<->", "color": INK, "linewidth": 0.9})
    axes[3].text(34, base_top + peg + clearance / 2, f"{clearance:.0f} mm", fontsize=7,
                 color=INK, va="center")
    # Frame 5: feeling the way down.
    axes[4].annotate("", xy=(55, base_top + 10), xytext=(55, base_top + 70),
                     arrowprops={"arrowstyle": "->", "color": INK})
    axes[4].text(0, -10, "the peg goes up inside\nthe glass; the rim lands\non the rack top",
                 fontsize=7, color=INK, ha="center", va="top")
    # Frame 6: away.
    axes[5].annotate("", xy=(55, 200), xytext=(55, 140),
                     arrowprops={"arrowstyle": "->", "color": INK})
    axes[1].text(0, -10, "the red pads are the fingers,\nseen looking down them",
                 fontsize=7, color=GRIP, ha="center", va="top")
    _save(fig, "step6-in-pictures.png")


if __name__ == "__main__":
    four_kinds()
    a_family_of_wine_glasses()
    features_of_a_profile()
    the_estimate_is_not_enough()
    tilt_budget()
    classification()
    three_questions()
    four_kinds_named()
    laying_a_glass_on_the_table()
    the_gripper_has_a_body()
    the_rack_the_planner_saw()
    which_way_is_down()
    the_turn_swings_the_arm()
    the_hinge()
    weight_and_the_hinge()
    pad_shapes()
    ways_to_turn()
    step_six_in_pictures()
