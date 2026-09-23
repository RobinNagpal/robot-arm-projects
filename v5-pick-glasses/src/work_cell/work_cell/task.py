"""The workflow.

For every glass on the table:

1. move the wrist camera to a side view and measure it, because nobody has
   told the arm how big it is;
2. work out where to hold it and how wide the fingers must open, by applying
   that kind's rule to what was measured;
3. pick it up, find out what it really weighs, and adjust the squeeze;
4. turn it 180 degrees so the mouth points down;
5. lower it into a free slot until the rim touches, and let go.

This module is the only one that knows what order things happen in. Everything
it calls is a capability that does not know it is part of a sequence, which is
what lets those parts be tested on their own.

Two things are worth knowing before reading it.

The arm is never told the size of a glass. Every number it uses about one is
measured during the run, and a glass it cannot measure is left standing.

A glass left standing is a result, not a failure. Broken glass leaves shards
and an arm that will carry on moving through them, so anything doubtful ends
with the glass back on the table and a line in the report.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, replace

import numpy as np

from .arm.camera import WristCamera
from .arm.dimensions import (
    CAMERA_OFFSET,
    CARRY_SPEED,
    COMFORTABLE_REACH,
    FINGERTIP_OFFSET,
    GRASP_DEPTH,
    GRASP_NUDGE_LIMIT,
    GRASP_OFFSET,
    GRIPPER_MAX_OPENING,
    GRIPPER_WEIGHT_N,
    LIFT_HEIGHT,
    LOWEST_GRIP,
    MEASURE_FRAME_MARGIN,
    MEASURE_STANDOFF,
    MEASURE_VIEW_HEIGHT,
    PLACE_CLEARANCE,
    SLIP_TEST_DEG,
    SURVEY_BASELINE,
    SURVEY_HEIGHT,
    TURNING_ROOM,
    WEIGH_LIFT,
    survey_stations,
)
from .arm.motion import DESCENT_LIMIT, Arm, MotionFailed
from .glasses import spec
from .glasses.detect import (
    STANDING_CLEARANCE,
    Detection,
    classify,
    find_glasses,
    foot_of,
    merge_sightings,
    standing_on_the_table,
    the_one_in_the_middle,
    where_they_stand,
)
from .glasses.force import (
    CONTACT_FORCE_N,
    HOLD_BOOST,
    TooHeavyToHold,
    estimate_mass,
    force_for_measured_mass,
    holding_force,
    is_slipping,
    mass_from_wrist,
    starting_force,
)
from .glasses.perception import NotMeasurable, handle_direction, profile_from_mask
from .glasses.profile import Profile
from .glasses.rules import Grip, NoGrip, find_grip
from .rack.layout import (
    GLASS_ZONE,
    PEG_HEIGHT,
    RACK_AREA,
    ROBOT_BASE,
    TABLE_TOP_Z,
    Slot,
    fill_order,
    landing_point,
    needs_empty_neighbour,
    slots_consumed,
    slots_from_marker,
    slots_within_stretch,
    usable_slots,
)
from .report import with_mask
from .scene import PlanningSceneClient
from .transforms import facing_options, frame, grasp_options, look_along, make_pose

UP = np.array([0.0, 0.0, 1.0])

# How tall the planner is told an unmeasured glass is. The overhead view cannot
# say, so the planner is given the tallest glass the cell handles: being told a
# tumbler is a flute costs a few detours, and being told a flute is a tumbler
# costs the flute.
TALLEST_GLASS = 0.26

# How many tries a single glass gets before it is left alone. Two, because the
# second attempt is usually a different viewpoint or a firmer grip, and a third
# is almost always the same failure again.
TRIES_PER_GLASS = 2

# How far apart the two measuring viewpoints are, for a kind that might have a
# handle. Ninety degrees, because a handle is whatever makes the glass not a
# solid of revolution, and that shows up most strongly a quarter turn away.
SECOND_VIEW_DEG = 90.0


@dataclass
class Placed:
    """One glass the arm got into the rack."""

    name: str
    kind: str
    profile: Profile
    grip: Grip
    mass: float
    slot: int
    needs_gap: bool


@dataclass
class Refused:
    """One glass the arm decided not to touch, and why."""

    name: str
    kind: str | None
    reason: str


class UnknownShape(Exception):
    """The measured profile matches no kind the arm has a rule for."""


class _Quiet:
    """Stands in for the report when a run was not asked to write one.

    Saves every call site an `if self._report`, which on a file this size is
    the difference between the sequencing being readable and not.
    """

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class PickGlassesTask:
    def __init__(
        self,
        node,
        arm: Arm,
        camera: WristCamera,
        scene: PlanningSceneClient,
        report=None,
    ) -> None:
        self._log = node.get_logger()
        self._arm = arm
        self._camera = camera
        self._scene = scene
        self._report = _Quiet() if report is None else report
        self._survey_stations: list[np.ndarray] | None = None
        self._standoff: float | None = None

    # ------------------------------------------------------------------ run

    def run(self) -> tuple[list[Placed], list[Refused]]:
        # The launch file gives the cell a head start, but how long it really
        # needs depends on the machine, so wait for the pieces themselves.
        self._log.info("waiting for the cell to come up")
        self._scene.wait_until_ready()
        self._arm.wait_until_ready()
        self._camera.wait_until_ready()

        self._scene.add_table()
        self._arm.set_gripper(GRIPPER_MAX_OPENING)

        slots = self._find_rack()
        self._scene.add_rack(slots)
        free = {slot.index for slot in slots}

        placed: list[Placed] = []
        refused: list[Refused] = []
        skip: set[str] = set()

        standing: list[Detection] = []
        rounds = 0
        while free:
            rounds += 1
            # Everything known to be standing goes into the scene before the
            # arm moves again, because the survey is itself a series of moves.
            # Until this was done here the planner was told about the glasses
            # only *after* the survey, so the arm crossed the table each round
            # believing it was empty, and the first round it still does —
            # nothing has seen the table yet. That is why the survey is flown
            # high enough to clear the tallest glass the cell handles.
            self._scene.set_glasses(
                {g.name: (g.position, g.rough_width, TALLEST_GLASS) for g in standing}
            )

            seen = self._survey(rounds)
            standing = seen
            found = [g for g in seen if g.name not in skip]
            if not found:
                break

            # Nearest first, so the arm never reaches over one glass for
            # another it could have taken first.
            target = min(found, key=lambda g: float(np.linalg.norm(g.position - ROBOT_BASE)))
            self._log.info(f"--- {target.name} ---")
            self._report.step(f"{target.name}")
            self._report.doing(
                "sort by distance from the arm's base",
                f"the nearest of the {len(found)} it can see, standing at "
                f"({target.position[0]:.3f}, {target.position[1]:.3f}) and about "
                f"{target.rough_width * 1000:.0f} mm across from above",
            )
            self._report.say(
                "Nearest first, because reaching over one glass for another it could have "
                "taken is how neighbours get knocked over. Steps 2 to 6 below are this one "
                "glass, all the way to the rack."
            )

            # Every glass goes in, the one being reached for included. It only
            # comes out at the last moment, in _pick_up, once the arm is lined
            # up above it and the one move left is straight down the tool's own
            # axis. Leaving it out from here instead means every move of the
            # approach — carrying the camera round it, hunting for a way to
            # hold it — is planned as though it were not there, and the arm
            # shoves it across the table or knocks it over before the fingers
            # ever close.
            self._scene.set_glasses(
                {
                    other.name: (other.position, other.rough_width, TALLEST_GLASS)
                    for other in found
                }
            )
            self._report.doing(
                "hand every glass to the planner as a cylinder",
                f"{_count(len(found), 'cylinder')} in the planning scene. The target only comes out "
                "later, in step 5, once the one move left is straight down the tool's axis",
            )

            try:
                result = self._do_one(target, found, slots, free)
            except UnknownShape as why:
                self._log.error(f"giving up on {target.name}: {why}")
                refused.append(Refused(target.name, None, str(why)))
                skip.add(target.name)
                continue
            except NotMeasurable as why:
                self._log.error(f"giving up on {target.name}: could not measure it: {why}")
                refused.append(Refused(target.name, None, f"could not measure it: {why}"))
                skip.add(target.name)
                continue
            except NoGrip as why:
                self._log.error(f"giving up on {target.name}: nowhere safe to hold it: {why}")
                refused.append(Refused(target.name, None, f"nowhere safe to hold it: {why}"))
                skip.add(target.name)
                continue
            except TooHeavyToHold as why:
                self._log.error(f"giving up on {target.name}: {why}")
                refused.append(Refused(target.name, None, str(why)))
                skip.add(target.name)
                continue
            except MotionFailed as why:
                # One glass the arm cannot manage is not a reason to stop.
                self._log.error(f"giving up on {target.name}: {why}")
                self._say_why_stuck()
                refused.append(Refused(target.name, None, f"the arm could not do it: {why}"))
                skip.add(target.name)
                self._arm.set_gripper(GRIPPER_MAX_OPENING)
                self._stand_clear()
                continue

            placed.append(result)
            free -= slots_consumed(slots[result.slot], needs_gap=result.needs_gap)

        self._park()
        return placed, refused

    # ------------------------------------------------------------- one glass

    def _do_one(
        self, target: Detection, found: list[Detection], slots: list[Slot], free: set[int]
    ) -> Placed:
        # 1. Measure it. Everything after this uses what comes back and
        #    nothing that was written down in advance.
        self._report.step(
            f"Step 2 — measuring {target.name}",
            doc="step2-measuring-one.md",
            code="_view_from() in task.py, glasses/perception.py",
            level=3,
        )
        others = [g for g in found if g.name != target.name]
        profile, foot = self._view_from(target, others, angle=0.0)
        if foot is not None:
            # The survey put the arm in front of the right glass; the picture
            # it took there says where that glass actually stands, to within
            # the width of a stem. Everything from here on is a grasp.
            moved = float(np.linalg.norm((foot - target.position)[:2]))
            self._log.info(f"the side view puts it {moved * 1000:.0f} mm from where the survey did")
            self._report.say(
                f"The side view puts the glass {moved * 1000:.0f} mm from where the survey "
                "did. That correction is what the fingers are aimed by, so a wrong one is a "
                "miss."
            )
            target = replace(target, position=foot)
        self._log.info(
            f"measured {profile.total_height * 1000:.0f} mm tall, "
            f"{profile.max_width * 1000:.0f} mm at its widest"
        )
        self._report.table(
            {
                "measured height": f"{profile.total_height * 1000:.0f} mm",
                "measured width": f"{profile.max_width * 1000:.0f} mm",
                "width at the rim": f"{profile.rim_width * 1000:.0f} mm",
                "width at the base": f"{profile.base_width * 1000:.0f} mm",
            }
        )

        # 2. Decide what kind of glass it is, from the shape just measured
        #    rather than from the view above. A stem is invisible from overhead.
        self._report.step(
            "Step 3 — what kind of glass it is",
            doc="step3-what-kind-of-glass.md",
            code="classify() in glasses/detect.py",
            level=3,
        )
        # Asked again here only so the report can show the evidence the
        # decision was made on. classify() is still the one that decides.
        waist = profile.waist_at()
        self._report.doing(
            "waist = the narrowest point below the widest",
            f"at {waist * 1000:.0f} mm up, which is "
            f"{waist / profile.total_height:.2f} of the height"
            if waist is not None
            else "none — so the question is whether the wall leans",
        )
        name = classify(profile)
        self._report.doing(
            "name the kind from the waist, or from the lean",
            f"**{name or 'no kind any rule describes'}**"
            + (
                ""
                if name
                else ". Nothing is known about how to hold it, so it is left standing"
            ),
        )
        if name is None:
            raise UnknownShape(
                "this is not a shape any rule describes, so it is left standing"
            )
        kind = spec.kind(name)
        self._log.info(f"that shape is a {name}")

        handle = None
        if kind.expects_handle:
            second, _ = self._view_from(target, others, angle=math.radians(SECOND_VIEW_DEG))
            handle = handle_direction(profile, second)
            if handle is not None:
                self._log.info("it has a handle, so the approach comes in square to it")

        # 3. Work out where to hold it.
        self._report.step(
            "Step 4 — where to hold it",
            doc="step4-where-to-hold-it.md",
            code="find_grip() in glasses/rules.py",
            level=3,
        )
        band = kind.band_for(profile.total_height)
        self._report.doing(
            "look up what this kind of glass asks for",
            f"the `{kind.grip_rule}` rule, searching {band[0] * 1000:.0f} to "
            f"{band[1] * 1000:.0f} mm up, with {kind.min_band_height_m * 1000:.0f} mm of "
            "wall needed for the pads",
        )
        self._report.doing(
            "raise the bottom of that band to LOWEST_GRIP",
            f"so the search starts at {max(band[0], LOWEST_GRIP) * 1000:.0f} mm, because the "
            f"gripper body will not clear the table below {LOWEST_GRIP * 1000:.0f} mm",
        )
        try:
            grip = find_grip(
                profile, kind, gripper_max_opening=GRIPPER_MAX_OPENING, lowest_grip=LOWEST_GRIP
            )
        except NoGrip as why:
            self._report.doing("run the rule on the measured profile", f"**no grip**: {why}")
            self._report.trouble(
                f"There is nowhere on this glass the fingers can safely go, so it is left "
                f"standing. {str(why).capitalize()}."
            )
            raise
        self._report.doing(
            "run the rule on the measured profile",
            f"it picks the band {grip.band[0] * 1000:.0f}–{grip.band[1] * 1000:.0f} mm up",
        )
        self._report.doing(
            "height = the middle of the band it chose",
            f"hold it **{grip.height * 1000:.0f} mm up**",
        )
        self._report.doing(
            "opening = the measured width at that height",
            f"the fingers go to **{grip.opening * 1000:.0f} mm apart**",
        )
        self._report.doing(
            "check the answer five ways",
            "all five passed, or this would have raised `NoGrip` with the reason",
        )
        self._log.info(
            f"holding it {grip.height * 1000:.0f} mm up, fingers "
            f"{grip.opening * 1000:.0f} mm apart"
        )
        self._report.say(
            "That opening is not looked up anywhere: it is the width that was measured at "
            "that height a moment ago. The fingers will go there and close until they touch, "
            "and if what they touch is not that wide, the grasp is not where it should be."
        )

        # 4. Pick a slot, now that the width is known.
        needs_gap = needs_empty_neighbour(profile.max_width, profile.total_height)
        slot = self._choose_slot(slots, free, needs_gap)
        self._report.doing(
            "choose a slot",
            f"**slot {slot.index}**, at ({slot.centre[0]:.3f}, {slot.centre[1]:.3f})"
            + (
                ", with the slot beside it left empty because this glass is both wide and tall"
                if needs_gap
                else ""
            ),
        )
        if needs_gap:
            self._log.info("wide and tall, so the slot beside it stays empty")

        # 5. Pick it up and find out what it weighs.
        mass = self._pick_up(target, others, profile, grip, kind, handle)
        self._log.info(f"it weighs {mass * 1000:.0f} g")

        # 6. Turn it over and stand it in the rack.
        self._invert_and_place(target.name, grip, slot, profile)

        return Placed(target.name, name, profile, grip, mass, slot.index, needs_gap)

    # ------------------------------------------------------------- measuring

    def _view_from(
        self, target, others: list[Detection], angle: float
    ) -> tuple[Profile, np.ndarray | None]:
        """Put the camera to one side of the glass and measure its outline.

        The camera looks horizontally at the glass, from a known distance,
        which is what lets pixels become millimetres. The distance is known
        because the arm chose how far back to stand — it never needs a depth
        reading of the glass itself, only the table's height, which it has.

        Which side it looks from is not free. Standing off a glass means
        putting the camera a further ``MEASURE_STANDOFF`` away from it, and on
        the far side that is a third of a metre added to a reach that is
        already most of what the arm has. So the near side is the default:
        ``angle`` is measured from the line back to the arm's own base, and
        zero means standing between the glass and the arm. A second view for a
        handle is then a turn off that, and lands somewhere the arm can still
        reach.
        """
        toward_base = math.atan2(
            ROBOT_BASE[1] - target.position[1], ROBOT_BASE[0] - target.position[0]
        )

        standing_back = self._measuring_distance()
        self._report.doing(
            "work out how far back to stand",
            f"**{standing_back * 1000:.0f} mm**, from the lens, the height the camera looks "
            f"at, and the {TALLEST_GLASS * 1000:.0f} mm tallest glass this cell handles",
        )
        places = list(self._standoffs(target, others, angle + toward_base))
        self._report.doing(
            "list the places to stand, best first",
            f"{len(places)} of them, a line of sight with nothing behind it first and the "
            "least reach after that",
        )

        trouble: Exception | None = None
        for eye, rotation in places:
            try:
                # tool0 does not go to the eye point: the camera is bolted to
                # one side of the tool, and that offset turns with the tool.
                self._arm.move_to_pose(eye - rotation @ CAMERA_OFFSET, rotation)
            except MotionFailed as why:
                trouble = why
                continue

            self._report.doing(
                "move the camera there, looking level",
                f"standing at ({eye[0]:.3f}, {eye[1]:.3f}, {eye[2]:.3f})",
            )
            view = self._camera.capture()
            standoff = self._measuring_distance()
            everything = self._things_standing_up(
                view, within=(standoff - 0.12, standoff + 0.12)
            )
            self._report.doing(
                "mask = what stands up, near the standoff",
                f"{int(everything.sum())} pixels, within 120 mm either side of the standoff, "
                "which is what drops the rack and the glasses behind this one",
            )
            mask = the_one_in_the_middle(everything)
            self._report.doing(
                "mask = just the patch in the middle",
                f"{int(mask.sum())} pixels left, the one the camera was aimed at",
            )
            try:
                self._report.picture(
                    with_mask(view.rgb, mask),
                    f"measuring {target.name} from the side, standing "
                    f"{self._measuring_distance() * 1000:.0f} mm back",
                    then=(
                        "The green outline is what the arm believes is glass. Everything it "
                        "measures — how tall, how wide at each height, where the stem is — "
                        "comes from that outline and nothing else."
                    ),
                )
                measured = profile_from_mask(mask, view.intrinsics, self._measuring_distance())
                self._report.doing(
                    "profile = a width for every row of mask",
                    f"**{measured.total_height * 1000:.0f} mm tall**, "
                    f"**{measured.max_width * 1000:.0f} mm at its widest**, from "
                    f"{measured.height.size} rows of mask",
                )
                if measured.total_height > TALLEST_GLASS:
                    # Taller than any glass this cell handles, so it is not
                    # one glass. Two standing one behind the other read as a
                    # single tall one, and the height is the cheapest way to
                    # notice: the rules downstream would take it seriously.
                    raise NotMeasurable(
                        f"it measures {measured.total_height * 1000:.0f} mm tall, over the "
                        f"{TALLEST_GLASS * 1000:.0f} mm this cell handles, so the mask has "
                        "caught more than one glass"
                    )
                self._report.doing(
                    "not taller than the cell's tallest glass",
                    f"{measured.total_height * 1000:.0f} mm is under the "
                    f"{TALLEST_GLASS * 1000:.0f} mm limit, so this is one glass and not two "
                    "standing one behind the other",
                )
                foot = foot_of(
                    mask, view.to_world, TABLE_TOP_Z, edge_above=STANDING_CLEARANCE
                )
                if foot is not None:
                    strayed = float(np.linalg.norm((foot - target.position)[:2]))
                    self._report.doing(
                        "foot near where the arm aimed",
                        f"the foot of what is in the picture stands {strayed * 1000:.0f} mm "
                        f"from where the survey put this glass, and up to "
                        f"{GRIPPER_MAX_OPENING * 1000:.0f} mm — a gripper's width — is "
                        "taken as the same glass",
                    )
                    if strayed > GRIPPER_MAX_OPENING:
                        # Further off than a glass is wide, so whatever is in
                        # the middle of this picture is not the glass the arm
                        # came to measure. Measuring it would be bad enough;
                        # correcting the target's position onto it and then
                        # closing the fingers there would be worse.
                        raise NotMeasurable(
                            f"what is in the middle of the picture stands {strayed * 1000:.0f} mm "
                            "from the glass this was aimed at, so it is a different glass"
                        )
                return measured, foot
            except NotMeasurable as why:
                # Which is what the next side is for. A glass with a
                # neighbour touching it in this picture usually stands clear
                # in one taken from somewhere else, and the arm is already up
                # and holding nothing, so another look is cheap.
                self._log.info(f"that side did not measure ({why}), trying another")
                self._report.say(
                    f"**This side did not measure: {why}.** The arm goes round to another "
                    "one. A glass with a neighbour touching it in one picture usually "
                    "stands clear in a picture taken from somewhere else."
                )
                trouble = why

        self._report.trouble(
            f"None of the {len(places)} places it could stand gave a measurement worth "
            "using, so the glass is left standing."
        )
        raise trouble if trouble else MotionFailed("nowhere to stand to look at this glass")

    def _standoffs(self, target, others: list[Detection], preferred: float):
        """Places to stand the camera to look at one glass, best first.

        Two things decide the order. A glass standing behind the one being
        measured is a second patch in the same mask, touching the first, and
        the two measure as one glass the width of the table — so a line of
        sight with nothing behind it comes first. After that, the
        least reach: straight in from the arm's own base, because a glass far
        out leaves nowhere to stand beyond it and one close in leaves nowhere
        on the near side.

        Whether a pose can really be reached is still the planner's business.
        This only avoids asking it questions whose answer is obviously no.
        """
        offered = []
        for step in range(-4, 5):
            angle = preferred + step * math.radians(40.0)
            direction = np.array([math.cos(angle), math.sin(angle), 0.0])
            eye = target.position + direction * self._measuring_distance() + UP * MEASURE_VIEW_HEIGHT
            out = float(np.linalg.norm((eye - ROBOT_BASE)[:2]))
            if not COMFORTABLE_REACH[0] <= out <= COMFORTABLE_REACH[1]:
                continue
            offered.append((self._blocked(target, others, eye), abs(step), eye, direction))

        for _, _, eye, direction in sorted(offered, key=lambda row: (row[0], row[1])):
            # The roll is pinned so that up in the picture is up in the room,
            # the same way round from every side of the glass. It matters here
            # and nowhere else: the profile is measured row by row, with a row
            # meaning a height, so a picture that comes out rolled measures
            # the glass across instead of up. The default hint is chosen for
            # poses that look downwards, and for one looking along the table
            # it gives a different roll for each way round the arm stands.
            forward = -direction
            yield eye, look_along(forward, up_hint=np.cross(UP, forward))

    @staticmethod
    def _blocked(target, others: list[Detection], eye: np.ndarray) -> int:
        """How many other glasses would share the picture with this one.

        Judged as an angle at the camera rather than as a distance from the
        line of sight, because that is what decides whether two glasses touch
        in the picture. A glass well off to the side but twice as far away
        covers the same part of the frame as one just beside the target, and
        the mask cannot tell the two apart once they meet.

        Both the positions and the widths come from the survey, which by now
        knows where every glass stands and roughly how wide each one is.
        """
        to_target = (target.position - eye)[:2]
        range_to_target = float(np.linalg.norm(to_target))
        if range_to_target <= 0.0:
            return len(others)
        half_target = math.atan2(target.rough_width / 2.0, range_to_target)

        count = 0
        for other in others:
            to_other = (other.position - eye)[:2]
            range_to_other = float(np.linalg.norm(to_other))
            if range_to_other <= 0.0:
                continue
            turn = to_target[0] * to_other[1] - to_target[1] * to_other[0]
            between = abs(math.atan2(float(turn), float(np.dot(to_target, to_other))))
            if between < half_target + math.atan2(other.rough_width / 2.0, range_to_other):
                count += 1
        return count

    # --------------------------------------------------------------- picking

    def _pick_up(
        self, target, others: list[Detection], profile: Profile, grip: Grip, kind, handle
    ) -> float:
        """Close on the glass, lift it a little, and weigh it.

        The order matters. Which way round the gripper holds the glass is
        settled *before* the fingers close, by checking that the arm could turn
        the glass over from there. The last wrist joint stops short of a full
        turn, so some ways of holding a glass leave it impossible to invert,
        and discovering that with the glass already in the gripper leaves
        nothing to do but put it back down.
        """
        approaches = _approach_directions(handle, target, others)
        grip_point = target.position + UP * grip.height

        # The glass stays in the scene, at the height it was measured, while
        # the arm finds a hover above it. A planner that does not know it is
        # there routes an elbow or the camera straight through it. It comes out
        # only for the straight descent in: see _hover_and_choose_grasp().
        without_it = {
            other.name: (other.position, other.rough_width, TALLEST_GLASS) for other in others
        }
        with_it = dict(without_it)
        with_it[target.name] = (target.position, profile.max_width, profile.total_height)

        self._report.doing(
            "choose which way round to hold it",
            f"{len(approaches)} directions the fingers could come in from, two ways round "
            "each, and the arm has to be able to reach it *and* still turn the wrist far "
            "enough to put the glass upside down afterwards",
        )
        self._arm.set_gripper(min(grip.opening + 0.020, GRIPPER_MAX_OPENING))
        rotation = self._hover_and_choose_grasp(grip_point, approaches, with_it, without_it)
        self._report.doing(
            "take the first the arm can reach and turn",
            f"coming in along ({rotation[0, 2]:.2f}, {rotation[1, 2]:.2f})",
        )
        position = grip_point - rotation[:, 2] * GRASP_DEPTH

        # Take up the slack gently. The width when contact arrives is the true
        # width of the glass, measured by touch rather than by camera.
        self._report.say(
            f"Reaching in along ({rotation[0, 2]:.2f}, {rotation[1, 2]:.2f}) with the fingers "
            f"opened to {min(grip.opening + 0.020, GRIPPER_MAX_OPENING) * 1000:.0f} mm."
        )
        # Taken from the grasp pose rather than from the hover above it. The
        # camera is on the wrist looking the way the gripper reaches, so from
        # here it looks straight down the approach at the glass; from the
        # hover, a fifth of a metre higher and still looking level, it looks
        # over the top of everything at the empty sky.
        position = self._centre_on_what_is_there(position, rotation, grip_point)

        self._report.step(
            "Step 5 — how hard to squeeze",
            doc="step5-how-hard-to-squeeze.md",
            code="glasses/force.py, _pick_up() in task.py",
            level=3,
        )
        guessed = estimate_mass(profile, kind)
        self._report.doing(
            "guess = estimate the mass from the shape",
            f"about **{guessed * 1000:.0f} g**, from a {kind.wall} wall. Openly a guess: the "
            "camera cannot see wall thickness, and the lift below is what settles it",
        )
        self._report.doing(
            "force = mass * g / (friction * pads), doubled",
            f"**{starting_force(profile, kind):.1f} N** to start with",
        )
        self._report.doing("stage one: close the fingers at 1 N")
        self._arm.set_gripper_force(CONTACT_FORCE_N)
        time.sleep(0.4)
        touched = self._arm.gripper_gap
        self._report.doing(
            "read the gap they stopped at",
            f"the fingers found **{touched * 1000:.1f} mm**, by touch rather than by camera",
        )
        self._report.doing(
            "compare with the width the camera said",
            f"the camera said {grip.opening * 1000:.1f} mm, so they are "
            f"{abs(touched - grip.opening) * 1000:.1f} mm apart and 4 mm is allowed",
        )
        if abs(touched - grip.opening) > 0.004:
            self._report.trouble(
                f"The fingers closed to {touched * 1000:.1f} mm where the glass should have "
                f"stopped them at {grip.opening * 1000:.1f} mm."
                + (
                    " Closing to nothing means they met no glass at all, so they went to the "
                    "wrong place rather than squeezed the wrong amount."
                    if touched < 0.002
                    else " They met something, but not something the right width."
                )
            )
            raise MotionFailed(
                f"the fingers met the glass at {touched * 1000:.0f} mm and the camera "
                f"said {grip.opening * 1000:.0f} mm, so the grasp is not where it should be"
            )

        self._report.doing(
            "stage two: squeeze to the estimated force",
            f"squeezing at {starting_force(profile, kind):.1f} N",
        )
        self._arm.set_gripper_force(starting_force(profile, kind))
        time.sleep(0.3)

        # Lift a centimetre and weigh it. This is the last moment a mistake is
        # free: the glass is off the table but nothing has been turned over.
        self._report.doing(
            "lift 10 mm in a straight line",
            "the last moment a mistake is free: the glass is off the table and nothing has "
            "been turned over",
        )
        self._straight_if_possible(position + UP * WEIGH_LIFT, rotation, "a centimetre off the table")
        self._report.doing(
            "read the wrist force-torque sensor",
            f"{self._arm.wrist_load:.1f} N, upright, as the median of 32 samples",
        )
        mass = mass_from_wrist(self._arm.wrist_load, GRIPPER_WEIGHT_N)
        self._report.doing(
            "mass = that, less the gripper's own weight",
            f"**{mass * 1000:.0f} g**, against the {guessed * 1000:.0f} g guessed from the "
            f"shape — {abs(mass - guessed) / max(guessed, 1e-6) * 100:.0f}% out",
        )

        needed = force_for_measured_mass(mass, kind)
        self._report.doing(
            "stage three: refuse if it needs too much",
            f"it wants {needed:.1f} N, and a {kind.wall}-walled {kind.name} is capped at "
            f"{kind.force_cap_n:.1f} N",
        )
        hold = holding_force(mass, kind)
        self._report.doing(
            "re-squeeze if the guess was low",
            f"the weight alone needs {needed:.1f} N, but it is set down and re-gripped at "
            f"{hold:.1f} N, {HOLD_BOOST:.1f} times the {kind.force_cap_n:.1f} N the wall is "
            "rated for: the weight sum stops it sliding down, not turning about the line "
            "between the pads once it is upside down",
        )
        # Setting it down and re-gripping is safe; increasing the squeeze while
        # holding it arrives as a shock.
        self._log.info(f"re-gripping at {hold:.1f} N")
        self._straight_if_possible(position, rotation, "back down to re-grip")
        self._arm.set_gripper_force(hold)
        time.sleep(0.3)

        self._straight_if_possible(position + UP * LIFT_HEIGHT, rotation, "up off the table")

        # Now that the arm has it, the planner is told so, or it will plan the
        # turn as though the gripper were empty.
        #
        # Both of these are where things are *now*, after the lift, and that
        # is the whole of it: attach() works out where the glass sits in the
        # gripper by comparing them, so a glass taken from before the lift and
        # a tool taken from after it hangs the glass the height of the lift
        # below where it really is. That reads as a glass through the table,
        # every move afterwards starts in collision, and a Cartesian path
        # comes back having solved none of the way — including the one that
        # would have stood the arm clear.
        lifted = position + UP * LIFT_HEIGHT
        self._scene.attach(
            target.name,
            held_at=target.position + UP * LIFT_HEIGHT,
            width=profile.max_width,
            height=profile.total_height,
            tool_pose=frame(lifted, rotation),
        )
        return mass

    def _centre_on_what_is_there(
        self, position: np.ndarray, rotation: np.ndarray, grip_point: np.ndarray
    ) -> np.ndarray:
        """Look down the fingers and shift sideways onto the glass before closing.

        Everything up to here aimed the fingers from pictures taken half a
        metre away. This is the one look taken from where the fingers actually
        are — the camera is on the wrist, so at the grasp pose it stares
        straight down the approach at the glass from a hand's breadth away,
        and a millimetre of error on the table is worth many pixels here.

        Only sideways, and only along the axis the fingers close on. How high
        up to hold the glass came from its measured profile and is better
        known than anything this view could say about it; how far along the
        approach the glass is, this view cannot see at all. What it can see,
        better than anything else, is whether the glass is between the fingers
        or beside them, which is exactly what was going wrong.
        """
        view = self._camera.capture()
        # The fingers are around the glass by now and stand on the table
        # themselves, so the picture is restricted to the depth the glass is
        # believed to be at. The arm put the tool there, so it knows it.
        eye = np.asarray(view.camera_to_world[:3, 3], dtype=float)
        away = float(np.dot(grip_point - eye, np.asarray(view.camera_to_world[:3, 2], dtype=float)))
        mask = the_one_in_the_middle(
            self._things_standing_up(view, within=(away - 0.06, away + 0.06))
        )
        self._report.picture(
            with_mask(view.rgb, mask),
            "in position, looking along the fingers at what they are about to close on",
            then=(
                "The outline is what the arm takes to be the glass. If it is off to one "
                "side, the fingers are beside the glass rather than around it."
            ),
        )
        if not mask.any():
            self._report.doing(
                "look down the fingers and shift sideways",
                "nothing glass-shaped in view, so the aim is left as it is",
            )
            return position

        # The middle of what is there, across the picture.
        columns = np.nonzero(mask.any(axis=0))[0]
        rows = np.nonzero(mask.any(axis=1))[0]
        middle = np.array(
            [
                (float(columns.min()) + float(columns.max())) / 2.0,
                (float(rows.min()) + float(rows.max())) / 2.0,
            ]
        )

        # Where that is in the room, at the distance the glass is already
        # believed to be along the line of sight. The camera frame is x right,
        # y down, z forwards, so this needs no assumption about which way the
        # wrist happens to be rolled.
        ray = view.camera_to_world[:3, :3] @ np.array(
            [
                (middle[0] - view.intrinsics.cx) / view.intrinsics.fx,
                (middle[1] - view.intrinsics.cy) / view.intrinsics.fy,
                1.0,
            ]
        )
        seen = eye + ray * away

        across = rotation[:, 1]
        sideways = float(np.dot(seen - grip_point, across))
        self._report.doing(
            "look down the fingers and shift sideways",
            f"what is in the middle of this picture is **{sideways * 1000:.1f} mm** to one "
            f"side of the fingers, and up to {GRASP_NUDGE_LIMIT * 1000:.0f} mm is allowed",
        )
        if abs(sideways) > GRASP_NUDGE_LIMIT:
            self._report.trouble(
                f"What is in the middle of this picture is {sideways * 1000:.0f} mm off to "
                "one side, which is further than the glass can be and still be the one "
                "about to be held. The aim is left alone and the fingers will report what "
                "they meet."
            )
            return position

        if abs(sideways) < 0.001:
            return position

        moved = position + across * sideways
        self._arm.move_linear([make_pose(moved, rotation)])
        return moved

    def _straight_if_possible(self, position: np.ndarray, rotation: np.ndarray, what: str) -> None:
        """Go there in a straight line, or by any path the planner will allow.

        A straight line is asked for first, and for good reason: it is what
        keeps the fingers from sweeping sideways through a neighbour on the
        way down, and what keeps a held glass over the table rather than over
        the floor. But a Cartesian path is all or nothing — it comes back
        having solved none of the way as readily as all of it, and a run that
        has measured a glass, reached it and closed on it should not end
        because the last 180 mm could not be done in a straight line.

        The fallback is not a free-for-all. Every other glass is in the
        planning scene, so the planner has to miss them too; what is given up
        is the shape of the path, not the checking of it.
        """
        try:
            self._arm.move_linear([make_pose(position, rotation)])
            return
        except MotionFailed as why:
            self._log.info(f"no straight line {what} ({why}), planning a way instead")
            self._report.say(f"No straight line {what}: {why}.")
            self._say_why_stuck()
            self._report.say(
                "Planning a way round instead, which is checked against everything on the "
                "table just the same."
            )

        self._arm.move_to_pose(position, rotation)

    def _say_why_stuck(self) -> None:
        """Ask MoveIt what it thinks is touching, and write it down.

        A path that solves none of the way is nearly always a path whose first
        step was already impossible, and the percentage on its own does not
        say which part of the arm is the problem.
        """
        touching = self._scene.why_stuck()
        if not touching:
            return
        self._log.info("the planner thinks these are touching: " + "; ".join(touching))
        self._report.trouble(
            "The planner already considers the arm to be in collision here, before the "
            "move even starts: " + "; ".join(touching)
        )

    def _hover_and_choose_grasp(
        self,
        grip_point: np.ndarray,
        approaches: list[np.ndarray],
        with_it: dict,
        without_it: dict,
    ) -> np.ndarray:
        """Hover above the glass, turnable, and come straight down around it.

        A parallel gripper is symmetric, so the two orientations half a turn
        apart are the same grip on the same glass. They are not the same to
        the arm: one of them may leave the wrist with no room to invert. Nor
        are the ways round the glass — so both are tried, direction by
        direction, until one is found that the arm can reach, turn, and come
        down from in a straight line.

        Asked here rather than after the fingers close, because finding out
        with the glass in the gripper leaves nothing to do but put it back.

        The glass is in the scene for every move but the descent. The descent
        has to leave it out, since the fingers end up straddling it, so it is
        a straight line or nothing: a planned path with the glass left out is
        free to sweep the fingers through it, and that is how glasses were
        being knocked over. A way round that cannot come straight down is
        dropped, and the next is tried from its own hover.
        """
        tried = 0
        for approach in approaches:
            for rotation in grasp_options(_grasp_rotation(approach)):
                grasp = grip_point - rotation[:, 2] * GRASP_DEPTH
                hover = grasp + UP * LIFT_HEIGHT
                tried += 1
                self._scene.set_glasses(with_it)
                try:
                    self._arm.move_to_pose(hover, rotation)
                except MotionFailed:
                    continue
                if not self._arm.can_rotate_tool(math.pi):
                    continue
                self._scene.set_glasses(without_it)
                try:
                    self._arm.move_linear([make_pose(grasp, rotation)])
                except MotionFailed as why:
                    self._log.info(f"no straight line in to the glass ({why}), trying another way")
                    self._say_why_stuck()
                    continue
                return rotation

        self._scene.set_glasses(with_it)
        raise MotionFailed(
            f"none of the {tried} ways of holding this glass can be reached, turned over "
            "afterwards, and come down in a straight line"
        )

    # -------------------------------------------------------- turn and place

    def _invert_and_place(self, name: str, grip: Grip, slot: Slot, profile: Profile) -> None:
        """Tilt, check for slip, turn right over, then lower until it touches."""
        held_at = self._arm.gripper_gap

        self._report.step(
            f"Step 6 — turning {name} over and standing it down",
            doc="step6-turning-it-over.md",
            code="_invert_and_place() in task.py, turn_wrist() in arm/motion.py",
            level=3,
        )

        # Carry it somewhere with room before turning it. See TURNING_ROOM.
        _, rotation = self._arm.current_pose()
        self._report.doing(
            "carry the glass to the middle of the table",
            f"the glass is parked {TURNING_ROOM[0] * 1000:.0f} mm out and "
            f"{TURNING_ROOM[2] * 1000:.0f} mm up, not the tool — a turn swings the tool a "
            "grasp's depth either side of the glass, so parking the tool at a "
            "comfortable reach puts it past the end of the arm on the way round",
        )
        self._report.say(
            "Turning in place asks more of the wrist than anything else here, and doing it "
            "from wherever the pick happened to end makes it a different problem for every "
            "glass."
        )
        # In a straight line, never by a planned path. A planner free to choose
        # its own way swung a held glass up over the top of the arm and round
        # the far side, and a grip sized for a glass held still threw it off.
        try:
            self._arm.move_linear(
                [make_pose(ROBOT_BASE + np.array(TURNING_ROOM) - rotation[:, 2] * GRASP_DEPTH, rotation)]
            )
        except MotionFailed as why:
            # Not worth losing a held glass over: the turn may still be
            # possible from where it is, and if it is not, that is the failure
            # that gets reported.
            self._log.info(f"could not carry it to the middle ({why}), turning it where it is")

        # Lean it over a little first. Twenty degrees is enough to put some of
        # the glass's weight on the pads sideways, which is what makes it slip
        # if it is going to, and it is a lean the glass can be brought back
        # from. A hundred and eighty degrees is not.
        self._arm.tilt(math.radians(SLIP_TEST_DEG))
        time.sleep(0.4)
        leaning = self._arm.gripper_gap
        self._report.doing(
            "lean it 20 degrees and watch the finger gap",
            f"{held_at * 1000:.1f} mm before the lean, {leaning * 1000:.1f} mm during it"
            + (" — **slipping**" if is_slipping(held_at, leaning) else ", so it is holding"),
        )
        if is_slipping(held_at, leaning):
            raise MotionFailed("the glass slid in the fingers during the tilt")

        self._report.doing(
            "turn 180 degrees about the grip point",
            f"about the grip point, not the tool origin, so the glass turns on the spot. "
            f"{180 - SLIP_TEST_DEG:.0f} degrees of it are left after the lean",
        )
        self._arm.turn_over(already=math.radians(SLIP_TEST_DEG))

        # Upside down, the rim is as far below the pads as it was above them.
        # That distance comes from the measurement, and so does the height the
        # glass is held at, which is why the last few millimetres are felt out
        # rather than driven to.
        _, rotation = self._arm.current_pose()
        rim_to_grip = profile.total_height - grip.height
        # Measured from the rack's top, not the slot's centre, which sits at the
        # marker's height. And clear of the peg, because the move over the slot
        # comes in sideways: a rim any lower meets the peg side on, which knocks
        # the glass round in the fingers and leaves it sitting on the peg.
        landing = landing_point(slot)
        above = landing + UP * (rim_to_grip + PEG_HEIGHT + PLACE_CLEARANCE)

        self._report.doing(
            "move above the slot",
            f"the rim starts {PLACE_CLEARANCE * 1000:.0f} mm above the peg in slot {slot.index}",
        )
        self._report.table(
            {
                "the rack top is at": f"({landing[0]:.3f}, {landing[1]:.3f}, {landing[2]:.3f})",
                "rim to grip": f"{rim_to_grip * 1000:.0f} mm "
                f"({profile.total_height * 1000:.0f} mm tall, held {grip.height * 1000:.0f} up)",
                "so the rim starts": f"{(PEG_HEIGHT + PLACE_CLEARANCE) * 1000:.0f} mm above "
                f"the rack top, {PLACE_CLEARANCE * 1000:.0f} mm over the peg",
                "weight in the wrist": f"{self._arm.wrist_load:.1f} N",
            }
        )
        outward = (slot.centre - ROBOT_BASE)[:2]
        facing = self._carry_over(above, facing_options(rotation, outward))
        self._report.doing(
            "point the gripper away from the base",
            f"pointing along ({facing[0, 2]:.2f}, {facing[1, 2]:.2f})",
        )

        self._report.doing(
            "come down in 2 mm steps until it touches",
            "watching the pad contact sensors and the weight leaving the wrist, for up to "
            f"{(PEG_HEIGHT + DESCENT_LIMIT) * 1000:.0f} mm",
        )
        try:
            # The peg's height is known and passes inside the glass untouched,
            # so it is added to the limit rather than eating into it.
            came_down = self._arm.descend_until_contact(PEG_HEIGHT + DESCENT_LIMIT)
        except MotionFailed:
            self._report.trouble(
                "It went the whole way down without feeling anything. Either the rim is not "
                "where the measurement says it is, or nothing reported the touch: the pads "
                "cannot feel a rim, so what should have said so is the weight leaving the "
                f"wrist, and that still reads {self._arm.wrist_load:.1f} N."
            )
            raise
        self._report.say(
            f"The rim found the rack {came_down * 1000:.0f} mm down, and the wrist now "
            f"carries {self._arm.wrist_load:.1f} N."
        )

        # Before letting go, check the rack is carrying it. If the load has not
        # transferred, the glass is caught on a peg and opening the fingers
        # would drop it.
        taken = self._arm.load_transferred(GRIPPER_WEIGHT_N)
        self._report.doing(
            "is the rack really taking the weight?",
            f"the wrist reads {self._arm.wrist_load:.1f} N against "
            f"{GRIPPER_WEIGHT_N:.1f} N for the gripper alone, so "
            + (
                "the rack has it"
                if taken
                else "**it has not** — the rim is caught, and the fingers stay shut"
            ),
        )
        if not taken:
            raise MotionFailed("the rack is not taking the weight, so the glass is caught")

        self._report.doing("open the fingers")
        self._report.doing("tell the planner the arm is empty")
        self._arm.set_gripper(GRIPPER_MAX_OPENING)
        time.sleep(0.3)
        self._scene.detach(name)

        position, rotation = self._arm.current_pose()
        self._arm.move_linear([make_pose(position + UP * LIFT_HEIGHT, rotation)])

    def _carry_over(self, glass_at: np.ndarray, facings: list[np.ndarray]) -> np.ndarray:
        """Take the held glass to ``glass_at``, facing the first way that works.

        A straight line for each facing first, because a planned path is free
        to swing a held glass round the far side of the arm, and that throws it
        out of the fingers. Slowly, because upside down the glass hangs from
        the line between the pads and a quick move swings it about that line;
        see CARRY_SPEED. Only if no straight line will do is a planned path
        allowed, because by now the glass is upside down and there is nowhere
        better to take it.
        """
        for facing in facings:
            try:
                self._arm.move_linear(
                    [make_pose(glass_at - facing[:, 2] * GRASP_DEPTH, facing)], speed=CARRY_SPEED
                )
                return facing
            except MotionFailed:
                continue
        self._log.info("no straight line over the slot, planning one instead")
        for index, facing in enumerate(facings):
            try:
                self._arm.move_to_pose(glass_at - facing[:, 2] * GRASP_DEPTH, facing)
                return facing
            except MotionFailed:
                if index == len(facings) - 1:
                    raise
        raise MotionFailed("no way of facing was offered")

    def _grip_point(self) -> np.ndarray:
        """Where the pads are gripping, in world coordinates, right now.

        A turn happens about this point rather than about the tool origin,
        because this is the one place on the glass that is not moving relative
        to the fingers. Turning about the tool origin instead would swing the
        glass through an arc as wide as the fingers are long.
        """
        position, rotation = self._arm.current_pose()
        return position + rotation[:, 2] * GRASP_DEPTH

    # ---------------------------------------------------------------- pieces

    def _find_rack(self) -> list[Slot]:
        """Read the marker on the rack, and place all six slots from it."""
        # The camera, not the tool, straight above the middle of RACK_AREA.
        x_from, x_to, y_from, y_to = RACK_AREA
        down = look_along(-UP)
        eye = ROBOT_BASE + np.array([(x_from + x_to) / 2.0, (y_from + y_to) / 2.0, SURVEY_HEIGHT])
        self._arm.move_to_pose(eye - down @ CAMERA_OFFSET, down)
        self._report.step(
            "Before the steps — finding the rack",
            doc="step6-turning-it-over.md",
            code="_find_rack() in task.py, slots_from_marker() in rack/layout.py",
        )
        self._report.say(
            "There is nowhere to put a glass until the rack is found, so this "
            "happens first. The arm looks down at where the rack usually "
            "stands and reads the marker printed on its base: one sighting of "
            "that square places all six slots."
        )
        view = self._camera.capture()
        marker = self._camera.capture_marker(TABLE_TOP_Z)
        self._report.picture(
            view.rgb,
            "looking for the marker on the rack",
            then=(
                "Found it, and the six slots follow from it."
                if marker is not None
                else "**Not found.** Without it there is nowhere to put anything, so the run stops."
            ),
        )
        self._report.doing(
            "read the rack's ArUco marker",
            f"found at ({marker.position[0]:.3f}, {marker.position[1]:.3f}), turned "
            f"{math.degrees(marker.yaw):.0f}°"
            if marker is not None
            else "**not found** — the run stops here",
        )
        if marker is None:
            raise MotionFailed("cannot see the rack, so there is nowhere to put anything")
        slots = slots_from_marker(marker.position, marker.yaw)
        self._report.doing(
            "place the six slots from it",
            "slot 0 at ("
            + f"{slots[0].centre[0]:.3f}, {slots[0].centre[1]:.3f}) through slot "
            + f"{slots[-1].index} at ({slots[-1].centre[0]:.3f}, {slots[-1].centre[1]:.3f})",
        )
        self._log.info(f"rack found, {len(slots)} slots")
        return slots

    def _survey(self, rounds: int = 1) -> list[Detection]:
        """Pictures from above: where the glasses are, and roughly how big.

        Deliberately not what kind each one is. From overhead a tall glass and
        a short one look almost the same and a stem is invisible, so the kind
        is decided later from the side-on measurement.

        Two pictures at each station, not one. A single picture from above
        cannot say how far away a glass is, only which direction it lies in;
        the pair measures the rest. See ``where_they_stand()``.
        """
        self._report.step(
            "Step 1 — finding the glasses"
            + (f" ({_ordinal(rounds)} time round the table)" if rounds > 1 else ""),
            doc="step1-finding-the-glasses.md",
            code="_survey() in task.py, glasses/detect.py",
        )
        self._report.say(
            "One picture from above cannot say how far away a glass is, only "
            "which direction it lies in: the camera has to lay the silhouette "
            "down on the table, and a glass stands above the table. So each "
            "station takes two pictures a known distance apart, and how far a "
            "glass appears to shift between them is what fixes where it "
            "stands. A glass caught in only one of the two cannot be placed "
            "and is left for another station."
        )

        stations = self._stations()
        self._report.doing(
            "work out where to stand the camera",
            f"**{len(stations)} stations** — places to park the camera and take a pair of "
            "pictures — spread over the part of the table the glasses are on, each picture "
            "overlapping its neighbours so that no glass falls only on an edge",
        )

        found: list[Detection] = []
        for number, centre in enumerate(stations, start=1):
            sideways = np.array([0.0, SURVEY_BASELINE / 2.0, 0.0])
            middle = np.array([centre[0], centre[1], SURVEY_HEIGHT])
            try:
                here = self._look_down_from(middle - sideways)
                there = self._look_down_from(middle + sideways)
            except MotionFailed as why:
                # A station the arm cannot reach from where it is standing is
                # a station that goes unphotographed, not a run that stops.
                # The others still cover most of the table, and the next time
                # round the arm is somewhere else and may well manage it.
                self._log.warning(f"skipping a survey station: {why}")
                self._report.doing(
                    "for each station:",
                    f"station {number} of {len(stations)}, at ({centre[0]:.3f}, "
                    f"{centre[1]:.3f}) — **skipped**, the arm could not get there from where "
                    f"it is standing: {why}",
                )
                continue

            # Both pictures are taken from the same commanded height, so one
            # measured height is as good as the other; the mean drops the
            # little the arm missed it by.
            above_table = (here[1][2] + there[1][2]) / 2.0 - TABLE_TOP_Z
            self._report.doing(
                "for each station:",
                f"station {number} of {len(stations)}, at ({centre[0]:.3f}, {centre[1]:.3f}), "
                f"{above_table * 1000:.0f} mm above the table",
            )
            self._report.doing(
                "sightings = lay the patches on the table",
                f"{len(here[0])} in the left picture, {len(there[0])} in the right",
            )
            notes: list[str] = []
            placed = where_they_stand(
                here[0], here[1], there[0], there[1], above_table, tallest=TALLEST_GLASS, notes=notes
            )
            for label, (dets, picture) in (
                ("left", (here[0], here[2])),
                ("right", (there[0], there[2])),
            ):
                self._report.picture(
                    picture,
                    f"station ({centre[0]:.2f}, {centre[1]:.2f}), the {label} picture of the "
                    f"pair: {_count(len(dets), 'glass-shaped patch', 'glass-shaped patches')}",
                    then=(
                        f"Camera at ({(here[1] if label == 'left' else there[1])[0]:.3f}, "
                        f"{(here[1] if label == 'left' else there[1])[1]:.3f}), "
                        f"{above_table * 1000:.0f} mm above the table. "
                        "Where each patch is laid down on the table, before the pair is used: "
                        + ("; ".join(
                            f"({d.position[0]:.3f}, {d.position[1]:.3f}) {d.rough_width * 1000:.0f} mm wide"
                            for d in dets
                        ) or "nothing")
                    ),
                )
            for note in notes:
                self._report.say(f"- {note}")
            self._report.doing(
                "placed = pair the two and solve the height",
                f"**{len(placed)} placed** out of {len(here[0])} and {len(there[0])} seen"
                + (
                    ""
                    if placed
                    else ". Nothing could be paired, so this station contributes nothing"
                ),
            )
            for glass in placed:
                self._report.say(
                    f"- `{glass.name}` stands at ({glass.position[0]:.3f}, "
                    f"{glass.position[1]:.3f}), about {glass.rough_width * 1000:.0f} mm across"
                )
            # A glass in one picture and not the other is a glass this station
            # cannot place, so the count is worth seeing: a station that keeps
            # dropping them is a station whose two pictures are too far apart.
            self._log.info(
                f"station at {np.round(centre, 3).tolist()}: "
                f"{len(here[0])} and {len(there[0])} seen, {len(placed)} placed"
            )
            found += placed

        merged = merge_sightings(found)
        self._report.doing(
            "merge sightings across stations",
            f"{_count(len(found), 'sighting')} from {_count(len(stations), 'station')} "
            f"became **{_count(len(merged), 'glass', 'glasses')}**",
        )
        return merged

    def _look_down_from(
        self, position: np.ndarray
    ) -> tuple[list[Detection], np.ndarray, np.ndarray]:
        """One picture straight down, and where the camera really was for it.

        Where the camera really was, rather than where the arm was sent: the
        camera sits off to one side of the wrist, and the pair of pictures
        measures a distance between them, so being a centimetre out would go
        straight into every position the survey reports.
        """
        self._arm.move_to_pose(ROBOT_BASE + position, look_along(-UP))
        view = self._camera.capture()
        mask = self._things_standing_up(view)
        return (
            find_glasses(mask, view.to_world, TABLE_TOP_Z),
            np.asarray(view.camera_to_world[:3, 3], dtype=float),
            # The outline of what it decided was glass, drawn on the picture
            # it came from. A measurement that is wrong and one that is right
            # about the wrong thing look identical in a number and obvious
            # here.
            with_mask(view.rgb, mask),
        )

    @staticmethod
    def _things_standing_up(view, *, within: tuple[float, float] | None = None) -> np.ndarray:
        """Whatever in this picture is standing on the table rather than being it.

        The glasses are opaque, so the depth camera sees them like anything
        else, and a glass is a patch of the picture whose points are above the
        table top. See ``standing_on_the_table()``.

        Nothing taller than the tallest glass the cell handles counts, which
        keeps the arm's own fingers out of its own pictures. ``within`` adds a
        band of distance when the caller knows roughly how far away the thing
        it came to look at should be.
        """
        return standing_on_the_table(
            view.depth,
            view.intrinsics,
            view.camera_to_world,
            TABLE_TOP_Z,
            tallest=TALLEST_GLASS,
            within=within,
        )

    def _measuring_distance(self) -> float:
        """How far back to stand to measure a glass, worked out from the lens.

        The camera looks level at ``MEASURE_VIEW_HEIGHT``, so the frame has to
        reach down that far to catch the foot the glass stands on and up the
        rest of the way to the rim of the tallest glass the cell handles. Both
        are angles, so how far back that puts the camera depends on the lens,
        and a number written down here would be right for one camera only.

        The foot matters as much as the rim. A wine glass with its foot cut
        off the bottom of the picture is a bowl narrowing to a stem and
        nothing below it, which has no waist in it, and a glass with no waist
        is not a stemmed glass to any rule that looks for one.
        """
        if self._standoff is None:
            view = self._camera.capture()
            rows = view.rgb.shape[0]
            half_frame = (rows / 2.0) / view.intrinsics.fy
            reach = max(MEASURE_VIEW_HEIGHT, TALLEST_GLASS - MEASURE_VIEW_HEIGHT)
            self._standoff = max(MEASURE_STANDOFF, reach / (half_frame * MEASURE_FRAME_MARGIN))
            self._log.info(f"measuring glasses from {self._standoff * 1000:.0f} mm back")
        return self._standoff

    def _stations(self) -> list[np.ndarray]:
        """Where to stand the camera so every glass is in some picture.

        Worked out once, from how much table the camera actually covers at
        survey height, which comes from its own lens rather than from a number
        written down here.
        """
        if self._survey_stations is None:
            view = self._camera.capture()
            rows, columns = view.rgb.shape[:2]
            footprint = (
                SURVEY_HEIGHT * columns / view.intrinsics.fx,
                SURVEY_HEIGHT * rows / view.intrinsics.fy,
            )

            # A station is only worth as much as the part of the table both of
            # its pictures show, because a glass in one and not the other
            # cannot be placed. Sliding sideways for the second picture costs
            # the baseline off that axis, and a glass has to be inside far
            # enough not to be cut off at the edge, which costs the widest
            # glass the gripper could ever close on off both.
            shared = (
                footprint[0] - GRIPPER_MAX_OPENING,
                footprint[1] - SURVEY_BASELINE - GRIPPER_MAX_OPENING,
            )
            self._survey_stations = survey_stations(GLASS_ZONE, shared)
            self._log.info(
                f"surveying from {len(self._survey_stations)} stations, each picture covering "
                f"{footprint[0] * 1000:.0f} x {footprint[1] * 1000:.0f} mm, "
                f"of which {shared[0] * 1000:.0f} x {shared[1] * 1000:.0f} mm is in both"
            )
        return self._survey_stations

    def _choose_slot(self, slots: list[Slot], free: set[int], needs_gap: bool) -> Slot:
        candidates = usable_slots([s for s in slots if s.index in free], needs_gap=needs_gap)

        # Of those, the ones the arm can stand over from either side. Which
        # side it will be standing on is settled by how the glass was picked
        # up, and that is not known yet, so a slot that only works from one
        # side is a coin toss with a glass in hand. If none qualify the list
        # is left alone: a slot that might not work beats refusing a glass
        # that is already held.
        within = slots_within_stretch(candidates, ROBOT_BASE, COMFORTABLE_REACH, GRASP_DEPTH)
        if within:
            candidates = within
        else:
            self._log.info("no slot is reachable from both sides; taking the best of the rest")
        if not candidates:
            raise MotionFailed(
                "no slot left that this glass fits in"
                + (" with an empty neighbour" if needs_gap else "")
            )
        return fill_order(candidates)[0]

    def _stand_clear(self) -> None:
        """Back to somewhere ordinary, after a glass the arm could not manage.

        A pick that fails leaves the arm wherever it gave up, which is usually
        folded in over the table with the planner unable to get anywhere from
        it — and then the next survey cannot be reached either, and one glass
        the arm could not manage turns into a run that does nothing. Failing
        to stand clear is not itself worth stopping for.
        """
        try:
            # Straight up first. Wherever the arm gave up, it gave up close to
            # the table with the glass beside it, and a planner asked to get
            # from there to anywhere has to find its way out of that corner
            # first. Up is the one direction that is always clear.
            position, rotation = self._arm.current_pose()
            self._arm.move_linear([make_pose(position + UP * LIFT_HEIGHT, rotation)])
        except MotionFailed as why:
            self._log.info(f"could not lift clear, trying to park from here: {why}")

        try:
            self._park()
        except MotionFailed as why:
            self._log.warning(f"could not stand clear after that: {why}")

    def _park(self) -> None:
        self._arm.set_gripper(GRIPPER_MAX_OPENING)
        self._arm.move_to_pose(ROBOT_BASE + np.array([0.5, 0.0, SURVEY_HEIGHT]), look_along(-UP))


def _ordinal(which: int) -> str:
    """"second", "third", and so on, for the headings of repeated passes."""
    names = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth")
    return names[which - 1] if which <= len(names) else f"{which}th"


def _count(how_many: int, thing: str, plural: str | None = None) -> str:
    """"3 stations", or "1 station".

    The report is meant to be read, and "1 glasses" in the middle of a sentence
    is the kind of thing that makes a reader stop trusting the rest of it.
    """
    if how_many == 1:
        return f"1 {thing}"
    return f"{how_many} {plural or thing + 's'}"


def _approach_directions(
    handle: float | None, target: Detection, others: list[Detection]
) -> list[np.ndarray]:
    """Which ways the fingers may come in from, best first.

    A glass is round, so for most of them the direction is free, and that
    freedom is worth spending: the wrist's last joint stops short of a full
    turn, so whether a glass can be turned over at all depends on which way
    round it was picked up. One direction is one chance; the ring is several.

    A handle is the exception. There the direction is not free — the fingers
    come in square to it so that neither lands on it — and the only choice
    left is which of the two square-on directions to use.

    Order is by least reach first, which means coming in from the side of the
    glass nearest the arm's own base, and directions that would sweep the
    fingers through a neighbour are left out.
    """
    if handle is not None:
        across = handle + math.pi / 2
        return [
            np.array([math.cos(across), math.sin(across), 0.0]),
            np.array([-math.cos(across), -math.sin(across), 0.0]),
        ]

    # The tool ends up a grasp's depth back along the approach, so coming
    # in along the line out from the base puts it between the base and the
    # glass: the shortest reach of any direction on the ring.
    outward = math.atan2(target.position[1] - ROBOT_BASE[1], target.position[0] - ROBOT_BASE[0])

    directions = []
    for step in sorted(range(-5, 6), key=abs):
        angle = outward + step * math.radians(30.0)
        direction = np.array([math.cos(angle), math.sin(angle), 0.0])
        if not _fingers_clear(target, others, direction):
            continue

        # The tool ends up GRASP_DEPTH back along the approach, and that is
        # the point the arm has to reach. Coming straight in from the
        # base is the shortest reach of any direction, which for a glass
        # already close in can be shorter than the arm can fold itself to.
        tool = (target.position - direction * GRASP_DEPTH - ROBOT_BASE)[:2]
        if not COMFORTABLE_REACH[0] <= float(np.linalg.norm(tool)) <= COMFORTABLE_REACH[1]:
            continue
        directions.append(direction)
    return directions


def _fingers_clear(target: Detection, others: list[Detection], approach: np.ndarray) -> bool:
    """Whether the fingers can come in this way without meeting another glass.

    The gripper comes in along ``approach``, so what has to be clear is the
    length of it behind the glass, and the fingertips that reach past it, not
    the whole ring.
    """
    past = FINGERTIP_OFFSET - GRASP_DEPTH
    for other in others:
        offset = (other.position - target.position)[:2]
        along = float(np.dot(offset, -approach[:2]))
        if not -(past + other.rough_width / 2.0) < along < FINGERTIP_OFFSET + GRASP_OFFSET:
            continue
        across = float(np.linalg.norm(offset - along * -approach[:2]))
        if across < (other.rough_width + GRIPPER_MAX_OPENING) / 2.0:
            return False
    return True


def _grasp_rotation(approach: np.ndarray) -> np.ndarray:
    """Tool orientation that reaches along ``approach`` with the fingers level."""
    z = approach / np.linalg.norm(approach)
    y = np.cross(UP, z)
    y /= np.linalg.norm(y)
    return np.column_stack((np.cross(y, z), y, z))
