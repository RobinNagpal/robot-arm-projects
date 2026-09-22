"""Draw the pictures in this folder.

Every picture here is made by running the project's own functions and plotting
what comes back. Nothing is drawn by hand and nothing is illustrative. If a
grip point moves in `rules.py`, it moves in the picture the next time this is
run, which is the only way a diagram stays true.

    python docs/make_images.py

Needs matplotlib, which is not a dependency of the project itself.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "work_cell"))

from work_cell.arm.dimensions import GRIPPER_MAX_OPENING, PAD_HEIGHT  # noqa: E402
from work_cell.glasses import spec  # noqa: E402
from work_cell.glasses.detect import classify  # noqa: E402
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
    SLOT_SPACING,
    tilt_budget_deg,
)

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
            lean = float(np.degrees(np.median(profile.slope())))
            ax.scatter(
                lean,
                fraction,
                marker=markers[made_as],
                s=18,
                color=colours[called],
                alpha=0.75,
            )

    ax.axhline(0.17, color=INK, linestyle="--", linewidth=1.0)
    ax.text(
        0.03,
        0.97,
        "a waist above this line is a long stem,\nbelow it a short one (0.17)",
        transform=ax.transAxes,
        va="top",
        fontsize=8,
        color=INK,
    )
    ax.axvline(6.0, color=INK, linestyle=":", linewidth=1.0)
    ax.text(
        0.42,
        0.20,
        "no waist at all, so the question is the lean:\nupright to the left, tapered to the right (6 deg)",
        transform=ax.transAxes,
        fontsize=8,
        color=INK,
    )

    _style(ax, "Marker shape is how the glass was made; colour is what it was called")
    ax.set_xlabel("median wall lean, degrees", fontsize=8)
    ax.set_ylabel("waist height / glass height (0 = no waist)", fontsize=8)
    _save(fig, "classify-from-profile.png")


if __name__ == "__main__":
    four_kinds()
    a_family_of_wine_glasses()
    features_of_a_profile()
    the_estimate_is_not_enough()
    tilt_budget()
    classification()
