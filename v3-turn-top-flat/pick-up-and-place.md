# Picking the top up and putting it on the legs

This is a plan, not code. None of it is built yet. It covers the whole job for
v3: the table top starts **standing upright between two holders**, and the arm
has to lift it out, turn it flat, and put it on the four legs.

v2 as it is today starts the top lying flat on two grey stands, so its arm
never has to turn it. This file explains how to add the turn. File and
function names in it (`task.py`, `carry_round()`, and so on) are v2's.

Two related files, which are v3's two parts:

- [`one-joint-or-many.md`](one-joint-or-many.md) — part 1, built as
  `make wrist` and `make whole-arm`: to turn the top 90 degrees, should the
  arm turn one joint or several?
- [`tilt-onto-legs.md`](tilt-onto-legs.md) — part 2, built as `make tilt`:
  rest the top on two legs first, then tilt it down onto all four.

It uses the same words as the rest of the docs. If a word is new to you, look
in [Words used here](#words-used-here) at the end.

The pictures are sketches, not to scale. They are drawn by
[`figures/pick_up_and_place.py`](figures/pick_up_and_place.py). See the
[README](README.md) for how to redraw them.

---

## 1. The problem in one picture

![The table top standing upright between two holders at the start, and lying flat on four legs at the end](figures/problem.png)

So the top has to go from **upright** to **flat**: a turn of exactly 90
degrees.

The holders make the start as easy as it can be, on purpose. They hold the top
still, so the camera can measure it once and be sure it has not moved since.
They hold it by its ends, so the middle of its upper edge is free for the
fingers. And they only let it go one way — straight up — so getting it out
needs no thought. All the difficulty is left in the turn, which is the part
worth studying.

Everything else stays the same as v2: finding the room, measuring the top,
planning the table, and standing the four legs.

---

## 2. What an earlier version taught

An earlier version of this project started the top leaning against a wall,
and it kept failing. I did not run it for this file. These lessons come from
reading its code (commit `c54165c`, `task.py` `_install_top()`) and its own
notes. Two of them are about the turn, not the wall, so they still apply:

1. **The whole turn was one planned move.** After the lift, one call to
   `move_to_first(level_top_poses(...))` asked MoveIt to go from "board hanging
   from its edge" straight to "board flat over the legs". MoveIt's planner
   (OMPL) picks its own path for that. It can swing the wrist fast and far.
   The board is held by friction only, so it slips or falls. The old notes say
   the same thing happened to the legs ("a turn folded into one long planned
   move ... flings a part held only by friction"). The legs got a slow turn in
   small steps. The top never did.
2. **Nothing was checked before the grip.** The arm gripped the board first and
   found out later if it could reach the flat pose. Some grips need the wrist
   flipped the other way at the end. With a part in hand, a wrist flip is not
   allowed, so the move was refused with the board already in the air.

The other failures belonged to the wall: one finger had to squeeze behind the
board with barely a centimetre to spare, and the lift had to run with
collision checking off because the board started out touching the wall. The
holders remove the first. The second remains, smaller: the board starts inside
the holders' slots, so the lift out of them also runs without collision
checking — but it is short, and straight up.

The fix is not a new library. It is to **split the turn into small, slow,
simple moves**, and to **check every one of them before touching the board**.

![The old way does the whole turn in one planned move; the new way splits it into small moves](figures/old_vs_new.png)

---

## 3. The ways it can be done

![The four ways: turn it flat in the air, suction cup, rest on stands, edge on two legs then tilt down](figures/ways.png)

| | Way | Gripper | Good | Bad |
| --- | --- | --- | --- | --- |
| **A** | Grip the upper edge. Lift it straight out of the holders. Turn it flat in the air, slowly, in small steps. Carry it flat and set it down on all four legs at once. | The two-finger gripper you have now | The simplest. After the turn, the board is held exactly as v2 holds it, so v2's code for carrying it and setting it down can be reused. | The turn in the air is the hard part. Held flat by one edge, only a light top stays in the fingers — about 0.8 kg with v2's gripper. |
| **B** | Stick a suction cup on the middle of the board's face. Lift it straight out of the holders. Turn the tool to point down, so the board is flat. Put it down from above. | A vacuum (suction) gripper | Holds the board at its middle, so its weight does not try to tip it. Put down from above and lifted straight off, like a leg. | A new gripper. Gazebo has no real suction, so it has to be faked (see section 9). |
| **C** | Two stages: do A, but set the board flat on two stands first. Let go. Look at it with the camera. Then run v2's code, which starts from exactly that. | Two-finger | Two small problems instead of one big one. The camera measures the board again after the turn, so any slip in the fingers is corrected. | Slower. Needs two stands in the room. Still needs the turn in the air. |
| **D** | Grip and lift it out as in A. Carry it hanging to the far legs and rest its lower edge on them. Then turn it down about that edge, moving the arm as it goes, until it lies on all four legs. | Two-finger | It is never held flat in the air: by the time it is flat, the legs carry half its weight. So it takes much heavier tops. | A leg standing on its own is easy to knock over, and a board sliding on its top will do it. The arm has to turn it exactly about the edge that rests on the legs. |

One way an earlier version of this list considered, pushing the board over
without gripping it, is ruled out: the holders will not let it tip.

**v3's plan: part 1, then D.** Part 1 studies the turn itself — whether to turn
one joint or several — because every way that turns the top needs the turn
done well, in the air or on the legs. Then D, which is part 2, because it is
the one that copes with a real, heavy top. Its full plan is in
[`tilt-onto-legs.md`](tilt-onto-legs.md).

**A stays the quickest way to a working table with a light top,** and the rest
of this file plans it in detail. Most of it carries straight over to D: the
pick-up, the carry, the slow turn in small steps, and checking everything
before the grip.

---

## 4. Way A, step by step

This is the order of things, in plain words. Steps marked **(exists)** are
already done by v2's code and can stay as they are.

![Way A in eight pictures, from coming in above the edge to letting go on the legs](figures/steps.png)

1. **Look round the room** (exists). Find the floor, the top, the legs, and the
   holders. The holders are grey, so they are obstacles, and they go into
   MoveIt's picture of the room.
2. **Measure the top up close** (exists). The fitting code (`fit_plate()`) fits
   a board at any angle, so upright is easy for it. From it, get the top's
   length, width and thickness, and where its upper edge is. That edge is the
   one to grip, and there is only one.
3. **Plan the table** (exists). The gripped edge becomes the near edge of the
   table, facing the arm, as now.
4. **Stand the four legs** (exists).
5. **Plan the whole top move before touching the board.** Work out every pose
   the tool will pass through, from the first approach to the last pull-out.
   Check that the arm can reach every one, without hitting anything, and
   **with the wrist the same way round the whole time**. If no grip passes,
   stop here, and say why. Nothing has moved yet.
6. **Come in above the upper edge.** Open the fingers. Line up a few
   centimetres above the middle of the edge, with the tool pointing straight
   down and a finger either side of the board. The middle is clear of the
   holders, which only hold the ends. Move straight down until the fingers are
   5 cm over the edge.
7. **Grip.** Close the fingers. Check both fingertip sensors feel the board.
8. **Tell MoveIt the board is now part of the arm** (`scene.attach()`). From
   now on it plans for the board as well.
9. **Lift it straight up**, slowly, until its lower edge is a few centimetres
   above the holders. Collision checking has to be off for this one move,
   because the board starts inside the holders' slots, touching them. It is
   the only move without it, and it goes straight up, so it cannot reach
   anything the board was not already touching. The board is now **hanging
   straight down**, which is the safest way to hold it: its weight pulls
   straight along the fingers and does not try to turn it.
10. **Carry it round, hanging**, to a clear place in the air. Use
    `carry_round()`, exactly as for a leg. The board is just a wide, flat leg
    here. Carry it high enough that its lower edge passes 4 cm above anything
    in the room. On the way, turn it so its gripped edge ends up **square
    across the arm's line of reach** (see section 5).
11. **Turn it flat.** Turn the tool about the gripped edge, slowly, in steps of
    about 5 degrees, until the board is flat. It swings **away from the arm**,
    so it ends up sticking out from the fingers, away from the base. Check the
    fingertip sensors after every step. Which of the arm's joints should do the
    turning is the question of part 1,
    [`one-joint-or-many.md`](one-joint-or-many.md).
12. **Carry it round flat** to above the legs (exists: `carry_round()` with the
    top level). From here on it is exactly v2's code.
13. **Lower it onto the legs** (exists: `_lower()`).
14. **Let go and pull the fingers back out** from under it (exists:
    `_release()`, `_pull_out()`).
15. **Look at the table and check it** (exists: `_check_table()`).

Only steps 5, 6, 9, 10 and 11 are new or changed. The earlier version put
steps 10 to 12 into one planned move. That is the part to change.

---

## 5. The swing, explained

The swing (step 11) is the new, hard part. Four rules make it safe.

### Rule 1: turn about the gripped edge, like a drawbridge

![The board swinging flat about its gripped edge, 5 degrees per step](figures/swing.png)

The fingers stay in one place. Only the board turns round them. The part of
the room the board sweeps through is a quarter circle as big as the board's
width, 16 to 20 cm. So the swing needs a clear space of about 25 cm round the
fingers, below them and on the side away from the arm.

This is one of three ways of making the turn that part 1 compares. The others
are turning wrist 1 alone, and turning the board about its own middle. For the
arm's joints the three come out almost the same (see
[`one-joint-or-many.md`](one-joint-or-many.md)), so this one is chosen for a
practical reason: it needs the least empty space.

### Rule 2: small steps, slowly, in a straight-line path

Do not ask MoveIt's free planner for this. Work out the tool's pose every
5 degrees yourself, and send the list to MoveIt's straight-line (Cartesian)
path service. That is what `move_linear()` already does. Run it at a tenth of
full speed (`CARRY_SPEED`), like every other move with a part in hand.

The straight-line service sometimes stops a few percent short, as it did for
the legs. If it stops within 10 degrees of flat, finish with one small move to
the exact flat pose. If it stops earlier, treat it as a failure (section 7).

### Rule 3: the gripped edge square across the arm's reach

Picture a line from the arm's base out to the fingers. Before the swing, turn
the hanging board (a turn about the vertical, which is harmless) so its
gripped edge runs **across** that line, not along it.

Then the swing is just the wrist bending the way it normally bends, like the
arm's elbow. If the edge ran along that line instead, the swing would need the
wrist to twist through a pose where two of its joints line up (a *wrist
singularity*). No path goes smoothly through that pose. The legs taught this
lesson in the earlier version.

It also matches the plan: the table's near edge faces the arm, and the gripped
edge becomes that near edge.

![Seen from above: the gripped edge should run across the line from the base, not along it](figures/edge_direction.png)

### Rule 4: swing it away from the arm

Swinging the board towards the arm would leave the tool pointing back at the
arm's own base, with the board in its lap. Always swing it away. Then the tool
ends level and pointing out from the base, which is exactly the pose v2's code
uses to carry the top and lay it on the legs.

### Why the grip can hold it

![The pull on the grip against the board's angle: zero when hanging, largest when flat](figures/grip_load.png)

The board weighs 0.25 to 0.48 kg (400 kg/m³, and the size ranges in
`world/spec.py`).

- **Hanging**, its weight pulls straight along the fingers. It does not try to
  turn the board at all.
- **Flat**, its weight tries to tip it down about the gripped edge. At worst,
  that is about 0.48 kg × 9.81 × 0.073 m ≈ 0.34 N·m. The two rows of pads on
  each finger are 2.4 cm apart, and they fight the tip like two hands on a
  lever: 0.34 N·m / 0.024 m ≈ 14 N. The fingers squeeze with up to 25 N. That
  is enough, and v2's code proves it, because it already carries the board
  flat this way.
- **During the swing**, the tipping pull grows smoothly from zero (hanging) to
  the flat case. So the swing never asks more of the grip than v2 already
  does. Moving fast adds to the pull, which is one more
  reason to go slowly.

---

## 6. Pseudo code for way A

Plain pseudo code. Names ending in `# exists` are in v2's code already. The
rest would be new.

```text
# ----------------------------------------------------------------------
# Constants: choices about how to do the job, not facts about the room
# ----------------------------------------------------------------------
TOP_INSERTION   = 5 cm      # how far the fingers reach over the edge   # exists
LIFT_CLEAR      = 3 cm      # how far above the holders the lift leaves the top
SWING_STEP      = 5 degrees # size of each step of the swing
SWING_CLEARANCE = 25 cm     # empty space needed round the fingers to swing
CARRY_SPEED     = 0.1       # a tenth of full speed with a part in hand # exists


# ----------------------------------------------------------------------
# The top, from the holders to the legs
# ----------------------------------------------------------------------
procedure INSTALL_TOP_FROM_HOLDERS(top, holders, plan, legs):

    # 1. Where the top has to end up (same as v2)
    goal_centre  = middle of the four legs as they really stand
    goal_centre.z = height of the tallest leg + half the top's thickness + DROP
    outward      = flat direction from the arm's base to the table

    # 2. Where to grip it
    edge = UPPER_LONG_EDGE(top)            # it stands upright: there is only one
    grips = EDGE_PICK_POSES(top, edge)     # tool straight down at the middle of
                                           # the edge, fingers either side,
                                           # two ways round

    # 3. Plan everything before touching it
    chosen = none
    for grip in grips:
        route = PLAN_ROUTE(top, grip, goal_centre, outward)
        if route is not none:
            chosen = route
            break
    if chosen is none:
        stop "no grip can take the top from the holders to the legs"

    # 4. Grip it
    open_gripper(top.thickness + 3 cm)                          # exists
    move_to(chosen.approach)          # above the edge, fingers open   # exists
    move_linear(chosen.grip)          # straight down onto the edge   # exists
    forget "top" in the planning scene                          # exists
    grip(top.thickness)                                         # exists
    if the fingertip sensors do not both feel the board:
        let go, lift clear, stop "closed on nothing"

    held = hold(top, chosen.grip)     # the board's pose in the tool  # exists
    scene.attach("carried", top, chosen.grip)                   # exists

    try:
        # 5. Straight up out of the holders. The only move with collision
        #    checking off, because the top starts inside their slots. It now
        #    hangs straight down, so there is nothing to straighten.
        move_linear(chosen.lifted, avoid_collisions = false, speed = CARRY_SPEED)

        # 6. Carry it hanging to the swing point, like a leg
        FOLLOW_SLOWLY(chosen.hanging_carry)                     # carry_round exists

        # 7. Swing it flat, away from the arm
        FOLLOW_SLOWLY(chosen.swing_steps)

        # 8. The rest is v2's code
        FOLLOW_SLOWLY(chosen.flat_carry)                        # carry_round exists
        lower(chosen.place)                                     # exists
        if not in_contact: stop "the top slipped out on the way"
        release()                                               # exists
    finally:
        scene.detach("carried")                                 # exists

    pull_out(chosen.place, TOP_RETREAT)                         # exists


# ----------------------------------------------------------------------
# Plan every pose, check every pose, before moving at all
# ----------------------------------------------------------------------
function PLAN_ROUTE(top, holders, grip, goal_centre, outward):

    held = hold(top, grip)

    approach = grip moved straight up by TOP_APPROACH
    lifted   = grip moved straight up until the top's lower edge
               is LIFT_CLEAR above the taller holder
    hanging  = lifted          # lifted straight out, it already hangs straight

    # Where to swing. Somewhere in reach, high enough that the hanging board's
    # lower edge is clear of everything, with nothing the camera saw within
    # SWING_CLEARANCE of the fingers.
    swing_point = PICK_SWING_POINT(hanging, held, the planning scene)
    if swing_point is none: return none

    # At the swing point, the gripped edge runs across the arm's reach.
    hanging_at_swing = tool straight down at swing_point,
                       turned so the gripped edge is square to the line from the base
    hanging_carry = carry_round(held, hanging, hanging_at_swing,         # exists
                                height = above everything, base)

    swing_steps = SWING_ABOUT_EDGE(held, hanging_at_swing,
                                   to = "board flat, sticking out away from the base",
                                   step = SWING_STEP)
    flat_at_swing = last of swing_steps

    place = level_top_pose(held, goal_centre, outward, pinch)             # exists
    flat_carry = carry_round(held, flat_at_swing, place,                  # exists
                             height = above the legs, base)

    # The check. Every pose, the board included, same wrist side throughout.
    wrist = wrist_side(approach)                                          # exists
    all_poses = [approach, grip, lifted] + hanging_carry
              + swing_steps + flat_carry + [place moved up, place]
    for pose in all_poses:
        if not can_reach(pose, with the board attached, wrist):           # exists
            return none
    if any two poses in a row ask a joint to turn more than about 20 degrees:
        return none        # a jump there means the wrist is near a bad pose

    return all of the above


# ----------------------------------------------------------------------
# The swing itself: the fingers stay put, the board turns round them
# ----------------------------------------------------------------------
function SWING_ABOUT_EDGE(held, start_tool_pose, to, step):

    pivot = the middle of the gripped edge, in the room      # from start pose and held
    axis  = the direction the gripped edge runs
    angle = how far to turn about axis to get from start to the "to" pose
    choose the direction of turn that swings the board AWAY from the arm

    poses = []
    for k = 1 .. ceil(angle / step):
        a = angle * k / number of steps
        R = rotation by a about axis, through pivot
        poses.append(R applied to start_tool_pose)
    return poses


# ----------------------------------------------------------------------
# Move through a list of poses slowly, watching the grip
# ----------------------------------------------------------------------
procedure FOLLOW_SLOWLY(poses):

    done = move_linear(poses, speed = CARRY_SPEED)            # exists
    if not in_contact:
        stop "the board slipped"
    if done < 100%:
        if the last pose it reached is within 10 degrees of the final one:
            move_to(final pose, any_shape = false)            # exists
        else:
            stop "the path stopped at {done}%"
```

---

## 7. When something goes wrong

The same rule as the rest of the project: stop and say why, never carry on
quietly.

| What happens | How it is noticed | What to do |
| --- | --- | --- |
| No grip can do the whole route | `PLAN_ROUTE` gives `none` for every grip | Stop before moving. Say which pose failed: the swing, the place, or the grip. |
| Fingers close on nothing | Fingertip contact sensors | Open, lift clear, look at the top again, try once more. |
| The top catches in a holder as it lifts | The wrist joints' efforts jump, or the fingertip sensors report the board shifting | Stop. Lower it back into the slots and let go. Measure the top and the holders again: a top standing a little askew rubs against a slot. |
| Board slips while lifted or swung | Contact sensors go quiet | Stop moving. Lift clear with collision checking on, then open. Look round the room, find the top wherever it is. |
| The swing stops early | `move_linear()` reports less than 100% | Within 10 degrees of flat: finish with one small move. Otherwise lower the board to where it is safe, let go, try a different swing point. |
| The top lands tilted | `_check_table()` measures the tilt | Report it. Picking it up again is a later improvement. |

---

## 8. Which libraries

**Stay with what the project already uses. No new library is needed for
way A.**

| Tool | What it does in this job | New? |
| --- | --- | --- |
| **MoveIt 2** | Plans the arm's moves, knows what is in the room, checks for collisions | Already used |
| - planning scene | Holds the floor, the holders and the legs. `attach()` tells it the board is in the gripper, so plans account for it | Already used (`scene.py`) |
| - inverse kinematics (KDL) | Turns "tool here" into joint angles. Used to check every pose before the grip | Already used (`_solve()`, `can_reach()`) |
| - Cartesian path service | Follows a list of tool poses in straight lines. Used for the lift, the swing, the lower and the pull-out | Already used (`move_linear()`) |
| - OMPL planner | Free moves with an empty hand | Already used |
| **ros2_control** | Drives the joints and the fingers | Already used |
| **Gazebo Harmonic** | The physics, the camera, the contact sensors | Already used |
| **NumPy / OpenCV** | Fits the upright board from camera points. `fit_plate()` already handles any angle | Already used |

Two parts of MoveIt that are not switched on here, and might help later:

- **Pilz industrial motion planner.** It plans straight lines (`LIN`) and
  circular arcs (`CIRC`) with a known shape and speed. The swing is exactly a
  circular arc of the tool round the gripped edge. It ships with MoveIt 2.
  `pilz_cartesian_limits.yaml` is already in the config folder, but the
  `pilz_industrial_motion_planner` pipeline is not in `moveit_cpp.yaml` yet.
- **MoveIt Task Constructor (MTC).** It is built for pick-and-place jobs like
  this one. You describe the job as stages (approach, grasp, lift, turn,
  place, retreat), and it finds a plan for **all of them before the arm
  moves**. That is what `PLAN_ROUTE` does by hand. It is mainly C++, so it is
  a bigger change. Only worth it if the hand-written check gets messy.

Not recommended here: a different motion library (Drake, cuRobo, and so on).
The failures were about *which moves were asked for*, not about the planner.

---

## 9. Which gripper

### For ways A and C: the two-finger gripper you have now

What it needs, and what it has:

| Need | Why | Now |
| --- | --- | --- |
| Opens wider than the board is thick, with room to line up | The board is 1.6 to 2.0 cm thick. The fingers need about 3 cm spare so a small error does not catch a corner. | Opens to 7.4 cm. Fine. |
| Long fingers | They reach 5 cm over the edge, and the body must stay clear of the board. | 12 cm fingers. Fine. |
| Grip pads in two rows, spread along the finger | The spread between rows is what stops a board held by one edge from tipping. Flat fingers touch at one point in the simulator and let it turn. | 4 pads per finger, rows 2.4 cm apart. Fine. |
| Enough squeeze | See section 5: about 14 N needed at worst. | 25 N. Fine. |
| Touch sensors on the fingertips | To know it holds the board, and to notice at once if it slips. | Yes. |

If the board slips in the swing, these help, most useful first:

1. Go slower, in smaller steps.
2. Grip deeper (a larger `TOP_INSERTION`, for example 6 cm) and move the inner
   row of pads further from the tip row. A bigger spread resists the tip better.
3. Raise the pad friction in `gripper.urdf.xacro`.
4. Raise the finger effort above 25 N. Keep `GRIP_SQUEEZE` small, or the
   position-controlled fingers fire the board out sideways.

A real gripper of this kind: a Robotiq 2F-85 or similar, with rubber
fingertip pads.

### For way B: a suction (vacuum) gripper

A flat, smooth board is the ideal part for suction. One cup, 4 to 5 cm across,
on the middle of the face is plenty: at a vacuum of about 60 kPa it pulls
with roughly 75 N, against a board weighing under 5 N. A cup on a soft bellows
lets it press flat even if the tool is a few degrees off. Real examples:
Robotiq EPick, Schmalz, OnRobot VGC10.

Way B, in short:

```text
procedure INSTALL_TOP_BY_SUCTION(top, holders, plan, legs):
    face_centre = middle of the board's face that looks at the arm
    grip = tool pointing straight into the face, at face_centre
    check the whole route before moving (as PLAN_ROUTE above)

    move_to(grip moved back 5 cm)
    move_linear(grip)                  # press the cup on; the holders keep it still
    vacuum on
    if the cup does not report a seal: vacuum off, back off, stop

    scene.attach("carried", top, grip)
    move_linear(lift straight up, out of the holders, avoid_collisions = false)
    TURN_ABOUT_CUP(from "tool into the face" to "tool straight down")
                                        # the board turns about its own middle,
                                        # so it sweeps half as much room as in A
    carry_round(held, ..., to above the legs, tool still pointing down)
    move_linear(straight down onto the legs)
    vacuum off
    scene.detach("carried")
    move_linear(straight up)           # no pulling out from under it
```

Its weak moment is the start: while the board is upright, its weight slides
along the cup's face instead of pulling on it. Turn slowly there.

**In Gazebo there is no real suction.** The usual way to fake it is Gazebo's
`DetachableJoint` system, which joins two links with a fixed joint when it
gets a message and frees them on another. Check the exact settings for your
Gazebo version. Two warnings, because of this project's one rule:

- The plugin has to name the part it will join to. That name is a fact about
  the room, so it belongs on the simulator's side (`world/`), never in the
  robot's code.
- Only send "join" once the cup's contact sensor really touches the board.
  Otherwise the simulator would grab a part the cup is not touching.

---

## 10. What the room must allow

Whichever way is used, the room has to make it possible. These belong in
`world/spec.py`, on the simulator's side.

- **The holders.** Two of them, one at each end of the top, each with a slot
  the top's end stands in. They must be heavy, or fixed to the floor, so that
  nothing the arm does can move them. They hold only the ends, so the middle
  of the upper edge stays free for the fingers. They only need to be a third
  of the top's width tall to keep it upright, and shorter is better: the lift
  out of them is the one move made without collision checking, so it should be
  short.
- **The top** stands on one long edge, straight up, with a face towards the
  arm, within reach (about 45 to 60 cm from the base).
- **For ways A and C:** somewhere in reach with 25 cm of empty space round it,
  high enough to swing the board. The survey finds it; it is not given.

---

## 11. Where the code would go

Keeping to the rules in `CLAUDE.md`:

| File | What changes |
| --- | --- |
| `world/spec.py`, `world/spawn.py`, `world/holder.sdf` | New: the two holders, and the top standing upright in them. Simulator side only. |
| `perception/room.py`, `perception/fitting.py` | Probably nothing. `fit_plate()` fits a board at any angle, and upright is the easy case. The holders are grey, so they are found as obstacles, like anything else grey. |
| `assembly/plan.py` | Which long edge to grip: always the upper one, so there is no choice to make. |
| `assembly/grasps.py` | New: `edge_pick_poses()` (the old `top_pick_poses()`), `swing_about_edge()`. Reused as they are: `hold()`, `carry_round()`, `level_top_pose()`. |
| `task.py` | New `_install_top_from_holders()`, with `_plan_top_route()` and `_follow_slowly()`. Only this file decides the order. |
| `test/test_grasps.py` | New tests, see below. |

---

## 12. How to test it, a little at a time

**Without the simulator** (`make test`), for twenty rooms:

- Every swing step keeps the gripped edge in the same place.
- The last swing step leaves the board flat, sticking out away from the base.
- No step turns the board more than `SWING_STEP`.
- The fingers grip the middle of the edge, clear of both holders.
- The lift ends with the top's lower edge above both holders.
- The hanging board's lower edge never goes below the floor.

**In the simulator**, one stage at a time. Get each one working before adding
the next:

1. Grip the top in the holders, lift it clear, put it back, let go.
2. Lift it clear and hold it hanging for 10 seconds. Does it stay put?
3. Add the swing at a clear spot. Hold it flat for 10 seconds. Does it stay put?
4. Add the carry and the place: the whole job.

After each stage, ask Gazebo where the board really is
(`gz model -m table_top -p`) and compare it with where the code thinks it is.

---

## Words used here

- **Pose**: where something is *and* which way it faces.
- **Tool**: the end of the arm where the gripper is bolted on (`tool0`).
- **Grip / grasp**: closing the fingers on a part.
- **Hold**: how the part sits in the fingers, stored once at the moment of the
  grip. Afterwards, "put the part here" becomes "put the tool here".
- **Planning scene**: MoveIt's picture of the room, used to avoid collisions.
- **Attach**: telling MoveIt a part now moves with the gripper.
- **Inverse kinematics (IK)**: working out the joint angles that put the tool
  at a given pose.
- **Free move**: MoveIt finds any path that hits nothing. The shape of the
  path is up to the planner.
- **Straight-line (Cartesian) move**: the tool follows a list of poses in
  straight lines. The shape of the path is up to you.
- **Wrist flip**: most poses can be reached with the wrist bent one way or the
  other. Changing between the two in the middle of a move is not possible
  smoothly, so with a part in hand it is not allowed.
- **Wrist singularity**: a pose where two wrist joints line up and the arm
  cannot move the tool in some direction. Paths near it jerk or stop.
- **Friction grip**: the fingers hold the part only by squeezing. If a force
  turns or pulls the part harder than friction can resist, it slips.
