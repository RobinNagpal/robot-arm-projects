"""Diagrams for solution 8 — a learned early-abort.

Everything drawn here is computed, not sketched. The glass outlines come from
``work_cell.glasses.shapes``, drawn at sizes inside the tapered kind's declared
range, and the mass, the height of the centre of mass and the moment of inertia
come from ``work_cell.glasses.spawn``, which is the same arithmetic the
simulator is handed when it spawns the glass. No size of any glass is written
down in this file.

Two of these pictures show a force against time. Those curves are **computed
from the model stated in the document**, not recorded from a run, and both the
caption and the axis label say so. The model is one line: a glass tipping about
the leading edge of its foot needs a horizontal push at world height ``h`` of

    F = m g r sin(theta_c - theta) / h

where ``r`` is the distance from that edge to the centre of mass and
``theta_c`` is the rotation that brings the centre of mass over the edge. It
falls to zero at ``theta_c`` because the glass is then balanced and needs no
help. A sliding glass instead needs ``mu m g``, which does not change.

Run from the project root:

    pixi run python images/generators/problem-3/make_08_images.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from diagram_style import (
    CAST,
    FINGER_HEIGHT,
    GLASS,
    GOOD,
    INK,
    JAW_TOP,
    LABEL_SIZE,
    LOWEST_GRIP,
    MU_HIGH,
    MU_LOW,
    MUTED,
    NOTE_SIZE,
    PAD_HEIGHT,
    STURDY,
    TABLE_FRICTION,
    TIPPY,
    TITLE_SIZE,
    WARN,
    bare,
    base_width,
    new,
    push_arrow,
    pushable,
    save,
    tips,
    topple_height,
)
from matplotlib.patches import Polygon, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.shapes import build, family  # noqa: E402
from work_cell.glasses.spawn import SpawnedGlass  # noqa: E402

# ---------------------------------------------------------------------------
# The push, in the numbers the rest of problem 3 uses.
# ---------------------------------------------------------------------------
KIND = "tapered_glass"
GRAVITY = 9.81

# Where the push actually lands. The middle of the jaw rides at LOWEST_GRIP,
# but the jaw is FINGER_HEIGHT tall and a tapered glass is wider higher up, so
# the glass meets the jaw's TOP edge first. That is JAW_TOP, and it is 15 mm
# higher than the number it is easy to reach for. Every figure in this script
# is computed at JAW_TOP and says so in its caption.
PUSH_HEIGHT = JAW_TOP              # mm; problem-3-sim/bench.py JAW_TOP
JAW_MIDDLE = LOWEST_GRIP           # mm; what a careless tipping check would use

PUSH_SPEED = 20.0                  # mm/s; problem-3-sim/bench.py PUSH_SPEED
SLOW_PUSH = 10.0                   # mm/s; half speed, for the comparison

# What the simulator really puts under the glasses, and what the arm is never
# told. The plan assumes MU_LOW; the table is grippier than that.
TRUE_MU = TABLE_FRICTION

# The project's own definition of fallen: problem-3-sim/bench.py
# STANDING_TILT_DEG, "A glass leaning further than this has fallen over."
# scoring.py reads it from the settled pose at the end of a run, so a glass
# that leans past it and rocks back still scores as standing. It is used here
# as the stricter of two deadlines, because a design that relies on a glass
# passing through the project's own failure state and coming back is not one
# to put in writing.
STANDING_TILT = 20.0
SENSOR_HZ = 100.0                  # the-cell.md: the wrist force-torque rate
SAMPLE_MS = 1000.0 / SENSOR_HZ

# The chain from a changed signal to a stopped arm, in milliseconds. The first
# is the sensor period, the second is the width of the median filter the
# monitor runs (counted in full, which is pessimistic: a median's own lag is
# about half its window), the third is features plus one tree evaluation, and
# the last is the controller ramping a velocity command to zero.
CHAIN = (("one sample", SAMPLE_MS), ("5-sample median", 5 * SAMPLE_MS),
         ("features and tree", 1.0), ("brake ramp", 35.0))
CHAIN_MS = sum(cost for _name, cost in CHAIN)

# How many glasses the sweeps draw. Large enough that a percentage is stable to
# the nearest whole number, and one fixed seed so the document can quote it.
SWEEP = 400
SEED = 3

# How grippy a silicone pad is on dry glass: glasses/force.py GRIP_FACTOR. Used
# only to bound a force, never to predict one.
PAD_GRIP = 0.6


# ---------------------------------------------------------------------------
# The arithmetic of going over the leading edge.
# ---------------------------------------------------------------------------

def properties(outline):
    """Mass in kg, centre-of-mass height in m, inertia across the axis, for one outline.

    Straight out of ``SpawnedGlass.mass_properties``, so these are the numbers
    the simulator itself is given rather than a second estimate of them.
    """
    spawned = SpawnedGlass(name="one", kind=KIND, outline=outline,
                           position=(0.0, 0.0, 0.0), yaw=0.0)
    mass, centre, across, _spin = spawned.mass_properties
    return mass, centre, across


def tipping(outline, push_height_mm=PUSH_HEIGHT, speed_mms=PUSH_SPEED) -> dict:
    """Everything about one glass going over the leading edge of its foot.

    The glass is a rigid body pivoting on that edge. ``theta_c`` is the rotation
    that puts the centre of mass straight above the edge, which is the balance
    point. The push is quasi-static, so the glass rotates only as fast as the
    arm feeds the contact forward: the contact sits at world height ``h``, so
    its forward speed is ``omega h`` and ``omega`` is the push speed over ``h``.

    The glass is past saving a little before the balance point, because it
    arrives there already turning. ``theta_nr`` is where the rotational energy
    it already has covers the rest of the climb, so that stopping the arm no
    longer brings it back.
    """
    mass, centre, across = properties(outline)
    half_base = float(outline.radius[0])
    reach = float(np.hypot(half_base, centre))
    inertia = across + mass * reach ** 2
    balance = float(np.arctan2(half_base, centre))

    height = push_height_mm / 1000.0
    omega = (speed_mms / 1000.0) / height
    energy = 0.5 * inertia * omega ** 2
    climb = mass * GRAVITY * reach
    short_of_balance = float(np.arccos(np.clip(1.0 - energy / climb, -1.0, 1.0)))
    no_return = max(0.0, balance - short_of_balance)

    # Two deadlines. The physical one is the point of no return: stop after it
    # and the glass goes over whatever the arm does. The project's own one is
    # STANDING_TILT, the lean at which bench.py calls a glass fallen. Whichever
    # comes first is the deadline a design should be held to.
    counted_fallen = np.radians(STANDING_TILT)
    deadline = min(no_return, counted_fallen)

    return dict(
        mass=mass, centre=centre, half_base=half_base, reach=reach,
        inertia=inertia, balance=balance, no_return=no_return, omega=omega,
        deadline=deadline, strict=no_return > counted_fallen,
        window_ms=1000.0 * deadline / omega,
        physical_window_ms=1000.0 * no_return / omega,
        to_balance_ms=1000.0 * balance / omega,
        onset_force=mass * GRAVITY * half_base / height,
        slide_low=MU_LOW * mass * GRAVITY,
        slide_high=MU_HIGH * mass * GRAVITY,
        wall_angle=float(np.arctan2(float(outline.radius[-1]) - half_base,
                                    outline.total_height)),
        climb_speed=1000.0 * omega * (half_base + float(
            np.interp(height, outline.height, outline.radius))),
    )


def tip_force(state, angle):
    """The horizontal push a tipping glass needs, in newtons, at body rotation ``angle``.

    Modelled, not measured. A horizontal force applied at world height ``h``
    has moment ``F h`` about the pivot whatever the glass has rotated to, and
    gravity holds the glass back with ``m g r sin(theta_c - theta)``, so the two
    give F directly. It ignores any vertical force the finger puts into the
    wall, which adds a moment of its own and which depends on the pad.
    """
    height = PUSH_HEIGHT / 1000.0
    return (state["mass"] * GRAVITY * state["reach"]
            * np.sin(np.clip(state["balance"] - angle, 0.0, None)) / height)


def fall_time_ms(state, to_degrees):
    """How long from the balance point to ``to_degrees`` of further rotation.

    Past the balance point nothing holds the glass back, so this is a falling
    inverted pendulum released with the angular speed the push gave it. Energy
    gives the speed at every angle and the time is one integral of its inverse.
    """
    angle = np.linspace(0.0, np.radians(to_degrees), 40001)
    speed = np.sqrt(state["omega"] ** 2
                    + 2.0 * state["mass"] * GRAVITY * state["reach"]
                    * (1.0 - np.cos(angle)) / state["inertia"])
    return 1000.0 * float(np.trapezoid(1.0 / speed, angle))


def side_polygon(outline, rotation=0.0):
    """The glass seen level, in millimetres, rotated about the leading edge of its foot.

    Returns the closed outline: up the trailing wall, across the rim, down the
    leading wall. Rotating the real outline rather than a trapezium is the
    point of the first picture, because the foot's edge is where it pivots and
    the foot is the part a trapezium gets wrong.
    """
    z = outline.height * 1000.0
    r = outline.radius * 1000.0
    x = np.concatenate([-r, r[::-1]])
    y = np.concatenate([z, z[::-1]])
    pivot_x = r[0]
    dx, dy = x - pivot_x, y
    return np.column_stack([
        dx * np.cos(rotation) + dy * np.sin(rotation) + pivot_x,
        -dx * np.sin(rotation) + dy * np.cos(rotation),
    ])


def how_it_looks(outline, rotation):
    """What a leaning glass looks like from above and from the side, in millimetres.

    Returns how much wider its outline has become along the push direction, and
    how much its tallest point has moved. Both are read off the rotated real
    outline, because the question is whether a glass that has passed the
    project's own failure angle is visibly different, and the answer decides
    how much a camera could have done instead.
    """
    upright = side_polygon(outline, 0.0)
    leaning = side_polygon(outline, rotation)
    widened = (leaning[:, 0].max() - leaning[:, 0].min()) - (
        upright[:, 0].max() - upright[:, 0].min())
    risen = leaning[:, 1].max() - upright[:, 1].max()
    return float(widened), float(risen)


def rotate_point(point, rotation, pivot_x):
    """One (x, z) point in millimetres, rotated forward about the pivot on the table."""
    dx, dy = point[0] - pivot_x, point[1]
    return (dx * np.cos(rotation) + dy * np.sin(rotation) + pivot_x,
            -dx * np.sin(rotation) + dy * np.cos(rotation))


# ---------------------------------------------------------------------------
# The cast. Drawn, never written down.
# ---------------------------------------------------------------------------

FAMILY = [outline for outline, _chosen in family(KIND, SWEEP, SEED)]
STATES = [tipping(outline) for outline in FAMILY]

# The glasses a correctly written check would push: topple height above the
# jaw's top edge at the friction the plan assumes.
KEPT = [i for i, outline in enumerate(FAMILY)
        if pushable(2000.0 * float(outline.radius[0]), MU_LOW, PUSH_HEIGHT)]
REFUSED = [i for i in range(SWEEP) if i not in set(KEPT)]

# The set that matters most, and it is not KEPT. An arm that guesses MU_LOW and
# checks the rule against the height the jaw aims at rather than the height it
# touches at authorises a larger set, and these are the ones in it that the
# real table then topples. They are the pushes this detector exists to stop, so
# the timing budget is computed over them.
DOOMED = [i for i, outline in enumerate(FAMILY)
          if pushable(2000.0 * float(outline.radius[0]), MU_LOW, JAW_MIDDLE)
          and not pushable(2000.0 * float(outline.radius[0]), TRUE_MU, PUSH_HEIGHT)]

# The example the document works through. It is picked by a rule, not by hand:
# of the glasses the plan authorises at the assumed friction and the table's
# real friction topples, take the one with the middling warning window. That is
# the population this whole solution exists for.
_doomed = np.array([STATES[i]["window_ms"] for i in DOOMED])
EXAMPLE = DOOMED[int(np.argmin(np.abs(_doomed - np.median(_doomed))))]

# The doomed glass with the shortest window of all, which is the hard case.
TIGHTEST = DOOMED[int(np.argmin(_doomed))]

# Two from the shared cast, for the contrast in the first picture: a wide foot
# that slides and a narrow foot that the geometry refuses before any push.
WIDE_FOOT = build(KIND, height=STURDY[0] / 1000.0, rim_diameter=STURDY[1] / 1000.0,
                  base_fraction=STURDY[2])
NARROW_FOOT = build(KIND, height=TIPPY[0] / 1000.0, rim_diameter=TIPPY[1] / 1000.0,
                    base_fraction=TIPPY[2])


def describe(label, outline, state) -> None:
    print(f"{label}: height {outline.total_height * 1000:.0f} mm, rim "
          f"{2000 * float(outline.radius[-1]):.0f} mm, base "
          f"{2000 * state['half_base']:.1f} mm, mass {state['mass'] * 1000:.0f} g, "
          f"centre of mass {state['centre'] * 1000:.0f} mm up")
    print(f"    balance point {np.degrees(state['balance']):.1f} deg, past saving at "
          f"{np.degrees(state['no_return']):.1f} deg, window {state['window_ms']:.0f} ms "
          f"= {state['window_ms'] / SAMPLE_MS:.1f} samples")
    print(f"    topple height {topple_height(2000 * state['half_base'], MU_LOW):.0f} mm at "
          f"mu={MU_LOW}, {topple_height(2000 * state['half_base'], MU_HIGH):.0f} mm at "
          f"mu={MU_HIGH}; slide force {state['slide_low']:.2f} N and "
          f"{state['slide_high']:.2f} N, tip onset {state['onset_force']:.2f} N")
    print(f"    wall {np.degrees(state['wall_angle']):.1f} deg off vertical, contact climbs "
          f"the wall at {state['climb_speed']:.0f} mm/s")


# ---------------------------------------------------------------------------
# 1. The geometry of going over the leading edge.
# ---------------------------------------------------------------------------

def contact_x(outline, rotation, pivot_x):
    """Where the pad meets the trailing wall, in millimetres, at this rotation.

    The pad sits at a fixed world height, so as the glass turns the pad meets a
    different point of the wall. Finding it rather than guessing is what keeps
    the finger touching the glass in all three panels.
    """
    trailing = np.column_stack([-outline.radius * 1000.0, outline.height * 1000.0])
    turned = np.array([rotate_point(point, rotation, pivot_x) for point in trailing])
    order = np.argsort(turned[:, 1])
    return float(np.interp(PUSH_HEIGHT, turned[order, 1], turned[order, 0]))


def over_the_leading_edge() -> None:
    outline = FAMILY[EXAMPLE]
    state = STATES[EXAMPLE]
    pivot_x = 1000.0 * state["half_base"]
    stages = (
        (0.0, "upright, and pushed", GOOD),
        (state["no_return"], "past saving", WARN),
        (state["balance"], "balanced on the edge", WARN),
    )

    figure, axes = new(11.4, 4.6, columns=3)
    for axis, (rotation, title, colour) in zip(axes, stages, strict=True):
        bare(axis)
        # Otherwise the next panel's white background paints over a label that
        # reaches past this panel's edge.
        axis.patch.set_visible(False)
        axis.plot([-95, 95], [0, 0], color=INK, lw=1.4, zorder=1)
        axis.add_patch(Polygon(side_polygon(outline, rotation), closed=True,
                               facecolor=GLASS, alpha=0.28, edgecolor=GLASS,
                               lw=1.2, zorder=3))

        centre = rotate_point((0.0, 1000.0 * state["centre"]), rotation, pivot_x)
        axis.plot(*centre, marker="o", ms=5.0, color=INK, zorder=6)
        axis.plot([pivot_x, centre[0]], [0.0, centre[1]], color=INK, lw=0.9,
                  ls=(0, (3, 2)), zorder=5)
        axis.plot([centre[0], centre[0]], [centre[1], 0.0], color=MUTED, lw=0.8,
                  ls=(0, (1, 2)), zorder=4)
        axis.plot(pivot_x, 0.0, marker="v", ms=7.0, color=colour, zorder=7)

        # The pad, touching the wall at the lowest height the gripper can reach.
        wall = contact_x(outline, rotation, pivot_x)
        axis.add_patch(Rectangle((wall - 9.0, PUSH_HEIGHT - PAD_HEIGHT / 2.0), 9.0,
                                 PAD_HEIGHT, facecolor=INK, alpha=0.75,
                                 edgecolor="none", zorder=6))
        push_arrow(axis, (wall - 32.0, PUSH_HEIGHT), (wall - 11.0, PUSH_HEIGHT),
                   colour=INK, lw=1.4)

        axis.set_title(title, fontsize=TITLE_SIZE, color=colour, pad=8)
        axis.set_xlim(-100, 100)
        axis.set_ylim(-40, 1.30 * outline.total_height * 1000.0)
        axis.set_aspect("equal")

    lean = np.degrees(state["no_return"])
    over = np.degrees(state["balance"])
    notes = (
        f"The foot is {2000 * state['half_base']:.0f} mm across, so the edge it turns on\n"
        f"is {1000 * state['half_base']:.0f} mm from the axis, and the centre of mass\n"
        f"is {1000 * state['centre']:.0f} mm up.",
        f"{lean:.1f} degrees over. The arm can still stop, but the\n"
        f"turning it has already given the glass covers the\n"
        f"rest of the climb, so stopping no longer saves it.",
        f"{over:.1f} degrees over. The dotted plumb line has\n"
        f"reached the edge, the glass needs no more push,\n"
        f"and it leaves the pad behind.",
    )
    for axis, note in zip(axes, notes, strict=True):
        axis.text(0.5, -0.03, note, transform=axis.transAxes, ha="center", va="top",
                  fontsize=NOTE_SIZE, color=MUTED, linespacing=1.6)

    axes[0].annotate("the leading edge of the foot",
                     xy=(pivot_x + 1.0, -1.0), xytext=(pivot_x - 4.0, -28.0),
                     fontsize=NOTE_SIZE, color=WARN, ha="left", va="center",
                     annotation_clip=False,
                     arrowprops=dict(arrowstyle="-", color=WARN, lw=0.9))
    wall0 = contact_x(outline, 0.0, pivot_x)
    axes[0].annotate(f"the jaw's top edge, at {PUSH_HEIGHT:.0f} mm",
                     xy=(wall0 - 6.0, PUSH_HEIGHT - PAD_HEIGHT / 2.0),
                     xytext=(-96.0, -20.0), fontsize=NOTE_SIZE, color=INK,
                     ha="left", va="center", annotation_clip=False,
                     arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))
    axes[0].annotate("centre of mass", xy=(2.0, 1000.0 * state["centre"]),
                     xytext=(14.0, 1000.0 * state["centre"] + 26.0),
                     fontsize=NOTE_SIZE, color=INK, ha="left", va="center",
                     arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))

    figure.suptitle(f"A tipping glass turns on one edge of its foot, pushed at "
                    f"{PUSH_HEIGHT:.0f} mm, and the window closes before it balances",
                    fontsize=TITLE_SIZE, color=INK, y=1.0)
    save(figure, "08-over-the-leading-edge.png")


# ---------------------------------------------------------------------------
# 2. No level of force separates a slide from a tip.
# ---------------------------------------------------------------------------

def no_threshold_separates() -> None:
    mass = np.array([state["mass"] for state in STATES]) * 1000.0
    slide_low = np.array([state["slide_low"] for state in STATES])
    slide_high = np.array([state["slide_high"] for state in STATES])
    onset = np.array([state["onset_force"] for state in STATES])

    figure, axis = new(8.2, 4.6)
    axis.scatter(mass, slide_low, s=9, color=GOOD, alpha=0.55, lw=0,
                 label=f"sliding, at mu = {MU_LOW}")
    axis.scatter(mass, slide_high, s=9, color=MUTED, alpha=0.7, lw=0,
                 label=f"sliding, at mu = {MU_HIGH}")
    axis.scatter(mass, onset, s=9, color=WARN, alpha=0.6, lw=0,
                 label=f"starting to tip, pushed at {PUSH_HEIGHT:.0f} mm")

    low, high = onset.min(), slide_high.max()
    axis.axhspan(low, high, color=WARN, alpha=0.07, zorder=0)
    axis.axhline(low, color=WARN, lw=0.8, ls=(0, (4, 3)))
    axis.axhline(high, color=INK, lw=0.8, ls=(0, (4, 3)))
    axis.text(mass.max(), low + 0.07, f"the lightest tip: {low:.2f} N",
              fontsize=NOTE_SIZE, color=WARN, ha="right", va="bottom")
    axis.text(mass.max(), high + 0.07, f"the heaviest ordinary slide: {high:.2f} N",
              fontsize=NOTE_SIZE, color=INK, ha="right", va="bottom")
    axis.text(mass.min() + 4.0, 0.5 * (low + high),
              "every level in this band\nis both a slide and a tip",
              fontsize=NOTE_SIZE, color=WARN, ha="left", va="center", linespacing=1.5)

    axis.set_xlabel("what the glass weighs, in grammes", fontsize=LABEL_SIZE, color=INK)
    axis.set_ylabel("horizontal force at the wrist, in newtons", fontsize=LABEL_SIZE, color=INK)
    axis.set_title(f"{SWEEP} drawn tapered glasses pushed at {PUSH_HEIGHT:.0f} mm, and no "
                   f"level that tells the two apart",
                   fontsize=TITLE_SIZE, color=INK, pad=12)
    axis.tick_params(labelsize=NOTE_SIZE, colors=MUTED)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)
    axis.legend(fontsize=NOTE_SIZE, frameon=False, loc="upper left")
    axis.figure.text(0.5, -0.04,
                     f"Computed, not measured, at a push height of {PUSH_HEIGHT:.0f} mm — the jaw's "
                     f"top edge, which is where a tapered glass meets it. Sliding needs mu m g;\nstarting to "
                     f"tip needs m g a / h. The mass of each drawn glass is the simulator's own "
                     f"spawn arithmetic.",
                     ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED, linespacing=1.5)
    save(figure, "08-no-threshold-separates.png")


# ---------------------------------------------------------------------------
# 3. What the force and the contact angle do in a slide and in a tip.
# ---------------------------------------------------------------------------

def slide_against_tip() -> None:
    state = STATES[EXAMPLE]
    outline = FAMILY[EXAMPLE]
    window = state["window_ms"]
    balance = state["to_balance_ms"]
    end_ms = 1.10 * balance
    time = np.linspace(0.0, end_ms, 1400)
    angle = state["omega"] * time / 1000.0
    # Past the balance point the glass needs no push at all, so it runs away
    # from the finger and there is no longer a contact to read. Both curves
    # stop there rather than pretending otherwise.
    touching = time <= balance
    ticks = np.arange(0.0, end_ms, SAMPLE_MS)

    figure, axes = new(11.4, 4.6, columns=2)

    force = axes[0]
    top = 1.42 * max(state["onset_force"], state["slide_low"])
    force.set_ylim(-0.10, top)
    force.plot(time, np.full_like(time, state["slide_low"]), color=GOOD, lw=1.9,
               label=f"it slides, at mu = {MU_LOW}")
    force.plot(time[touching], tip_force(state, angle[touching]), color=WARN, lw=1.9,
               label=f"it tips, at any mu above "
                     f"{1000.0 * state['half_base'] / PUSH_HEIGHT:.2f}")
    force.set_ylabel("horizontal force at the wrist, in newtons",
                     fontsize=LABEL_SIZE, color=INK)
    force.set_title("the force holds steady in one case and falls away in the other",
                    fontsize=LABEL_SIZE, color=INK, pad=10)
    force.legend(fontsize=NOTE_SIZE, frameon=False, loc="upper left")
    shed = 100.0 * (1.0 - tip_force(state, state["no_return"]) / state["onset_force"])
    force.annotate(f"by here it has shed {shed:.0f} per cent\nof the force it started with",
                   xy=(window, tip_force(state, state["no_return"])),
                   xytext=(window * 0.90, top * 0.70), fontsize=NOTE_SIZE, color=WARN,
                   ha="right", va="bottom", linespacing=1.6,
                   arrowprops=dict(arrowstyle="-", color=WARN, lw=0.8))

    contact = axes[1]
    wall = np.degrees(state["wall_angle"])
    swept = np.where(touching, wall - np.degrees(angle), np.nan)
    contact.set_ylim(min(np.nanmin(swept), 0.0) - 4.4, wall + 4.6)
    contact.plot(time, np.full_like(time, wall), color=GOOD, lw=1.9)
    contact.plot(time, swept, color=WARN, lw=1.9)
    contact.axhline(0.0, color=MUTED, lw=0.8)
    contact.text(end_ms * 0.03, wall + 0.7,
                 "sliding: the wall keeps the angle it had", fontsize=NOTE_SIZE,
                 color=GOOD, ha="left", va="bottom")
    contact.text(end_ms * 0.03, contact.get_ylim()[0] + 0.5,
                 "tipping: the wall turns away from the pad,\nthrough flush and past it",
                 fontsize=NOTE_SIZE, color=WARN, ha="left", va="bottom", linespacing=1.6)
    contact.text(end_ms * 0.03, 0.9, "flush with the pad's face",
                 fontsize=NOTE_SIZE, color=MUTED, ha="left", va="bottom")
    contact.set_ylabel("angle between the pad's face and the wall, in degrees",
                       fontsize=LABEL_SIZE, color=INK)
    contact.set_title("and the contact rolls down the pad, which the torque channel reads",
                      fontsize=LABEL_SIZE, color=INK, pad=10)

    for axis in axes:
        low, high = axis.get_ylim()
        axis.axvline(window, color=WARN, lw=1.0, ls=(0, (4, 3)))
        axis.axvline(balance, color=INK, lw=0.9, ls=(0, (1, 2)))
        axis.text(window - 6.0, high, "past saving", fontsize=NOTE_SIZE, color=WARN,
                  rotation=90, ha="right", va="top")
        axis.text(balance - 6.0, high, "balanced, and off the pad", fontsize=NOTE_SIZE,
                  color=INK, rotation=90, ha="right", va="top")
        axis.plot(ticks, np.full_like(ticks, low), marker="|", ms=3.4, lw=0,
                  color=MUTED, alpha=0.7, clip_on=False)
        axis.set_ylim(low, high)
        axis.set_xlim(-0.02 * end_ms, end_ms)
        axis.set_xlabel("milliseconds since the glass began to turn",
                        fontsize=LABEL_SIZE, color=INK)
        axis.tick_params(labelsize=NOTE_SIZE, colors=MUTED)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axis.spines[side].set_color(MUTED)

    figure.suptitle("Both curves are computed from the model in the text, not recorded "
                    "from a run", fontsize=TITLE_SIZE, color=INK, y=1.03)
    figure.text(0.5, -0.07,
                f"One drawn tapered glass: {outline.total_height * 1000:.0f} mm tall, a foot "
                f"{2000 * state['half_base']:.0f} mm across, {state['mass'] * 1000:.0f} g, "
                f"pushed at {PUSH_HEIGHT:.0f} mm — the jaw's top edge — at {PUSH_SPEED:.0f} mm/s. "
                f"The marks along "
                f"the bottom of each panel are the wrist\nsensor's {SENSOR_HZ:.0f} Hz samples. "
                "The left panel ignores any vertical force the finger puts into the wall. The "
                "right panel is geometry alone: how much torque\nthat angle moves depends on "
                "the stiffness of the pad, which nothing in this cell has measured.",
                ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED, linespacing=1.5)
    save(figure, "08-slide-against-tip.png")


# ---------------------------------------------------------------------------
# 4. The timing budget.
# ---------------------------------------------------------------------------

def the_timing_budget() -> None:
    state = STATES[EXAMPLE]
    tight = STATES[TIGHTEST]
    # From the balance point to the lean bench.py calls fallen. The glass is
    # accelerating here, so this is shorter than the steady rate would give.
    fall = (state["to_balance_ms"] - state["window_ms"]
            + fall_time_ms(state, STANDING_TILT - np.degrees(state["balance"])))
    slow = tipping(FAMILY[TIGHTEST], speed_mms=SLOW_PUSH)["window_ms"]
    span = state["window_ms"] + fall

    figure, axis = new(10.6, 4.8)
    bare(axis)
    axis.set_xlim(-0.03 * span, 1.52 * span)
    axis.set_ylim(-3.05, 2.7)

    # The two phases of the topple, on one time line.
    axis.add_patch(Rectangle((0.0, 1.30), state["window_ms"], 0.60, facecolor=GOOD,
                             alpha=0.28, edgecolor=GOOD, lw=1.0))
    axis.add_patch(Rectangle((state["window_ms"], 1.30), fall, 0.60, facecolor=WARN,
                             alpha=0.22, edgecolor=WARN, lw=1.0))
    axis.text(state["window_ms"] / 2.0, 1.60,
              f"the arm can still stop it: {state['window_ms']:.0f} ms",
              fontsize=LABEL_SIZE, color=INK, ha="center", va="center")
    axis.text(state["window_ms"] + fall / 2.0, 1.60,
              f"it is going over: {fall:.0f} ms more",
              fontsize=LABEL_SIZE, color=WARN, ha="center", va="center")
    axis.text(0.0, 2.02, "the glass starts to turn", fontsize=NOTE_SIZE, color=GOOD,
              ha="left", va="bottom")
    axis.text(state["window_ms"], 2.02, "past saving", fontsize=NOTE_SIZE, color=WARN,
              ha="center", va="bottom")
    axis.text(state["window_ms"] + fall, 2.02,
              f"{STANDING_TILT:.0f} degrees: bench.py calls it fallen", fontsize=NOTE_SIZE,
              color=WARN, ha="left", va="bottom")

    # The sensor's samples, counted in fives.
    for index, tick in enumerate(np.arange(0.0, span + SAMPLE_MS, SAMPLE_MS)):
        axis.plot([tick, tick], [0.74, 1.02], color=MUTED, lw=1.0, alpha=0.8)
        if index % 5 == 0:
            axis.text(tick, 0.62, f"{index}", fontsize=6.6, color=MUTED,
                      ha="center", va="top")
    axis.text(span + 14.0, 0.88, f"wrist samples, one every {SAMPLE_MS:.0f} ms",
              fontsize=NOTE_SIZE, color=MUTED, ha="left", va="center")

    # The chain from a changed signal to a stopped arm.
    left = 0.0
    colours = (MUTED, GLASS, INK, GOOD)
    for (_name, cost), colour in zip(CHAIN, colours, strict=True):
        axis.add_patch(Rectangle((left, -0.62), cost, 0.55, facecolor=colour, alpha=0.5,
                                 edgecolor=colour, lw=0.9))
        left += cost
    axis.text(0.0, -0.80,
              " + ".join(f"{name} {cost:.0f}" for name, cost in CHAIN)
              + "  (milliseconds)", fontsize=NOTE_SIZE, color=MUTED,
              ha="left", va="top")

    # The hard case, and the same glass pushed at half speed.
    bars = (
        (-1.70, tight["window_ms"], WARN,
         f"the tightest of the {len(DOOMED)} pushes that topple, at "
         f"{PUSH_SPEED:.0f} mm/s: {tight['window_ms']:.0f} ms — still "
         f"{tight['window_ms'] / CHAIN_MS:.1f} times the chain"),
        (-2.55, slow, GOOD,
         f"the same glass at {SLOW_PUSH:.0f} mm/s: {slow:.0f} ms"),
    )
    for offset, value, colour, label in bars:
        axis.add_patch(Rectangle((0.0, offset), value, 0.48, facecolor=colour, alpha=0.25,
                                 edgecolor=colour, lw=1.0))
        axis.text(max(value, CHAIN_MS) + 14.0, offset + 0.24, label, fontsize=NOTE_SIZE,
                  color=colour, ha="left", va="center")

    axis.plot([CHAIN_MS, CHAIN_MS], [-0.68, 0.22], color=INK, lw=1.2)
    axis.plot([CHAIN_MS, CHAIN_MS], [-2.70, -1.02], color=INK, lw=1.2)
    axis.text(CHAIN_MS, -2.80,
              f"{CHAIN_MS:.0f} ms: a changed signal to a stopped arm",
              fontsize=NOTE_SIZE, color=INK, ha="center", va="top")

    axis.set_title("The budget: how long the arm has, against how long it takes to stop",
                   fontsize=TITLE_SIZE, color=INK, pad=14)
    figure.text(0.5, -0.02,
                f"Times computed for drawn tapered glasses pushed at {PUSH_HEIGHT:.0f} mm, the jaw's "
                f"top edge, which is where a tapered glass meets it.\nThe time line at the top is the "
                f"worked example; "
                "the two bars below it are the worst case the plan lets through, at full speed "
                "and at half speed.",
                ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED, linespacing=1.5)
    save(figure, "08-the-timing-budget.png")


# ---------------------------------------------------------------------------
# 5. How many samples there are, across every glass the plan would push.
# ---------------------------------------------------------------------------

def how_many_samples() -> None:
    fast = np.array([STATES[i]["window_ms"] for i in DOOMED]) / SAMPLE_MS
    slow = np.array([tipping(FAMILY[i], speed_mms=SLOW_PUSH)["window_ms"]
                     for i in DOOMED]) / SAMPLE_MS
    edges = np.arange(0.0, max(fast.max(), slow.max()) + 4.0, 4.0)

    figure, axis = new(8.6, 4.4)
    axis.hist(fast, bins=edges, color=WARN, alpha=0.55,
              label=f"pushed at {PUSH_SPEED:.0f} mm/s")
    axis.hist(slow, bins=edges, color=GOOD, alpha=0.45,
              label=f"pushed at {SLOW_PUSH:.0f} mm/s")
    need = CHAIN_MS / SAMPLE_MS
    axis.set_ylim(0.0, 1.20 * axis.get_ylim()[1])
    axis.axvline(need, color=INK, lw=1.4)
    axis.axvspan(0.0, need, color=INK, alpha=0.06, zorder=0)
    axis.text(need + 2.0, axis.get_ylim()[1] * 0.985,
              f"the detector needs {need:.1f} samples", fontsize=NOTE_SIZE, color=INK,
              ha="left", va="top")
    short_fast = int((fast < need).sum())
    short_slow = int((slow < need).sum())
    axis.text(edges.max() * 0.47, axis.get_ylim()[1] * 0.72,
              f"{short_fast} of {len(fast)} glasses fall short at {PUSH_SPEED:.0f} mm/s\n"
              f"{short_slow} of {len(slow)} fall short at {SLOW_PUSH:.0f} mm/s",
              fontsize=NOTE_SIZE, color=INK, ha="left", va="top", linespacing=1.6)

    axis.set_xlabel(f"wrist samples between the first sign and the deadline, at "
                    f"{SENSOR_HZ:.0f} Hz", fontsize=LABEL_SIZE, color=INK)
    axis.set_ylabel("how many glasses", fontsize=LABEL_SIZE, color=INK)
    axis.set_title(f"The {len(DOOMED)} of {SWEEP} drawn glasses a careless check authorises "
                   f"and the real table topples", fontsize=TITLE_SIZE, color=INK, pad=12)
    axis.tick_params(labelsize=NOTE_SIZE, colors=MUTED)
    for side in ("top", "right"):
        axis.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axis.spines[side].set_color(MUTED)
    axis.legend(fontsize=NOTE_SIZE, frameon=False, loc="upper right")
    figure.text(0.5, -0.04,
                "Computed for each drawn glass from its own mass, centre of mass and inertia, "
                f"pushed at {PUSH_HEIGHT:.0f} mm — the jaw's top edge, not the {JAW_MIDDLE:.0f} mm "
                f"its middle rides at. The deadline is the point of no return\nor "
                f"{STANDING_TILT:.0f} degrees of lean, whichever comes first. Halving the push "
                "speed doubles every window, which is the cheapest way to buy time.",
                ha="center", va="top", fontsize=NOTE_SIZE, color=MUTED, linespacing=1.5)
    save(figure, "08-how-many-samples.png")


# ---------------------------------------------------------------------------
# Every number the document quotes, printed.
# ---------------------------------------------------------------------------

def report() -> None:
    print("--- the cell")
    print(f"wrist force-torque runs at {SENSOR_HZ:.0f} Hz, so one sample every {SAMPLE_MS:.0f} ms")
    print(f"the jaw's middle rides at {JAW_MIDDLE:.0f} mm and the jaw is {FINGER_HEIGHT:.0f} mm "
          f"tall, so a tapered glass meets its top edge at {PUSH_HEIGHT:.0f} mm — that is the "
          f"push height every figure here uses")
    print(f"pad {PAD_HEIGHT:.0f} mm tall; the table's real friction is {TRUE_MU}, which the arm "
          f"is never told")
    print(f"the chain from evidence to a stopped arm: {CHAIN_MS:.0f} ms = "
          f"{CHAIN_MS / SAMPLE_MS:.1f} samples = {PUSH_SPEED * CHAIN_MS / 1000.0:.1f} mm of "
          f"further travel at {PUSH_SPEED:.0f} mm/s")

    print("\n--- the drawn family")
    mass = np.array([state["mass"] for state in STATES]) * 1000.0
    base = np.array([2000.0 * state["half_base"] for state in STATES])
    height = np.array([outline.total_height * 1000.0 for outline in FAMILY])
    centre = np.array([state["centre"] * 1000.0 for state in STATES])
    print(f"{SWEEP} tapered glasses, seed {SEED}")
    print(f"  height {height.min():.0f}..{height.max():.0f} mm")
    print(f"  foot {base.min():.1f}..{base.max():.1f} mm")
    print(f"  mass {mass.min():.0f}..{mass.max():.0f} g, median {np.median(mass):.0f} g")
    print(f"  centre of mass {centre.min():.0f}..{centre.max():.0f} mm up")
    wall = np.degrees([state["wall_angle"] for state in STATES])
    print(f"  wall {wall.min():.1f}..{wall.max():.1f} degrees off vertical, median "
          f"{np.median(wall):.1f} — it leans outwards going up, so the pad is loaded on its "
          f"top edge before the glass turns")
    print("  pushable, by assumed friction and by which height the check is written against:")
    for height, name in ((JAW_MIDDLE, "the jaw's middle"), (PUSH_HEIGHT, "the jaw's top edge")):
        for mu in (MU_LOW, TRUE_MU, MU_HIGH):
            ok = sum(1 for b in base if pushable(b, mu, height))
            print(f"    {name:>18} ({height:.0f} mm), mu={mu}: {ok:>3d}/{SWEEP} = "
                  f"{100.0 * ok / SWEEP:>5.1f}%  (needs a foot of "
                  f"{2 * mu * height:.0f} mm or wider)")
    # The two ways an unmeasured number authorises a push that topples.
    wrong_height = [b for b in base
                    if pushable(b, MU_LOW, JAW_MIDDLE) and not pushable(b, MU_LOW, PUSH_HEIGHT)]
    wrong_mu = [b for b in base
                if pushable(b, MU_LOW, PUSH_HEIGHT) and not pushable(b, TRUE_MU, PUSH_HEIGHT)]
    both = [b for b in base
            if pushable(b, MU_LOW, JAW_MIDDLE) and not pushable(b, TRUE_MU, PUSH_HEIGHT)]
    print(f"  authorised by a check written against the jaw's middle but toppled by the top "
          f"edge, at mu={MU_LOW}: {len(wrong_height)}/{SWEEP} = "
          f"{100.0 * len(wrong_height) / SWEEP:.1f}%")
    print(f"  authorised at mu={MU_LOW} and the top edge but toppled by the table's real "
          f"mu={TRUE_MU}: {len(wrong_mu)}/{SWEEP} = {100.0 * len(wrong_mu) / SWEEP:.1f}%")
    print(f"  authorised by both mistakes together and toppled: {len(both)}/{SWEEP} = "
          f"{100.0 * len(both) / SWEEP:.1f}%")
    kept_feet = np.array([2000.0 * STATES[i]["half_base"] for i in KEPT])
    print(f"  the kept set is the wide-footed half of the kind: feet {kept_feet.min():.1f}.."
          f"{kept_feet.max():.1f} mm, median {np.median(kept_feet):.1f} mm, against "
          f"{base.min():.1f}..{base.max():.1f} mm for the whole kind")
    over = sum(1 for state in STATES if state["onset_force"] > state["slide_low"])
    print(f"  glasses whose tip-onset force is above their own slide force at mu={MU_LOW}: "
          f"{over}/{SWEEP} — the same set as the {PUSH_HEIGHT:.0f} mm row, because both "
          f"conditions are h < a/mu")

    print("\n--- the size of the job this detector is doing")
    authorised = [b for b in base if pushable(b, MU_LOW, JAW_MIDDLE)]
    doomed = [b for b in authorised if not pushable(b, TRUE_MU, PUSH_HEIGHT)]
    print(f"an arm that guesses mu={MU_LOW} and checks the rule against the {JAW_MIDDLE:.0f} mm "
          f"the jaw aims at declares {len(authorised)} of {SWEEP} safe")
    print(f"  of those, {len(doomed)} go over once the real friction {TRUE_MU} and the real "
          f"{PUSH_HEIGHT:.0f} mm contact height are accounted for: "
          f"{100.0 * len(doomed) / SWEEP:.0f}% of the whole population, "
          f"{100.0 * len(doomed) / len(authorised):.0f}% of the pushes it authorises")

    print("\n--- forces")
    slide_low = np.array([state["slide_low"] for state in STATES])
    slide_high = np.array([state["slide_high"] for state in STATES])
    onset = np.array([state["onset_force"] for state in STATES])
    print(f"slide force at mu={MU_LOW}: {slide_low.min():.2f}..{slide_low.max():.2f} N")
    print(f"slide force at mu={MU_HIGH}: {slide_high.min():.2f}..{slide_high.max():.2f} N")
    print(f"tip-onset force at {PUSH_HEIGHT:.0f} mm: {onset.min():.2f}..{onset.max():.2f} N")
    print(f"overlap band: {onset.min():.2f} N to {slide_high.max():.2f} N — every level in it "
          f"is both a slide and a tip")

    print("\n--- which deadline bites")
    strict = [i for i in DOOMED if STATES[i]["strict"]]
    print(f"of the {len(DOOMED)} pushes that topple, {len(strict)} reach "
          f"{STANDING_TILT:.0f} degrees — the project's own fallen line — before they reach "
          f"the point of no return, so for those {STANDING_TILT:.0f} degrees is the earlier "
          f"deadline")
    nr = np.degrees([STATES[i]["no_return"] for i in DOOMED])
    print(f"  point of no return over that set: {nr.min():.1f}..{nr.max():.1f} degrees, "
          f"median {np.median(nr):.1f}")
    print(f"  scoring.py reads the tilt from the settled pose, and a glass has no resting "
          f"place between upright and over, so a glass that leans past "
          f"{STANDING_TILT:.0f} degrees and rocks back still scores as standing; the strict "
          f"deadline is a design choice, not the scorer's")
    look = [how_it_looks(FAMILY[i], np.radians(STANDING_TILT)) for i in range(SWEEP)]
    wider = np.array([w for w, _ in look])
    higher = np.array([h for _, h in look])
    print(f"  at {STANDING_TILT:.0f} degrees the outline from above has grown by "
          f"{wider.min():.0f}..{wider.max():.0f} mm, median {np.median(wider):.0f} mm, and the "
          f"tallest point has risen in {int((higher > 0).sum())} of {SWEEP} cases by "
          f"{higher.min():.0f}..{higher.max():.0f} mm")

    print("\n--- the timing budget, over the pushes that actually topple")
    windows = np.array([STATES[i]["window_ms"] for i in DOOMED])
    physical = np.array([STATES[i]["physical_window_ms"] for i in DOOMED])
    kept_w = np.array([STATES[i]["window_ms"] for i in KEPT])
    print(f"a correct check keeps {len(KEPT)} and refuses {len(REFUSED)}; its windows are "
          f"{kept_w.min():.0f}..{kept_w.max():.0f} ms, median {np.median(kept_w):.0f}")
    print(f"the set this detector has to catch is the {len(DOOMED)} authorised by the "
          f"careless check and toppled by the real table")
    print(f"window to the point of no return at {PUSH_SPEED:.0f} mm/s: "
          f"{physical.min():.0f}..{physical.max():.0f} ms, median {np.median(physical):.0f}")
    print(f"window to the earlier of the two deadlines at {PUSH_SPEED:.0f} mm/s: "
          f"{windows.min():.0f}..{windows.max():.0f} ms, "
          f"median {np.median(windows):.0f} ms, 5th percentile "
          f"{np.percentile(windows, 5):.0f} ms")
    print(f"  in samples: {windows.min() / SAMPLE_MS:.1f}..{windows.max() / SAMPLE_MS:.1f}, "
          f"median {np.median(windows) / SAMPLE_MS:.1f}, 5th percentile "
          f"{np.percentile(windows, 5) / SAMPLE_MS:.1f}")
    for speed in (10.0, 15.0, PUSH_SPEED, 30.0, 40.0, 60.0, 80.0):
        rows = [tipping(FAMILY[i], speed_mms=speed) for i in DOOMED]
        w = np.array([row["window_ms"] for row in rows])
        pw = np.array([row["physical_window_ms"] for row in rows])
        print(f"  at {speed:>4.0f} mm/s: to {STANDING_TILT:.0f} deg or no-return, whichever "
              f"first — median {np.median(w):>5.0f} ms, worst {w.min():>4.0f} ms, "
              f"{int((w < CHAIN_MS).sum()):>3d} of {len(w)} short; to no-return alone — "
              f"median {np.median(pw):>5.0f} ms, worst {pw.min():>4.0f} ms, "
              f"{int((pw < CHAIN_MS).sum()):>3d} short")
    feet = np.array([2000.0 * STATES[i]["half_base"] for i in DOOMED])
    print(f"the feet of the doomed set: {feet.min():.1f}..{feet.max():.1f} mm, median "
          f"{np.median(feet):.1f} mm")
    shed = np.array([100.0 * (1.0 - tip_force(STATES[i], STATES[i]["deadline"])
                              / STATES[i]["onset_force"]) for i in DOOMED])
    print(f"per cent of the onset force already shed by the point of no return: "
          f"{shed.min():.0f}..{shed.max():.0f}, median {np.median(shed):.0f}")
    lift = np.array([1000.0 * STATES[i]["reach"]
                     * (np.cos(STATES[i]["balance"] - STATES[i]["deadline"])
                        - np.cos(STATES[i]["balance"])) for i in DOOMED])
    print(f"how far the centre of mass has risen by then, which is how far it drops when "
          f"the glass rocks back: {lift.min():.1f}..{lift.max():.1f} mm, median "
          f"{np.median(lift):.1f} mm")
    margin = np.array([topple_height(2000.0 * STATES[i]["half_base"], MU_LOW) - PUSH_HEIGHT
                       for i in DOOMED])
    print(f"correlation between a glass's window and its geometric margin: "
          f"{np.corrcoef(windows, margin)[0, 1]:.2f}")
    print(f"free fall past the balance point, over the whole family: to 30 degrees "
          f"{min(fall_time_ms(s, 30.0) for s in STATES):.0f}.."
          f"{max(fall_time_ms(s, 30.0) for s in STATES):.0f} ms; to 90 degrees "
          f"{min(fall_time_ms(s, 90.0) for s in STATES):.0f}.."
          f"{max(fall_time_ms(s, 90.0) for s in STATES):.0f} ms")

    print("\n--- the worked example and the hard case")
    describe("example", FAMILY[EXAMPLE], STATES[EXAMPLE])
    example_slow = tipping(FAMILY[EXAMPLE], speed_mms=SLOW_PUSH)
    print(f"    at {SLOW_PUSH:.0f} mm/s its window is {example_slow['window_ms']:.0f} ms")
    print(f"    the friction that would make it tip at {PUSH_HEIGHT:.0f} mm: above "
          f"{1000.0 * STATES[EXAMPLE]['half_base'] / PUSH_HEIGHT:.2f}; at the jaw's middle "
          f"({JAW_MIDDLE:.0f} mm) a careless check would have allowed up to "
          f"{1000.0 * STATES[EXAMPLE]['half_base'] / JAW_MIDDLE:.2f}")
    example = STATES[EXAMPLE]
    first_50 = (example["onset_force"] - tip_force(example, example["omega"] * 0.05)) / 0.05
    print(f"    tip onset {example['onset_force']:.2f} N falls to zero over "
          f"{example['to_balance_ms']:.0f} ms, so it sheds "
          f"{example['onset_force'] / example['to_balance_ms'] * 1000:.1f} N/s on average "
          f"and {first_50:.1f} N/s over the first 50 ms")
    print(f"    the pad is {PAD_HEIGHT:.0f} mm tall, so the torque the moving contact can add "
          f"is at most {STATES[EXAMPLE]['onset_force'] * PAD_HEIGHT / 1000.0 * 1000:.1f} mN m, "
          f"and the vertical force at most {PAD_GRIP:.1f} x "
          f"{STATES[EXAMPLE]['onset_force']:.2f} N = "
          f"{PAD_GRIP * STATES[EXAMPLE]['onset_force']:.2f} N")
    describe("tightest kept", FAMILY[TIGHTEST], STATES[TIGHTEST])
    for label, outline in (("cast: the wide foot", WIDE_FOOT),
                           ("cast: the narrow foot", NARROW_FOOT)):
        describe(label, outline, tipping(outline))
        half = 1000.0 * float(outline.radius[0])
        print(f"    at {PUSH_HEIGHT:.0f} mm — pushable at mu={MU_LOW}: "
              f"{pushable(2 * half, MU_LOW, PUSH_HEIGHT)}; at the real mu={TRUE_MU}: "
              f"{pushable(2 * half, TRUE_MU, PUSH_HEIGHT)}; at mu={MU_HIGH}: "
              f"{pushable(2 * half, MU_HIGH, PUSH_HEIGHT)}; "
              f"tips at mu={MU_HIGH}: {tips(2 * half, PUSH_HEIGHT, MU_HIGH)}")
    print(f"the shared cast holds {len(CAST)} glasses; "
          f"base_width(100, 0.58) = {base_width(100.0, 0.58):.1f} mm")


def main() -> None:
    report()
    print()
    over_the_leading_edge()
    no_threshold_separates()
    slide_against_tip()
    the_timing_budget()
    how_many_samples()


if __name__ == "__main__":
    main()
