"""Diagrams for solution 6 — the same foundation model, fine-tuned here.

Four pictures, and all four are about **what the fitting changed**. Solution
5's generator draws the join between a borrowed model and this cell, and these
two sets deliberately do not overlap: nothing here redraws the three inputs,
the six action slots or the scale the pair agreed on.

Every number drawn here is read out of a committed file rather than typed in:

- ``06-smolvla-fine-tuned/correction/training.json`` — the recipe, how many of
  the model's numbers move, what the training held, and the held-out error at
  each check;
- ``06-smolvla-fine-tuned/demonstrations/collected.json`` — what the teacher's
  own chunks looked like, which is the shape the student was fitted towards;
- ``06-smolvla-fine-tuned/asking.json`` and ``05-smolvla-as-it-downloads/asking.json``
  — the shape of each half of the pair's answers, measured the same way by the
  same code;
- both folders' ``results.json`` — the three evaluation runs each.

One figure quotes a number that is in no file here: the compute LeRobot's own
SmolVLA fine-tune spends. It is named below with the comment it comes from,
and it is drawn as the ratio the README states rather than as a measurement of
anything in this repository.

Nothing here loads the model or the correction, and nothing imports MuJoCo, so
this runs in any environment that has matplotlib.

    cd 03-push-glasses-apart
    pixi run python ../images/generators/03-push-glasses-apart/make_06_images.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from diagram_style import (
    CAST,
    GLASS_ZONE,
    GOOD,
    INK,
    LABEL_SIZE,
    MUTED,
    NOTE_SIZE,
    PUSH_HEIGHT,
    PUSH_SPEED,
    TOP_SPEED,
    TRAVEL_HEIGHT,
    WARN,
    WAYPOINT_PERIOD,
    bare,
    base_width,
    glass_from_the_side,
    new,
    save,
)
from matplotlib.colors import to_rgba
from matplotlib.patches import FancyBboxPatch, Rectangle

PROJECT = Path(__file__).resolve().parents[3]
PROBLEM = PROJECT / "03-push-glasses-apart"
FITTED = PROBLEM / "06-smolvla-fine-tuned"
DOWNLOADED = PROBLEM / "05-smolvla-as-it-downloads"

# What LeRobot's own SmolVLA fine-tune spends, from the comment above ``STEPS``
# in 06-smolvla-fine-tuned/train.py and repeated in that folder's README:
# twenty thousand steps at a batch of sixty-four, on an NVIDIA card. It is not
# measured in this repository and nothing here claims it is; it is drawn only
# as the ratio against what was really fitted, which is the caveat the README
# attaches to every number this solution reports.
RECIPE_STEPS = 20_000
RECIPE_BATCH = 64

# The accelerator memory the document quotes for a low-rank fine-tune of pi0,
# which is about seven times SmolVLA's size. Quoted so that the 1.02 GiB that
# was really held has something to be read against.
PI_ZERO_LORA_GIB = 22.0


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def middle_run(results: dict) -> dict:
    """The run of three whose push count is the middle one.

    The same choice solution 5's generator makes, and for the same reason:
    these pictures draw parts of a whole, and the medians of the parts do not
    add up to the median of the total. Every figure that uses it says which
    run it is and quotes the spread beside it.
    """
    return sorted(results["each"], key=lambda run: run["pushes"]["total"])[1]


def span(values: list[float], unit: str = "") -> str:
    low, high = min(values), max(values)
    if low == high:
        return f"{low:g}{unit}"
    return f"{low:g}–{high:g}{unit}"


def fates(run: dict) -> list[tuple[str, int, str]]:
    """How one run's pushes ended, as pieces that add up to its total."""
    pushes = run["pushes"]
    clean = (pushes["total"] - pushes["blocked_on_the_way_down"] - pushes["never_touched"]
             - pushes["jammed"])
    return [
        ("blocked coming down", pushes["blocked_on_the_way_down"], WARN),
        ("never touched anything", pushes["never_touched"], MUTED),
        ("jammed", pushes["jammed"], WARN),
        ("touched and ran to the end", clean, GOOD),
    ]


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
    figure.text((column + 0.5) / columns, y, text, fontsize=NOTE_SIZE, color=INK,
                ha="center", va="top")


def card(axis, x, y, width, height, title, lines, colour, fill=0.08) -> None:
    axis.add_patch(FancyBboxPatch((x, y), width, height, boxstyle="round,pad=0,rounding_size=2.2",
                                  facecolor=to_rgba(colour, fill), edgecolor=colour, lw=1.2,
                                  zorder=3))
    axis.text(x + 3.0, y + height - 4.4, title, fontsize=NOTE_SIZE + 0.6, color=colour,
              ha="left", va="center", zorder=4)
    for step, line in enumerate(lines):
        axis.text(x + 3.0, y + height - 10.4 - 5.2 * step, line, fontsize=NOTE_SIZE - 0.4,
                  color=INK, ha="left", va="center", zorder=4)


def along(axis, start, end, colour=INK, lw=1.3) -> None:
    axis.annotate("", xy=tuple(end), xytext=tuple(start), zorder=6,
                  arrowprops={"arrowstyle": "-|>", "color": colour, "lw": lw,
                              "shrinkA": 1.0, "shrinkB": 1.0})


# --------------------------------------------------------------------------- #
# 1. The shape of the correction, and what it leaves alone.
# --------------------------------------------------------------------------- #
def picture_the_correction(training: dict, mine: dict, theirs: dict) -> None:
    moving, total = training["moving_numbers"], training["total_numbers"]
    share = moving / total
    figure, axes = new(14.6, 6.6, columns=3)
    layer, size, after = axes
    for axis in axes:
        axis.set_xlim(0, 100)
        axis.set_ylim(0, 100)

    stage(layer, "One weight table, during the training")
    layer.add_patch(Rectangle((8, 40), 34, 34, facecolor=to_rgba(MUTED, 0.14), edgecolor=INK,
                              lw=1.2, zorder=3))
    note(layer, 25, 57, "the borrowed\ntable, frozen", INK, va="center")
    note(layer, 25, 34, "every number of it\nleft exactly where it was", MUTED, va="top")
    note(layer, 49, 57, "+", INK, size=NOTE_SIZE + 6, va="center")
    layer.add_patch(Rectangle((56, 66), 34, 8, facecolor=to_rgba(GOOD, 0.26), edgecolor=GOOD,
                              lw=1.2, zorder=3))
    layer.add_patch(Rectangle((56, 40), 8, 22, facecolor=to_rgba(GOOD, 0.26), edgecolor=GOOD,
                              lw=1.2, zorder=3))
    note(layer, 73, 78, f"down to {training['rank']} numbers", GOOD, va="bottom")
    note(layer, 78, 51, "and back out\nto full width", GOOD, va="center", ha="center")
    note(layer, 74, 34,
         "the correction: two thin tables\nwhose product is as wide as the\ntable they correct, "
         "and which\ntogether hold under a hundredth of it", GOOD, va="top")
    note(layer, 50, 20,
         f"rank {training['rank']}, scaling {training['scaling']}, on the four projections of every\n"
         f"attention layer — {', '.join(training['tables'])} — in the\n"
         f"vision-language half and the action expert alike.\nThe feed-forward tables are not "
         f"touched at all, which\nis the trade: fewer numbers to fit, less of the model\nthat can "
         f"move.", INK, va="top")

    stage(size, "How much of the model moves", equal=True)
    size.add_patch(Rectangle((0, 0), 100, 100, facecolor=to_rgba(MUTED, 0.12), edgecolor=MUTED,
                             lw=1.0, zorder=2))
    small = 100 * np.sqrt(share)
    size.add_patch(Rectangle((0, 100 - small), small, small, facecolor=to_rgba(GOOD, 0.75),
                             edgecolor=GOOD, lw=1.0, zorder=4))
    note(size, 52, 50, f"{total:,} borrowed numbers,\nfrozen for the whole run", INK, va="center")
    size.annotate(f"{moving:,} move: {100 * share:.2f}%",
                  xy=(small, 100 - small / 2), xytext=(34, 112), fontsize=NOTE_SIZE, color=GOOD,
                  ha="center", va="bottom",
                  arrowprops={"arrowstyle": "-", "color": GOOD, "lw": 0.8})
    note(size, 50, -10,
         f"Only those numbers carry a gradient and the\noptimiser's running averages, so what has "
         f"to be\nheld is the model plus a little: "
         f"{training['memory_gib']:.2f} GiB,\nmeasured while it ran, on this laptop's own\nMetal, "
         f"with nothing rented. The document quotes\n{PI_ZERO_LORA_GIB:.0f} GB for the same trick "
         f"on a model seven\ntimes the size, so at 450 million the saving is\nlarger than it needed "
         f"to be.", INK, va="top")
    size.set_xlim(-6, 106)
    size.set_ylim(-62, 118)

    stage(after, "And what it costs to run, afterwards")
    card(after, 4, 72, 92, 24, "the two thin tables are folded in",
         ["once trained they are multiplied out and added",
          "into the borrowed table, so what runs is a model",
          "of exactly the original size and the original speed"], GOOD)
    mine_ms = 1000 * mine["spread"]["seconds_per_push"]["median"]
    theirs_ms = 1000 * theirs["spread"]["seconds_per_push"]["median"]
    for index, (label, value, colour) in enumerate(
        (("solution 5, as it downloads", theirs_ms, MUTED), ("this solution, fitted", mine_ms, GOOD))
    ):
        y = 50 - 16 * index
        after.add_patch(Rectangle((6, y), value / 400.0 * 80.0, 11,
                                  facecolor=to_rgba(colour, 0.34), edgecolor=colour, lw=1.0,
                                  zorder=3))
        after.text(6, y + 13, label, fontsize=NOTE_SIZE, color=colour, ha="left", va="bottom")
        after.text(value / 400.0 * 80.0 + 9, y + 5.5, f"{value:.0f} ms", fontsize=NOTE_SIZE,
                   color=colour, ha="left", va="center")
    note(after, 50, 26,
         "Thinking per push, median of three runs, with the\nbench's own share taken off and both "
         "measured on an\nidle machine. The two are the same price, which is\nwhat a low-rank "
         "correction guarantees rather than\nmerely permits: it changes which weights are used,\n"
         "not how many. Timed instead on a laptop busy with\nother training, the same two read "
         "about a second\nand 0.82 s — a compute column measured under load\ncompares the load "
         "and not the methods.", INK, va="top")

    footer(figure,
           f"This is the whole of the difference between solution 5 and this one. Every borrowed "
           f"number stays where it is; {100 * share:.2f} per cent of them gain a correction learned "
           f"on this examiner's own pushes; and the correction\nis folded back in before anything is "
           f"scored. So nothing separating the two scores can be put down to one of them being "
           f"larger, slower, or given more computation at run time — which is what makes the "
           f"pair\nworth measuring at all. What it buys is the next picture.")
    figure.subplots_adjust(bottom=0.115, top=0.90, wspace=0.10)
    save(figure, "06-where-the-correction-goes.png")
    print(f"  {moving:,} of {total:,} numbers move ({100 * share:.2f}%); "
          f"{training['memory_gib']:.2f} GiB held; {theirs_ms:.0f} ms against {mine_ms:.0f} ms per push")


# --------------------------------------------------------------------------- #
# 2. What the training moved, in the shape of the chunks themselves.
# --------------------------------------------------------------------------- #
def picture_what_moved(mine: dict, theirs: dict, teacher: dict) -> None:
    rows = (
        ("solution 5, untrained", theirs["lowest_mm_median"], theirs["across_mm_median"],
         theirs["step_mm_median"], WARN),
        ("this solution, fitted", mine["lowest_mm_median"], mine["across_mm_median"],
         mine["step_mm_median"], GOOD),
        ("the teacher's own pushes", PUSH_HEIGHT, teacher["across_mm_median"],
         teacher["step_mm_median"], MUTED),
    )
    figure, axes = new(14.6, 6.4, columns=3)
    low, far, fast = axes

    stage(low, "From the side: how low a chunk comes", equal=True)
    height, rim, fraction = CAST[2]
    glass_from_the_side(low, 270.0, height, rim, fraction, alpha=0.20)
    low.plot([-150, 350], [0, 0], color=INK, lw=1.6, zorder=4)
    for _label, lowest, _across, _step, colour in rows:
        low.plot([-150, 350], [lowest, lowest], color=colour, lw=1.5,
                 ls="-" if colour is not MUTED else (0, (4, 3)), zorder=5)
    low.text(-146, rows[0][1] + 8, f"solution 5, untrained:\n{rows[0][1]:.0f} mm above the table",
             fontsize=NOTE_SIZE, color=WARN, ha="left", va="bottom")
    low.text(-146, PUSH_HEIGHT + 8,
             f"the fitted model and its teacher, both:\n{PUSH_HEIGHT:.0f} mm, which is the height\n"
             f"the gripper pushes at",
             fontsize=NOTE_SIZE, color=GOOD, ha="left", va="bottom")
    low.set_xlim(-155, 355)
    low.set_ylim(-50, 270)

    stage(far, "From the top: how far one chunk travels", equal=True)
    x_from, x_to, y_from, y_to = GLASS_ZONE
    far.add_patch(Rectangle((x_from, y_from), x_to - x_from, y_to - y_from,
                            facecolor=to_rgba(MUTED, 0.07), edgecolor=MUTED, lw=1.0,
                            ls=(0, (5, 4)), zorder=1))
    note(far, (x_from + x_to) / 2, y_to + 16, "the glass zone, 320 by 360 mm", MUTED, va="bottom")
    for index, (label, _lowest, across, _step, colour) in enumerate(rows):
        y = y_from - 60 + 130 * index
        far.annotate("", xy=(x_from + across, y), xytext=(x_from, y), zorder=5,
                     arrowprops={"arrowstyle": "-|>", "color": colour, "lw": 1.6})
        far.text(x_from, y + 34, f"{label}: {across:.0f} mm", fontsize=NOTE_SIZE, color=colour,
                 ha="left", va="bottom")
    far.set_xlim(x_from - 40, x_from + rows[0][2] + 70)
    far.set_ylim(y_from - 120, y_to + 90)

    stage(fast, "And how fast the jaw is asked to go")
    fast.set_aspect("auto")
    fast.axvline(TOP_SPEED, color=WARN, lw=1.2, zorder=2)
    fast.text(TOP_SPEED + 10, -0.80, f"{TOP_SPEED:.0f} mm/s: the arm's own top speed,\npast which a "
              f"leg simply takes longer\nthan one waypoint period",
              fontsize=NOTE_SIZE, color=WARN, ha="left", va="top")
    fast.axvline(PUSH_SPEED, color=MUTED, lw=1.0, ls=(0, (3, 3)), zorder=2)
    fast.text(PUSH_SPEED - 10, -0.80, f"{PUSH_SPEED:.0f} mm/s: what the examiner's\nown push macro "
              f"really pushes at", fontsize=NOTE_SIZE, color=MUTED, ha="right", va="top")
    for index, (label, _lowest, _across, step, colour) in enumerate(rows):
        speed = step / WAYPOINT_PERIOD
        y = 2 - index
        fast.add_patch(Rectangle((0, y - 0.23), speed, 0.46, facecolor=to_rgba(colour, 0.34),
                                 edgecolor=colour, lw=1.0, zorder=3))
        fast.text(-10, y, label, fontsize=NOTE_SIZE, color=colour, ha="right", va="center")
        fast.text(speed + 8, y, f"{speed:.0f} mm/s, from {step:g} mm a waypoint", fontsize=NOTE_SIZE,
                  color=colour, ha="left", va="center")
    fast.set_xlabel("speed, mm/s", fontsize=NOTE_SIZE, color=INK)
    fast.tick_params(labelsize=NOTE_SIZE - 0.8, colors=MUTED, left=False, labelleft=False)
    fast.set_xticks([0, 100, 200, 300])
    for side in ("top", "right", "left"):
        fast.spines[side].set_visible(False)
    fast.spines["bottom"].set_visible(True)
    fast.spines["bottom"].set_color(MUTED)
    fast.set_xlim(-230, 470)
    fast.set_ylim(-1.9, 2.7)

    footer(figure,
           f"The first panel is what the training bought, and it is not nothing: the borrowed model "
           f"never brings the jaw down to the glasses at all, and the fitted one brings it to "
           f"exactly the height a push lands at. The\nother two are what it did not buy. Its chunks "
           f"still cover {rows[1][2] / rows[2][2]:.1f} times the ground its teacher's chunks did, at "
           f"{rows[1][3] / rows[2][3]:.1f} times their speed and "
           f"{rows[1][3] / WAYPOINT_PERIOD / PUSH_SPEED:.1f} times the speed the examiner's own macro "
           f"really pushes at,\nand on a crowded table a push three times too long is a push into a "
           f"neighbour. So the model learned where a push happens long "
           f"before it learned how far one goes — and the teacher's own chunks are already "
           f"faster than the teacher, because fitting a recorded push into fifty\nwaypoints "
           f"resamples it. That is forced by the borrowed model's chunk length, and it falls on both "
           f"halves of the pair alike.")
    figure.subplots_adjust(bottom=0.165, top=0.92, wspace=0.12)
    save(figure, "06-the-height-was-learned-the-length-was-not.png")
    for label, lowest, across, step, _colour in rows:
        print(f"  {label}: lowest {lowest:g} mm, across {across:g} mm, "
              f"{step:g} mm a waypoint = {step / WAYPOINT_PERIOD:.0f} mm/s")


# --------------------------------------------------------------------------- #
# 3. The measured failure: the jaw comes down on the glass.
# --------------------------------------------------------------------------- #
def picture_coming_down(mine: dict, theirs: dict) -> None:
    run, other = middle_run(mine), middle_run(theirs)
    figure, axes = new(14.8, 6.6, columns=3)
    descent, fate, follows = axes

    stage(descent, "What follow() does with a chunk's first waypoint", equal=True)
    height, rim, fraction = CAST[2]
    foot = base_width(rim, fraction)
    for slot, behind, colour in ((0.0, True, GOOD), (420.0, False, WARN)):
        glass_from_the_side(descent, slot, height, rim, fraction, alpha=0.18)
        descent.plot([slot - 150, slot + 120], [0, 0], color=INK, lw=1.4, zorder=4)
        start_x = slot - 108.0 if behind else slot
        stops = PUSH_HEIGHT if behind else height + 16.0
        along(descent, (start_x, TRAVEL_HEIGHT), (start_x, stops + 20.0), colour=colour, lw=1.5)
        descent.add_patch(Rectangle((start_x - 15, stops - 15), 30, 30,
                                    facecolor=to_rgba(colour, 0.30), edgecolor=colour, lw=1.0,
                                    zorder=6))
        if behind:
            along(descent, (start_x + 18, PUSH_HEIGHT), (slot - foot / 2 - 6, PUSH_HEIGHT),
                  colour=colour, lw=1.5)
        else:
            along(descent, (start_x + 30, stops + 6), (start_x + 30, TRAVEL_HEIGHT - 6),
                  colour=colour, lw=1.3)
    descent.axhline(TRAVEL_HEIGHT, color=MUTED, lw=1.0, ls=(0, (4, 3)), zorder=3)
    note(descent, -295, TRAVEL_HEIGHT + 12,
         f"{TRAVEL_HEIGHT:.0f} mm: follow() puts the jaw clear above the chunk's\n"
         f"first waypoint and brings it straight down onto that waypoint,\n"
         f"before any of the rest of the chunk is carried out at all",
         MUTED, va="bottom", ha="left")
    note(descent, -130, -34, "first waypoint behind the glass:\nthe jaw comes down clear,\n"
         "feels forward, and pushes", GOOD, va="top")
    note(descent, 420, -34, "first waypoint over the glass: the jaw\ncomes down onto its rim and is "
         "blocked.\nStraight back up, and nothing is pushed", WARN, va="top")
    descent.set_xlim(-300, 660)
    descent.set_ylim(-160, 470)

    stage(fate, "How each half of the pair's pushes ended")
    fate.set_aspect("auto")
    for index, (which, each) in enumerate(
        ((f"solution 5, {other['pushes']['total']} pushes", other),
         (f"this solution, {run['pushes']['total']} pushes", run))
    ):
        y = 62 - 34 * index
        at = 0.0
        total = each["pushes"]["total"]
        for _label, count, colour in fates(each):
            width = 100.0 * count / total
            fate.add_patch(Rectangle((at, y), width, 15, facecolor=to_rgba(colour, 0.34),
                                     edgecolor=colour, lw=0.9, zorder=3))
            if width > 7.0:
                fate.text(at + width / 2, y + 7.5, f"{count}", fontsize=NOTE_SIZE, color=colour,
                          ha="center", va="center", zorder=4)
            at += width
        fate.text(0, y + 17, which, fontsize=NOTE_SIZE, color=INK, ha="left", va="bottom")
    for index, (label, _count, colour) in enumerate(fates(run)):
        fate.text(index * 25.6, 22, label.replace(" ", "\n", 1), fontsize=NOTE_SIZE, color=colour,
                  ha="left", va="top")
    fate.text(0, 4,
              f"Each bar is that solution's own pushes, so the two are\n"
              f"shares and not counts; the middle run of three by push\n"
              f"count in each case. Across the three runs this solution\n"
              f"was blocked coming down "
              f"{span([r['pushes']['blocked_on_the_way_down'] for r in mine['each']])} times and "
              f"solution 5 never\nonce, because solution 5 never came down.",
              fontsize=NOTE_SIZE, color=INK, ha="left", va="top")
    fate.set_xlim(-2, 102)
    fate.set_ylim(-32, 86)

    stage(follows, "And what follows from coming down on a glass")
    follows.set_aspect("auto")
    pairs = (
        ("glasses toppled", "glasses_end", "toppled", WARN),
        ("tables scored wrong", "outcome", "wrong", WARN),
        ("glasses racked", "glasses_end", "racked", GOOD),
        ("tables finished", "outcome", "done", GOOD),
    )
    for index, (label, group, key, colour) in enumerate(pairs):
        y = 3.9 - 1.35 * index
        theirs_count, mine_count = other[group][key], run[group][key]
        biggest = max(theirs_count, mine_count, 1)
        follows.add_patch(Rectangle((0, y + 0.04), 42.0 * theirs_count / biggest, 0.28,
                                    facecolor=to_rgba(MUTED, 0.34), edgecolor=MUTED, lw=0.9))
        follows.add_patch(Rectangle((0, y - 0.34), 42.0 * mine_count / biggest, 0.28,
                                    facecolor=to_rgba(colour, 0.34), edgecolor=colour, lw=0.9))
        follows.text(0, y + 0.42, label, fontsize=NOTE_SIZE, color=INK, ha="left", va="bottom")
        follows.text(42.0 * theirs_count / biggest + 1.6, y + 0.18, f"{theirs_count}  solution 5",
                     fontsize=NOTE_SIZE, color=MUTED, ha="left", va="center")
        follows.text(42.0 * mine_count / biggest + 1.6, y - 0.20, f"{mine_count}  this solution",
                     fontsize=NOTE_SIZE, color=colour, ha="left", va="center")
    follows.text(0, -1.6,
                 "Each pair is drawn to its own larger value, so compare within a pair\n"
                 "and not between them; the same middle run of three in both columns.\n\n"
                 "The fitting bought a few more tables finished and a third more glasses\n"
                 "racked, and it cost seven times the toppled glasses and nearly eight\n"
                 "times the tables marked wrong. Nothing in this project stands a glass\n"
                 "back up, so on this scorecard a policy that never reaches a glass scores\n"
                 "better than one that reaches the wrong part of it. That is the pair's\n"
                 "answer, and it is not that training bought nothing: it is that a thousand\n"
                 "steps bought enough competence to act and not enough to act safely.",
                 fontsize=NOTE_SIZE, color=INK, ha="left", va="top")
    follows.set_xlim(-2, 76)
    follows.set_ylim(-6.6, 4.8)

    footer(figure,
           "The model learned the height a push happens at, and did not learn where to put the jaw "
           "down. Those are different things, and the demonstrations could only teach the first: a "
           "teacher that always comes\ndown behind a glass never produces an example of coming down "
           "on one, so the state the learner spends two thirds of its pushes in is precisely the "
           "state its training set has nothing to say about. That is\nwhat DAgger exists to repair, "
           "and it is a prescription in this folder rather than code.")
    figure.subplots_adjust(bottom=0.12, top=0.92, wspace=0.12)
    save(figure, "06-the-jaw-comes-down-on-the-glass.png")
    print(f"  blocked coming down: {run['pushes']['blocked_on_the_way_down']} of "
          f"{run['pushes']['total']}, against {other['pushes']['blocked_on_the_way_down']} of "
          f"{other['pushes']['total']}; toppled {run['glasses_end']['toppled']} against "
          f"{other['glasses_end']['toppled']}")


# --------------------------------------------------------------------------- #
# 4. The honest caveat: how little of the recipe was actually spent.
# --------------------------------------------------------------------------- #
def picture_the_compute(training: dict, collected: dict) -> None:
    spent = training["steps_done"] * training["batch"]
    recipe = RECIPE_STEPS * RECIPE_BATCH
    part = recipe / spent
    history = training["history"]

    figure, axes = new(13.4, 7.0, columns=2)
    compute, curve = axes

    stage(compute, "What was spent, against what the published recipe spends", equal=True)
    compute.add_patch(Rectangle((0, 0), 100, 100, facecolor=to_rgba(MUTED, 0.12), edgecolor=MUTED,
                                lw=1.0, zorder=2))
    small = 100 * np.sqrt(spent / recipe)
    compute.add_patch(Rectangle((0, 100 - small), small, small, facecolor=to_rgba(GOOD, 0.80),
                                edgecolor=GOOD, lw=1.0, zorder=4))
    note(compute, 56, 48, f"LeRobot's own SmolVLA fine-tune:\n{RECIPE_STEPS:,} steps at a batch of "
         f"{RECIPE_BATCH},\non an NVIDIA card", INK, va="center")
    compute.annotate(f"what ran here: {training['steps_done']:,} steps at a batch of "
                     f"{training['batch']}",
                     xy=(small, 100 - small / 2), xytext=(42, 114), fontsize=NOTE_SIZE, color=GOOD,
                     ha="center", va="bottom",
                     arrowprops={"arrowstyle": "-", "color": GOOD, "lw": 0.8})
    note(compute, 50, -8,
         f"Both squares are drawn by area, so the small one is one part in {part:.0f}.\n"
         f"{training['minutes']:.0f} minutes of this laptop's Metal, about four seconds a step, on a "
         f"machine\nalso running three other solutions' training; {training['memory_gib']:.2f} GiB "
         f"held. Memory was\nnever the obstacle at this size and time was, so every number this "
         f"solution\nreports carries this square as its caveat.", INK, va="top")
    compute.set_xlim(-6, 106)
    compute.set_ylim(-58, 120)

    # Not stage(): this panel is a plot and keeps its axes.
    curve.set_title("How far the answers were from the teacher's, on tables nothing was fitted on",
                    fontsize=LABEL_SIZE, color=INK, pad=8)
    steps = [point["step"] for point in history]
    middles = [point["tuning_mm"]["median"] for point in history]
    worsts = [point["tuning_mm"]["worst"] for point in history]
    curve.plot(steps, worsts, color=MUTED, lw=1.4, marker="o", ms=4.5, zorder=4)
    curve.plot(steps, middles, color=GOOD, lw=1.8, marker="o", ms=5.5, zorder=5)
    zone_across = GLASS_ZONE[1] - GLASS_ZONE[0]
    curve.axhline(zone_across, color=WARN, lw=1.2, ls=(0, (4, 3)), zorder=3)
    curve.text(1170, zone_across + 12, f"the glass zone is {zone_across:.0f} mm across",
               fontsize=NOTE_SIZE, color=WARN, ha="right", va="bottom")
    for step, middle, worst in zip(steps, middles, worsts, strict=True):
        curve.text(step + 22, middle - 30, f"{middle:.0f} mm", fontsize=NOTE_SIZE, color=GOOD,
                   ha="left", va="top")
        curve.text(step + 22, worst + 12, f"{worst:.0f} mm at worst", fontsize=NOTE_SIZE,
                   color=MUTED, ha="left", va="bottom")
    curve.annotate("the correction is still zero here,\nso this point is exactly solution 5",
                   xy=(0, middles[0]), xytext=(330, 640), fontsize=NOTE_SIZE, color=INK,
                   ha="left", va="top",
                   arrowprops={"arrowstyle": "-", "color": INK, "lw": 0.8})
    curve.set_xlabel("training steps", fontsize=NOTE_SIZE, color=INK)
    curve.set_ylabel("distance from the teacher's own waypoints, mm", fontsize=NOTE_SIZE, color=INK)
    curve.tick_params(labelsize=NOTE_SIZE - 0.8, colors=MUTED)
    curve.set_xticks(steps)
    for side in ("top", "right"):
        curve.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        curve.spines[side].set_color(MUTED)
    curve.set_xlim(-80, 1180)
    curve.set_ylim(0, 770)
    under(figure, 1, 2,
          f"Each point is {16} chunks from a policy that draws its answer, so "
          f"{history[1]['tuning_mm']['median']:.0f} mm to "
          f"{history[2]['tuning_mm']['median']:.0f} mm is inside the noise. What is outside it is "
          f"that the fall stopped: between {history[1]['step']}\nand {history[2]['step']} the "
          f"fitting loss halved, from {history[1]['loss']:.3f} to {history[2]['loss']:.3f}, while "
          f"the held-out distance did not improve \u2014 which is the\nshape that says the extra "
          f"training is going into the examples rather than into the pushing. That is why the\n"
          f"training stopped where it did, and it is also why the square on the left is not simply "
          f"an argument for more of it.", y=0.215)

    footer(figure,
           f"Both halves of this picture have to be read together. The correction was fitted on "
           f"{training['demonstrations']:,} demonstrations from {training['tables_fitted_on']} "
           f"training tables, recorded in {collected['seconds'] / 60:.0f} minutes of simulator time "
           f"by a program rather than\na person, which is what makes the data free. What was then "
           f"spent on it is one part in {part:.0f} of the published recipe, and the one thing the "
           f"policy most needed to learn — where to put the jaw down — is the thing it had "
           f"least\nof. So the honest conclusion about the method is still open, and what it is "
           f"waiting on is more training and DAgger rather than a verdict.")
    figure.subplots_adjust(bottom=0.275, top=0.90, wspace=0.14)
    save(figure, "06-a-thousandth-of-the-recipe.png")
    print(f"  {spent:,} examples against the recipe's {recipe:,}: one part in {part:.0f}; "
          f"tuning error {' -> '.join(f'{m:.0f}' for m in middles)} mm")


def main() -> None:
    training = read_json(FITTED / "correction" / "training.json")
    collected = read_json(FITTED / "demonstrations" / "collected.json")
    mine_asking = read_json(FITTED / "asking.json")
    theirs_asking = read_json(DOWNLOADED / "asking.json")
    mine = read_json(FITTED / "results.json")
    theirs = read_json(DOWNLOADED / "results.json")
    print(f"solution 6: rank {training['rank']} on {', '.join(training['tables'])}; "
          f"{training['steps_done']} steps at a batch of {training['batch']}; "
          f"{training['demonstrations']} demonstrations")
    picture_the_correction(training, mine, theirs)
    picture_what_moved(mine_asking, theirs_asking, collected)
    picture_coming_down(mine, theirs)
    picture_the_compute(training, collected)


if __name__ == "__main__":
    main()
