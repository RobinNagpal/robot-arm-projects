"""The Robotiq 2F-85's linkage: what one knuckle angle does to the fingers.

The rest of this project thinks about the gripper in millimetres. It measures a
glass, works out how wide the pads must sit apart, and asks for that width.
The real gripper does not take a width. It has **one motor driving one knuckle
joint**, and both fingers hang off that joint through a four-bar linkage, so
the only thing that can be commanded is an angle in radians. Everything else
follows from it.

This module is the translation between the two. It answers three questions:

- Given a width the task wants, what angle does the gripper have to be at?
- Given an angle the gripper is actually at, how far apart are the pads?
- Given that angle, where along the finger does the pad sit?

The third question is the one that does not arise with a sliding gripper, and
it matters here. Because the fingers swing rather than slide, the pads travel
along an **arc**: closing the gripper moves the pads sideways, which is the
point, but it also moves them *forwards*, further from the flange. Over the
full stroke that forward travel is about 13 mm. The tool points down at the
table, so forwards means downwards, which means closing the gripper slides the
contact patch **down the wall of the glass**. A grip rule that picks a height
on the glass and drives the tool there would therefore land the pads somewhere
lower than it chose. Since the width is measured before the fingers close, the
angle is known in advance, so the travel can be worked out and taken off the
approach height. That is what ``pad_reach()`` is for.

Every number here is read out of ``robotiq_description``, the description
package Robotiq publish, and not measured by hand or taken from a drawing. The
link offsets are the joint origins in ``robotiq_2f_85_macro.urdf.xacro`` and
the pad face comes from the fingertip collision mesh that ships beside it. So
if the description is updated, these are the only numbers to re-read.

Plain numpy, no ROS, so it can be tested directly.
"""

from __future__ import annotations

import numpy as np

# The driven joint, as the description declares it: one revolute joint per
# side, the right one mimicking the left at -1. Zero is wide open and the
# angle grows as the gripper shuts.
OPEN_ANGLE = 0.0
SHUT_ANGLE = 0.7929

# Where the knuckle joint sits on the gripper body, from robotiq_85_base_link.
KNUCKLE = np.array([0.03060114, 0.0, 0.05490452])

# Knuckle to pad, with the two fixed hops along the finger added together: the
# knuckle-to-finger offset plus the finger-to-fingertip offset. They can be
# added because the fingertip joint mimics the knuckle at -1, so the fingertip
# link never turns — the pad face stays parallel to itself over the whole
# stroke. That is why this gripper can pinch a straight-walled glass at all.
ARM = np.array([0.03152616 + 0.00563134, 0.0, -0.00376347 + 0.04718515])

# The flat gripping face, in the fingertip link's own frame. Taken from the
# collision mesh: the inner face is the plane at the smallest x, and the patch
# on it is 22 mm across by 38 mm along the finger.
PAD_FACE_X = -0.02526
PAD_NEAR_Z = 0.01302
PAD_FAR_Z = 0.05102

# How tall the pad is where it meets an upright wall, and how far it runs along
# the finger. The gripper comes in level, so the pad's width across the finger
# is what sits on the glass, and these are gripper properties rather than glass
# ones. PAD_LENGTH is why the glass is held at the middle of the pad and not at
# the fingertip.
PAD_HEIGHT = 0.022
PAD_LENGTH = PAD_FAR_Z - PAD_NEAR_Z

# How far the rubber stands proud of the metal behind it. The collision mesh
# does not separate the pad from the fingertip, so this one number is an
# estimate rather than a reading, and nothing but a drawing uses it.
PAD_THICKNESS = 0.003


def _swing(angle: float) -> np.ndarray:
    """Where the pad frame sits for a knuckle angle, from the gripper's base.

    The knuckle turns about the axis the description gives it, which is the
    negative y axis, and the pad rides round with it.
    """
    cos, sin = np.cos(angle), np.sin(angle)
    turn = np.array([[cos, 0.0, -sin], [0.0, 1.0, 0.0], [sin, 0.0, cos]])
    return KNUCKLE + turn @ ARM


def opening_at(angle: float) -> float:
    """How far apart the two pad faces are, in metres, at this knuckle angle.

    The gripper is symmetric, so the gap is twice what one pad is off the
    middle. Fully open this is the 85 mm Robotiq publish as the stroke.
    """
    return 2.0 * float(_swing(angle)[0] + PAD_FACE_X)


def pad_reach(angle: float) -> float:
    """How far the middle of the pad is from the gripper's base, in metres.

    This grows as the gripper shuts, which is the arc the module docstring
    warns about: the pads do not only come together, they also come forward.
    """
    return float(_swing(angle)[2] + (PAD_NEAR_Z + PAD_FAR_Z) / 2.0)


# The widest and narrowest the pads can be, worked out rather than written
# down, so they cannot drift away from the linkage above.
MAX_OPENING = opening_at(OPEN_ANGLE)
MIN_OPENING = opening_at(SHUT_ANGLE)

# How far the fingertips reach past the gripper's base. The pad's far edge is
# also the furthest point of the fingertip, so this follows from the pad rather
# than needing a second measurement of the mesh.
FINGERTIP_REACH = pad_reach(OPEN_ANGLE) + PAD_LENGTH / 2.0

# The front face of the gripper's body, measured from its base: a 90 mm tall
# housing, from the base collision mesh. Anything held has to stop short of it.
PALM_REACH = 0.090

# How much room is left between the body and whatever is held. Small, because
# the fingers are long and there is not much to spare, but not nothing: the arm
# does not arrive exactly where it was sent.
PALM_CLEARANCE = 0.002


def grips_clear_of_the_palm(opening: float) -> bool:
    """Can something this wide be held at the middle of the pads?

    Holding at the middle of the pads is what keeps a round glass from being
    squeezed out of the fingers, so it is the arrangement this project wants.
    It is not always available. A wide object held there sticks back towards
    the gripper's own body, and past a certain width it reaches it.
    """
    return pad_reach(angle_for(opening)) - opening / 2.0 >= PALM_REACH + PALM_CLEARANCE


def _widest_grip() -> float:
    """The widest thing that can be held at the middle of the pads.

    It comes out a few millimetres under the full stroke, and that gap is a
    real limitation of this gripper rather than a conservative choice. The
    85 mm Robotiq publish is how far the fingers part, which is not the same
    as how wide a round object they can close on properly: at the very end of
    the stroke the pads sit too far back along the fingers, and an object
    filling them touches the body behind.

    Searched rather than solved, for the same reason angle_for() is.
    """
    low, high = MIN_OPENING, MAX_OPENING
    for _ in range(40):
        middle = (low + high) / 2.0
        if grips_clear_of_the_palm(middle):
            low = middle
        else:
            high = middle
    return low


# The furthest forward the pads ever come, over the whole stroke. It is a
# maximum rather than simply the fully shut figure because the arc turns over
# near the end: the pads reach furthest at about 10 mm of opening and come back
# a fraction of a millimetre after that. Any particular grip costs less than
# this, and pad_travel_to() gives that, but this is the worst case.
PAD_TRAVEL = max(
    pad_reach(angle) - pad_reach(OPEN_ANGLE) for angle in np.linspace(OPEN_ANGLE, SHUT_ANGLE, 2001)
)

# The gripper's position command is one byte over Modbus spread across the
# stroke, so it cannot resolve a finer step than this. Asking for a width
# inside this of another width asks for the same width.
POSITION_STEP = MAX_OPENING / 255.0


class OutsideStroke(ValueError):
    """This width is wider than the gripper opens, or narrower than it shuts."""


def angle_for(opening: float) -> float:
    """The knuckle angle that puts the pads this far apart, in metres.

    Going the other way is the hard direction. ``opening_at()`` is a sine and a
    cosine of the angle, so inverting it in closed form is possible but ugly,
    and it is not worth the algebra: the function decreases steadily over the
    whole stroke, so a binary search on it is exact to as many figures as
    anyone needs and obviously correct by inspection. Twelve rounds of halving
    bring the error below a thousandth of a millimetre, which is far inside
    what the gripper itself can resolve.

    A width the gripper cannot reach is refused rather than clipped, because
    silently gripping at a different width than the measurement asked for is
    how a glass gets squeezed in the wrong place. The allowance either end is
    half a position step rather than a round number, because inside that the
    gripper cannot tell the two widths apart: asking for the 85 mm Robotiq
    print on the data sheet, when the linkage gives 84.997 mm, is the same
    request and not a mistake to report.
    """
    slack = POSITION_STEP / 2.0
    if not MIN_OPENING - slack <= opening <= MAX_OPENING + slack:
        raise OutsideStroke(
            f"the 2F-85 opens {1000 * MIN_OPENING:.1f} to {1000 * MAX_OPENING:.1f} mm, "
            f"so {1000 * opening:.1f} mm is outside its stroke"
        )
    opening = min(max(opening, MIN_OPENING), MAX_OPENING)
    low, high = OPEN_ANGLE, SHUT_ANGLE
    for _ in range(40):
        middle = (low + high) / 2.0
        if opening_at(middle) > opening:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def pad_travel_to(opening: float) -> float:
    """How far forward the pads come in closing from wide open to this width.

    This is what a grip has to be raised by, so that the pads finish at the
    height the rule chose rather than that much below it.
    """
    return pad_reach(angle_for(opening)) - pad_reach(OPEN_ANGLE)


# How hard the gripper can be told to squeeze, in newtons at the fingertip.
# Robotiq publish 20 N to 235 N as the adjustable range, and the lower figure
# is the one that matters to this project: **the 2F-85 cannot squeeze more
# gently than 20 N.** It is not that 20 N is the recommended minimum or the
# reliable minimum. It is the bottom of the range the gripper exposes.
#
# That single number is the biggest thing a real gripper changes here. This
# project worked out how hard to hold each glass from its weight and the
# friction of the pad, and the answers come out in single newtons: a tumbler
# needs a couple, a wine glass a little more. All of them are under 20. So the
# gentlest squeeze this gripper has is still several times what the sums ask
# for, and glasses/force.py has to decide what to do about that rather than
# quietly command a force the hardware would round up.
MIN_FORCE_N = 20.0
MAX_FORCE_N = 235.0

# What Robotiq's description allows at the knuckle, in newton metres.
JOINT_EFFORT_LIMIT = 50.0


class OutsideForceRange(ValueError):
    """This squeeze is harder or gentler than the gripper can be set to."""


def effort_for(newtons: float) -> float:
    """The knuckle torque that presses the pads together with this force.

    The honest version of this is a function of the angle, because the
    linkage's leverage changes as the fingers swing, and the exact curve is
    not something Robotiq publish. What they do publish is the pair of
    endpoints: a setting spread between 20 N and 235 N at the fingertip, and a
    joint that takes up to 50 N m. Their own driver presents the setting as a
    fraction of the maximum, so that is the mapping used here — a straight
    line between the published ends.

    It is an approximation, and it is the second thing to check against a real
    gripper after the friction of the pad. It is written down here, in one
    place, rather than spread through the code that squeezes, so that checking
    it means changing one function.
    """
    if not MIN_FORCE_N <= newtons <= MAX_FORCE_N:
        raise OutsideForceRange(
            f"the 2F-85 squeezes between {MIN_FORCE_N:.0f} and {MAX_FORCE_N:.0f} N, "
            f"so {newtons:.1f} N cannot be commanded"
        )
    return JOINT_EFFORT_LIMIT * newtons / MAX_FORCE_N


# Worked out down here rather than beside _widest_grip, because the search it
# runs needs angle_for, which needs the position step defined above it.
MAX_GRIP = _widest_grip()


# --------------------------------------------------------------- the closed jaw

# The axis-aligned box each moving link fills, in its own frame, read off the
# collision meshes that ship with the description. Same provenance as
# PAD_FACE_X above, and for the same reason: the shape of a moulded part is not
# something to approximate by eye. Each entry is (low corner, high corner).
#
# The links never turn, because every one of their joints mimics the knuckle in
# a way that cancels the knuckle's own rotation, so a link's box can be shifted
# with the link instead of being rotated with it. That is what makes these
# numbers usable at any angle.
FINGER_BOX = (np.array([-0.01450, -0.01440, -0.00626]), np.array([0.01408, 0.01280, 0.05315]))
TIP_BOX = (np.array([-0.02526, -0.01430, -0.00598]), np.array([0.00596, 0.01270, 0.05102]))
BODY_BOX = (np.array([-0.04244, -0.03755, -0.00335]), np.array([0.04251, 0.03749, 0.09000]))

# Where the two fixed hops along the finger put each link, so the boxes above
# can be placed. ARM is their sum, which is all the linkage needs; the jaw
# needs them apart, because the finger and the fingertip are different widths.
KNUCKLE_TO_FINGER = np.array([0.03152616, 0.0, -0.00376347])
FINGER_TO_TIP = np.array([0.00563134, 0.0, 0.04718515])


def _part(box, origin) -> tuple[np.ndarray, np.ndarray]:
    return box[0] + origin, box[1] + origin


def _placed(angle: float) -> tuple:
    """Where the three moulded parts sit at this knuckle angle.

    Shared by ``parts()`` and ``jaw()`` so that the two can never disagree
    about where the hand is, which they would if each worked the swing out for
    itself.
    """
    turn = np.array(
        [
            [np.cos(angle), 0.0, -np.sin(angle)],
            [0.0, 1.0, 0.0],
            [np.sin(angle), 0.0, np.cos(angle)],
        ]
    )
    finger = _part(FINGER_BOX, KNUCKLE + turn @ KNUCKLE_TO_FINGER)
    tip = _part(TIP_BOX, KNUCKLE + turn @ (KNUCKLE_TO_FINGER + FINGER_TO_TIP))
    body = _part(BODY_BOX, np.zeros(3))
    return tip, finger, body


def parts(angle: float = SHUT_ANGLE) -> list[dict]:
    """Every piece of the hand on its own, with the gap between the fingers left open.

    ``jaw()`` below answers the question a push asks, which is what shape the
    hand fills, so it folds each pair of fingers into a single box covering both
    of them and the space between them. That is the right answer for a push,
    because a glass standing in that space would be swept along just the same.

    A drawing needs the opposite answer, and that is what this function is for.
    Shut, the two fingertips sit one millimetre apart and really are one solid
    stub, but the fingers behind them stand about 82 mm apart, so a picture
    built from ``jaw()`` shows a brick where a hand should be. With the pieces
    listed separately a picture can show the fingers, the gap between them, and
    the fingers opening and closing.

    Each piece is measured the same way as in ``jaw()``: ``back`` and ``depth``
    run along the approach and are measured from the fingertips, and ``tall`` is
    the thickness across the finger. Two fields are new. ``span`` is how far this
    one piece reaches along the direction the fingers open, rather than how far
    the pair reaches, and ``offset`` is how far the piece's middle sits from the
    hand's own middle. A pair appears twice, once at each offset, because the
    second finger is the same moulding turned around, and ``side`` says which of
    the two a piece is.
    """
    tip, finger, body = _placed(angle)
    reach = tip[1][2]
    pieces = []
    for name, (low, high), sides in (
        ("fingertips", tip, (1, -1)),
        ("fingers", finger, (1, -1)),
        ("body", body, (0,)),
    ):
        middle = float((high[0] + low[0]) / 2.0)
        for side in sides:
            pieces.append(
                {
                    "name": name,
                    "side": side,
                    "back": float(reach - high[2]),
                    "depth": float(high[2] - low[2]),
                    "tall": float(high[1] - low[1]),
                    "span": float(high[0] - low[0]),
                    "offset": middle if side >= 0 else -middle,
                }
            )
    return pieces


def pads(angle: float = SHUT_ANGLE) -> list[dict]:
    """The two rubber pads, measured the same way as ``parts()``.

    The pads are the only part of the hand that is meant to touch anything, so
    a picture of the hand holding a glass is wrong without them: the glass has
    to be seen resting against the pads and not against the metal. They are kept
    out of ``parts()`` because they are not a separate moulding — each one is a
    face of the fingertip it sits on — and adding them there would change what
    ``jaw()`` reports the hand's shape to be.

    ``PAD_THICKNESS`` is the only number here that is not read out of the
    description. It is how far the rubber stands off the metal, which the
    collision mesh does not separate out, and it is used for drawing only.
    """
    tip, _, _ = _placed(angle)
    reach = tip[1][2]
    inner = float(tip[0][0])
    return [
        {
            "name": "pads",
            "side": side,
            "back": float(reach - pad_reach(angle)) + PAD_LENGTH / 2.0,
            "depth": PAD_LENGTH,
            "tall": PAD_HEIGHT,
            "span": PAD_THICKNESS,
            "offset": (inner + PAD_THICKNESS / 2.0) * (1.0 if side >= 0 else -1.0),
        }
        for side in (1, -1)
    ]


def jaw(angle: float = SHUT_ANGLE) -> list[dict]:
    """The gripper as a stack of boxes, seen from the side, at one angle.

    The linkage above answers where the pads are. This answers what shape the
    whole hand is, which is a different question and the one that matters
    whenever the hand has to fit somewhere: pushing a glass along a table with
    the fingers shut, or coming down around a glass with them open.

    At the shut angle this is how 03-push-glasses-apart uses the gripper —
    fingers closed, hand held level, and the whole thing driven forward to
    shove a glass sideways. What that needs is not the linkage but the
    silhouette, so that is what this returns.

    Each box is measured **back from the fingertips**, because the fingertips
    are what reaches a glass first, and across and up, because the hand is held
    level. ``back`` and ``depth`` run along the push, ``across`` is the width
    the hand sweeps, and ``tall`` is its height.

    The shape is worth looking at rather than summarising, because it is not a
    blade and a blade is what a reader would assume. The two fingertips meet in
    the middle and make a stub about 63 mm across and 57 mm long. Behind that
    the fingers flare out to about 139 mm, more than twice as wide, and they
    begin only 35 mm back from the tip. So the hand can put 35 mm of itself
    into a gap the width of the stub and no more; going deeper needs a gap
    twice as wide. Behind the fingers again is the 85 by 75 mm body.

    A jaw described as one long thin blade, which is what this project assumed
    before it had a real gripper, can reach into gaps this one cannot.
    """
    tip, finger, body = _placed(angle)
    reach = tip[1][2]
    folded = []
    for name, (low, high) in (("fingertips", tip), ("fingers", finger), ("body", body)):
        # Mirrored about the middle, because the other finger is the same part
        # the other way round, so the width is twice the outer edge. The body
        # straddles the middle already and is taken as it is.
        across = 2.0 * high[0] if name != "body" else high[0] - low[0]
        folded.append(
            {
                "name": name,
                "back": reach - high[2],
                "depth": high[2] - low[2],
                "across": across,
                "tall": high[1] - low[1],
            }
        )
    return folded


# How far the fingertips stick out in front of the fingers behind them. The
# depth of the only gap the shut hand can enter at its narrowest width.
JAW_LEAD = jaw()[1]["back"]

# The narrowest the shut hand ever is, across the push, and the widest.
JAW_TIP_ACROSS = jaw()[0]["across"]
JAW_WIDEST_ACROSS = max(part["across"] for part in jaw())

# How tall the fingertips are, which is what decides how high up a glass is
# shoved and therefore whether it slides or topples.
JAW_TALL = jaw()[0]["tall"]

# How far the *open* hand reaches either side of its own middle. This is what
# decides whether there is room to grip a glass at all: the hand has to come
# down around it, so everything within this of the glass's middle has to be
# clear, and a neighbour whose edge is inside it is in the way.
#
# It is the fingers rather than the fingertips that set it. Open, the fingers
# stand further out than the pads do, so the widest part of the hand is not the
# part that touches the glass.
OPEN_HALF_WIDTH = max(part["across"] for part in jaw(OPEN_ANGLE)) / 2.0
