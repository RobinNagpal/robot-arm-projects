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
from dataclasses import dataclass

import numpy as np

from .arm.camera import WristCamera
from .arm.dimensions import (
    CAMERA_OFFSET,
    COMFORTABLE_REACH,
    FINGERTIP_OFFSET,
    GRIPPER_MAX_OPENING,
    GRIPPER_WEIGHT_N,
    LIFT_HEIGHT,
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


class PickGlassesTask:
    def __init__(self, node, arm: Arm, camera: WristCamera, scene: PlanningSceneClient) -> None:
        self._log = node.get_logger()
        self._arm = arm
        self._camera = camera
        self._scene = scene
        self._survey_stations: list[np.ndarray] | None = None

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

        while free:
            found = [g for g in self._survey() if g.name not in skip]
            if not found:
                break

            # Nearest first, so the arm never reaches over one glass for
            # another it could have taken first.
            target = min(found, key=lambda g: float(np.linalg.norm(g.position - ROBOT_BASE)))
            self._log.info(f"--- {target.name} ---")

            # The planner is told about every glass except the one being
            # reached for. A glass it believes is solid is a glass it will not
            # let the fingers approach.
            self._scene.set_glasses(
                {
                    other.name: (other.position, other.rough_width, TALLEST_GLASS)
                    for other in found
                    if other.name != target.name
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
        profile = self._view_from(target, others, angle=0.0)
        self._log.info(
            f"measured {profile.total_height * 1000:.0f} mm tall, "
            f"{profile.max_width * 1000:.0f} mm at its widest"
        )

        # 2. Decide what kind of glass it is, from the shape just measured
        #    rather than from the view above. A stem is invisible from overhead.
        name = classify(profile)
        if name is None:
            raise UnknownShape(
                "this is not a shape any rule describes, so it is left standing"
            )
        kind = spec.kind(name)
        self._log.info(f"that shape is a {name}")

        handle = None
        if kind.expects_handle:
            second = self._view_from(target, others, angle=math.radians(SECOND_VIEW_DEG))
            handle = handle_direction(profile, second)
            if handle is not None:
                self._log.info("it has a handle, so the approach comes in square to it")

        # 3. Work out where to hold it.
        grip = find_grip(profile, kind, gripper_max_opening=GRIPPER_MAX_OPENING)
        self._log.info(
            f"holding it {grip.height * 1000:.0f} mm up, fingers "
            f"{grip.opening * 1000:.0f} mm apart"
        )

        # 4. Pick a slot, now that the width is known.
        needs_gap = needs_empty_neighbour(profile.max_width, profile.total_height)
        slot = self._choose_slot(slots, free, needs_gap)
        if needs_gap:
            self._log.info("wide and tall, so the slot beside it stays empty")

        # 5. Pick it up and find out what it weighs.
        mass = self._pick_up(target, profile, grip, kind, handle)
        self._log.info(f"it weighs {mass * 1000:.0f} g")

        # 6. Turn it over and stand it in the rack.
        self._invert_and_place(target.name, grip, slot, profile)

        return Placed(target.name, name, profile, grip, mass, slot.index, needs_gap)

    # ------------------------------------------------------------- measuring

    def _view_from(self, target, others: list[Detection], angle: float) -> Profile:
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

        last: MotionFailed | None = None
        for eye, rotation in self._standoffs(target, others, angle + toward_base):
            try:
                # tool0 does not go to the eye point: the camera is bolted to
                # one side of the tool, and that offset turns with the tool.
                self._arm.move_to_pose(eye - rotation @ CAMERA_OFFSET, rotation)
                break
            except MotionFailed as why:
                last = why
        else:
            raise last if last else MotionFailed("nowhere to stand to look at this glass")

        view = self._camera.capture()

        mask = the_one_in_the_middle(glass_mask(view.rgb, view.depth))
        return profile_from_mask(mask, view.intrinsics, MEASURE_STANDOFF)

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
            eye = target.position + direction * MEASURE_STANDOFF + UP * MEASURE_VIEW_HEIGHT
            out = float(np.linalg.norm((eye - ROBOT_BASE)[:2]))
            if not COMFORTABLE_REACH[0] <= out <= COMFORTABLE_REACH[1]:
                continue
            offered.append((self._blocked(target, others, direction), abs(step), eye, direction))

        for _, _, eye, direction in sorted(offered, key=lambda row: (row[0], row[1])):
            yield eye, look_along(-direction)

    @staticmethod
    def _blocked(target, others: list[Detection], direction: np.ndarray) -> int:
        """How many other glasses stand behind this one, looking in along ``direction``.

        Behind means further along the line of sight and close enough to it to
        overlap in the picture. Both of those come from the survey, which by
        now knows where every glass stands and roughly how wide it is.
        """
        count = 0
        for other in others:
            offset = (other.position - target.position)[:2]
            along = float(np.dot(offset, -direction[:2]))
            if along <= 0.0:
                continue
            across = float(np.linalg.norm(offset - along * -direction[:2]))
            if across < (other.rough_width + target.rough_width) / 2.0:
                count += 1
        return count

    # --------------------------------------------------------------- picking

    def _pick_up(self, target, profile: Profile, grip: Grip, kind, handle) -> float:
        """Close on the glass, lift it a little, and weigh it.

        The order matters. Which way round the gripper holds the glass is
        settled *before* the fingers close, by checking that the arm could turn
        the glass over from there. The last wrist joint stops short of a full
        turn, so some ways of holding a glass leave it impossible to invert,
        and discovering that with the glass already in the gripper leaves
        nothing to do but put it back down.
        """
        approach = _approach_direction(handle)
        grip_point = target.position + UP * grip.height

        self._arm.set_gripper(min(grip.opening + 0.020, GRIPPER_MAX_OPENING))
        rotation = self._hover_and_choose_grasp(grip_point, approach)
        position = grip_point - rotation[:, 2] * FINGERTIP_OFFSET
        self._arm.move_linear([make_pose(position, rotation)])

        # Take up the slack gently. The width when contact arrives is the true
        # width of the glass, measured by touch rather than by camera.
        self._arm.set_gripper_force(CONTACT_FORCE_N)
        time.sleep(0.4)
        touched = self._arm.gripper_gap
        if abs(touched - grip.opening) > 0.004:
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

        self._arm.move_linear([make_pose(position + UP * LIFT_HEIGHT, rotation)])

        # Now that the arm has it, the planner is told so, or it will plan the
        # turn as though the gripper were empty.
        self._scene.attach(
            target.name,
            held_at=target.position,
            width=profile.max_width,
            height=profile.total_height,
            tool_pose=frame(position + UP * LIFT_HEIGHT, rotation),
        )
        return mass

    def _hover_and_choose_grasp(self, grip_point: np.ndarray, approach: np.ndarray) -> np.ndarray:
        """Hover above the glass, holding it whichever way round can be turned.

        A parallel gripper is symmetric, so the two orientations half a turn
        apart are the same grip on the same glass. They are not the same to the
        arm: one of them may leave the wrist with no room to invert.
        """
        for index, rotation in enumerate(grasp_options(_grasp_rotation(approach))):
            hover = grip_point + UP * LIFT_HEIGHT - rotation[:, 2] * FINGERTIP_OFFSET
            try:
                self._arm.move_to_pose(hover, rotation)
            except MotionFailed:
                continue
            if self._arm.can_rotate_tool(math.pi):
                return rotation
            self._log.info("that way round the wrist could not turn it over, trying the other")
            if index:
                break
        raise MotionFailed("no way of holding this glass leaves the wrist able to turn it over")

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
        marker = self._camera.capture_marker(TABLE_TOP_Z)
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
            placed = where_they_stand(here[0], here[1], there[0], there[1], above_table)
            # A glass in one picture and not the other is a glass this station
            # cannot place, so the count is worth seeing: a station that keeps
            # dropping them is a station whose two pictures are too far apart.
            self._log.info(
                f"station at {np.round(centre, 3).tolist()}: "
                f"{len(here[0])} and {len(there[0])} seen, {len(placed)} placed"
            )
            found += placed

        return merge_sightings(found)

    def _look_down_from(self, position: np.ndarray) -> tuple[list[Detection], np.ndarray]:
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
        )

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

    def _park(self) -> None:
        self._arm.set_gripper(GRIPPER_MAX_OPENING)
        self._arm.move_to_pose(ROBOT_BASE + np.array([0.5, 0.0, SURVEY_HEIGHT]), look_along(-UP))


def _approach_direction(handle: float | None) -> np.ndarray:
    """Which way the fingers come in from.

    A glass is round, so for most of them the direction is free and the arm
    takes the one that keeps it clear of its neighbours. A handle is the
    exception: come in square to it, so that neither finger lands on it.
    """
    if handle is None:
        return np.array([1.0, 0.0, 0.0])
    across = handle + math.pi / 2
    return np.array([math.cos(across), math.sin(across), 0.0])


def _grasp_rotation(approach: np.ndarray) -> np.ndarray:
    """Tool orientation that reaches along ``approach`` with the fingers level."""
    z = approach / np.linalg.norm(approach)
    y = np.cross(UP, z)
    y /= np.linalg.norm(y)
    return np.column_stack((np.cross(y, z), y, z))
