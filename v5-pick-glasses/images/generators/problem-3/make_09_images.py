"""Diagrams for solution 9 — identify the contact parameters.

Every glass in these pictures is one the project's own spawner drew. Nothing is
a size typed in here: ``work_cell.glasses.shapes.family`` supplies the outlines,
``work_cell.glasses.spawn.SpawnedGlass`` supplies the mass and the height of the
centre of mass from the same shell model the simulator is told, and
``diagram_style`` supplies the tipping arithmetic every problem-3 document
shares.

The script prints every number the document quotes. If a number appears in
``09-identify-the-contact-parameters.md`` and not in this output, it was not
verified and does not belong there.

    pixi run python images/generators/problem-3/make_09_images.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from diagram_style import (
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
    TABLE_FRICTION,
    TITLE_SIZE,
    WARN,
    bare,
    glass_from_above,
    glass_from_the_side,
    new,
    push_arrow,
    push_margin,
    pushable,
    save,
    tips,
    topple_height,
)
from matplotlib.patches import Circle, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "work_cell"))

from work_cell.glasses.force import GRAVITY  # noqa: E402
from work_cell.glasses.shapes import KIND_RANGES, build, family  # noqa: E402
from work_cell.glasses.spawn import SpawnedGlass  # noqa: E402

KIND = "tapered_glass"
DRAWN = 400            # how many glasses of the kind the curve is computed over
SEED = 0

# The survey's own resolution, from the cell: 450 mm up through a 320-wide frame
# 1.047 rad across. Drawn as a scale bar so that a predicted drift can be
# compared against what the camera could actually see.
SURVEY_PIXEL = 1.62    # mm on the table, docs/the-cell.md

# What the table's friction really is. This is not a choice made for these
# pictures: it is problem-3-sim/bench.py's TABLE_FRICTION, the number the
# simulator applies and every run is scored against. The arm is never told it,
# which is the whole of this solution, and it is what lets an estimate here be
# checked rather than merely reported.
MU_TRUE = TABLE_FRICTION

# One reading of one force channel, assumed. The cell specifies the wrist
# sensor's rate but not its noise, so this is a stated assumption and every
# error below is quoted against it.
FORCE_NOISE_N = 0.05
FORCE_RATE_HZ = 100.0

# The probe push: how far the glass is moved and how fast the steady part of it
# goes. Both are commanded, so both are known exactly.
PROBE_LENGTH_MM = 10.0
PROBE_SPEED_MM_S = 20.0


# --------------------------------------------------------------------------- #
# The kind, measured rather than declared
# --------------------------------------------------------------------------- #

def measured(kind: str, count: int, seed: int):
    """Every glass of ``kind`` the spawner draws, with what the cell knows of it.

    Returns arrays in millimetres and grams. The mass and the centre of mass
    come from ``SpawnedGlass``, which is the same shell model the simulator is
    handed, so they are the glass's real properties and not a guess at them.
    """
    rows = []
    for index, (outline, _) in enumerate(family(kind, count, seed)):
        glass = SpawnedGlass(name=f"g{index}", kind=kind, outline=outline,
                             position=(0.0, 0.0, 0.0), yaw=0.0)
        mass, centre, _, _ = glass.mass_properties
        rows.append((
            2000.0 * outline.radius[0],                     # foot diameter, mm
            1000.0 * outline.total_height,                  # height, mm
            1000.0 * outline.max_diameter,                  # rim diameter, mm
            1000.0 * mass,                                  # mass, g
            1000.0 * centre,                                # centre of mass, mm
            1000.0 * outline.diameter_at(JAW_TOP / 1000.0),      # width where the jaw meets it
        ))
    return np.array(rows).T


def declared_mass_range(kind: str, steps: int = 9) -> tuple[float, float]:
    """The lightest and heaviest glass the kind's declared range allows, in grams.

    This is what the arm may assume about a glass it has not weighed, and it is
    derived from ``KIND_RANGES`` rather than written down, so it moves if the
    range does.
    """
    ranges = KIND_RANGES[kind]
    grid = np.linspace
    masses = []
    for height in grid(*ranges["height"], steps):
        for rim in grid(*ranges["rim_diameter"], steps):
            for fraction in grid(*ranges["base_fraction"], steps):
                outline = build(kind, height=height, rim_diameter=rim, base_fraction=fraction)
                glass = SpawnedGlass(name="probe", kind=kind, outline=outline,
                                     position=(0.0, 0.0, 0.0), yaw=0.0)
                masses.append(1000.0 * glass.mass)
    return float(min(masses)), float(max(masses))


def share_pushable(feet: np.ndarray, mu: float, height: float = JAW_TOP) -> float:
    """What share of these glasses could be pushed at ``height`` without tipping.

    The default is the top edge of the jaw, not the height the jaw's middle
    rides at. A tapered glass is wider higher up, so the top edge is what it
    meets, and that is where the push lands.
    """
    return float(np.mean([pushable(foot, mu, height) for foot in feet]))


def pick(feet: np.ndarray, percentile: float) -> int:
    """The index of the drawn glass whose foot is nearest a percentile of the kind."""
    return int(np.argmin(np.abs(feet - np.percentile(feet, percentile))))


# --------------------------------------------------------------------------- #
# What a pair of pushes can say about mu
# --------------------------------------------------------------------------- #

def force_readings(mass_g: float, mu: float, acceleration: float) -> tuple[float, float]:
    """The wrist force during the steady part of a push and during the brisk part.

    A glass sliding at constant speed needs only the friction, ``mu m g``. A
    glass being accelerated needs that plus ``m a``. Two readings, two unknowns,
    which is what makes ``mu`` separable from the mass at all.
    """
    mass = mass_g / 1000.0
    return mu * mass * GRAVITY, mass * (mu * GRAVITY + acceleration)


def mu_from_pair(steady: float, brisk: float, acceleration: float) -> float:
    """Solve ``mu`` out of the two readings. The mass cancels; the noise does not."""
    return acceleration * steady / (GRAVITY * (brisk - steady))


def samples_in(distance_mm: float, speed_mm_s: float) -> float:
    """How many force readings a slide of this length yields at the wrist's rate."""
    return max(1.0, FORCE_RATE_HZ * distance_mm / speed_mm_s)


def pair_error(mass_g: float, mu: float, acceleration: float,
               steady_samples: float, brisk_samples: float) -> float:
    """The relative error in ``mu`` from one push pair, as a fraction.

    Both readings are averages over their phase, so the noise on each falls with
    the square root of the number of samples. The estimate divides by the
    difference between the two, so the error in ``mu`` is the error in that
    difference, scaled up by how small the difference is.
    """
    steady, brisk = force_readings(mass_g, mu, acceleration)
    spread = np.hypot(FORCE_NOISE_N / np.sqrt(steady_samples),
                      FORCE_NOISE_N / np.sqrt(brisk_samples))
    # d(mu)/mu from the difference alone dominates; the steady term adds a little.
    return float(np.hypot(spread / (brisk - steady),
                          FORCE_NOISE_N / np.sqrt(steady_samples) / steady))


def probe_phases(acceleration: float) -> tuple[float, float, float]:
    """Length, speed and sample count of the brisk half of a probe push.

    The probe is one push in two halves. The first half slides at the steady
    probe speed, which is where the friction force is read. The second half
    accelerates away from that speed, which is where the force rises. Both
    halves are commanded, so the speed the second one reaches is arithmetic.
    """
    half = PROBE_LENGTH_MM / 2.0
    start = PROBE_SPEED_MM_S / 1000.0
    reached = np.sqrt(start**2 + 2.0 * acceleration * half / 1000.0)    # m/s
    duration = (reached - start) / acceleration
    return half, reached * 1000.0, max(1.0, FORCE_RATE_HZ * duration)


def estimate_spread(mass_g: np.ndarray, mu: float, acceleration: float,
                    pairs: int, trials: int) -> tuple[float, float, float]:
    """Monte-Carlo the pooled estimate of ``mu`` from ``pairs`` push pairs.

    Each pair lands on a different glass, so each carries a different mass. The
    mass cancels out of every pair on its own, which is why the pairs can be
    averaged at all.

    The random stream is seeded from ``pairs`` alone, so every figure this
    function produces is the same on every run and does not move when unrelated
    code above it is added or removed.
    """
    rng = np.random.default_rng(1000 + pairs)
    _, _, brisk_samples = probe_phases(acceleration)
    steady_samples = samples_in(PROBE_LENGTH_MM / 2.0, PROBE_SPEED_MM_S)
    out = []
    for _ in range(trials):
        chosen = rng.choice(mass_g, size=pairs, replace=False)
        got = []
        for mass in chosen:
            steady, brisk = force_readings(float(mass), mu, acceleration)
            steady += rng.normal(0.0, FORCE_NOISE_N / np.sqrt(steady_samples))
            brisk += rng.normal(0.0, FORCE_NOISE_N / np.sqrt(brisk_samples))
            if brisk - steady > 1e-6:
                got.append(mu_from_pair(steady, brisk, acceleration))
        out.append(np.median(got) if got else np.nan)
    out = np.array(out)
    return (float(np.nanpercentile(out, 5)), float(np.nanmedian(out)),
            float(np.nanpercentile(out, 95)))


def turn_and_drift(foot_mm: float, offset_mm: float, spread: float,
                   length_mm: float = PROBE_LENGTH_MM) -> tuple[float, float, float]:
    """How far an off-centre push turns a glass, and how far sideways it walks.

    Under the standard quasi-static approximation the glass turns at a rate set
    by the torque the push applies about the foot's centre, so a push of length
    ``length_mm`` offset by ``offset_mm`` turns it through ``length*offset/c^2``
    about a centre ``c^2/offset`` away, where ``c`` is the length that describes
    how the weight is spread over the foot.

    Returns the characteristic length, the turn in radians, and the sideways
    drift of the glass's own centre in millimetres. The drift is what an
    overhead camera could see; the turn, on a circular glass, is not.
    """
    c = spread * foot_mm / 2.0
    radius = c**2 / offset_mm
    turn = length_mm * offset_mm / c**2
    return c, turn, float(radius * (1.0 - np.cos(turn)))


# --------------------------------------------------------------------------- #
# Diagram 1 — what knowing mu is worth
# --------------------------------------------------------------------------- #

def diagram_worth(feet: np.ndarray, mus: np.ndarray, shares: np.ndarray,
                  shares_at_middle: np.ndarray) -> None:
    """The curve, at the height the glass is really pushed and at the jaw's middle."""
    figure, (left, right) = new(12.0, 4.5, columns=2)

    left.plot(mus, 100.0 * shares_at_middle, color=MUTED, lw=1.8, ls=(0, (5, 3)), zorder=3)
    left.plot(mus, 100.0 * shares, color=GLASS, lw=2.4, zorder=4)
    left.axvspan(MU_LOW, MU_HIGH, color=MUTED, alpha=0.12, zorder=1)
    truth = 100.0 * share_pushable(feet, MU_TRUE)
    left.plot([MU_TRUE, MU_TRUE], [0.0, truth], color=INK, lw=1.4, zorder=3)
    left.plot([MU_TRUE], [truth], "o", color=INK, ms=7, zorder=7)
    left.annotate(f"the simulator's own μ = {MU_TRUE:.2f}:\nonly {truth:.1f}% can be pushed",
                  xy=(MU_TRUE, truth), xytext=(MU_TRUE + 0.075, 15.0),
                  color=INK, fontsize=NOTE_SIZE, va="center",
                  arrowprops=dict(arrowstyle="->", color=INK, lw=0.9))
    for mu, colour, where in ((MU_LOW, GOOD, (0.155, 78.0)), (MU_HIGH, WARN, (0.545, 26.0))):
        share = 100.0 * share_pushable(feet, mu)
        left.plot([mu], [share], "o", color=colour, ms=7, zorder=6)
        left.annotate(f"a guess of {mu:.2f} says\n{share:.1f}% can be pushed",
                      xy=(mu, share), xytext=where,
                      color=colour, fontsize=NOTE_SIZE, va="center",
                      arrowprops=dict(arrowstyle="->", color=colour, lw=0.8))
    at_middle = 100.0 * share_pushable(feet, MU_TRUE, LOWEST_GRIP)
    left.annotate("", xy=(MU_TRUE, truth), xytext=(MU_TRUE, at_middle),
                  arrowprops=dict(arrowstyle="<->", color=WARN, lw=1.4))
    left.text(MU_TRUE + 0.008, (truth + at_middle) / 2.0, f"{at_middle - truth:.0f} points",
              color=WARN, fontsize=NOTE_SIZE, ha="left", va="center")
    left.text(0.155, 127.0,
              f"dashed: pushed at the jaw's middle, {LOWEST_GRIP:.0f} mm\n"
              f"solid: pushed where a tapered glass really meets it, {JAW_TOP:.0f} mm\n"
              f"at the true μ the two disagree by {at_middle - truth:.1f} points of the kind",
              color=INK, fontsize=NOTE_SIZE, va="top")
    left.set_xlabel("friction between glass and table, μ", fontsize=LABEL_SIZE)
    left.set_ylabel(f"share of {DRAWN} drawn glasses that\ncan be pushed at all (%)",
                    fontsize=LABEL_SIZE)
    left.set_title("Fifteen millimetres of jaw move the answer by forty points",
                   fontsize=TITLE_SIZE, color=INK)
    left.set_xlim(mus[0], mus[-1])
    left.set_ylim(-5, 130)
    left.grid(color=MUTED, alpha=0.22, lw=0.6)
    left.tick_params(labelsize=NOTE_SIZE, colors=MUTED)

    right.hist(feet, bins=26, color=GLASS, alpha=0.35, edgecolor=GLASS, lw=0.8, zorder=3)
    top = right.get_ylim()[1]
    for mu, colour, height in ((MU_LOW, GOOD, 0.99), (MU_TRUE, INK, 0.80), (MU_HIGH, WARN, 0.61)):
        need = 2.0 * mu * JAW_TOP
        right.axvline(need, color=colour, lw=1.6, ls=(0, (4, 3)), zorder=5)
        side = "right" if mu == MU_LOW else "left"
        right.text(need + (-0.7 if side == "right" else 0.7), top * height,
                   f"at μ = {mu:.2f} the foot\nmust beat {need:.0f} mm",
                   color=colour, fontsize=NOTE_SIZE, va="top", ha=side)
    right.set_xlim(23.0, 92.0)
    right.set_xlabel(f"the foot the glass stands on (mm), {DRAWN} drawn glasses",
                     fontsize=LABEL_SIZE)
    right.set_ylabel("how many", fontsize=LABEL_SIZE)
    right.set_title(f"A glass is pushable only if its foot beats 2 × {JAW_TOP:.0f} × μ",
                    fontsize=TITLE_SIZE, color=INK)
    right.grid(axis="y", color=MUTED, alpha=0.22, lw=0.6)
    right.tick_params(labelsize=NOTE_SIZE, colors=MUTED)

    figure.tight_layout()
    save(figure, "09-what-knowing-mu-is-worth.png")


# --------------------------------------------------------------------------- #
# Diagram 2 — what one push actually measures
# --------------------------------------------------------------------------- #

def diagram_what_a_push_measures(foot, height, rim, centre, width_at_push,
                                 steady_force, drifts) -> None:
    """One drawn glass, and the two things a push on it could be read for."""
    figure, (left, right) = new(12.4, 4.9, columns=2)
    fraction = foot / rim

    # ---- from the side: where the push really lands, and what the force says.
    glass_from_the_side(left, 0.0, height, rim, fraction, alpha=0.22)
    left.plot([-rim * 1.00, rim * 1.00], [0, 0], color=INK, lw=1.7, zorder=5)
    limit = topple_height(foot, MU_TRUE)
    at_push = width_at_push / 2.0

    # The jaw, to scale: its middle rides at LOWEST_GRIP and it is FINGER_HEIGHT
    # tall, so a glass that widens upwards meets its top edge, not its middle.
    jaw_left = -at_push - 62.0
    left.add_patch(Rectangle((jaw_left, LOWEST_GRIP - FINGER_HEIGHT / 2.0),
                             62.0 - 3.0, FINGER_HEIGHT, facecolor=MUTED, alpha=0.35,
                             edgecolor=INK, lw=1.0, zorder=6))
    push_arrow(left, (jaw_left + 8.0, LOWEST_GRIP), (jaw_left + 50.0, LOWEST_GRIP), lw=2.0)
    left.text(jaw_left - 6.0, LOWEST_GRIP,
              f"the wrist reads\n{steady_force:.2f} N while it slides",
              color=INK, fontsize=NOTE_SIZE, ha="right", va="center")
    left.text(jaw_left, LOWEST_GRIP - FINGER_HEIGHT / 2.0 - 5.0,
              f"the jaw: its middle rides at {LOWEST_GRIP:.0f} mm,\n"
              f"and it is {FINGER_HEIGHT:.0f} mm tall",
              color=MUTED, fontsize=NOTE_SIZE, ha="left", va="top")

    left.plot([jaw_left, rim * 1.00], [JAW_TOP] * 2, color=INK, lw=1.3, zorder=7)
    left.text(rim * 1.04, JAW_TOP,
              f"its top edge, {JAW_TOP:.0f} mm — where a tapered glass meets it",
              color=INK, fontsize=NOTE_SIZE, va="center")
    left.plot([-rim * 0.40, rim * 1.00], [limit] * 2, color=WARN, lw=1.3,
              ls=(0, (4, 3)), zorder=4)
    left.text(rim * 1.04, limit,
              f"a/μ = {limit:.0f} mm, if μ really is {MU_TRUE:.2f} — only "
              f"{push_margin(foot, MU_TRUE, JAW_TOP):.0f} mm higher",
              color=WARN, fontsize=NOTE_SIZE, va="center")

    left.plot([0.0], [centre], "o", color=INK, ms=5, zorder=8)
    left.annotate(f"its weight acts {centre:.0f} mm up",
                  xy=(0.0, centre), xytext=(rim * 1.04, LOWEST_GRIP - 8.0),
                  color=INK, fontsize=NOTE_SIZE, ha="left", va="center",
                  arrowprops=dict(arrowstyle="->", color=INK, lw=0.8))
    left.annotate("", xy=(-foot / 2.0, -10.0), xytext=(foot / 2.0, -10.0),
                  arrowprops=dict(arrowstyle="<->", color=MUTED, lw=1.0))
    left.text(0.0, -14.0, f"foot 2a = {foot:.0f} mm", color=MUTED,
              fontsize=NOTE_SIZE, ha="center", va="top")
    left.text(jaw_left - 6.0, height * 1.40,
              f"F = μ m g, so {steady_force:.2f} N gives the product μm,\n"
              f"not μ. Nothing in this cell weighs a glass, so\n"
              f"the two cannot be told apart from this alone.",
              color=GLASS, fontsize=NOTE_SIZE, ha="left", va="top")
    left.set_title("From the side: the force names a product", fontsize=TITLE_SIZE, color=INK)
    left.set_xlim(jaw_left - 62.0, rim * 2.45)
    left.set_ylim(-34.0, height * 1.45)
    left.set_aspect("equal")
    bare(left)

    # ---- from above: how far the glass's centre walks sideways, against the offset.
    offsets, uniform, rim_held, turn_limit, usable = drifts
    top = max(uniform) * 1.10
    right.fill_between(offsets, 0.0, SURVEY_PIXEL, color=MUTED, alpha=0.22, zorder=2)
    right.text(offsets[0] + 0.4, SURVEY_PIXEL * 0.72, " one survey pixel",
               color=MUTED, fontsize=NOTE_SIZE, ha="left", va="center")
    right.plot(offsets, uniform, color=GOOD, lw=2.2, zorder=5)
    right.plot(offsets, rim_held, color=WARN, lw=2.2, zorder=5)
    right.text(offsets[-1] - 0.6, uniform[-1], "weight spread evenly ",
               color=GOOD, fontsize=NOTE_SIZE, ha="right", va="bottom")
    right.text(offsets[-1] - 0.6, rim_held[-1], "weight out on the rim ",
               color=WARN, fontsize=NOTE_SIZE, ha="right", va="top")
    right.axvline(turn_limit, color=INK, lw=1.3, zorder=6)
    right.text(turn_limit - 0.5, top * 0.99,
               "past here the turn is\nover 20°, and the sum\nthat drew these curves\n"
               "no longer describes it",
               color=INK, fontsize=NOTE_SIZE, ha="right", va="top")
    right.annotate("", xy=(turn_limit, usable[0]), xytext=(turn_limit, usable[1]),
                   arrowprops=dict(arrowstyle="<->", color=GLASS, lw=1.4))
    right.annotate(f"{abs(usable[1] - usable[0]):.2f} mm apart where\n"
                   f"the arithmetic still holds",
                   xy=(turn_limit, usable[0]),
                   xytext=(turn_limit + 3.6, SURVEY_PIXEL * 0.20),
                   color=GLASS, fontsize=NOTE_SIZE, ha="left", va="center",
                   arrowprops=dict(arrowstyle="->", color=GLASS, lw=0.8))
    right.set_xlabel("how far off the centre the push is aimed, d (mm)", fontsize=LABEL_SIZE)
    right.set_ylabel("how far the glass's centre walks sideways (mm)", fontsize=LABEL_SIZE)
    right.set_title("From above: the answer is smaller than the camera",
                    fontsize=TITLE_SIZE, color=INK)
    right.set_xlim(0.0, offsets[-1])
    right.set_ylim(0.0, top)
    right.grid(color=MUTED, alpha=0.22, lw=0.6)
    right.tick_params(labelsize=NOTE_SIZE, colors=MUTED)

    figure.tight_layout()
    save(figure, "09-what-a-push-measures.png")


# --------------------------------------------------------------------------- #
# Diagram 3 — how wide the estimate is
# --------------------------------------------------------------------------- #

def diagram_how_wide(accelerations, errors, speeds, spreads) -> None:
    figure, (left, right) = new(11.8, 4.3, columns=2)

    left.plot(accelerations, 100.0 * np.array(errors), color=GLASS, lw=2.2, zorder=4)
    left.axhline(10.0, color=GOOD, lw=1.4, ls=(0, (4, 3)), zorder=3)
    left.text(accelerations[-1], 12.0, "10%: tight enough to decide ",
              color=GOOD, fontsize=NOTE_SIZE, ha="right", va="bottom")
    for step, (acceleration, speed) in enumerate(speeds):
        error = 100.0 * errors[int(np.argmin(np.abs(np.array(accelerations) - acceleration)))]
        left.plot([acceleration], [error], "o", color=INK, ms=5, zorder=6)
        left.annotate(f"{acceleration:.1f} m/s² reaches {speed:.0f} mm/s",
                      xy=(acceleration, error),
                      xytext=(2.5, 45.0 + 17.0 * (len(speeds) - 1 - step)),
                      color=INK, fontsize=NOTE_SIZE,
                      arrowprops=dict(arrowstyle="-", color=INK, lw=0.7))
    left.set_xlabel("how briskly the brisk half of the probe accelerates (m/s²)",
                    fontsize=LABEL_SIZE)
    left.set_ylabel("error in μ from one push pair (%)", fontsize=LABEL_SIZE)
    left.set_title("A gentle push tells you almost nothing about μ",
                   fontsize=TITLE_SIZE, color=INK)
    left.set_ylim(0, 108)
    left.set_xlim(accelerations[0], accelerations[-1])
    left.grid(color=MUTED, alpha=0.22, lw=0.6)
    left.tick_params(labelsize=NOTE_SIZE, colors=MUTED)

    rows = list(range(len(spreads)))
    for row, (_, low, middle, high) in zip(rows, spreads, strict=True):
        beats = low > MU_LOW and high < MU_HIGH
        colour = GOOD if beats else GLASS
        right.plot([low, high], [row, row], color=colour, lw=7.0, solid_capstyle="butt",
                   alpha=0.55, zorder=4)
        right.plot([middle], [row], "|", color=colour, ms=18, mew=2.0, zorder=6)
        right.text(high + 0.006, row, f"  {low:.3f} to {high:.3f}", color=colour,
                   fontsize=NOTE_SIZE, va="center")
    right.axvline(MU_TRUE, color=INK, lw=1.4, zorder=5)
    right.text(MU_TRUE, len(rows) - 0.10, f"the table's real μ = {MU_TRUE:.2f}",
               color=INK, fontsize=NOTE_SIZE, ha="center", va="top")
    for mu in (MU_LOW, MU_HIGH):
        right.axvline(mu, color=MUTED, lw=1.2, ls=(0, (4, 3)), zorder=3)
    right.text(MU_LOW + 0.004, -0.62, "what a guess offers instead: anywhere in here",
               color=MUTED, fontsize=NOTE_SIZE)
    right.annotate("", xy=(MU_LOW, -0.42), xytext=(MU_HIGH, -0.42),
                   arrowprops=dict(arrowstyle="<->", color=MUTED, lw=1.0))
    right.set_yticks(rows)
    right.set_yticklabels([f"{pairs} push pair{'s' if pairs > 1 else ''}"
                           for pairs, _, _, _ in spreads], fontsize=NOTE_SIZE)
    right.set_xlabel("μ, the 5th to 95th percentile of the estimate", fontsize=LABEL_SIZE)
    right.set_title("Twenty pairs beat the guess; one pair does not",
                    fontsize=TITLE_SIZE, color=INK)
    right.set_xlim(MU_LOW - 0.050, MU_HIGH + 0.095)
    right.set_ylim(-0.9, len(rows) - 0.02)
    right.grid(axis="x", color=MUTED, alpha=0.22, lw=0.6)
    right.tick_params(labelsize=NOTE_SIZE, colors=MUTED)

    figure.tight_layout()
    save(figure, "09-how-wide-the-estimate-is.png")


# --------------------------------------------------------------------------- #
# Diagram 4 — per object, or per table
# --------------------------------------------------------------------------- #

def diagram_per_object_or_per_table(mass_g, feet, rims, chosen, odd_index, odd_mu,
                                    band_feet, band_low, band_high, pair, odd_force) -> None:
    """Why one estimate may serve a whole table, and how one glass breaks that."""
    figure, (left, right) = new(12.4, 4.6, columns=2)

    ordinary = np.array([index for index in chosen if index != odd_index])
    forces = MU_TRUE * mass_g[ordinary] / 1000.0 * GRAVITY

    # ---- two real glasses on the same table, one of them standing on a ring.
    first, second = pair
    apart = 0.60 * (rims[first] + rims[second])
    ring = feet[second] / 2.0 + 6.0
    left.add_patch(Circle((apart / 2.0, 0.0), ring, facecolor=WARN, alpha=0.30,
                          edgecolor=WARN, lw=1.2, zorder=1))
    for index, at in ((first, -apart / 2.0), (second, apart / 2.0)):
        glass_from_above(left, (at, 0.0), rims[index], feet[index] / rims[index],
                         alpha=0.22, zorder=3)
    left.text(-apart / 2.0, -rims[first] / 2.0 - 8.0,
              f"foot {feet[first]:.0f} mm,\nbare table",
              color=GLASS, fontsize=NOTE_SIZE, ha="center", va="top")
    left.text(apart / 2.0, -rims[second] / 2.0 - 8.0,
              f"foot {feet[second]:.0f} mm,\nstanding on a sticky ring",
              color=WARN, fontsize=NOTE_SIZE, ha="center", va="top")
    left.text(0.0, -apart * 0.74,
              "μ belongs to a pair of surfaces, not to a glass. The simulator gives\n"
              "every glass the same table friction, so one estimate is exactly right\n"
              "there. A real table is where the case on the right comes from.",
              color=INK, fontsize=NOTE_SIZE, ha="center", va="top")
    left.set_title("One table, one μ, until a foot meets something else",
                   fontsize=TITLE_SIZE, color=INK)
    left.set_xlim(-apart * 1.02, apart * 1.02)
    left.set_ylim(-apart * 1.16, apart * 0.66)
    left.set_aspect("equal")
    bare(left)

    # ---- the pool, and the one reading that does not sit in it.
    right.fill_between(band_feet, band_low, band_high, color=GLASS, alpha=0.18, zorder=2)
    right.plot(band_feet, band_low, color=GLASS, lw=0.9, alpha=0.7, zorder=3)
    right.plot(band_feet, band_high, color=GLASS, lw=0.9, alpha=0.7, zorder=3)
    right.text(band_feet[-1], 0.06,
               f"the blue band is where the kind's own masses put the reading at "
               f"μ = {MU_TRUE:.2f}, 5th to 95th ",
               color=GLASS, fontsize=NOTE_SIZE, ha="right", va="bottom")
    right.plot(feet[ordinary], forces, "o", color=GLASS, ms=8, zorder=5)
    right.plot([feet[odd_index]], [odd_force], "o", color=WARN, ms=9, zorder=6)
    right.annotate("the glass on the ring: the arm cannot\nweigh it, but it can see that it\n"
                   "does not read like the others",
                   xy=(feet[odd_index], odd_force),
                   xytext=(feet[odd_index] - 2.5, odd_force),
                   color=WARN, fontsize=NOTE_SIZE, ha="right", va="center",
                   arrowprops=dict(arrowstyle="->", color=WARN, lw=1.0))
    right.set_xlabel("the foot the survey measured (mm)", fontsize=LABEL_SIZE)
    right.set_ylabel("the force the wrist reads while it slides (N)", fontsize=LABEL_SIZE)
    right.set_title("Pooling gives an odd glass something to stand out against",
                    fontsize=TITLE_SIZE, color=INK)
    right.set_xlim(band_feet[0] - 1.0, band_feet[-1] + 1.0)
    right.set_ylim(0.0, max(band_high.max(), odd_force) * 1.28)
    right.grid(color=MUTED, alpha=0.22, lw=0.6)
    right.tick_params(labelsize=NOTE_SIZE, colors=MUTED)

    figure.tight_layout()
    save(figure, "09-per-object-or-per-table.png")


# --------------------------------------------------------------------------- #
# Diagram 5 — the verdict, before and after
# --------------------------------------------------------------------------- #

def _verdict_panel(axis, rows, mu_low, mu_high, title, undecided) -> None:
    for row, (label, foot) in enumerate(rows):
        high = topple_height(foot, mu_high)      # pessimistic mu, lowest ceiling
        low = topple_height(foot, mu_low)        # optimistic mu, highest ceiling
        if high > JAW_TOP:
            colour, verdict = GOOD, "pushed, whichever μ is true"
        elif low <= JAW_TOP:
            colour, verdict = WARN, "refused, whichever μ is true"
        else:
            colour, verdict = GLASS, undecided
        axis.plot([high, low], [row, row], color=colour, lw=9.0, alpha=0.5,
                  solid_capstyle="butt", zorder=4)
        axis.plot([high], [row], "|", color=colour, ms=20, mew=2.2, zorder=6)
        axis.text(low + 2.0, row, f"  {verdict}", color=colour, fontsize=NOTE_SIZE,
                  va="center")
        axis.text(-3.0, row, label, color=INK, fontsize=NOTE_SIZE, ha="right", va="center")
    axis.axvline(JAW_TOP, color=INK, lw=1.6, zorder=5)
    axis.text(JAW_TOP - 2.0, len(rows) - 0.35,
              f"the jaw's top edge rides at {JAW_TOP:.0f} mm ",
              color=INK, fontsize=NOTE_SIZE, ha="right")
    axis.set_yticks([])
    axis.set_xlabel("the height a push has to stay under, a/μ (mm)", fontsize=LABEL_SIZE)
    axis.set_title(title, fontsize=TITLE_SIZE, color=INK)
    axis.set_xlim(0.0, 112.0)
    axis.set_ylim(-0.8, len(rows) - 0.2)
    axis.grid(axis="x", color=MUTED, alpha=0.22, lw=0.6)
    axis.tick_params(labelsize=NOTE_SIZE, colors=MUTED)
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)


def diagram_verdict(rows, identified) -> None:
    figure, (left, right) = new(12.4, 4.4, columns=2)
    _verdict_panel(left, rows, MU_LOW, MU_HIGH,
                   f"Guessed: μ somewhere in [{MU_LOW:.2f}, {MU_HIGH:.2f}]",
                   "the guess decides, not the glass")
    _verdict_panel(right, rows, identified[0], identified[1],
                   f"Identified: μ in [{identified[0]:.3f}, {identified[1]:.3f}]",
                   "still too close to call")
    figure.tight_layout()
    save(figure, "09-the-verdict-as-mu-is-pinned-down.png")


# --------------------------------------------------------------------------- #

def main() -> None:
    feet, heights, rims, mass_g, centres, widths = measured(KIND, DRAWN, SEED)
    print(f"\n=== the kind, over {DRAWN} drawn {KIND}s at seed {SEED} ===")
    print(f"foot          {feet.min():.1f} to {feet.max():.1f} mm")
    print(f"height        {heights.min():.1f} to {heights.max():.1f} mm")
    print(f"rim           {rims.min():.1f} to {rims.max():.1f} mm")
    print(f"mass          {mass_g.min():.0f} to {mass_g.max():.0f} g, "
          f"a factor of {mass_g.max() / mass_g.min():.2f}")
    print(f"centre of mass {centres.min():.1f} to {centres.max():.1f} mm above the table")
    print(f"share with the centre of mass above the jaw's top edge: "
          f"{100.0 * np.mean(centres > JAW_TOP):.1f}%")
    light, heavy = declared_mass_range(KIND)
    print(f"the declared range allows {light:.0f} to {heavy:.0f} g, "
          f"a factor of {heavy / light:.2f}")
    print(f"foot width and mass are correlated at {np.corrcoef(feet, mass_g)[0, 1]:.2f}, so "
          f"measuring the foot barely narrows the mass")

    print("\n=== the share that can be pushed at all, against mu ===")
    mus = np.round(np.arange(0.15, 0.7001, 0.0025), 6)
    shares = np.array([share_pushable(feet, mu) for mu in mus])
    at_middle = np.array([share_pushable(feet, mu, LOWEST_GRIP) for mu in mus])
    for mu in sorted({0.20, 0.25, 0.30, 0.35, 0.40, MU_TRUE, 0.45, 0.50, 0.55, 0.60}):
        print(f"  mu {mu:.2f} -> {100.0 * share_pushable(feet, mu):5.1f}%   "
              f"(the foot must beat {2.0 * mu * JAW_TOP:.1f} mm)")
    ends = KIND_RANGES[KIND]
    narrowest = 1000.0 * ends["rim_diameter"][0] * ends["base_fraction"][0]
    widest = 1000.0 * ends["rim_diameter"][1] * ends["base_fraction"][1]
    print(f"the declared range allows feet of {narrowest:.1f} to {widest:.1f} mm, so the "
          f"cliff runs from mu {narrowest / (2 * JAW_TOP):.3f} to "
          f"{widest / (2 * JAW_TOP):.3f}")
    window = 0.02
    slopes = [(share_pushable(feet, mu - window / 2) - share_pushable(feet, mu + window / 2))
              / window for mu in np.arange(0.26, 0.591, 0.005)]
    steepest = float(np.max(slopes)) * 0.01 * 100.0
    at = 0.26 + 0.005 * int(np.argmax(slopes))
    print(f"the curve is steepest near mu {at:.3f}, falling {steepest:.1f} percentage "
          f"points for every 0.01 of mu")
    authorised = 100.0 * share_pushable(feet, MU_LOW)
    truly = 100.0 * share_pushable(feet, MU_TRUE)
    refused = 100.0 * share_pushable(feet, MU_HIGH)
    print(f"the simulator's own table friction is {MU_TRUE:.2f}, so the true answer is "
          f"{truly:.1f}%")
    print(f"an optimistic guess of {MU_LOW:.2f} authorises {authorised:.1f}%, which is "
          f"{authorised - truly:.1f} points of authorisations that would topple a glass")
    print(f"a pessimistic guess of {MU_HIGH:.2f} authorises {refused:.1f}%, which needlessly "
          f"refuses {truly - refused:.1f} points of the kind")
    print(f"the two guesses disagree by {authorised - refused:.1f} percentage points")
    band = [f for f in feet if pushable(f, MU_LOW, JAW_TOP) and not pushable(f, MU_TRUE, JAW_TOP)]
    print(f"the dangerous band is feet of {2.0 * MU_LOW * JAW_TOP:.1f} to "
          f"{2.0 * MU_TRUE * JAW_TOP:.1f} mm: {100.0 * len(band) / len(feet):.1f}% of the kind, "
          f"authorised by a guess of {MU_LOW:.2f} and toppled by the real {MU_TRUE:.2f}")
    print(f"at the jaw's middle, {LOWEST_GRIP:.0f} mm, the same guesses would say "
          f"{100.0 * share_pushable(feet, MU_LOW, LOWEST_GRIP):.1f}% and "
          f"{100.0 * share_pushable(feet, MU_HIGH, LOWEST_GRIP):.1f}%, and the truth would be "
          f"{100.0 * share_pushable(feet, MU_TRUE, LOWEST_GRIP):.1f}% — so mistaking the jaw's "
          f"middle for its top edge is worth "
          f"{100.0 * (share_pushable(feet, MU_TRUE, LOWEST_GRIP) - share_pushable(feet, MU_TRUE)):.1f} "
          f"points at the true mu, all of them in the dangerous direction")
    diagram_worth(feet, mus, shares, at_middle)

    print("\n=== the same curve over six different draws of the kind ===")
    for mu in (MU_LOW, MU_TRUE, 0.40, MU_HIGH):
        over = [100.0 * share_pushable(measured(KIND, DRAWN, other)[0], mu) for other in range(6)]
        print(f"  mu {mu:.2f}: {min(over):.1f}% to {max(over):.1f}% across seeds 0-5")
    medians = [float(np.median(measured(KIND, DRAWN, other)[0])) for other in range(6)]
    print(f"  the median foot of the kind is {min(medians):.1f} to {max(medians):.1f} mm across "
          f"those seeds, so the median glass stops being pushable above mu "
          f"{min(medians) / (2 * JAW_TOP):.3f} to {max(medians) / (2 * JAW_TOP):.3f}")
    fall = 100.0 * (share_pushable(feet, MU_TRUE) - share_pushable(feet, 0.40))
    print(f"  between mu {MU_TRUE:.2f} and 0.40 the share falls {fall:.1f} points")

    print("\n=== how accurate the estimate has to be ===")
    # Measured over a window wide enough to hold a useful number of glasses: a
    # narrower one is dominated by how many of the 400 happen to fall in it.
    step = 0.025
    slope = (share_pushable(feet, MU_TRUE - step) - share_pushable(feet, MU_TRUE + step)) / (2 * step)
    print(f"  across mu {MU_TRUE - step:.3f} to {MU_TRUE + step:.3f} the curve falls "
          f"{100.0 * slope * 0.01:.1f} points per 0.01 of mu")
    for target_points in (5.0, 10.0):
        need = target_points / (100.0 * slope)
        print(f"    knowing the share to +-{target_points:.0f} points needs mu to "
              f"+-{need:.3f}, which is +-{100.0 * need / MU_TRUE:.1f}% of it")
    for pairs in (10, 20, 40, 80):
        low, _, high = estimate_spread(mass_g, MU_TRUE, 1.0, pairs, 2000)
        print(f"    {pairs:3d} push pairs give +-{(high - low) / 2.0:.4f}, which is the share "
              f"to +-{100.0 * slope * (high - low) / 2.0:.1f} points")

    print("\n=== one glass, one push ===")
    index = pick(feet, 95.0)
    foot, height, rim = feet[index], heights[index], rims[index]
    mass, centre, width = mass_g[index], centres[index], widths[index]
    steady, _ = force_readings(mass, MU_TRUE, 0.0)
    print(f"glass {index}: foot {foot:.1f} mm, height {height:.1f} mm, rim {rim:.1f} mm, "
          f"{mass:.0f} g, centre of mass {centre:.1f} mm up, {width:.1f} mm wide where "
          f"the gripper touches it")
    print(f"pushed at {JAW_TOP:.0f} mm on a table of mu {MU_TRUE:.2f}, the wrist reads "
          f"{steady:.3f} N; a/mu is {topple_height(foot, MU_TRUE):.1f} mm")
    print(f"the same reading over the declared mass range gives mu in "
          f"[{steady / (GRAVITY * heavy / 1000.0):.3f}, {steady / (GRAVITY * light / 1000.0):.3f}], "
          f"a factor of {heavy / light:.2f}")
    print(f"half the foot, a, is {foot / 2.0:.2f} mm, so at the optimistic guess of "
          f"{MU_LOW:.2f} its ceiling would be {topple_height(foot, MU_LOW):.1f} mm and at "
          f"the pessimistic {MU_HIGH:.2f} it would be {topple_height(foot, MU_HIGH):.1f} mm, "
          f"against a jaw top of {JAW_TOP:.0f} mm")
    print(f"does that push tip it at mu {MU_TRUE:.2f}? "
          f"{'yes' if tips(foot, JAW_TOP, MU_TRUE) else 'no'}; "
          f"it leaves {push_margin(foot, MU_TRUE, JAW_TOP):.1f} mm of margin")
    print(f"the no-tip bound that push then proves: mu < a/h = {foot / 2.0 / JAW_TOP:.3f}")
    narrowest_ok = min(f for f in feet if not tips(f, JAW_TOP, MU_TRUE))
    print(f"the narrowest foot in the kind that survives a push at {JAW_TOP:.0f} mm is "
          f"{narrowest_ok:.1f} mm, which would prove mu < {narrowest_ok / 2.0 / JAW_TOP:.3f}")
    offsets = np.linspace(1.0, width / 2.0, 120)
    uniform = np.array([turn_and_drift(foot, d, 2.0 / 3.0) for d in offsets])
    rim_held = np.array([turn_and_drift(foot, d, 1.0) for d in offsets])
    turn_limit = float(np.interp(np.radians(20.0), uniform[:, 1], offsets))
    usable = (float(np.interp(turn_limit, offsets, rim_held[:, 2])),
              float(np.interp(turn_limit, offsets, uniform[:, 2])))
    print(f"an off-centre push turns the glass through {np.degrees(uniform[0, 1]):.0f} to "
          f"{np.degrees(uniform[-1, 1]):.0f} degrees as the offset runs from "
          f"{offsets[0]:.0f} to {offsets[-1]:.0f} mm, if its weight is spread evenly; "
          f"c is {uniform[0, 0]:.1f} mm for an even spread and {rim_held[0, 0]:.1f} mm "
          f"for weight out on the rim")
    print(f"one survey pixel covers {SURVEY_PIXEL:.2f} mm of table")
    print(f"the turn passes 20 degrees at an offset of {turn_limit:.1f} mm; there the "
          f"centre walks {usable[1]:.2f} mm under an even spread and {usable[0]:.2f} mm "
          f"under a rim-held one, a difference of {abs(usable[1] - usable[0]):.2f} mm, "
          f"which is {abs(usable[1] - usable[0]) / SURVEY_PIXEL:.2f} survey pixels")
    at_widest = (rim_held[-1, 2], uniform[-1, 2])
    print(f"even at the widest offset the gripper could reach, {offsets[-1]:.0f} mm, the "
          f"difference is only {abs(at_widest[1] - at_widest[0]):.2f} mm, or "
          f"{abs(at_widest[1] - at_widest[0]) / SURVEY_PIXEL:.2f} survey pixels")
    diagram_what_a_push_measures(foot, height, rim, centre, width, steady,
                                 (offsets, uniform[:, 2], rim_held[:, 2], turn_limit, usable))

    print("\n=== separating mu from the mass, and what it costs ===")
    steady_samples = samples_in(PROBE_LENGTH_MM / 2.0, PROBE_SPEED_MM_S)
    print(f"the steady half of a {PROBE_LENGTH_MM:.0f} mm probe at "
          f"{PROBE_SPEED_MM_S:.0f} mm/s gives {steady_samples:.0f} force readings, so an "
          f"assumed {FORCE_NOISE_N:.2f} N per reading averages to "
          f"{FORCE_NOISE_N / np.sqrt(steady_samples):.3f} N")
    accelerations = np.round(np.arange(0.05, 4.001, 0.025), 4)
    errors, speeds = [], []
    for acceleration in accelerations:
        _, reached, brisk_samples = probe_phases(float(acceleration))
        errors.append(pair_error(mass, MU_TRUE, float(acceleration),
                                 steady_samples, brisk_samples))
        if np.isclose(acceleration, [0.1, 0.5, 1.0, 2.0, 4.0]).any():
            brisk_force = force_readings(mass, MU_TRUE, float(acceleration))[1]
            print(f"  {acceleration:.2f} m/s^2: reaches {reached:.0f} mm/s over "
                  f"{PROBE_LENGTH_MM / 2:.0f} mm, {brisk_samples:.0f} readings, force rises "
                  f"from {steady:.3f} to {brisk_force:.3f} N, a difference of "
                  f"{brisk_force - steady:.3f} N, error in mu {100.0 * errors[-1]:.0f}%")
            if 0.5 <= acceleration <= 2.0:
                speeds.append((float(acceleration), reached))
    worst = JAW_TOP - centres.min()
    print(f"the acceleration term in the centre of pressure is (h - h_cm) x a/g; h is now "
          f"{JAW_TOP:.0f} mm and {100.0 * np.mean(centres > JAW_TOP):.1f}% of the kind has "
          f"its centre of mass above that, so for those the term is negative and helps")
    print(f"  for the rest — {100.0 * np.mean(centres <= JAW_TOP):.1f}% of the kind — it is "
          f"positive, at most {worst:.1f} mm, which moves the centre of "
          f"pressure {worst * 1.0 / GRAVITY:.2f} mm at 1 m/s^2 and "
          f"{worst * 4.0 / GRAVITY:.2f} mm at 4 m/s^2, against a half-foot of "
          f"{feet.min() / 2:.1f} to {feet.max() / 2:.1f} mm")

    spreads = []
    for pairs in (1, 5, 20):
        low, middle, high = estimate_spread(mass_g, MU_TRUE, 1.0, pairs, 4000)
        spreads.append((pairs, low, middle, high))
        print(f"  {pairs:2d} push pair(s) at 1.0 m/s^2: mu estimated in "
              f"[{low:.3f}, {high:.3f}], middle {middle:.3f}; the middle is off the "
              f"simulator's {MU_TRUE:.2f} by {100.0 * abs(middle - MU_TRUE) / MU_TRUE:.1f}%, "
              f"and the interval is {100.0 * (high - low) / MU_TRUE:.0f}% of it wide")
    diagram_how_wide([float(a) for a in accelerations], errors, speeds, spreads)

    print("\n=== per object, or per table ===")
    chosen = np.random.default_rng(7).choice(np.arange(DRAWN), size=8, replace=False)
    # The odd glass is one of middling width, so that the pool around it is
    # well populated and the picture is not making its point at an edge.
    odd_index = int(chosen[int(np.argmin(np.abs(feet[chosen] - np.median(feet))))])
    odd_mu = round(1.6 * MU_TRUE, 3)
    band_feet = np.linspace(feet.min() + 1.0, feet.max() - 1.0, 40)
    band_low, band_high = [], []
    for foot_mm in band_feet:
        near = np.abs(feet - foot_mm) < 4.0
        forces = MU_TRUE * mass_g[near] / 1000.0 * GRAVITY
        band_low.append(np.percentile(forces, 5))
        band_high.append(np.percentile(forces, 95))
    band_low, band_high = np.array(band_low), np.array(band_high)

    # The anomaly is quoted for a glass of ORDINARY mass for its foot, not for
    # the particular glass that happened to be drawn. A heavy glass would make
    # the same sticky ring look more obvious than it is.
    near = np.abs(feet - feet[odd_index]) < 4.0
    local = MU_TRUE * mass_g[near] / 1000.0 * GRAVITY
    typical, spread = float(local.mean()), float(local.std())
    odd_force = odd_mu / MU_TRUE * typical
    print(f"at a foot of {feet[odd_index]:.1f} mm, the kind's own masses put the reading "
          f"between {local.min():.2f} and {local.max():.2f} N, with a spread of "
          f"{100.0 * spread / typical:.0f}% about {typical:.2f} N")
    print(f"a sticky ring raising a typical such glass's own mu to {odd_mu:.2f} makes it read "
          f"{odd_force:.2f} N, which is {(odd_force - typical) / spread:.1f} spreads above "
          f"the middle of the pool")
    for factor in (1.2, 1.4, 1.6, 2.0):
        lifted = factor * typical
        print(f"  mu x {factor:.1f} (so {factor * MU_TRUE:.2f}) -> {lifted:.2f} N, "
              f"{(lifted - typical) / spread:.1f} spreads out")
    # Repeating an ordinary push on the same glass buys nothing: the mass is the
    # same both times, so the pool's width is unchanged. A probe does buy
    # something, because the mass divides out of it.
    typical_mass = float(mass_g[near].mean())
    steady_samples = samples_in(PROBE_LENGTH_MM / 2.0, PROBE_SPEED_MM_S)
    _, _, brisk_samples = probe_phases(1.0)
    for factor in (1.2, 1.6):
        own = factor * MU_TRUE
        error = own * pair_error(typical_mass, own, 1.0, steady_samples, brisk_samples)
        print(f"  a probe on that glass returns its own mu = {own:.2f} to +-{error:.3f}, so "
              f"the gap from the pooled {MU_TRUE:.2f} is "
              f"{(own - MU_TRUE) / error:.1f} times the probe's own uncertainty")
    pair = (int(chosen[int(np.argmin(feet[chosen]))]), odd_index)
    diagram_per_object_or_per_table(mass_g, feet, rims, chosen, odd_index, odd_mu,
                                    band_feet, band_low, band_high, pair, odd_force)

    print("\n=== the verdict, before and after ===")
    identified = (spreads[-1][1], spreads[-1][3])
    rows = []
    for percentile in (5, 25, 50, 75, 95):
        at_index = pick(feet, float(percentile))
        rows.append((f"foot {feet[at_index]:.0f} mm\n({percentile}th of the kind)",
                     float(feet[at_index])))
        print(f"  {percentile:2d}th percentile: foot {feet[at_index]:.1f} mm, "
              f"height {heights[at_index]:.0f} mm, {mass_g[at_index]:.0f} g; a/mu = "
              f"{topple_height(feet[at_index], MU_LOW):.0f} mm at mu {MU_LOW:.2f}, "
              f"{topple_height(feet[at_index], MU_HIGH):.0f} mm at mu {MU_HIGH:.2f}, "
              f"{topple_height(feet[at_index], identified[0]):.0f} to "
              f"{topple_height(feet[at_index], identified[1]):.0f} mm across the identified "
              f"[{identified[0]:.3f}, {identified[1]:.3f}]")
    before = sum(1 for _, foot_mm in rows
                 if topple_height(foot_mm, MU_LOW) > JAW_TOP
                 >= topple_height(foot_mm, MU_HIGH))
    after = sum(1 for _, foot_mm in rows
                if topple_height(foot_mm, identified[0]) > JAW_TOP
                >= topple_height(foot_mm, identified[1]))
    print(f"of these five, {before} were decided by the guess rather than by the glass; "
          f"after identification {after} are")
    print(f"the identified interval authorises "
          f"{100.0 * share_pushable(feet, identified[1]):.1f}% of the kind at its "
          f"pessimistic end and {100.0 * share_pushable(feet, identified[0]):.1f}% at its "
          f"optimistic end")
    diagram_verdict(rows, identified)

    print("\n=== the worked example, followed through ===")
    one_pair = spreads[0]
    steady_n = samples_in(PROBE_LENGTH_MM / 2.0, PROBE_SPEED_MM_S)
    _, _, brisk_n = probe_phases(1.0)
    worth = pair_error(mass, MU_TRUE, 1.0, steady_n, brisk_n)
    after = (MU_TRUE * (1.0 - worth), MU_TRUE * (1.0 + worth))
    print(f"one probe at 1.0 m/s^2 on glass {index} is worth {100.0 * worth:.0f}%, so mu "
          f"lands in roughly [{after[0]:.2f}, {after[1]:.2f}] around a true {MU_TRUE:.2f}")
    print(f"  that glass's own ceiling at the pessimistic {after[1]:.2f} is "
          f"{topple_height(foot, after[1]):.1f} mm, against a jaw top of {JAW_TOP:.0f} mm, "
          f"so {push_margin(foot, after[1], JAW_TOP):.1f} mm of margin")
    for other in (42.0, 47.0):
        print(f"  a {other:.0f} mm foot: ceiling {topple_height(other, after[1]):.1f} mm at "
              f"the pessimistic {after[1]:.2f}, {topple_height(other, MU_LOW):.1f} mm at the "
              f"optimistic guess of {MU_LOW:.2f}, and it really tips above "
              f"{topple_height(other, MU_TRUE):.1f} mm, which is "
              f"{abs(topple_height(other, MU_TRUE) - JAW_TOP):.1f} mm from the jaw's top edge")
    print(f"  the single-pair spread over 4000 runs was "
          f"[{one_pair[1]:.3f}, {one_pair[3]:.3f}]")


if __name__ == "__main__":
    main()
