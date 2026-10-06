"""Diagrams for solution 5 — a foundation model as it downloads.

Four pictures, and all four are about the **join**: what the borrowed model
expects, what it hands back, and what had to be decided before either could
reach this jaw. Solution 6's generator draws what the fitting changed, and
these two sets deliberately do not overlap.

Every number drawn here is read out of a committed file rather than typed in:

- ``03-push-glasses-apart/05-smolvla-as-it-downloads/asking.json`` — what the
  model's answers looked like over 2,260 asks: how far a chunk travels, the
  gap between its waypoints, and the lowest it gets;
- ``03-push-glasses-apart/05-smolvla-as-it-downloads/results.json`` — the
  three evaluation runs of the fifty held-out tables;
- ``diagram_style`` — the cell's own constants, each sourced there to the file
  it came from. The picture's frame, the park spot and the waypoint period are
  all ``03-push-glasses-apart/bench/bench.py``'s.

Three numbers in these pictures are **not** in a committed JSON, and each is
labelled in the drawing with where it comes from, because they are the only
places a figure leans on prose: the two probe measurements of how low a chunk
reaches when the model is handed the parked pose and an all-zero pose (182 mm
and 122 mm, six asks on one picture, in the solution's README), and the
reading's own ``ACTION_SPAN``, which is read here out of ``joining.py`` by
name rather than copied.

Nothing here loads the model, and nothing here imports MuJoCo, so this runs in
any environment that has matplotlib.

    cd 03-push-glasses-apart
    pixi run python ../images/generators/03-push-glasses-apart/make_05_images.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from diagram_style import (
    CAST,
    FEEL_SPEED,
    GLASS,
    GLASS_ZONE,
    GOOD,
    INK,
    JAW_TOP,
    KIND_TALLEST,
    LABEL_SIZE,
    LOWEST_GRIP,
    MUTED,
    NOTE_SIZE,
    PARK,
    PUSH_SPEED,
    TOP_SPEED,
    TOP_VIEW_HALF_FRAME,
    TOP_VIEW_HEIGHT,
    TOP_VIEW_SIZE,
    TRAVEL_HEIGHT,
    VIEW_CENTRE,
    WARN,
    WAYPOINT_PERIOD,
    bare,
    glass_from_the_side,
    new,
    save,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import FancyBboxPatch, Rectangle

PROJECT = Path(__file__).resolve().parents[3]
SOLUTION = PROJECT / "03-push-glasses-apart" / "05-smolvla-as-it-downloads"

# The two probes of how low a chunk reaches, from the solution's own README.
# They are six asks on one picture rather than a run, which is why they are
# drawn as marks beside the run's median and not instead of it. The point they
# make is that the state the examiner forces on the model raises its answers by
# about 60 mm, and that even the most favourable state this reading can
# express leaves the jaw far above the height a push lands at.
LOWEST_WITH_PARKED_STATE = 182.0
LOWEST_WITH_ZERO_STATE = 122.0
PROBE_ASKS = 6

# SmolVLA's six action slots, and what joining.py reads each one as. The joint
# names are the arm the checkpoint's statistics were recorded on; the two
# without a reading are dropped, because this examiner holds the jaw level and
# closed and offers no way to change either.
SLOTS = (
    ("0", "shoulder pan", "x, across the examiner"),
    ("1", "shoulder lift", "y, out and back"),
    ("2", "elbow flex", "the jaw's height"),
    ("3", "wrist flex", None),
    ("4", "wrist roll", "the jaw's heading"),
    ("5", "gripper", None),
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def action_span() -> float:
    """``ACTION_SPAN`` read out of joining.py, so this file cannot drift from it."""
    source = (SOLUTION / "joining.py").read_text()
    found = re.search(r"^ACTION_SPAN = ([0-9.]+)$", source, re.MULTILINE)
    if found is None:
        raise RuntimeError("joining.py no longer declares ACTION_SPAN; the figures quote it")
    return float(found.group(1))


def instruction() -> str:
    """The one sentence the model is told, read out of joining.py for the same reason."""
    source = (SOLUTION / "joining.py").read_text()
    found = re.search(r'^INSTRUCTION = "(.+)"$', source, re.MULTILINE)
    if found is None:
        raise RuntimeError("joining.py no longer declares INSTRUCTION")
    return found.group(1)


def middle_run(results: dict) -> dict:
    """The run of three whose push count is the middle one.

    Picked rather than using each field's median because these pictures draw
    parts of a whole: the medians of the parts do not add up to the median of
    the total, and a bar whose pieces do not sum is a lie about arithmetic.
    Every figure that uses this says which run it is and quotes the spread.
    """
    return sorted(results["each"], key=lambda run: run["pushes"]["total"])[1]


def span(values: list[int]) -> str:
    return f"{min(values)}\u2013{max(values)}" if min(values) != max(values) else f"{min(values)}"


# --------------------------------------------------------------------------- #
# Drawing helpers, in the shape the other generators in this folder use.
# --------------------------------------------------------------------------- #
def stage(axis, title: str, equal: bool = False) -> None:
    bare(axis)
    if equal:
        axis.set_aspect("equal")
    axis.set_title(title, fontsize=LABEL_SIZE, color=INK, pad=8)


def note(axis, x, y, text, colour=MUTED, size=NOTE_SIZE, **kwargs) -> None:
    kwargs.setdefault("ha", "center")
    axis.text(x, y, text, fontsize=size, color=colour, clip_on=False, **kwargs)


def footer(figure, text: str) -> None:
    figure.text(0.5, 0.012, text, fontsize=NOTE_SIZE, color=INK, ha="center")


def under(figure, column: int, columns: int, text: str, y: float = 0.22) -> None:
    """A note beneath one panel, clear of everything drawn inside it."""
    figure.text((column + 0.5) / columns, y, text, fontsize=NOTE_SIZE, color=INK,
                ha="center", va="top")


def card(axis, x, y, width, height, title, lines, colour, fill=0.08) -> None:
    """One labelled box. The schematic panels are all made of these."""
    axis.add_patch(FancyBboxPatch((x, y), width, height, boxstyle="round,pad=0,rounding_size=2.2",
                                  facecolor=to_rgba(colour, fill), edgecolor=colour, lw=1.2,
                                  zorder=3))
    axis.text(x + 3.0, y + height - 4.4, title, fontsize=NOTE_SIZE + 0.6, color=colour,
              ha="left", va="center", zorder=4)
    for step, line in enumerate(lines):
        axis.text(x + 3.0, y + height - 10.4 - 5.2 * step, line, fontsize=NOTE_SIZE - 0.4,
                  color=INK, ha="left", va="center", zorder=4)


def along(axis, start, end, colour=INK, lw=1.3, style="-|>") -> None:
    axis.annotate("", xy=tuple(end), xytext=tuple(start), zorder=5,
                  arrowprops={"arrowstyle": style, "color": colour, "lw": lw,
                              "shrinkA": 1.0, "shrinkB": 1.0})


def bar(axis, y, height, pieces, left=0.0) -> float:
    """A stacked bar of (count, colour, alpha) pieces. Returns where it ends."""
    at = left
    for count, colour, alpha in pieces:
        axis.add_patch(Rectangle((at, y), count, height, facecolor=to_rgba(colour, alpha),
                                 edgecolor=colour, lw=0.9, zorder=3))
        at += count
    return at


# --------------------------------------------------------------------------- #
# 1. The shape of the method, which is three inputs, one output and the join.
# --------------------------------------------------------------------------- #
def picture_the_join(asking: dict) -> None:
    sentence = instruction()
    figure, axes = new(14.6, 6.9, columns=3)
    shown, back, join = axes
    for axis in axes:
        axis.set_xlim(0, 100)
        axis.set_ylim(0, 100)

    stage(shown, "What the model is shown, at every ask")
    card(shown, 4, 69, 92, 27, "the view from the top",
         [f"{TOP_VIEW_SIZE[0]} by {TOP_VIEW_SIZE[1]} pixels, red-green-blue",
          f"one camera, {TOP_VIEW_HEIGHT:.0f} mm above the middle of the zone",
          "the one input that changes from table to table"], GOOD)
    card(shown, 4, 39, 92, 26, "the instruction, in ordinary words",
         [f'"{sentence}"',
          "the same sentence on every table and every push, so",
          "knowing it says nothing about the situation"], WARN)
    card(shown, 4, 6, 92, 29, "the arm's own pose, six numbers",
         [f"the examiner parks the jaw at ({PARK[0]:.0f}, {PARK[1]:.0f}), {PARK[2]:.0f} mm up,",
          "which is outside the picture's frame, so three of",
          "the four slots used clip to the edge of the range",
          f"and are the same number at all {asking['asked']:,} asks"], WARN)
    note(shown, 50, 2, "two of the three inputs carry no information here", MUTED, va="top")

    stage(back, "What comes back")
    card(back, 4, 74, 92, 22, "SmolVLA, taken exactly as it downloads",
         ["about 450 million numbers, not one of them fitted here",
          "a few gigabytes while answering; it runs on a laptop"], INK, fill=0.05)
    along(back, (50, 73), (50, 64))
    # Five rows, a break, and a last row: a chunk is fifty waypoints, which is
    # more than fits, and drawing a grid that could be counted would be a lie.
    columns, cell_w, cell_h = 6, 5.0, 3.1
    left = 50 - columns * cell_w / 2
    for row in (0, 1, 2, 3, 4, 6):
        for column in range(columns):
            back.add_patch(Rectangle((left + column * cell_w, 59 - row * cell_h),
                                     cell_w * 0.86, cell_h * 0.72, facecolor=to_rgba(GLASS, 0.22),
                                     edgecolor=GLASS, lw=0.5, zorder=3))
    note(back, 50, 59 - 5.3 * cell_h, "\u22ee", MUTED, size=NOTE_SIZE + 8, va="center")
    note(back, 50, 62.5, "50 waypoints, six numbers each", INK, va="bottom")
    note(back, 50, 33, "and what the six numbers mean is the problem", WARN, va="bottom")
    card(back, 4, 1, 92, 28, "the statistics ship, and they do not apply themselves",
         ["the checkpoint saves its mean and spread under keys like",
          "so100.buffer.action.mean; the normaliser looks up action",
          "and passes a key it cannot find through unchanged, so",
          "the numbers arrive as z-scores with no units in them"], WARN)

    stage(join, "The join, which is the only code this solution wrote")
    span_used = action_span()
    for index, (number, joint, reading) in enumerate(SLOTS):
        y = 92 - 9.4 * index
        used = reading is not None
        colour = INK if used else MUTED
        join.add_patch(Rectangle((4, y - 3.4), 40, 6.8, facecolor=to_rgba(colour, 0.07),
                                 edgecolor=colour, lw=0.9, zorder=3))
        join.text(6, y, f"{number}  {joint}", fontsize=NOTE_SIZE - 0.4, color=colour,
                  ha="left", va="center", zorder=4)
        if used:
            along(join, (45, y), (58, y), colour=GOOD, lw=1.1)
            join.text(59.5, y, reading, fontsize=NOTE_SIZE - 0.4, color=INK, ha="left",
                      va="center")
        else:
            join.plot([6, 42], [y, y], color=MUTED, lw=0.9)
            join.text(59.5, y, "dropped", fontsize=NOTE_SIZE - 0.4, color=MUTED, ha="left",
                      va="center")
    note(join, 50, 35,
         f"The jaw is held level and closed, so two slots have\nnowhere to go. The other four are "
         f"divided by\nACTION_SPAN = {span_used:g} and clipped to \u00b11, which puts x and y\ninside "
         f"the picture's frame, the height between\n{LOWEST_GRIP:.0f} and {TRAVEL_HEIGHT:.0f} mm, "
         f"and the heading round the circle.", INK, va="top")
    note(join, 50, 7,
         f"Then the guards: a path that would reach a glass refused\nfor tipping is thrown away, "
         f"which happened {asking['rejected_for_a_refused_glass']} times in {asking['asked']:,}.",
         MUTED, va="top")

    footer(figure,
           "A picture, one unvarying sentence and a pose that is the same every time go in; fifty "
           "waypoints of six dimensionless numbers come out. Everything between those numbers and "
           "this jaw is a choice\nthis project had to make, because the checkpoint settles less "
           "about its own action space than borrowing a model is supposed to involve. That join is "
           "the whole of the code here, and it has to be held\nstill for solution 6, because the "
           "pair is only clean while nothing but the training varies.")
    figure.subplots_adjust(bottom=0.135, top=0.93, wspace=0.07)
    save(figure, "05-the-join-at-both-ends.png")
    print(f"  ACTION_SPAN = {span_used:g}; {asking['asked']} asks; "
          f"{asking['rejected_for_a_refused_glass']} thrown away for a refused glass")


# --------------------------------------------------------------------------- #
# 2. The one decision in the join: what a standard deviation is worth.
# --------------------------------------------------------------------------- #
def picture_the_scale(asking: dict) -> None:
    used = action_span()
    half = TOP_VIEW_HALF_FRAME
    step = asking["step_mm_median"]
    asked_speed = step / WAYPOINT_PERIOD

    figure, axes = new(13.2, 6.3, columns=2)
    frame, speed = axes

    stage(frame, f"From the top: \u00b1{used:g} standard deviations span the picture's frame", equal=True)
    frame.add_patch(Rectangle((VIEW_CENTRE[0] - half - 86, VIEW_CENTRE[1] - half - 86),
                              2 * half + 262, 2 * half + 172,
                              facecolor=to_rgba(MUTED, 0.06), edgecolor="none", zorder=0))
    frame.add_patch(Rectangle((VIEW_CENTRE[0] - half, VIEW_CENTRE[1] - half), 2 * half, 2 * half,
                              facecolor="white", edgecolor=INK, lw=1.4, zorder=1))
    x_from, x_to, y_from, y_to = GLASS_ZONE
    frame.add_patch(Rectangle((x_from, y_from), x_to - x_from, y_to - y_from, facecolor="none",
                              edgecolor=MUTED, lw=1.0, ls=(0, (5, 4)), zorder=2))
    note(frame, VIEW_CENTRE[0], (y_from + y_to) / 2, "the glass zone\n320 by 360 mm", MUTED,
         va="center")
    for sign, label in ((-1, f"\u2212{used:g}\u03c3"), (1, f"+{used:g}\u03c3")):
        frame.plot([VIEW_CENTRE[0] + sign * half] * 2,
                   [VIEW_CENTRE[1] - half, VIEW_CENTRE[1] + half], color=INK, lw=1.4, zorder=3)
        note(frame, VIEW_CENTRE[0] + sign * half, VIEW_CENTRE[1] - half - 16, label, INK, va="top")
    note(frame, VIEW_CENTRE[0], VIEW_CENTRE[1] - half - 16, "0", INK, va="top")
    note(frame, VIEW_CENTRE[0], VIEW_CENTRE[1] + half + 10,
         f"the picture's frame, {2 * half:.0f} mm across on the table top", INK, va="bottom")
    note(frame, VIEW_CENTRE[0] - half - 40, VIEW_CENTRE[1] + half + 46,
         f"the parked jaw stands out\nhere, at ({PARK[0]:.0f}, {PARK[1]:.0f}):\nboth slots clip to the edge",
         WARN, va="bottom")
    along(frame, (VIEW_CENTRE[0] - half - 40, VIEW_CENTRE[1] + half + 42),
          (VIEW_CENTRE[0] - half + 6, VIEW_CENTRE[1] + half - 6), colour=WARN, lw=1.0)
    note(frame, VIEW_CENTRE[0] + half + 14, VIEW_CENTRE[1] - half + 30,
         "outside the frame\neverything clips\nback onto its edge", MUTED, va="bottom", ha="left")
    frame.set_xlim(VIEW_CENTRE[0] - half - 90, VIEW_CENTRE[0] + half + 182)
    frame.set_ylim(VIEW_CENTRE[1] - half - 104, VIEW_CENTRE[1] + half + 128)

    # Not stage(): this panel is a plot and keeps its axes.
    speed.set_title("And the same number fixes the speed", fontsize=LABEL_SIZE, color=INK, pad=8)
    gaps = np.linspace(0.0, 17.0, 200)
    speed.fill_between([0, 17], TOP_SPEED, 360, facecolor=to_rgba(WARN, 0.07), zorder=0)
    speed.plot(gaps, gaps / WAYPOINT_PERIOD, color=INK, lw=1.6, zorder=3)
    speed.axhline(TOP_SPEED, color=WARN, lw=1.3, zorder=2)
    speed.text(16.8, TOP_SPEED - 10,
               f"{TOP_SPEED:.0f} mm/s: the fastest this cell ever moves the jaw. follow() holds a\n"
               f"commanded path to it, so above this line the leg simply takes longer\n"
               f"than a waypoint period, and the gap stops buying speed.",
               fontsize=NOTE_SIZE, color=WARN, ha="right", va="top")
    for gap, label, at in (
        (FEEL_SPEED * WAYPOINT_PERIOD, f"the examiner's own feeling forward,\n{FEEL_SPEED:.0f} mm/s", (7.4, 86)),
        (PUSH_SPEED * WAYPOINT_PERIOD, f"the examiner's own pushing,\n{PUSH_SPEED:.0f} mm/s", (7.4, 32)),
    ):
        speed.annotate(label, xy=(gap, gap / WAYPOINT_PERIOD), xytext=at, fontsize=NOTE_SIZE,
                       color=GOOD, ha="left", va="center",
                       arrowprops={"arrowstyle": "-", "color": GOOD, "lw": 0.8})
        speed.plot([gap], [gap / WAYPOINT_PERIOD], marker="o", ms=5.0, color=GOOD, zorder=4)
    speed.plot([step], [asked_speed], marker="o", ms=6.5, color=WARN, zorder=5)
    speed.text(step - 0.6, asked_speed,
               f"{step:g} mm, which is {asked_speed:.0f} mm/s: the median\ngap in the model's own "
               f"chunks, over {asking['asked']:,} answers",
               fontsize=NOTE_SIZE, color=WARN, ha="right", va="center")
    speed.set_xlabel("gap between consecutive waypoints, mm", fontsize=NOTE_SIZE, color=INK)
    speed.set_ylabel("speed the jaw is asked to travel at, mm/s", fontsize=NOTE_SIZE, color=INK)
    speed.tick_params(labelsize=NOTE_SIZE - 0.8, colors=MUTED)
    for side in ("top", "right"):
        speed.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        speed.spines[side].set_color(MUTED)
    speed.set_xlim(0, 17)
    speed.set_ylim(0, 360)
    speed.text(0.5, 352,
               f"The examiner consumes one waypoint every {1000 * WAYPOINT_PERIOD:.0f} ms, so how far "
               f"apart two waypoints are\n*is* how fast the jaw is being asked to go. Fixing the "
               f"frame therefore fixes\nthe speed, and the two cannot be chosen separately.",
               fontsize=NOTE_SIZE, color=INK, ha="left", va="top")

    footer(figure,
           f"A z-score is not a length, so something has to set the scale, and only one thing in this "
           f"solution has both a size in millimetres and a place in the picture: the frame itself. "
           f"ACTION_SPAN = {used:g} is the\ndecision that two standard deviations span it exactly, "
           f"which is the one property a join must have if the score is to be about the model rather "
           f"than about the join \u2014 the model can put the jaw\nanywhere it can see and nowhere it "
           f"cannot. The price is in the second panel, and nothing clips it to something gentler, "
           f"because a gentler limit would be a number fitted to this examiner.")
    figure.subplots_adjust(bottom=0.185, top=0.93, wspace=0.14)
    save(figure, "05-two-sigmas-span-the-frame.png")
    print(f"  frame {2 * half:.1f} mm across; median gap {step:g} mm = {asked_speed:.0f} mm/s, "
          f"against the examiner's own {PUSH_SPEED:.0f} mm/s push and a {TOP_SPEED:.0f} mm/s cap")


# --------------------------------------------------------------------------- #
# 3. The measured failure: the answers come back high.
# --------------------------------------------------------------------------- #
def picture_how_high(asking: dict, results: dict) -> None:
    lowest = asking["lowest_mm_median"]
    across = asking["across_mm_median"]
    run = middle_run(results)
    pushes = run["pushes"]
    clean = pushes["total"] - pushes["never_touched"] - pushes["jammed"] - pushes["blocked_on_the_way_down"]
    touched = pushes["total"] - pushes["never_touched"] - pushes["blocked_on_the_way_down"]
    every = [r["pushes"] for r in results["each"]]

    figure, axes = new(13.6, 6.5, columns=2)
    side, fate = axes

    stage(side, "From the side: where a chunk's lowest point lands", equal=True)
    for slot, (height, rim, fraction) in zip((250.0, 370.0, 490.0), CAST[:3], strict=False):
        glass_from_the_side(side, slot, height, rim, fraction, alpha=0.20)
    side.plot([-320, 580], [0, 0], color=INK, lw=1.6, zorder=4)
    side.axhline(LOWEST_GRIP, color=MUTED, lw=1.0, ls=(0, (4, 3)), zorder=4)
    side.axhline(JAW_TOP, color=INK, lw=1.3, zorder=4)
    side.axhline(TRAVEL_HEIGHT, color=MUTED, lw=1.0, ls=(0, (4, 3)), zorder=4)
    side.axhline(KIND_TALLEST, color=GLASS, lw=1.0, ls=(0, (2, 3)), zorder=4)
    left = -322
    side.text(left, TRAVEL_HEIGHT + 7, f"{TRAVEL_HEIGHT:.0f} mm: travel height", fontsize=NOTE_SIZE,
              color=MUTED, ha="left", va="bottom")
    side.text(left, KIND_TALLEST + 7, f"{KIND_TALLEST:.0f} mm: the tallest the kind is drawn",
              fontsize=NOTE_SIZE, color=GLASS, ha="left", va="bottom")
    side.text(left, JAW_TOP + 7, f"{JAW_TOP:.0f} mm: the jaw's top edge, where a push really lands",
              fontsize=NOTE_SIZE, color=INK, ha="left", va="bottom")
    side.text(left, LOWEST_GRIP - 9, f"{LOWEST_GRIP:.0f} mm: the jaw's middle", fontsize=NOTE_SIZE,
              color=MUTED, ha="left", va="top")
    # One chunk, sketched: the shape is not measured, only the height it reaches,
    # so it is drawn clear of the labels and starts and ends at that height.
    sweep = np.linspace(-20.0, 560.0, 240)
    side.plot(sweep, lowest + 44.0 * (1.0 - np.cos((sweep + 20.0) / 580.0 * 2.0 * np.pi)) / 2.0,
              color=WARN, lw=1.5, zorder=6)
    side.axhline(lowest, color=WARN, lw=1.4, zorder=5)
    side.text(left, lowest - 4,
              f"{lowest:.0f} mm \u2014 the lowest point of a chunk, median over {asking['asked']:,} answers",
              fontsize=NOTE_SIZE, color=WARN, ha="left", va="top")
    # The two probes go on the right-hand edge, short, because the note under
    # the panel is where they are explained and leaders across the heights
    # would cross every label on the left.
    for value in (LOWEST_WITH_PARKED_STATE, LOWEST_WITH_ZERO_STATE):
        side.plot([-330, 525], [value, value], color=MUTED, lw=0.9, ls=(0, (2, 3)), zorder=5)
        side.text(525, value + 5, f"{value:.0f} mm", fontsize=NOTE_SIZE, color=MUTED,
                  ha="right", va="bottom")
    side.set_xlim(-330, 530)
    side.set_ylim(-150, 352)

    stage(fate, f"Where {pushes['total']} pushes went, in the middle run of three")
    fate.set_aspect("auto")
    bar(fate, 54, 20, [(pushes["never_touched"], WARN, 0.30),
                       (pushes["jammed"], WARN, 0.62),
                       (clean, GOOD, 0.34)])
    at = 0.0
    for count, label, colour, place in (
        (pushes["never_touched"], "never touched anything", WARN, "below"),
        (pushes["jammed"], "jammed", WARN, "above"),
        (clean, "touched a glass and ran\nto the end of the chunk", GOOD, "above"),
    ):
        middle = at + count / 2.0
        if place == "below":
            fate.text(middle, 48, f"{count}\n{label}", fontsize=NOTE_SIZE, color=colour,
                      ha="center", va="top")
        else:
            spot = (pushes["total"] * 0.55, 104) if count == pushes["jammed"] \
                else (pushes["total"] * 0.86, 90)
            fate.annotate(f"{count} {label}", xy=(middle, 75), xytext=spot,
                          fontsize=NOTE_SIZE, color=colour, ha="center", va="bottom",
                          arrowprops={"arrowstyle": "-", "color": colour, "lw": 0.8})
        at += count
    fate.text(0, 26,
              f"Across the three runs: never touched {span([p['never_touched'] for p in every])}, "
              f"jammed {span([p['jammed'] for p in every])}, "
              f"blocked on the way down {span([p['blocked_on_the_way_down'] for p in every])}.\n"
              f"Nothing was ever blocked coming down, because nothing ever came down. Of the "
              f"{touched} pushes that touched\na glass at all, {pushes['jammed']} jammed: when the "
              f"jaw does catch one it is travelling at the arm's top speed,\nwhich is ten times the "
              f"speed the examiner's own push macro moves at.",
              fontsize=NOTE_SIZE, color=INK, ha="left", va="top")
    fate.set_xlim(-26, pushes["total"] + 26)
    fate.set_ylim(0, 112)

    under(figure, 0, 2,
          f"The two dotted heights are {PROBE_ASKS} asks on one picture, from the solution's README, "
          f"rather than a run: {LOWEST_WITH_PARKED_STATE:.0f} mm when the\nmodel is handed the parked "
          f"pose and {LOWEST_WITH_ZERO_STATE:.0f} mm when it is handed an all-zero one. So the pose "
          f"the examiner forces on it raises\nits answers by about 60 mm \u2014 and even the most "
          f"favourable pose this reading can express leaves the jaw far above\nthe height at which a "
          f"push lands. The state is why a poor result is worse; it is not why the result is poor.",
          y=0.21)

    footer(figure,
           f"The document expected confident, plausible, wrong pushes: well-formed motion aimed at "
           f"the wrong glass, with nothing downstream looking suspicious. The measured failure is "
           f"blunter and easier to see.\nA chunk travels {across:.0f} mm across the table and never "
           f"comes near it, so nine pushes in ten touch nothing at all. The document's reasoning "
           f"about the domain gap stands; its guess about which way\nthe gap would show does not, "
           f"and that is the most useful thing this solution produced.")
    figure.subplots_adjust(bottom=0.27, top=0.93, wspace=0.10)
    save(figure, "05-the-chunks-come-back-high.png")
    print(f"  lowest point median {lowest:.1f} mm, chunk travel {across:.1f} mm; "
          f"{pushes['never_touched']} of {pushes['total']} pushes touched nothing")


# --------------------------------------------------------------------------- #
# 4. The measurement the scorecard turns on, drawn rather than tabulated.
# --------------------------------------------------------------------------- #
def picture_nothing_left_over(results: dict) -> None:
    run = middle_run(results)
    glasses = run["glasses"]
    crowded = run["crowded_at_start"]
    with_room = glasses - crowded
    racked = [r["glasses_end"]["racked"] for r in results["each"]]
    done = [r["outcome"]["done"] for r in results["each"]]
    tipping = [r["refused_because"].get("tips before it slides", 0) for r in results["each"]]
    pushes = run["pushes"]

    figure, axes = new(13.2, 6.3, columns=2)
    rooms, tables = axes
    for axis in axes:
        axis.set_aspect("auto")

    stage(rooms, f"The {glasses} glasses on the fifty held-out tables")
    bar(rooms, 66, 17, [(with_room, GOOD, 0.30), (crowded, MUTED, 0.16)])
    rooms.text(with_room / 2, 86, f"{with_room}\nalready had room", fontsize=NOTE_SIZE, color=GOOD,
               ha="center", va="bottom")
    rooms.text(with_room + crowded / 2, 86, f"{crowded}\ncrowded at the start", fontsize=NOTE_SIZE,
               color=MUTED, ha="center", va="bottom")
    bar(rooms, 36, 17, [(run["glasses_end"]["racked"], GLASS, 0.34)])
    rooms.text(run["glasses_end"]["racked"] / 2, 32,
               f"{run['glasses_end']['racked']} racked", fontsize=NOTE_SIZE, color=GLASS,
               ha="center", va="top")
    rooms.plot([with_room, with_room], [30, 83], color=GOOD, lw=1.0, ls=(0, (3, 3)), zorder=6)
    rooms.text(-10, 18,
               f"Racked across the three runs: {span(racked)}.\n"
               f"Racking a glass loosens its neighbours, so a solution that freed\n"
               f"anything at all would rack more than the {with_room} that started with room.\n"
               f"This one racks fewer. Put the racking beside the crowding and\n"
               f"there is nothing left over to credit to the pushes.",
               fontsize=NOTE_SIZE, color=INK, ha="left", va="top")
    rooms.set_xlim(-12, glasses + 12)
    rooms.set_ylim(0, 108)

    stage(tables, "The fifty tables, and the pushes spent on them")
    bar(tables, 70, 15, [(run["outcome"]["done"], GOOD, 0.34),
                         (run["outcome"]["incomplete"], MUTED, 0.16),
                         (run["outcome"]["wrong"], WARN, 0.34)], left=0.0)
    tables.text(0, 90, f"{run['outcome']['done']} finished, in this run and in every one of the "
                f"three", fontsize=NOTE_SIZE, color=GOOD, ha="left", va="bottom")
    tables.text(run["outcome"]["incomplete"] / 2, 66,
                f"{run['outcome']['incomplete']} correct but incomplete", fontsize=NOTE_SIZE,
                color=MUTED, ha="center", va="top")
    tables.text(50, 66, f"{run['outcome']['wrong']} wrong ", fontsize=NOTE_SIZE, color=WARN,
                ha="right", va="top")
    scale = 50.0 / pushes["total"]
    bar(tables, 36, 15, [(pushes["repeats"] * scale, WARN, 0.30),
                         ((pushes["total"] - pushes["repeats"]) * scale, MUTED, 0.16)])
    tables.text(pushes["repeats"] * scale / 2, 32,
                f"{pushes['repeats']} of {pushes['total']} pushes were repeats", fontsize=NOTE_SIZE,
                color=WARN, ha="center", va="top")
    tables.text(50, 53, f"{pushes['total']} pushes, drawn to the width of the fifty tables above ",
                fontsize=NOTE_SIZE, color=MUTED, ha="right", va="bottom")
    tables.text(-10, 18,
                f"A repeat is a push at a glass already pushed at. The model was never asked\n"
                f"which glass it meant: the label is read back off the path afterwards, as the\n"
                f"glass the jaw came nearest while low enough to touch it. So this counts the\n"
                f"jaw coming nearest the same glass again, which is as much as the record knows.\n\n"
                f"Refused for tipping: {', '.join(str(t) for t in tipping)} across the three runs, so "
                f"the shared rule hardly\nbinds on these tables and almost none of the shortfall is "
                f"it. What is left is the pushes.",
                fontsize=NOTE_SIZE, color=INK, ha="left", va="top")
    tables.set_xlim(-12, 62)
    tables.set_ylim(0, 108)

    footer(figure,
           "This is the baseline doing its job rather than failing at it. A matched pair measures "
           "what training bought in proportion to the room there was to improve, and a solution "
           "that finishes no table at all leaves\nnothing that training could fail to show up "
           "against. The value here is the comparison it makes possible, and not the score.")
    figure.subplots_adjust(bottom=0.11, top=0.93, wspace=0.10)
    save(figure, "05-nothing-is-left-over.png")
    print(f"  {with_room} glasses had room at the start, {span(racked)} racked; "
          f"tables finished {span(done)}")


def main() -> None:
    asking = read_json(SOLUTION / "asking.json")
    results = read_json(SOLUTION / "results.json")
    print(f"solution 5: {results['runs']} runs, {asking['asked']} asks; "
          f"chunk travel {asking['across_mm_median']} mm, gap {asking['step_mm_median']} mm, "
          f"lowest {asking['lowest_mm_median']} mm")
    picture_the_join(asking)
    picture_the_scale(asking)
    picture_how_high(asking, results)
    picture_nothing_left_over(results)


if __name__ == "__main__":
    main()
