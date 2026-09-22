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
    COMFORTABLE_REACH,
    FINGERTIP_OFFSET,
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
    WEIGH_LIFT,
    survey_stations,
)
from .arm.motion import Arm, MotionFailed
from .glasses import spec
from .glasses.detect import (
    Detection,
    classify,
    find_glasses,
    foot_of,
    glass_mask,
    merge_sightings,
    the_one_in_the_middle,
    where_they_stand,
)
from .glasses.force import (
    CONTACT_FORCE_N,
    TooHeavyToHold,
    force_for_measured_mass,
    is_slipping,
    mass_from_wrist,
    starting_force,
)
from .glasses.perception import NotMeasurable, handle_direction, profile_from_mask
from .glasses.profile import Profile
from .glasses.rules import Grip, NoGrip, find_grip
from .rack.layout import (
    GLASS_ZONE,
    ROBOT_BASE,
    TABLE_TOP_Z,
    Slot,
    fill_order,
    needs_empty_neighbour,
    slots_consumed,
    slots_from_marker,
    usable_slots,
)
from .report import with_mask
from .scene import PlanningSceneClient
from .transforms import frame, grasp_options, look_along, make_pose

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
        while free:
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

            seen = self._survey()
            standing = seen
            found = [g for g in seen if g.name not in skip]
            if not found:
                break

            # Nearest first, so the arm never reaches over one glass for
            # another it could have taken first.
            target = min(found, key=lambda g: float(np.linalg.norm(g.position - ROBOT_BASE)))
            self._log.info(f"--- {target.name} ---")
            self._report.step(f"Working on {target.name}")
            self._report.say(
                f"The nearest of the {len(found)} it can see, so it goes first: reaching over "
                "one glass for another it could have taken is how neighbours get knocked over. "
                f"It stands at ({target.position[0]:.3f}, {target.position[1]:.3f}) and looks "
                f"about {target.rough_width * 1000:.0f} mm across from above. Next it goes round "
                "to the side to measure it properly, because from overhead a tall glass and a "
                "short one look the same and a stem is invisible."
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
        others = [g for g in found if g.name != target.name]
        profile, foot = self._view_from(target, others, angle=0.0)
        if foot is not None:
            # The survey put the arm in front of the right glass; the picture
            # it took there says where that glass actually stands, to within
            # the width of a stem. Everything from here on is a grasp.
            moved = float(np.linalg.norm((foot - target.position)[:2]))
            self._log.info(f"the side view puts it {moved * 1000:.0f} mm from where the survey did")
            target = replace(target, position=foot)
        self._log.info(
            f"measured {profile.total_height * 1000:.0f} mm tall, "
            f"{profile.max_width * 1000:.0f} mm at its widest"
        )

        # 2. Decide what kind of glass it is, from the shape just measured
        #    rather than from the view above. A stem is invisible from overhead.
        self._report.table(
            {
                "measured height": f"{profile.total_height * 1000:.0f} mm",
                "measured width": f"{profile.max_width * 1000:.0f} mm",
            }
        )
        name = classify(profile)
        self._report.say(
            f"From that shape it is **{name or 'no kind any rule describes'}**."
            + (
                ""
                if name
                else " Nothing is known about how to hold it, so it is left standing."
            )
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
        grip = find_grip(
            profile, kind, gripper_max_opening=GRIPPER_MAX_OPENING, lowest_grip=LOWEST_GRIP
        )
        self._log.info(
            f"holding it {grip.height * 1000:.0f} mm up, fingers "
            f"{grip.opening * 1000:.0f} mm apart"
        )
        self._report.say(
            f"The rule for a {name} picks a height of **{grip.height * 1000:.0f} mm** up the "
            f"glass, where the camera measured it **{grip.opening * 1000:.0f} mm** across. That "
            "opening is not looked up anywhere: it is the width that was measured at that "
            "height a moment ago. The fingers will go there and close until they touch, and if "
            "what they touch is not that wide, the grasp is not where it should be."
        )

        # 4. Pick a slot, now that the width is known.
        needs_gap = needs_empty_neighbour(profile.max_width, profile.total_height)
        slot = self._choose_slot(slots, free, needs_gap)
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
        because the glass stands on the table and the table has been measured —
        the arm never needs a depth reading of the glass itself, which through
        transparent glass it could not get.

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

        trouble: Exception | None = None
        for eye, rotation in self._standoffs(target, others, angle + toward_base):
            try:
                # tool0 does not go to the eye point: the camera is bolted to
                # one side of the tool, and that offset turns with the tool.
                self._arm.move_to_pose(eye - rotation @ CAMERA_OFFSET, rotation)
            except MotionFailed as why:
                trouble = why
                continue

            view = self._camera.capture()
            mask = the_one_in_the_middle(glass_mask(view.rgb, view.depth))
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
                foot = foot_of(mask, view.to_world, TABLE_TOP_Z)
                if foot is not None:
                    strayed = float(np.linalg.norm((foot - target.position)[:2]))
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
                trouble = why

        raise trouble if trouble else MotionFailed("nowhere to stand to look at this glass")

    def _standoffs(self, target, others: list[Detection], preferred: float):
        """Places to stand the camera to look at one glass, best first.

        Two things decide the order. A glass standing behind the one being
        measured is a second hole in the same depth picture, touching the
        first, and the two measure as one glass the width of the table — so a
        line of sight with nothing behind it comes first. After that, the
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

        # Only now does the glass come out of the scene. Up to this point the
        # arm has been carrying the camera around it, and a planner that does
        # not know it is there routes an elbow straight through it. From here
        # on the fingers have to end up straddling it, which no planner will
        # agree to, so it has to go — and what is left is a hover directly
        # above it and a descent down the tool's own axis.
        self._scene.set_glasses(
            {
                other.name: (other.position, other.rough_width, TALLEST_GLASS)
                for other in others
            }
        )

        self._arm.set_gripper(min(grip.opening + 0.020, GRIPPER_MAX_OPENING))
        rotation = self._hover_and_choose_grasp(grip_point, approaches)
        position = grip_point - rotation[:, 2] * FINGERTIP_OFFSET
        self._straight_if_possible(position, rotation, "in to the glass")

        # Take up the slack gently. The width when contact arrives is the true
        # width of the glass, measured by touch rather than by camera.
        self._report.say(
            f"Reaching in along ({rotation[0, 2]:.2f}, {rotation[1, 2]:.2f}) with the fingers "
            f"opened to {min(grip.opening + 0.020, GRIPPER_MAX_OPENING) * 1000:.0f} mm, then "
            "closing gently until they touch."
        )
        self._arm.set_gripper_force(CONTACT_FORCE_N)
        time.sleep(0.4)
        touched = self._arm.gripper_gap
        self._report.table(
            {
                "the camera said": f"{grip.opening * 1000:.1f} mm",
                "the fingers found": f"{touched * 1000:.1f} mm",
                "difference": f"{(touched - grip.opening) * 1000:.1f} mm (4 mm is allowed)",
            }
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

        self._arm.set_gripper_force(starting_force(profile, kind))
        time.sleep(0.3)

        # Lift a centimetre and weigh it. This is the last moment a mistake is
        # free: the glass is off the table but nothing has been turned over.
        self._arm.move_linear([make_pose(position + UP * WEIGH_LIFT, rotation)])
        mass = mass_from_wrist(self._arm.wrist_force_z, GRIPPER_WEIGHT_N)

        needed = force_for_measured_mass(mass, kind)
        if needed > starting_force(profile, kind):
            # Setting it down and re-gripping is safe; increasing the squeeze
            # while holding it arrives as a shock.
            self._log.info(f"heavier than it looked, re-gripping at {needed:.1f} N")
            self._arm.move_linear([make_pose(position, rotation)])
            self._arm.set_gripper_force(needed)
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
        except MotionFailed as why:
            self._log.info(f"no straight line {what} ({why}), planning a way instead")
            self._report.say(
                f"No straight line {what}: {why}. Planning a way round instead, which is "
                "checked against everything on the table just the same."
            )
            self._arm.move_to_pose(position, rotation)

    def _hover_and_choose_grasp(
        self, grip_point: np.ndarray, approaches: list[np.ndarray]
    ) -> np.ndarray:
        """Hover above the glass, holding it whichever way round can be turned.

        A parallel gripper is symmetric, so the two orientations half a turn
        apart are the same grip on the same glass. They are not the same to
        the arm: one of them may leave the wrist with no room to invert. Nor
        are the ways round the glass — so both are tried, direction by
        direction, until one is found that the arm can both reach and turn.

        Asked here rather than after the fingers close, because finding out
        with the glass in the gripper leaves nothing to do but put it back.
        """
        self._report.say(
            f"Looking for a way to hold it: {len(approaches)} directions the fingers could come "
            "in from, two ways round for each, and the arm has to be able to reach it *and* "
            "still turn the wrist far enough to put the glass upside down afterwards. Asked "
            "now rather than later, because finding out with the glass already held leaves "
            "nothing to do but put it back."
        )
        tried = 0
        for approach in approaches:
            for rotation in grasp_options(_grasp_rotation(approach)):
                hover = grip_point + UP * LIFT_HEIGHT - rotation[:, 2] * FINGERTIP_OFFSET
                tried += 1
                try:
                    self._arm.move_to_pose(hover, rotation)
                except MotionFailed:
                    continue
                if self._arm.can_rotate_tool(math.pi):
                    self._report.picture(
                        self._camera.capture().rgb,
                        f"hovering over the glass, about to come down and close "
                        f"(way {tried} of the ones tried)",
                        then=(
                            "This is the last look before the fingers go in. If the glass is "
                            "not under them here, it will not be between them a moment later."
                        ),
                    )
                    return rotation

        raise MotionFailed(
            f"none of the {tried} ways of holding this glass leave the wrist able to "
            "turn it over"
        )

    # -------------------------------------------------------- turn and place

    def _invert_and_place(self, name: str, grip: Grip, slot: Slot, profile: Profile) -> None:
        """Tilt, check for slip, turn right over, then lower until it touches."""
        held_at = self._arm.gripper_gap

        # Lean it over a little first. Twenty degrees is enough to put some of
        # the glass's weight on the pads sideways, which is what makes it slip
        # if it is going to, and it is a lean the glass can be brought back
        # from. A hundred and eighty degrees is not.
        self._arm.tilt(math.radians(SLIP_TEST_DEG), about=self._grip_point())
        time.sleep(0.4)
        if is_slipping(held_at, self._arm.gripper_gap):
            raise MotionFailed("the glass slid in the fingers during the tilt")

        self._arm.turn_over(about=self._grip_point())

        # Upside down, the rim is as far below the pads as it was above them.
        # That distance comes from the measurement, and so does the height the
        # glass is held at, which is why the last few millimetres are felt out
        # rather than driven to.
        _, rotation = self._arm.current_pose()
        rim_to_grip = profile.total_height - grip.height
        above = slot.centre + UP * (rim_to_grip + PLACE_CLEARANCE)
        self._arm.move_to_pose(above - rotation[:, 2] * FINGERTIP_OFFSET, rotation)
        self._arm.descend_until_contact()

        # Before letting go, check the rack is carrying it. If the load has not
        # transferred, the glass is caught on a peg and opening the fingers
        # would drop it.
        if not self._arm.load_transferred(GRIPPER_WEIGHT_N):
            raise MotionFailed("the rack is not taking the weight, so the glass is caught")

        self._arm.set_gripper(GRIPPER_MAX_OPENING)
        time.sleep(0.3)
        self._scene.detach(name)

        position, rotation = self._arm.current_pose()
        self._arm.move_linear([make_pose(position + UP * LIFT_HEIGHT, rotation)])

    def _grip_point(self) -> np.ndarray:
        """Where the pads are gripping, in world coordinates, right now.

        A turn happens about this point rather than about the tool origin,
        because this is the one place on the glass that is not moving relative
        to the fingers. Turning about the tool origin instead would swing the
        glass through an arc as wide as the fingers are long.
        """
        position, rotation = self._arm.current_pose()
        return position + rotation[:, 2] * FINGERTIP_OFFSET

    # ---------------------------------------------------------------- pieces

    def _find_rack(self) -> list[Slot]:
        """Read the marker on the rack, and place all six slots from it."""
        self._arm.move_to_pose(
            ROBOT_BASE + np.array([0.5, 0.3, SURVEY_HEIGHT]), look_along(-UP)
        )
        self._report.step("Finding the rack")
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
        if marker is None:
            raise MotionFailed("cannot see the rack, so there is nowhere to put anything")
        slots = slots_from_marker(marker.position, marker.yaw)
        self._log.info(f"rack found, {len(slots)} slots")
        return slots

    def _survey(self) -> list[Detection]:
        """Pictures from above: where the glasses are, and roughly how big.

        Deliberately not what kind each one is. From overhead a tall glass and
        a short one look almost the same and a stem is invisible, so the kind
        is decided later from the side-on measurement.

        Two pictures at each station, not one. A single picture from above
        cannot say how far away a glass is, only which direction it lies in;
        the pair measures the rest. See ``where_they_stand()``.
        """
        self._report.step("Looking for the glasses")
        self._report.say(
            "One picture from above cannot say how far away a glass is, only "
            "which direction it lies in: the camera has to lay the silhouette "
            "down on the table, and a glass stands above the table. So each "
            "station takes two pictures a known distance apart, and how far a "
            "glass appears to shift between them is what fixes where it "
            "stands. A glass caught in only one of the two cannot be placed "
            "and is left for another station."
        )

        found: list[Detection] = []
        for centre in self._stations():
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
                continue

            # Both pictures are taken from the same commanded height, so one
            # measured height is as good as the other; the mean drops the
            # little the arm missed it by.
            above_table = (here[1][2] + there[1][2]) / 2.0 - TABLE_TOP_Z
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
                    f"station ({centre[0]:.2f}, {centre[1]:.2f}), the {label} picture of the pair: "
                    f"{len(dets)} glass-shaped holes",
                    then=(
                        f"Camera at ({(here[1] if label == 'left' else there[1])[0]:.3f}, "
                        f"{(here[1] if label == 'left' else there[1])[1]:.3f}), "
                        f"{above_table * 1000:.0f} mm above the table. "
                        "Where each hole is laid down on the table, before the pair is used: "
                        + ("; ".join(
                            f"({d.position[0]:.3f}, {d.position[1]:.3f}) {d.rough_width * 1000:.0f} mm wide"
                            for d in dets
                        ) or "nothing")
                    ),
                )
            for note in notes:
                self._report.say(f"- {note}")
            self._report.say(
                f"From that pair: **{len(placed)} placed** out of {len(here[0])} and "
                f"{len(there[0])} seen."
                + (
                    ""
                    if placed
                    else " Nothing could be paired, so this station contributes nothing."
                )
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

        return merge_sightings(found)

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
        mask = glass_mask(view.rgb, view.depth)
        return (
            find_glasses(mask, view.to_world, TABLE_TOP_Z),
            np.asarray(view.camera_to_world[:3, 3], dtype=float),
            # The outline of what it decided was glass, drawn on the picture
            # it came from. A measurement that is wrong and one that is right
            # about the wrong thing look identical in a number and obvious
            # here.
            with_mask(view.rgb, mask),
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

    # The tool ends up a fingertip's length back along the approach, so coming
    # in along the line out from the base puts it between the base and the
    # glass: the shortest reach of any direction on the ring.
    outward = math.atan2(target.position[1] - ROBOT_BASE[1], target.position[0] - ROBOT_BASE[0])

    directions = []
    for step in sorted(range(-5, 6), key=abs):
        angle = outward + step * math.radians(30.0)
        direction = np.array([math.cos(angle), math.sin(angle), 0.0])
        if not _fingers_clear(target, others, direction):
            continue

        # The tool ends up a fingertip's length back along the approach, and
        # that is the point the arm has to reach. Coming straight in from the
        # base is the shortest reach of any direction, which for a glass
        # already close in can be shorter than the arm can fold itself to.
        tool = (target.position - direction * FINGERTIP_OFFSET - ROBOT_BASE)[:2]
        if not COMFORTABLE_REACH[0] <= float(np.linalg.norm(tool)) <= COMFORTABLE_REACH[1]:
            continue
        directions.append(direction)
    return directions


def _fingers_clear(target: Detection, others: list[Detection], approach: np.ndarray) -> bool:
    """Whether the fingers can come in this way without meeting another glass.

    The gripper comes in along ``approach``, so what has to be clear is the
    length of it behind the glass, not the whole ring.
    """
    for other in others:
        offset = (other.position - target.position)[:2]
        along = float(np.dot(offset, -approach[:2]))
        if not 0.0 < along < FINGERTIP_OFFSET + GRASP_OFFSET:
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
