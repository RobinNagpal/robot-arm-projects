"""One table, explained step by step: which model or rule acts, on what, and what comes next.

Runs the real pipeline from run.py on a few held-out tables and draws every
step as it happens. Each table gets a folder in saved/workflow-explained/ with
a numbered picture per step and a README.md that reads top to bottom: what the
step is given, what it gives back, whether it is learned or programmed, and
what happens next.

    pixi run python explain.py                  # the four tables below
    pixi run python explain.py --tables 10022    # any held-out table
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np
import torch
from models import VOTE_SCALE  # 02-segment-glasses/02-train-from-scratch
from work_cell.glasses import spec

import nets
import pipeline as p2  # 02-segment-glasses/02-train-from-scratch
import push_features as features
import push_plan
import rack_plan
import show
import steps
import tables
import train
import viewpoints
from bench import STANDING_TILT_DEG
from drawing import WHITE, above, beside, foot, panel, tag
from push_model import Ensemble, sigmoid
from run import Run

OUT = show.SAVED / "workflow-explained"

# Chosen from the held-out run to show the range: pushes that free a glass,
# several glasses racked, a long table of pushes, and a push that topples one.
TABLES = (10000, 10035, 10009, 10013)

LEARNED, PROGRAMMED = "learned", "programmed"
RED, ORANGE = (0, 0, 255), (0, 165, 255)


def kind_bar(chances: np.ndarray, width: int = 320) -> np.ndarray:
    """SideNet's four kind chances as bars."""
    image = np.zeros((26 * len(chances) + 6, width, 3), np.uint8)
    for i, (kind, chance) in enumerate(zip(nets.KINDS, chances, strict=True)):
        y = 6 + 26 * i
        cv2.rectangle(image, (110, y), (110 + int(chance * (width - 170)), y + 18), show.COLOURS[kind], -1)
        show.write(image, show.short(kind), (6, y + 14), WHITE, 0.45)
        show.write(image, f"{chance:.2f}", (width - 52, y + 14), WHITE, 0.45)
    return image


class Explained(Run):
    """A run that writes down and draws every step as it happens."""

    def __init__(self, seed: int, models, push_model, folder: Path) -> None:
        super().__init__(seed, models, push_model)
        self.folder = folder
        self.steps: list[dict] = []
        self.looks = 0
        self.slots_held: dict[int, int] = {}  # slot -> glass

    # ----------------------------------------------------------- bookkeeping

    def step(self, title, family, by, picture, given, gives, then, data=None) -> None:
        number = len(self.steps) + 1
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40].rstrip("-")
        name = f"{number:02d}-{slug}.png"
        if picture is not None:
            cv2.imwrite(str(self.folder / name), picture)
        self.steps.append(
            {
                "number": number,
                "title": title,
                "family": family,
                "by": by,
                "picture": name if picture is not None else None,
                "given": given,
                "gives": gives,
                "then": then,
                "data": data,
            }
        )

    def name(self, glass: int | None) -> str:
        return "an unknown glass" if glass is None else f"glass {glass}"

    # ------------------------------------------------------------ the start

    def introduce(self) -> None:
        plan = show.Plan()
        image = plan.blank()
        lines = ["What the simulator put on the table. The arm is told none of this."]
        for i, glass in enumerate(self.bench.glasses):
            x, y = self.bench.start[i]
            grip = tables.glass_grip(glass)
            plan.glass(image, x, y, glass.outline.max_diameter, show.COLOURS[glass.kind], str(i))
            lines.append(
                (
                    show.COLOURS[glass.kind],
                    f"glass {i}: {show.short(glass.kind)}, {1000 * glass.outline.total_height:.0f} "
                    f"mm tall, {1000 * glass.outline.max_diameter:.0f} mm wide; the grip rule "
                    + (f"holds it {1000 * grip.height:.0f} mm up" if grip.holdable else "cannot hold it"),
                )
            )
        picture = above(panel(f"table {self.seed}: the truth, from above", image), foot(lines, 900))
        self.step(
            "The table, as the simulator made it",
            "neither",
            "the simulator",
            picture,
            "nothing: this is the answer sheet, used only to judge the run afterwards",
            f"{len(self.bench.glasses)} glasses of {len({g.kind for g in self.bench.glasses})} kinds, "
            f"some too close to grip",
            "The arm starts knowing nothing about any glass. Its first act is to look down on the table.",
            [
                {"glass": i, "kind": g.kind, "height_mm": round(1000 * g.outline.total_height, 1)}
                for i, g in enumerate(self.bench.glasses)
            ],
        )

    # ------------------------------------------------------------- the hooks

    def on_look(self, top, sightings, glasses, ids) -> None:
        self.looks += 1
        votes = p2.cast_votes(top, self.models["top_net"])
        given = nets.top_input(top)
        chance = 1 / (1 + np.exp(-votes.out[0]))
        arrows = show.heat(given[0], 0, 1)
        for k in range(0, len(votes.rows), 9):
            r, c = votes.rows[k], votes.columns[k]
            tip = (int(c + votes.out[1, r, c] * VOTE_SCALE), int(r + votes.out[2, r, c] * VOTE_SCALE))
            cv2.arrowedLine(arrows, (int(c), int(r)), tip, WHITE, 1, tipLength=0.2)
        for r, c in votes.middles:
            cv2.drawMarker(arrows, (c, r), RED, cv2.MARKER_CROSS, 12, 2)
        plan = show.Plan(scale=600)
        found = plan.blank()
        for s in sightings:
            known = self.measured.get(s.id)
            colour = show.COLOURS[known.kind] if known else show.COLOURS[features.NOT_MEASURED]
            plan.glass(found, s.seen.x, s.seen.y, s.seen.widest, colour, self.name(s.id).split()[-1])
            if s.id in self.refused:
                cv2.drawMarker(found, plan.px(s.seen.x, s.seen.y), RED, cv2.MARKER_TILTED_CROSS, 26, 2)
        picture = above(
            beside(
                panel("1. given: height above the table", show.big(show.heat(given[0], 0, 1))),
                panel("2. TopNet: chance each pixel is glass", show.big(show.heat(chance, 0, 1))),
            ),
            beside(
                panel("3. TopNet: arrows to each middle; red +", show.big(arrows)),
                panel("4. glasses gathered from the votes", found),
            ),
        )
        lines = [
            "Panels 2 and 3 are TopNet's two answers, for every pixel.",
            "Panel 4 is arithmetic on them: where 30 or more votes land",
            "together is one glass. Its pixels' depth readings give where",
            "it stands, how wide it is and how tall.",
            "Grey: not measured from the side yet. Coloured: the kind",
            "SideNet named. Red cross: refused, left standing.",
        ]
        picture = above(picture, foot(lines, picture.shape[1]))
        found_list = [
            {
                "glass": s.id,
                "x_mm": round(1000 * s.seen.x),
                "y_mm": round(1000 * s.seen.y),
                "widest_mm": round(1000 * s.seen.widest, 1),
                "height_mm": round(1000 * s.seen.height, 1),
            }
            for s in sightings
        ]
        new = [
            s
            for s in sightings
            if s.id is not None and s.id not in self.measured and s.id not in self.refused
        ]
        fallen = [i for i in ids if self.bench.tilt(i) >= STANDING_TILT_DEG]
        then = (
            f"Glass {', '.join(map(str, fallen))} is lying down. The run stops before anything else is "
            f"touched, "
            "and every glass left gets that as its reason."
            if fallen
            else f"Each of the {len(new)} glasses not yet measured is looked at from the side, one at a time."
            if new
            else "Every glass on the table is measured already, so the arm goes straight to deciding "
            "what to do: rack a glass with room, or push one."
        )
        self.step(
            f"Look {self.looks}: find every glass from above",
            LEARNED,
            "TopNet, then voting arithmetic",
            picture,
            "one overhead depth picture, 320 x 240, shrunk to 160 x 120; TopNet is given 3 grids: "
            "height above "
            "the table, row, column",
            f"per pixel: a chance it is glass and an arrow to its glass's middle. Gathered: {len(sightings)} "
            f"glasses, each with a place, a width and a height",
            then,
            found_list,
        )

    def on_measure(self, target, others, glasses, ids, best, side, measured, clean, reason) -> None:
        index = ids.index(target.id)
        who = self.name(target.id)
        self._ranker_step(target, others, glasses, index, best)
        if side is None:
            return
        truth_glass = glasses[index]
        given = nets.side_input(side)

        picture = beside(
            panel("the side picture: distance per pixel", show.big(show.heat(given[0], -2, 2))),
        )
        picture = above(
            picture,
            foot(
                [
                    f"{who} is the glass in the middle. Yellow is far, blue is near.",
                    "A neighbour in front or behind can spoil the outline; this picture is "
                    + ("clean." if clean else "SPOILED: another glass changes the outline."),
                ],
                640,
            ),
        )
        self.step(
            f"Take the side picture of {who}",
            PROGRAMMED,
            "the arm and its wrist camera",
            picture,
            f"the place the Ranker chose, {self.view_angle:.0f} degrees round the glass, 380 mm back",
            "one side depth picture, 320 x 240, shrunk to 160 x 120",
            "The same picture goes to two models: SideNet, then GripNet.",
            {"picture_shape": list(given.shape), "clean_judged_afterwards": bool(clean)},
        )

        truth = tables.glass_grip(self.bench.glasses[target.id])
        true_h = truth_glass.total_height
        true_w = 2 * np.interp(nets.FRACTIONS * true_h, truth_glass.height, truth_glass.radius)
        drawn = show._side_drawing(given, true_h, true_w, show.TRUE, side, truth_glass)
        drawn = show._side_drawing(
            given, measured.height, measured.widths, show.SAID, side, truth_glass, drawn
        )
        made = truth_glass.kind
        picture = beside(
            panel("SideNet (orange), truth (green)", drawn),
            panel("SideNet's kind", kind_bar(measured.kind_chances)),
        )
        lines = [
            (
                show.COLOURS[measured.kind],
                f"SideNet: {show.short(measured.kind)} "
                f"({measured.kind_chances.max():.2f}); made as {show.short(made)}"
                + (" - right" if measured.kind == made else " - WRONG"),
            ),
            f"height {1000 * measured.height:.0f} mm (true {1000 * true_h:.0f}); widths at 16 levels, median "
            f"{1000 * np.median(np.abs(measured.widths - true_w)):.1f} mm out",
        ]
        self.step(
            f"Measure and name {who}",
            LEARNED,
            "SideNet",
            above(picture, foot(lines, picture.shape[1])),
            "the side picture",
            "21 numbers: the height, the width at 16 levels, and a score for each of the 4 kinds",
            "The kind sets how hard the glass may be squeezed. Next, GripNet says where to hold it.",
            {
                "height_mm": round(1000 * measured.height, 1),
                "widths_mm": np.round(1000 * measured.widths, 1).tolist(),
                "kind_chances": dict(
                    zip(nets.KINDS, np.round(measured.kind_chances, 3).tolist(), strict=True)
                ),
                "true_kind": made,
                "true_height_mm": round(1000 * true_h, 1),
            },
        )

        drawn = show.big(show.heat(given[0], -2, 2))
        if truth.holdable:
            show._grip_drawing(side, truth_glass, truth.height, truth.opening, show.TRUE, drawn)
        said = drawn.copy()
        if measured.hold_chance >= steps.HOLD_CHANCE:
            show._grip_drawing(side, truth_glass, measured.grip_height, measured.opening, show.SAID, said)
        picture = beside(
            panel("the rule's grip, from the truth (green)", drawn), panel("GripNet's grip (orange)", said)
        )
        lines = [
            f"GripNet: chance it can be held {measured.hold_chance:.2f}; grip "
            f"{1000 * measured.grip_height:.1f} mm "
            f"up; pads {1000 * measured.opening:.1f} mm apart",
            (
                f"the rule, given the true shape: grip {1000 * truth.height:.1f} mm up, pads "
                f"{1000 * truth.opening:.1f} mm"
                if truth.holdable
                else f"the rule, given the true shape: cannot be held - {truth.reason[:80]}"
            ),
        ]
        self.step(
            f"Find where to hold {who}",
            LEARNED,
            "GripNet",
            above(picture, foot(lines, picture.shape[1])),
            "the same side picture",
            "3 numbers: the chance it can be held, the grip height, the finger opening",
            "Two written lines decide whether the arm may go in at all.",
            {
                "hold_chance": round(measured.hold_chance, 3),
                "grip_height_mm": round(1000 * measured.grip_height, 1),
                "opening_mm": round(1000 * measured.opening, 1),
                "rule": truth.__dict__,
            },
        )

        verdict = f"refused: {reason}" if reason else "go: it may be racked once it has room"
        self.step(
            f"Decide about {who}",
            PROGRAMMED,
            "two thresholds in steps.py",
            None,
            f"GripNet's chance it can be held ({measured.hold_chance:.2f}) and SideNet's best kind chance "
            f"({measured.kind_chances.max():.2f})",
            f"under {steps.HOLD_CHANCE} to hold, or under {steps.KIND_CHANCE} for the kind, the glass "
            f"is refused "
            f"and left standing. **{verdict}**. The squeeze is looked up from the kind: "
            f"{spec.kind(measured.kind).force_cap_n:.0f} N for {show.short(measured.kind)}.",
            "Back to the next glass not yet measured, or on to racking and pushing.",
        )

    def _ranker_step(self, target, others, glasses, index, best) -> None:
        who = self.name(target.id)
        plan = show.Plan(**show.CAMERA_PLAN)
        image = plan.blank()
        for s in [target, *others]:
            known = self.measured.get(s.id)
            colour = show.COLOURS[known.kind] if known else show.COLOURS[features.NOT_MEASURED]
            plan.glass(image, s.seen.x, s.seen.y, s.seen.widest, colour, str(s.id), filled=s is target)
        me = viewpoints.Seen(target.seen.x, target.seen.y, target.seen.widest / 2)
        rest = [viewpoints.Seen(o.seen.x, o.seen.y, o.seen.widest / 2) for o in others]
        vetoed, scored = {}, []
        colours = {
            "out of reach": RED,
            "camera too close to a glass": ORANGE,
            "a glass in the way": (255, 0, 255),
        }
        for angle in viewpoints.angles():
            eye = plan.px(*viewpoints.camera_place(me, angle))
            reason = viewpoints.veto(me, rest, angle)
            if reason:
                vetoed[reason] = vetoed.get(reason, 0) + 1
                cv2.drawMarker(image, eye, colours[reason], cv2.MARKER_TILTED_CROSS, 9, 2)
                continue
            features_ = viewpoints.features(me, rest, angle)
            score = float(sigmoid(nets.predict(self.models["ranker"], features_[None]))[0])
            scored.append((score, angle, features_))
            cv2.circle(image, eye, 4, WHITE, -1)
            tag(image, f"{score:.2f}", (eye[0] + 6, eye[1] + 4))
        lines = [(c, f"vetoed by geometry: {r} ({vetoed.get(r, 0)})") for r, c in colours.items()]
        lines.append("white dot: allowed, with the Ranker's chance the picture comes out clean")
        data = {
            "vetoed": vetoed,
            "allowed": [{"angle_deg": round(math.degrees(a)), "score": round(s, 3)} for s, a, _ in scored],
        }
        if best is not None and best[0] >= steps.MIN_VIEW_SCORE:
            score, angle = best
            self.view_angle = math.degrees(angle)
            chosen = next(f for s, a, f in scored if a == angle)
            cv2.circle(image, plan.px(*viewpoints.camera_place(me, angle)), 10, (0, 255, 255), 2)
            lines.append(
                f"chosen (yellow ring): score {score:.2f}. The 7 numbers it was given: "
                + ", ".join(f"{k} {v:.2f}" for k, v in zip(viewpoints.FEATURES, chosen, strict=True))
            )
            data["chosen"] = dict(zip(viewpoints.FEATURES, chosen.tolist(), strict=True)) | {"score": score}
            then = f"The arm takes the side picture of {who} from the yellow place."
        else:
            lines.append("no allowed place scores 0.5 or more: this glass is not measured yet")
            then = (
                f"{who} is skipped for now. A push may move it, or its neighbours, and give it a clear view "
                "on a later look."
            )
        picture = above(panel(f"24 camera places round {who}", image), foot(lines, 1000))
        self.step(
            f"Choose where to look at {who}",
            LEARNED,
            "geometry veto (programmed), then the Ranker (learned)",
            picture,
            "24 places in a ring 380 mm round the glass, and where every glass stands",
            "for each place the geometry allows, a chance its side picture will be clean; the best is chosen",
            then,
            data,
        )

    def on_rack(self, sighting, slot, free_before, rest, measured) -> None:
        who = self.name(sighting.id)
        wide = rack_plan.is_wide(measured.widest, measured.height)
        image = np.full((150, 760, 3), 40, np.uint8)
        options = rack_plan.usable(free_before, wide)
        room = {
            s: rack_plan.capacity(free_before - rack_plan.consumed(s, wide), tuple(sorted(rest)))
            for s in options
        }
        taken_now = rack_plan.consumed(slot, wide)
        for s in range(rack_plan.SLOT_COUNT):
            x = 20 + 120 * s
            if s in self.slots_held:
                colour, text = (120, 120, 120), f"glass {self.slots_held[s]}"
            elif s not in free_before:
                colour, text = (80, 80, 80), "kept empty"
            elif s == slot:
                colour, text = show.COLOURS[measured.kind], f"glass {sighting.id}"
            elif s in taken_now:
                colour, text = (60, 60, 140), "kept empty"
            else:
                colour, text = (70, 110, 70), "free"
            cv2.rectangle(image, (x, 30), (x + 100, 110), colour, -1)
            show.write(image, f"slot {s}", (x + 22, 22), WHITE, 0.5)
            show.write(image, text, (x + 8, 76), WHITE, 0.45)
            if s in room:
                show.write(image, f"leaves {room[s]}", (x + 14, 134), WHITE, 0.45)
        self.slots_held[slot] = sighting.id
        size = "WIDE: the slots either side must stay empty" if wide else "narrow: it needs one slot"
        lines = [
            f"{who} is {size} "
            f"({1000 * measured.widest:.0f} mm wide, {1000 * measured.height:.0f} mm tall, from SideNet)",
            f"'leaves N': how many of the {len(rest)} other glasses could still fit if this one went there. "
            + (
                f"Slot {slot} leaves the most."
                if len(set(room.values())) > 1
                else f"Every slot leaves the same, so the lowest, slot {slot}, is taken."
            ),
            f"squeeze: {show.short(measured.kind)} is rated {measured.squeeze:.0f} N (spec.py), so the "
            f"fingers "
            f"close at {1000 * measured.grip_height:.0f} mm up and press no harder",
        ]
        self.step(
            f"Rack {who}",
            PROGRAMMED,
            "the rack plan (rack_plan.py) and the force table (spec.py)",
            above(panel("the rack's six slots", image), foot(lines, 760)),
            f"{who} has room round it. Its width and height, whether each glass still standing is wide, and "
            f"the free slots",
            f"slot {slot}, chosen by trying every way of filling the rack; a squeeze of "
            f"{measured.squeeze:.0f} N",
            "The bench lifts the glass off (problem 1 does the real picking in Gazebo). Then the arm "
            "looks again.",
            {"slot": slot, "wide": wide, "leaves": room, "squeeze_n": measured.squeeze},
        )

    def on_push(self, seen, kinds, wanted, target, choice, started_at, felt) -> None:
        who = self.name(target.id)
        given = features.label(kinds, target)
        rows = features.encode(seen, target, kinds, choice.heading, choice.offset, choice.travel)
        out = self.push_model.predict(rows)
        said = out.mean(0)[0]
        drawing = show._push_drawing(rows[0], np.zeros(features.OUTPUTS), said)
        named = show._decode(rows[0])
        lines = [
            (
                show.COLOURS[given],
                f"pushed: {who}, told '{show.short(given)}'; "
                f"{named['push_travel_mm']:.0f} mm, {named['push_offset_mm']:+.0f} mm off centre",
            ),
            (
                show.SAID,
                f"PushNet: the orange arrows; topple chance {choice.topple:.3f} (worst of 5 copies); "
                f"blocked {float(sigmoid(out[:, 0, features.BLOCKED]).mean()):.2f}",
            ),
            "ring colour: the kind each glass was given; grey = not measured",
        ]
        self.step(
            f"Ask PushNet what pushing {who} does",
            LEARNED,
            "PushNet (5 copies)",
            above(
                panel("one push in its own frame: the jaw moves up the picture", drawing), foot(lines, 760)
            ),
            "60 numbers: the pushed glass's kind, height, width and foot; the push; and up to 5 neighbours, "
            "each with where it stands, its size and its kind",
            "14 numbers: where every glass moves, the chance something topples, the chance the jaw is "
            "blocked",
            "This is one of about 1,500 pushes the search asked about. The next step shows the search.",
            {"inputs_named": named, "inputs_raw": rows[0].tolist(), "outputs_mean_of_5": said.tolist()},
        )

        plan = show.Plan()
        image = plan.blank()
        for s in seen:
            colour = show.COLOURS[features.label(kinds, s)]
            plan.glass(image, s.x, s.y, s.widest, colour, str(s.id))
        rng = np.random.default_rng(0)
        fan = np.linspace(-math.pi, math.pi, 48, endpoint=False)
        cost, _, topple, _ = push_plan.score(
            self.push_model,
            seen,
            target,
            kinds,
            wanted,
            fan,
            np.full(48, choice.offset),
            np.full(48, choice.travel),
            rng,
        )
        limit = push_plan.TOPPLE_LIMIT if target.id in kinds else push_plan.UNMEASURED_TOPPLE_LIMIT
        finite = cost[np.isfinite(cost)]
        for h, c, t in zip(fan, cost, topple, strict=True):
            end = (target.x + 0.06 * math.cos(h), target.y + 0.06 * math.sin(h))
            if t > limit:
                colour = RED
            elif not math.isfinite(c):
                colour = (110, 110, 110)
            else:
                share = (c - finite.min()) / max(1e-9, finite.max() - finite.min()) if len(finite) else 0
                colour = (40, int(230 - 150 * share), 40)
            plan.arrow(image, (target.x, target.y), end, colour, 1)
        plan.arrow(image, (target.x, target.y), choice.aim, WHITE, 3)
        lines = [
            (RED, f"dropped: PushNet gives over a {100 * limit:.1f}% chance of a topple"),
            (
                (110, 110, 110),
                "dropped: lands outside the zone, out of the arm's reach, or a move PushNet is unsure of",
            ),
            ((40, 230, 40), "kept: brighter green leaves less room missing for the glasses worth racking"),
            "white: the push chosen, to where PushNet expects the glass to land",
            "shown: 48 headings at the chosen length; the search itself tries about 1,500 pushes on "
            "each glass",
        ]
        self.step(
            f"Search for the best push: {who}",
            PROGRAMMED,
            "the cross-entropy search (push_plan.py)",
            above(panel("pushes tried, from above", image), foot(lines, 900)),
            "PushNet's answers for every push it tried, on every glass on the table",
            f"one push: {who}, {1000 * choice.travel:.0f} mm, heading "
            f"{math.degrees(choice.heading):.0f} degrees",
            "The arm makes the push: the closed jaw comes down behind the glass, feels forward until it "
            "touches, "
            "pushes, and backs off.",
            {
                "heading_deg": math.degrees(choice.heading),
                "travel_mm": 1000 * choice.travel,
                "offset_mm": 1000 * choice.offset,
                "topple_chance": choice.topple,
                "limit": limit,
            },
        )

        plan = show.Plan()
        image = plan.blank()
        for i in self.bench.on_table():
            x, y = self.bench.position(i)
            fell = self.bench.tilt(i) >= STANDING_TILT_DEG
            plan.glass(
                image,
                x,
                y,
                self.bench.glasses[i].outline.max_diameter,
                RED if fell else (200, 200, 200),
                str(i),
            )
        plan.glass(image, *started_at, target.widest, (90, 90, 90))
        cv2.drawMarker(image, plan.px(*choice.aim), show.SAID, cv2.MARKER_CROSS, 14, 2)
        landed = self.bench.position(target.id)
        miss = 1000 * math.dist(landed, choice.aim)
        toppled = [i for i in self.bench.on_table() if self.bench.tilt(i) >= STANDING_TILT_DEG]
        lines = [
            "dark ring: where the glass stood before; orange cross: where PushNet said it would land",
            f"it landed {miss:.0f} mm from there"
            + ("; the jaw was BLOCKED on the way down" if felt.blocked else ""),
            (RED, f"TOPPLED: glass {', '.join(map(str, toppled))} fell over")
            if toppled
            else "nothing fell over",
        ]
        self.step(
            f"Push {who}, and see what happened",
            PROGRAMMED,
            "the arm, then the physics",
            above(panel("after the push, from above", image), foot(lines, 900)),
            "the chosen push",
            "the table as it now really stands",
            "The arm looks again, from step 1: a push is never trusted further than one move ahead."
            if not toppled
            else "A glass is lying on the table. Nothing more is touched; the table stops here.",
            {"landed_mm_from_aim": miss, "blocked": felt.blocked, "toppled": toppled},
        )

    def on_stop(self, here, verdicts) -> None:
        reasons = {s.id: self.refused[s.id] for s in here if s.id in self.refused}
        self.step(
            "Stop: nothing left worth doing",
            PROGRAMMED,
            "run.py",
            None,
            "every push PushNet was asked about, and the room each would leave",
            "no push expected to make enough room to be worth the risk. Each glass left standing gets its "
            "reason: " + "; ".join(f"glass {i}: {r}" for i, r in reasons.items()),
            "The run ends.",
        )

    # --------------------------------------------------------------- the end

    def finish(self) -> None:
        plan = show.Plan()
        image = plan.blank()
        lines = []
        for i, glass in enumerate(self.bench.glasses):
            if i in self.racked:
                lines.append(
                    (
                        show.COLOURS[glass.kind],
                        f"glass {i} ({show.short(glass.kind)}): racked in slot {self.racked[i]['slot']}",
                    )
                )
                continue
            x, y = self.bench.position(i)
            plan.glass(image, x, y, glass.outline.max_diameter, show.COLOURS[glass.kind], str(i))
            lines.append(
                (
                    show.COLOURS[glass.kind],
                    f"glass {i} ({show.short(glass.kind)}): left standing - {self.refused.get(i, '?')[:90]}",
                )
            )
        self.step(
            "The table at the end",
            "neither",
            "the simulator, judging",
            above(panel("what is left", image), foot(lines, 1000)),
            "the run's outcome",
            f"{len(self.racked)} racked, {len(self.refused)} left standing, {self.pushes} pushes",
            "Done.",
        )

    def story(self) -> str:
        """One line on what happened, from the run itself."""
        kinds = ", ".join(sorted({show.short(g.kind) for g in self.bench.glasses}))
        toppled = any(r.startswith("stopped") for r in self.refused.values())
        return (
            f"{len(self.bench.glasses)} glasses ({kinds}): {len(self.racked)} racked, "
            f"{self.pushes} push{'' if self.pushes == 1 else 'es'}, "
            f"{len(self.refused)} left standing" + ("; a push toppled a glass" if toppled else "")
        )

    def write(self, story: str) -> None:
        n_learned = sum(s["family"] == LEARNED for s in self.steps)
        n_programmed = sum(s["family"] == PROGRAMMED for s in self.steps)
        out = [
            f"# Table {self.seed}, step by step",
            "",
            f"{story}.",
            "",
            f"{len(self.steps)} steps: {n_learned} learned, {n_programmed} programmed. Read from top to "
            f"bottom. "
            "Each step says what it is given, what it gives back, and what happens next. The pictures "
            "are what "
            "happened on this table, not drawn for the document. Each step's numbers are in `steps.json`.",
            "",
            "Colours, everywhere: straight blue, tapered green, stemmed purple, short-stemmed orange, "
            "not measured grey. Green lines and pads are the truth; orange are what a model said.",
            "",
        ]
        for s in self.steps:
            family = {
                "learned": "**Learned**",
                "programmed": "**Programmed**",
                "neither": "*Not a step of the arm*",
            }
            out += [f"## {s['number']}. {s['title']}", "", f"{family[s['family']]} · {s['by']}", ""]
            if s["picture"]:
                out += [f"![{s['title']}]({s['picture']})", ""]
            out += [
                f"- **Given:** {s['given']}",
                f"- **Gives back:** {s['gives']}",
                f"- **Next:** {s['then']}",
                "",
            ]
        (self.folder / "README.md").write_text("\n".join(out))
        (self.folder / "steps.json").write_text(json.dumps(self.steps, indent=1, default=float) + "\n")


def index(done: dict[int, str]) -> None:
    lines = [
        "# The learned pipeline, step by step",
        "",
        "Each folder is one held-out table, cleared by the real pipeline, with every step drawn as it "
        "happened.",
        "Open a folder's README.md and read down: each step says which model or rule acts, what it is given,",
        "what it gives back, and what comes next.",
        "",
        "## A run, in one picture",
        "",
        "```",
        "look from above ............ TopNet                       learned",
        "   gather glasses .......... voting arithmetic            programmed",
        "for each glass not measured:",
        "   veto camera places ...... geometry                     programmed",
        "   choose a place .......... Ranker                       learned",
        "   measure and name ........ SideNet                      learned",
        "   where to hold it ........ GripNet                      learned",
        "   go, or refuse ........... two thresholds               programmed",
        "a measured glass with room:",
        "   choose its slot ......... rack plan                    programmed",
        "   how hard to squeeze ..... force table, by kind         programmed",
        "otherwise push one glass:",
        "   what each push does ..... PushNet                      learned",
        "   which push .............. the search                   programmed",
        "then look again",
        "```",
        "",
        "## The tables",
        "",
        *[f"- [table {seed}](table-{seed}/README.md): {story}" for seed, story in done.items()],
        "",
    ]
    (OUT / "README.md").write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, nargs="*", default=list(TABLES))
    arguments = parser.parse_args()
    torch.set_num_threads(4)
    models, push_model = train.load(), Ensemble.load(train.WEIGHTS)
    done = {}
    for seed in arguments.tables:
        folder = OUT / f"table-{seed}"
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.png"):
            old.unlink()
        run = Explained(seed, models, push_model, folder)
        run.introduce()
        run.clear()
        run.finish()
        story = run.story()
        run.write(story)
        done[seed] = story
        print(f"table {seed}: {len(run.steps)} steps, racked {len(run.racked)} -> {folder}")
    index(done)


if __name__ == "__main__":
    main()
