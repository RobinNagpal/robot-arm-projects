"""The arm's own measurements.

These are the numbers the code needs that are not in the robot model: how far
the fingertips reach past the flange, where the camera sits, and how high above
the table the arm does each part of its job. They are here rather than read out
of the URDF because they describe how the arm is *used*, not how it is built.

Every number in this file belongs to the arm. None of them belongs to a glass:
a glass's size is measured at run time, and where to hold it comes from a rule
in glasses/spec.py. If a number about a glass ever appears here, something has
gone wrong further up.

Anything changed here has a matching number in arm.urdf.xacro or
gripper.urdf.xacro, and the two have to move together.

The tool is three real products in a stack, and the numbers below follow from
them rather than from anything this project chose:

- a **Robotiq FT 300-S** force/torque sensor on the flange,
- a **Robotiq 2F-85** two-finger gripper on the sensor,
- an **Intel RealSense D405** depth camera beside the gripper.

Each one publishes its own robot description, so the shapes, masses and joint
limits are read out of ``robotiq_description`` and ``realsense2_description``
instead of being drawn here. What is left in this file is how the arm *uses*
that tool, which is this project's business and nobody else's.
"""

from __future__ import annotations

import math

import numpy as np

from . import robotiq_2f85

# How far the fingers part. The 2F-85's published 85 mm stroke, worked out
# from the linkage in arm/robotiq_2f85.py rather than typed in, so it cannot
# drift away from the model the simulator loads. This is the number to open
# the gripper to when it is being got out of the way.
GRIPPER_MAX_OPENING = robotiq_2f85.MAX_OPENING

# The widest glass that can actually be *held*, which is a few millimetres
# less. Every grip the rules propose is checked against this one, and a glass
# too wide for it is left standing rather than attempted.
#
# The two differ because of where the pads sit. A glass is held at the middle
# of the pads, and on this gripper the pads sit further back along the fingers
# the wider it opens, so a glass filling the last few millimetres of the
# stroke would reach back and touch the gripper's own body. Robotiq's 85 mm is
# how far the fingers part, which is a different question from how wide a
# round thing they can close on properly.
GRIPPER_MAX_GRIP = robotiq_2f85.MAX_GRIP

# How tall the pads are. This is what decides how much upright wall a grip
# needs to sit on, and it is why min_band_height in a glass record is about
# this size. The 2F-85's pad is 22 mm across, which is noticeably more than
# this project used to assume, so a grip now needs more straight wall.
PAD_HEIGHT = robotiq_2f85.PAD_HEIGHT

# How far the pads run along each finger.
PAD_LENGTH = robotiq_2f85.PAD_LENGTH

# The two real parts between the flange and the gripper, along the tool's own
# z axis, which is the direction the gripper reaches in.
#
# The FT 300-S's thickness is the figure Robotiq publish in the FT 300
# specification table. They describe the 300-S as a redesign of that sensor
# and do not publish a thickness for it separately, so this is the closest
# published number and it is the one to check first against a real sensor.
FORCE_SENSOR_HEIGHT = 0.0375

# Robotiq's own UR-to-gripper coupling, whose mount face sits this far above
# the plate. From ur_to_robotiq_adapter.urdf.xacro in robotiq_description.
GRIPPER_ADAPTER_HEIGHT = 0.011

# Where the gripper's own base sits, measured from tool0. Everything the
# gripper description says is measured from there, so this is the one offset
# that turns its numbers into this cell's numbers.
TOOL_TO_GRIPPER_BASE = FORCE_SENSOR_HEIGHT + GRIPPER_ADAPTER_HEIGHT

# Where the camera's own lens sits relative to tool0, in the tool's frame. It
# is off to one side so the fingers stay out of shot, which means pointing
# tool0 at something is not the same as pointing the camera at it, and this is
# what the difference is.
#
# The side it is off to is not free. The fingers swing in the tool's x
# direction and reach about 74 mm out either way when the gripper is open, so
# a camera mounted that way would be inside their swing. Across the fingers,
# in y, the widest thing is the gripper's own 75 mm body, so that is the side
# with room. Half that body, half the camera's thickness and a millimetre to
# spare clears it, which is where the mounting screw goes.
#
# How far *along* the tool it sits is the interesting half, and the camera
# decided it. The D405 cannot focus closer than about 70 mm, and the closest
# look this task takes is down the fingers at a glass they are already round.
# Mounted level with the middle of the gripper's body, the lens would be
# between 37 and 66 mm from the wall of any glass wider than about 30 mm,
# which is inside the camera's blind zone: that look would come back as
# nothing. Mounted at the *back* of the body instead, it is 71 mm away from
# the widest glass the gripper can hold and further from everything narrower,
# so the whole range fits. There is no room to go further back either, because
# the force sensor is behind it.
CAMERA_MOUNT = np.array([0.0, 0.0375 + 0.0115 + 0.001, TOOL_TO_GRIPPER_BASE + 0.010])

# The lens is not at the screw, and the gap is Intel's to decide rather than
# ours. Their description places the camera's own frame away from its mounting
# face by these three offsets, which in the tool's frame land along z, x and y
# in that order because the camera is turned a quarter turn to look the way the
# fingers point. They are imported from the published figures in spirit: each
# one is named in _d405.urdf.xacro, and test_dimensions.py reads that file and
# checks these against it, so an update to the camera package cannot move the
# lens without a test noticing.
#
# 10.85 mm forward is the depth sensor's distance behind the front glass,
# 9 mm is its sideways offset in the case, and 21 mm is half the case's height.
CAMERA_LENS_IN_CASE = np.array([0.009, 0.021, 0.01085])

CAMERA_OFFSET = CAMERA_MOUNT + CAMERA_LENS_IN_CASE

# The lowest a glass can be held, measured from the table top. The gripper
# comes in level, so the whole tool lies across the grip height rather than
# above it, and whatever hangs furthest below the tool's axis is what decides
# this. That is no longer the gripper: the 2F-85's body is 75 mm across, so it
# hangs 37.5 mm down, while the FT 300-S is 89 mm across on its robot side and
# hangs 44.5 mm down. Five millimetres of clearance under the sensor, rounded
# up, is how low the tool can go.
#
# Not a fact about glasses. A glass too short to be held this far up and still
# below its own half height is a glass this gripper cannot pick up, which is a
# result and not a failure.
LOWEST_GRIP = 0.050

# How far sideways the fingers may be shifted at the last moment, on the
# strength of the close-up look down them. Half the gripper's opening: a glass
# further off than that is not the one about to be closed on, and shifting
# onto it would be aiming at the wrong thing rather than aiming better.
GRASP_NUDGE_LIMIT = GRIPPER_MAX_OPENING / 2.0

# How far the fingertips reach past the flange: the furthest point of the
# fingertip, 149.35 mm above the gripper's own base, plus the stack under it.
# The real tool is about 30 mm longer than the one this project used to
# assume, which costs reach at the far corner of the glass zone.
FINGERTIP_OFFSET = TOOL_TO_GRIPPER_BASE + robotiq_2f85.FINGERTIP_REACH

GRASP_OFFSET = 0.110


def grasp_depth(opening: float) -> float:
    """Where the middle of the pads sits, from tool0, at a given finger gap.

    This is where the glass's axis has to be put. At the fingertip instead,
    the pads meet the glass only with their front edge, on the far side of its
    widest line, and squeezing a round glass there pushes it out of the
    fingers. With the axis at the middle of the pads, the whole pad length
    straddles the widest line, so an aim a few millimetres out still has pad
    either side of it.

    It is a function of the gap rather than a fixed number, and that is the
    one thing about the real gripper that a sliding gripper would not have
    forced. The 2F-85's fingers **swing** on a linkage instead of sliding
    along a rail, so as they come together they also come forward, by up to
    about 13.5 mm over the stroke. The pads therefore sit deeper the tighter
    the gripper is closed.

    So the gap has to be known before the tool is placed, and it is: the glass
    is measured first, and the gap follows from the measurement. Placing the
    tool for the gap the fingers will *end* at, rather than the gap they
    approach at, is what keeps the glass's axis in the middle of the pads.
    Ignoring it would leave the axis 13.5 mm behind the middle on a tight
    grip, which on a 38 mm pad is most of the way to its near edge — exactly
    the failure the paragraph above is about.
    """
    return TOOL_TO_GRIPPER_BASE + robotiq_2f85.pad_reach(robotiq_2f85.angle_for(opening))


# Where the pads sit while the gripper is open, which is the depth the arm
# approaches at before it knows better. Anything that holds a glass uses
# grasp_depth() with the gap it is going to close to.
GRASP_DEPTH = grasp_depth(GRIPPER_MAX_OPENING)

# Where the arm takes a glass to turn it over, measured from the base and the
# table top. Turning in place asks more of the wrist than anything else in the
# task, and where the pick happens to leave the arm is not chosen with that in
# mind — reaching out to the far corner of the glass zone leaves it stretched,
# which is exactly where the last joint has least left to give. Carrying the
# glass here first costs one move and makes the turn the same problem every
# time, in the middle of what the arm can do, instead of a different one for
# each glass.
#
# It says where the *glass* goes, not where the tool goes. The turn swings the
# tool through GRASP_DEPTH either side of the glass, so a tool parked at a
# comfortable reach comes out of the turn 300 mm further out than it went in —
# past the end of the arm. The glass is the thing that stays put, so the glass
# is what this places: 500 mm out leaves the tool at 350 before the turn and
# 650 after it, and both of those the arm can do.
TURNING_ROOM = (0.50, 0.0, 0.35)

# Heights the arm works at, measured from the table top.
SURVEY_HEIGHT = 0.45
LIFT_HEIGHT = 0.18

# How far the camera slides sideways between the two pictures that make a
# survey. It has to be wide enough that the apparent movement of a glass is
# much bigger than the error in finding its middle, and narrow enough that
# both pictures still catch the same glasses. A glass standing a third of the
# survey height tall shifts by half as much again as the camera does.
SURVEY_BASELINE = 0.12

# How much of one picture the next one repeats. A glass caught at the very
# edge of a picture is cut off, and a cut-off silhouette has its middle in the
# wrong place, so the stations are set close enough that anything cut off at
# one is well inside another.
SURVEY_OVERLAP = 0.35

# How far out from its base the arm works comfortably, measured flat on the
# table. Closer than the first and it is folded over itself; further than the
# second and it is reaching straight out with nothing left for the wrist. Used
# to choose which side of a glass to stand the camera on, not as a hard limit:
# whether a pose is really reachable is the planner's answer, not ours.
COMFORTABLE_REACH = (0.30, 0.78)

# The closest the wrist camera is ever stood off a glass to measure it. The
# distance actually used is worked out per cell from the lens, because what
# has to fit in the frame — the table at the bottom, the rim of the tallest
# glass at the top — is a question about the lens as much as about the glass.
# This is the floor on that: nearer than it and the glass fills the frame
# before it is all in it. The measurement converts pixels to millimetres using
# whatever distance was used, so it has to be known rather than guessed — see
# glasses/perception.py.
MEASURE_STANDOFF = 0.30

# How much of the half frame the glass may fill, top to bottom. The rest is
# margin: the arm does not arrive exactly where it was sent, and a rim that
# lands one row outside the picture is a glass measured short.
MEASURE_FRAME_MARGIN = 0.85

# How high above the table the wrist camera aims when measuring a glass from
# the side. It is a fixed height rather than half the glass's own height,
# because the overhead view cannot tell how tall a glass is — that is exactly
# what the side view is for. Aiming here keeps anything from a 60 mm tumbler to
# a 240 mm flute inside the frame at MEASURE_STANDOFF.
MEASURE_VIEW_HEIGHT = 0.12

# How far the glass is lifted before it is weighed. Clear of the table, and low
# enough that setting it back down is nothing.
WEIGH_LIFT = 0.010

# How far weighing has to move the grip before the fingers are moved to match.
# Under this, opening and re-closing costs more than the lever it takes away.
REGRIP_SHIFT = 0.002

# How high above the rack the inverted glass is brought before it starts
# feeling its way down. Big enough to clear an error in the measured height,
# small enough that the descent is quick. It must stay under the descent limit
# in arm/motion.py, or a correctly placed glass would be reported as missing.
PLACE_CLEARANCE = 0.030

# How fast an upside-down glass is carried to the rack, as a share of the
# arm's speed and acceleration limits. Held upside down, a glass hangs from the
# line between the two pads and can swing about it like a hinge. The pads hold
# its weight well and resist that swing poorly, and the carry also turns the
# gripper round, so it is done at a quarter of the usual 0.2.
CARRY_SPEED = 0.05

# How far the glass is tilted, slowly, to find out whether it is slipping
# before the full turn is attempted.
SLIP_TEST_DEG = 20.0

# What the tool itself weighs, as the wrist force sensor sees it. Subtracted
# from the reading to leave the weight of the glass.
#
# The sensor sits on the flange and reads only what is bolted beyond it, so
# its own 442 g is not in this sum. What is in it is the coupling, the gripper
# and the camera: 10 g, 921 g and 72 g, each taken from the link masses in the
# descriptions the simulator loads rather than from a data sheet.
GRIPPER_WEIGHT_N = (0.010 + 0.9209 + 0.072) * 9.81

# What the force sensor can and cannot settle, which decides how a glass gets
# weighed. The FT 300-S resolves about 0.1 N of noise on each force axis and
# Robotiq recommend 1 N as the smallest contact worth acting on. A glass
# weighs between about 1.5 N and 4 N, so weighing one is a few multiples of
# the noise floor and perfectly sound.
#
# This is the number that decided the sensor. The UR5e has a force sensor of
# its own built into the flange, which would have cost nothing and needed no
# description — but Universal Robots publish ±4.0 N of accuracy for it, which
# is the whole weight of a wine glass. A sensor that cannot tell a held glass
# from an empty gripper cannot do the one job this project needs it for.
FORCE_SENSOR_NOISE_N = 0.1
FORCE_SENSOR_THRESHOLD_N = 1.0

# The last wrist joint stops short of a full turn, so the 180 degrees the glass
# has to rotate through will not fit unless the wrist is wound backwards
# *before* the fingers close. Planning the turn after the grasp is the single
# most expensive mistake available in this task, because it is only discovered
# once the glass is already held.
WRIST_JOINT_LIMIT_DEG = 175.0


def survey_stations(
    zone: tuple[float, float, float, float],
    footprint: tuple[float, float],
    *,
    overlap: float = SURVEY_OVERLAP,
) -> list[np.ndarray]:
    """Where to stand the camera so that every part of ``zone`` is in a picture.

    A station is one place to park the camera and take a picture from. One
    picture from survey height does not cover the whole table, so the zone is
    covered by several of them: as few as will do, spread evenly, each picture
    overlapping its neighbour so that nothing lands only on an edge.

    ``zone`` is (x from, x to, y from, y to) and ``footprint`` is how much
    table one picture covers, which the camera works out from its own lens
    rather than being told.
    """
    x_from, x_to, y_from, y_to = zone
    centres = []
    for span, reach, low in (
        (x_to - x_from, footprint[0], x_from),
        (y_to - y_from, footprint[1], y_from),
    ):
        step = reach * (1.0 - overlap)
        if reach <= 0.0 or step <= 0.0:
            raise ValueError("a picture that covers nothing cannot be spread into a survey")

        # One station is enough when the whole span already fits in one picture.
        count = 1 if span <= reach else int(math.ceil((span - reach) / step)) + 1
        if count == 1:
            centres.append([low + span / 2.0])
        else:
            gap = (span - reach) / (count - 1)
            centres.append([low + reach / 2.0 + index * gap for index in range(count)])

    return [np.array([x, y]) for x in centres[0] for y in centres[1]]
