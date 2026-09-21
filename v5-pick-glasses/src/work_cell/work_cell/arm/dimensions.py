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
"""

from __future__ import annotations

import numpy as np

# The gripper. Every grip the rules propose is checked against this, and a
# glass too wide for it is left standing rather than attempted.
GRIPPER_MAX_OPENING = 0.095

# How tall the pads are. This is what decides how much upright wall a grip
# needs to sit on, and it is why min_band_height in a glass record is about
# this size.
PAD_HEIGHT = 0.014

# Where the camera sits relative to tool0, in the tool's own frame. It is off
# to one side so the fingers stay out of shot, which means pointing tool0 at
# something is not the same as pointing the camera at it.
CAMERA_OFFSET = np.array([0.085, 0.0, 0.015])

# Distances from tool0, measured along the tool's own z axis, which is the
# direction the gripper reaches in. See arm/gripper.urdf.xacro.
FINGERTIP_OFFSET = 0.170
GRASP_OFFSET = 0.110

# Heights the arm works at, measured from the table top.
SURVEY_HEIGHT = 0.45
LIFT_HEIGHT = 0.18

# How far the wrist camera stands off a glass to measure it. Close enough that
# a glass fills a useful part of the frame, far enough that a tall one fits in
# it at all. The measurement converts pixels to millimetres using this
# distance, so it has to be known rather than guessed — see
# glasses/perception.py.
MEASURE_STANDOFF = 0.30

# How high above the table the wrist camera aims when measuring a glass from
# the side. It is a fixed height rather than half the glass's own height,
# because the overhead view cannot tell how tall a glass is — that is exactly
# what the side view is for. Aiming here keeps anything from a 60 mm tumbler to
# a 240 mm flute inside the frame at MEASURE_STANDOFF.
MEASURE_VIEW_HEIGHT = 0.12

# How far the glass is lifted before it is weighed. Clear of the table, and low
# enough that setting it back down is nothing.
WEIGH_LIFT = 0.010

# How high above the rack the inverted glass is brought before it starts
# feeling its way down. Big enough to clear an error in the measured height,
# small enough that the descent is quick. It must stay under the descent limit
# in arm/motion.py, or a correctly placed glass would be reported as missing.
PLACE_CLEARANCE = 0.030

# How far the glass is tilted, slowly, to find out whether it is slipping
# before the full turn is attempted.
SLIP_TEST_DEG = 20.0

# What the gripper itself weighs, as the wrist force sensor sees it. Subtracted
# from the reading to leave the weight of the glass.
GRIPPER_WEIGHT_N = 9.5

# The last wrist joint stops short of a full turn, so the 180 degrees the glass
# has to rotate through will not fit unless the wrist is wound backwards
# *before* the fingers close. Planning the turn after the grasp is the single
# most expensive mistake available in this task, because it is only discovered
# once the glass is already held.
WRIST_JOINT_LIMIT_DEG = 175.0
