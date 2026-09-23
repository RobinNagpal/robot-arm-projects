# Step 6 — turning it over and standing it down

The glass is held, weighed and squeezed correctly. What is left is the part a
person does without thinking and a robot cannot. Turn the glass through 180
degrees. Stand it mouth-down in a rack slot. Touch nothing on the way, and do
not drive the rim into the rack at the end.

Three things make this harder than it sounds. First, turning a held glass is a
rotation about the grip, not a move to a new pose, and asking for it the wrong
way lets the planner take the glass on a detour. Second, the wrist has a limit
and cannot turn forever. Whether a glass *can* be inverted therefore depends on
which way round it was picked up, and that has to be checked before the fingers
ever close. Third, the height the rim lands at is the sum of two measured
numbers. Both carry error, and the errors add, which is why the last
millimetres are felt rather than driven.

This is also the step the project currently does not finish. The arm turns the
glass over and lowers it, and never feels it land. What is known about that is
at the end of this document, and under *Decisions still open* in the
[problem statement](../problem-statement.md).

Code: `rotate_tool()` and `descend_until_contact()` in `arm/motion.py`,
`rack/layout.py`, and `_invert_and_place()` in `task.py`.

Background, in robotics-basics: the whole of this step is
[letting go](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/05_holding-on.md#8-letting-go), which gives a six-step release
sequence this one follows most of. Turning the glass over is
[regrasping](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/05_holding-on.md#6-regrasping) avoided — nothing about a
two-finger grasp lets you invert an object in the hand, so this project inverts
the *arm* instead, which is why the wrist limit decides so much here. The
descent is
[the guarded move](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#21-what-you-can-actually-do-with-it) —
drive slowly until something fires and record where the arm was — and the rack
is found with [a marker of known size](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#24-a-marker-of-known-size).
When the arm ends up somewhere it should not, the order to check things in is
[the diagnosis ladder](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/07_making-it-work.md#3-when-it-does-not-work-a-diagnosis-ladder).

What follows, in order:

- the step in pseudocode, and the libraries it uses
- turning about the grip, not about the wrist
- the wrist limit, and why it is checked early
- how much room a glass needs in a slot
- feeling for the rack
- the last check before letting go
- what the run reports
- the three things the planner was told wrongly
- where a glass is turned over, and which slot it goes in
- where the method can still fail
- the other ways all of this could be done

## The step in pseudocode

Each line says who does the work: **ours** means code in this repo, and a named
library means the work is not ours.

```text
before any glass:                                 ours: task.py _find_rack()
    read the rack's ArUco marker                  OpenCV: cv2.aruco, on the wrist
                                                  camera's colour picture
    place the six slots from it                   ours: rack/layout.py
                                                  slots_from_marker()

choose a slot                                     ours: rack/layout.py. Done before
                                                  the pick-up, so a glass with
                                                  nowhere to go is never lifted.
    only slots this glass fits in                 usable_slots()
    only slots reachable from either side         slots_within_stretch()
    furthest from the arm first                   fill_order()
    leave a neighbour empty if it may tilt        needs_empty_neighbour() and
                                                  tilt_budget_deg()

with the glass held:                              ours: task.py _invert_and_place()
    carry the glass to the middle of the table    ours: arm/dimensions.py
                                                  TURNING_ROOM. The glass is parked
                                                  there, not the tool, because the
                                                  tool swings during the turn.
    lean it 20 degrees and watch the finger gap   ours: glasses/force.py
                                                  is_slipping(). A gap that has
                                                  shrunk means the glass is sliding.
    turn 180 degrees about the grip point         ours: arm/motion.py rotate_tool(),
                                                  about the point task.py
                                                  _grip_point() recomputes live

    move above the slot                           MoveIt 2: plan the move
    point the gripper away from the base          ours: transforms.py facing_options().
                                                  Turning over leaves the flange
                                                  past the glass; swinging it round
                                                  puts it back between base and slot.
    come down in 2 mm steps until it touches      ours: motion.py
                                                  descend_until_contact()
                                                  ros2_control: the pad contact
                                                  sensors and the wrist broadcaster
                                                  60 mm with no touch means the glass
                                                  is not where it was thought to be
    is the rack really taking the weight?         ours: motion.py
                                                  load_transferred(). No means the
                                                  rim is caught: do not let go.
    open the fingers                              ros2_control: back to position
    tell the planner the arm is empty             MoveIt 2: the planning scene
```

### What each library gives this step

| Piece | Ours or a library | What it does here |
| --- | --- | --- |
| `arm/motion.py` | ours | rotating about a point that is not the tool origin, and feeling the way down |
| `rack/layout.py` | ours | where the slots are, which ones this glass fits, and the tilt budget |
| `task.py` | ours | the order: check, carry, turn, choose, lower, check again, release |
| [MoveIt 2](https://moveit.picknik.ai/main/index.html) | library | plans every move; `compute_cartesian_path` for the straight ones, and the planning scene that keeps the held glass out of the rack |
| [OMPL](https://ompl.kavrakilab.org/) | library | the sampling planner MoveIt runs underneath for the free moves |
| [ros2_control](https://control.ros.org/jazzy/index.html) | library | runs the trajectories, and publishes the contact and wrist-force readings the descent watches |
| [Gazebo Harmonic](https://gazebosim.org/docs/harmonic/) | library | simulates the contact between rim and rack that the descent is feeling for |
| [tf2](https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Tf2.html) | library | the live tool pose the grip point is recomputed from |
| [OpenCV](https://github.com/opencv/opencv) | library | read the rack's ArUco marker, which is where every slot position comes from |

This is the step that leans on libraries most heavily. Steps 1 to 5 are mostly
NumPy on arrays we produced. Here MoveIt decides almost everything about how
the arm actually moves. The work in this repo is telling it the truth about the
world. The fault section below is three occasions when we did not.

## Turning about the grip, not about the wrist

Inverting a glass is a rotation. *What it rotates about* decides whether it is
safe.

The obvious implementation turns the tool about its own origin, because that is
what a pose command does. The fingertips are 170 mm from the tool origin, so
the glass swings through an arc 340 mm across — straight through whatever is
standing next to it.

Rotating about the **grip point** turns the glass on the spot, because the grip
point is the one place on the glass that is not moving relative to the fingers.

So `rotate_tool()` takes the point to turn about:

```python
turn = rotation_about(rotation[:, axis], angle)
moved = turn @ rotation
landing = about + turn @ (position - about)
```

and `task.py` passes the grip point, recomputed live from where the tool is now:

```python
def _grip_point(self):
    position, rotation = self._arm.current_pose()
    return position + rotation[:, 2] * FINGERTIP_OFFSET
```

`tilt()` and `turn_over()` are the same function with the two angles the task
uses — 20 degrees for the slip test, 180 for the real thing.

## The wrist limit, and why it is checked before the fingers close

The last wrist joint on a UR5e does not turn indefinitely. It stops a little
short, and there is a hard limit in the middle of its range that no plan can
cross.

That means whether the arm can invert a glass **depends on which way round it
took hold of it**. Approach from one side and the 180 degrees fits; approach
from the other and the wrist runs out halfway.

A parallel gripper is symmetric, so there are always exactly two ways round
that grip the same glass identically:

```python
for rotation in grasp_options(_grasp_rotation(approach)):
    hover above the glass in that orientation
    if self._arm.can_rotate_tool(math.pi):
        return rotation
```

`can_rotate_tool()` plans the turn without executing it. The arm asks this
question while hovering, **before the fingers close**, and takes the second way
round if the first cannot be turned.

Getting this wrong is the most expensive mistake available in the whole task.
It is discovered with the glass already in the gripper, and there is nothing
left to do but put it back down. It is also the kind of mistake that
works fine in testing and fails on the glass that happens to be standing at an
awkward angle.

## How much room a glass has in a slot

A glass going into a slot has `(spacing - width) / 2` of clearance on each
side. It pivots about its rim as it goes down, so the lean that uses up that
clearance is worked out per glass rather than chosen in advance — the general
form of that is
[from a measurement to a decision](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#28-from-a-measurement-to-a-decision).
The lean is

    atan(clearance / height)

![How much a glass may lean going into a slot](../images/tilt-budget.png)

The numbers are less forgiving than they look. Slots are 100 mm apart:

| Glass | Clearance each side | Budget |
| --- | --- | --- |
| 80 mm wide, 90 mm tall | 10 mm | 6.3° |
| 80 mm wide, 175 mm tall | 10 mm | 3.3° |
| 90 mm wide, 175 mm tall | 5 mm | 1.6° |

The arm holds about 3 degrees. So the third row is not something to attempt,
and `needs_empty_neighbour()` says so. Leaving the slot beside it empty doubles
the effective spacing, which takes 1.6 degrees to 17.4 — the dotted lines in
the picture.

What makes this worth a function rather than a rule of thumb is that it depends
on the **measured** width and height. It is decided per glass, on the day, and
it is why the rack takes six glasses on one run and four on another.

Slots are filled furthest-from-the-arm first, so a glass already standing in
the rack is never between the arm and the next slot.

## Feeling for the rack

The height at which the rim lands is

    slot height + (glass height - grip height)

and *both* of those glass numbers were measured, so both carry error, and the
errors add. Driving to a calculated height is how a rim gets chipped.

`descend_until_contact()` comes down in 2 mm steps until something reports a
touch, up to a 60 mm limit. Two millimetres because a rim meeting a peg at that
step size is a touch rather than a knock. This is
[the guarded move](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#21-what-you-can-actually-do-with-it), and
the accuracy of what comes out of it is the arm's own joint encoders rather
than anything about the sensor — the sensor's only job is to say *when*.

What counts as a touch took a correction. It originally watched the contact
sensors on the pads, which is the right signal when the pads are what arrives
first — and setting a glass down, they are not. The rim lands and the pads
touch nothing at all, so the descent reported an empty 60 mm every time while
the glass was already standing on the rack. What does give it away is the
weight leaving the wrist as the rack takes it. So that is watched as well. It
is the same reading the check under the next heading depends on.

Reaching the limit without touching anything is itself an answer — the glass is
not where it was thought to be — and it raises rather than carrying on.

## One last check before letting go

```python
if not self._arm.load_transferred(GRIPPER_WEIGHT_N):
    raise MotionFailed("the rack is not taking the weight, so the glass is caught")
```

Contact is not the same as support. A glass whose rim has caught on the edge of
a peg registers a contact while still hanging from the gripper, and opening the
fingers on it drops it. [Letting go](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/05_holding-on.md#8-letting-go) states
it as a rule — *move down until the weight leaves the wrist, not until
something touches* — and it is the same pattern as the fault above: watch the
sensor that observes the event, not the one nearest to it.

The wrist sensor settles this. If the rack has taken the weight, the sensor is
back to reading the gripper alone. If it is not, the glass is still there in
the reading, and the arm says so instead of letting go.

Only then do the fingers open, MoveIt is told the arm is empty, and the arm
lifts away for the next glass. The retreat is straight up, which is deliberate:
moving sideways at the moment the fingers open is how placed objects get
knocked over, and it is the usual cost of blending the release into the next
move.

Two steps of that release sequence are missing here, and both are cheap.
**The fingers open to `GRIPPER_MAX_OPENING` rather than to a width worked out
from the glass** — which happens to be past its widest point, so it works, but
by luck rather than by construction. And **nothing looks afterwards** to
confirm the glass is where it was put, which
[step 6 of the sequence](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/05_holding-on.md#8-letting-go) calls the
difference between a cell that reports a failed placement and one that carries
on stacking against a glass that is no longer there.

## What the run reports

Both columns, with the same weight given to each. A racked glass gets a line
saying what it turned out to be and where it went; a glass left standing gets
a line saying which step gave up and what it said. Here is a real one, from a
run with a single glass on the table:

```
finished: 0 racked, 1 left standing
  1. glass_0: left standing, the arm could not do it: came down 60 mm without
     touching anything, so the glass is not where it was thought to be
```

That is the failure this step currently ends on, and it is described at the
end of this document. A more ordinary refusal reads like this one, from a
stemmed glass whose stem was too narrow for the rules to allow:

```
  1. glass_0: left standing, nowhere safe to hold it: the rule wants the
     fingers 61 mm apart, outside the 4 to 40 mm a stemmed_glass should ever
     need
```

That second one is a working run, not a failed one, and the distinction is the
point of printing both columns at all. A glass the arm declines to touch, with
a sentence saying why, is the behaviour the
[problem statement](../problem-statement.md) asks for. The run to worry about is the one that racks everything by ignoring a doubt.
The doubt it ignored will still be there on the next run, and the glass may not
survive it twice.

## What the planner had to be told, and what it was told wrongly

Three separate faults lived in what MoveIt believed about the world at this
point in the run. All three arrived as the same symptom: a path that solved
none of the way. That is indistinguishable from a move that is simply
impossible.

**The pads were not allowed to touch the glass they were holding.** When a
glass is attached to the gripper, MoveIt is given a list of links that may be
against it without that counting as a collision. The list named the gripper
body and the two fingers. It did not name the two pads. The pads are the only
parts that ever touch a held glass — the fingers never reach it, because the
pads are what stands between. So from the moment a glass was picked up, it was
in collision with the gripper holding it, and the arm could not move at all. It
could not even stand clear, because standing clear is also a move. One stuck
glass ended the whole run.

**The glass was attached in the wrong place.** Where a glass sits in the
gripper is worked out by comparing where the glass is with where the tool is.
The two were being taken a lift apart: the glass from before the 180 mm lift
off the table, and the tool from after it. MoveIt therefore believed in a glass
hanging 180 mm below the real one, straight through the table. Everything after
that started in collision.

**The rack the planner saw was turned a quarter circle from the rack.**

![The box the planner was given, against the rack](../images/the-rack-the-planner-saw.png)

The box describing the rack was built from the length of the row of slots, and
never turned to match it. So it came out at right angles to the thing it was
standing in for. That put a 600 mm slab across open table, right where the arm
has to work. It is what the arm kept meeting when it failed to reach places
with nothing in them. And it left the real rack covered by nothing at all.

The same quarter turn appeared again, independently, in the marker. The way
that printed square is oriented is what says which way the rack is facing, and
every slot is placed from it. The square is painted onto a box face, and how a
texture lies on a box face is the simulator's business rather than ours. So the
arm read a rack square to the world, when the rack is in fact turned across it.
It laid its six slots out at right angles to the real rack and lowered a glass
over bare table. That is the other reason the descent above kept finding
nothing.

## Where a glass is turned over, and which slot it goes in

![A turn swings the tool either side of the glass](../images/the-turn-swings-the-arm.png)

Turning in place asks more of the wrist than anything else in this task. It was
being done wherever the pick happened to leave the arm, which was usually
stretched out towards the far corner of the glass zone. That is exactly where
the last joint has least left to give. The glass is now carried to the middle
of the table first, so the turn is the same problem every time rather than a
different one for every glass.

That needed a second go, and the reason is the picture above. The first version
parked the *tool* at a comfortable reach. But a turn swings the tool a
fingertip's length either side of the glass, so a tool parked at 450 mm came
out of the turn at 790 mm — past the end of the arm, with the glass in hand.
The glass is the thing that stays still during a turn, so the glass is what
gets parked. At 500 mm the tool starts the turn at 330 mm and finishes it at
670 mm, and the arm can do both.

The same arithmetic decides which slot a glass may go in. Standing a glass in a slot puts the tool a fingertip's length to one side of
it. Which side is settled long before, by how the glass was picked up and which
way it was turned. A slot that only works from one side is a coin toss with a glass already in
hand. So slots are filtered to the ones the arm can stand over from either
side. The far end of the row put the tool 796 mm out. If none qualify, the list
is left alone: a slot that might not work still beats refusing a glass that is
already held.

## Where this approach can fail

**The set-down does not work yet.** This is the open failure, not a
hypothetical one. The arm turns the glass over, lowers it the full 60 mm, and
never feels it land. No glass has been stood in the rack. The suspected cause
is what the planner is told about the attached glass, which is the subject of
the fault section above.

**Everything downstream of the marker depends on the marker.** Every slot
position comes from one printed square on the rack base. If the marker is
misread, or read at the wrong angle, the arm lowers a glass over bare table and
has no way to know. That has already happened once, for exactly that reason.
[A marker of known size](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#24-a-marker-of-known-size)
names the same failure — a bent or partly obscured marker gives a pose that is
wrong in a way that looks plausible — and notes that a single small square is
famously unstable in *angle* near face-on, which is exactly the quantity every
slot position here is derived from.

**A slot is chosen before the glass is known to fit through the approach.** The
tilt budget says whether a glass fits in a slot. It does not say whether the
arm can get it there without brushing the glass already in the next slot.

**The descent feels for contact, not for the right contact.** A rim landing on
the edge of a peg, or on a neighbouring glass, reads as a touch. The load check
afterwards is what catches it, and it is a threshold on a noisy sensor.

**The turn is checked, and then assumed.** `can_rotate_tool()` asks whether the
180 degrees is possible before the fingers close. Between that check and the
turn itself, the arm has moved: it has gripped, lifted, leaned 20 degrees, and
carried the glass to the middle of the table. The check is re-run at the turn,
and a refusal there comes with a glass already in hand.

**Carrying to the middle assumes the middle is free.** `TURNING_ROOM` is a
fixed point over the table. Nothing checks whether a glass is standing there.
The planner will refuse a path through it, which turns into a refused glass
rather than a collision, but it is a refusal that a smarter choice of turning
place would avoid.

**Nothing watches the glass after it is released.** The fingers open, the arm
lifts away, and the run moves on. A glass that topples out of its slot a second
later is recorded as racked. The wrist camera is looking more or less at the
slot at that moment, so the picture costs one frame.

## Other ways to move the arm and place the glass

Two separate questions hide in this step: how the arm works out a path, and
how it knows the glass has landed. Both have well-trodden alternatives.

| Approach | What it does | What it runs on | Suitability here |
| --- | --- | --- | --- |
| **Sampling planner, with straight lines where it matters** | plans free moves by random sampling, and forces a straight line for the delicate ones | [MoveIt 2](https://moveit.ai/) with [OMPL](https://ompl.kavrakilab.org/) | good, and in use |
| **Plan the whole task at once** | treats pick, turn and place as one problem with alternatives at each stage | [MoveIt Task Constructor](https://github.com/moveit/moveit_task_constructor) | already a dependency, and a good fit |
| **Optimising planners** | starts from a rough path and smooths it against a cost | CHOMP and STOMP in [MoveIt](https://moveit.ai/), [TrajOpt](https://github.com/tesseract-robotics/trajopt) | steadier paths, worse at squeezing through gaps |
| **Planning on a GPU** | solves thousands of candidate paths at once | [cuRobo](https://curobo.org/) | would make the retries free |
| **Full dynamics and contact** | plans with the physics of contact in the loop | [Drake](https://drake.mit.edu/) | more than this task needs |
| **Servo on the goal** | streams small corrections instead of planning a path | [MoveIt Servo](https://moveit.ai/) | good for the last few centimetres |
| **A learned policy** | outputs joint moves directly, with no planner at all | [ACT](https://tonyzhaozh.github.io/aloha/), [Diffusion Policy](https://diffusion-policy.cs.columbia.edu/) on [PyTorch](https://pytorch.org/) | would sidestep most of the failures above |

**What is in use** is the ordinary ROS arrangement. Free moves go to a sampling
planner, which is very good at finding a way around the rack. The delicate
moves — in to the glass, off the table, down into the slot — ask for a straight
line instead, so the fingers cannot sweep sideways through a neighbour.

The weakness of that split is written all over the faults above. A
straight-line request is all or nothing, so it comes back having solved none of
the way as readily as all of it. And a sampling planner gives a different
answer every time you ask it. That is why moves are now planned up to three
times before being believed.

**[MoveIt Task Constructor](https://github.com/moveit/moveit_task_constructor)**
is the most interesting entry, because the project already depends on it and
does not use it. It is built for exactly this shape of problem. A sequence of stages, each with
several possible ways of being done, solved together. A choice made early is
then not allowed to make a later stage impossible. Almost
every failure in this document is that class of mistake — a grasp chosen
without knowing which side the tool would end up on at the rack, a turn
attempted from wherever the pick happened to finish. Planning the whole task
at once would have prevented several of them outright. The cost is that it is
a much larger way of expressing the task, and that the sequencing, which
currently reads top to bottom in `task.py`, would become a tree.

**Optimising planners** such as CHOMP, STOMP and
[TrajOpt](https://github.com/tesseract-robotics/trajopt) start from a guess and push it away from
obstacles. That gives smooth, repeatable paths — the opposite of the sampling
planner's habit of finding a different contortion each time. They are worse in tight spaces. A path that has to thread a gap is
exactly where a local method gets stuck, and this cell is tight — an arm
bolted to the middle of its own table, with a rack alongside.

**[cuRobo](https://curobo.org/)** solves many candidate paths in parallel on a
GPU, fast enough to plan inside a control loop. The fix for marginal planning
here was to ask three times and hope. A planner that can ask a thousand times
in the same wall-clock second is an appealing answer to that. It also needs a
GPU the development machine may not have.
**[Drake](https://drake.mit.edu/)** goes further again and plans with contact
physics in the loop, which is the right tool for assembly or in-hand
manipulation and more than a pick-and-place needs.

**[MoveIt Servo](https://moveit.ai/)** streams small velocity corrections rather
than planning a path. It is the natural home for the two closed loops this task
has grown by hand: the sideways nudge onto the glass in step 4, and the
feel-for-the-rack descent on this page. Both are servo loops written
as a sequence of small planned moves, which works and is clumsy.

**A learned policy** — [ACT](https://tonyzhaozh.github.io/aloha/) or a
[diffusion policy](https://diffusion-policy.cs.columbia.edu/) — would replace
the planner entirely for the parts near the object, outputting joint moves
directly from what the arm sees and feels. That is attractive here for a
specific reason rather than a general one. A large share of the failures in
this document are the planner refusing a pose the arm could physically hold. A
policy never asks the planner anything. The sibling project
[`v5-learn-pick-place`](../../v5-learn-pick-place) does exactly this and
reaches 74 per cent on blocks it never saw. What it gives up is the thing this
project is built on — a policy cannot say why it refused a glass, and the
refusals here are supposed to be legible.

### And for knowing the glass has landed

Feeling for the rack has alternatives too, and they are much simpler. The
honest one is a **table of known slot heights**: the rack is a fixed object,
so the height its base sits at could be written down once and the glass driven
to it. That is a good deal simpler than the descent on this page. It fails the
moment either the glass measurement or the marker reading is a couple of
millimetres out, which is exactly the case this project is about. The same
argument that rules out a table of glass sizes rules this out too. A
**downward-looking camera check** before letting go would confirm the glass is
standing rather than leaning, which is a real gap: nothing currently checks
that. And a **load cell under the rack** would say the rack had taken the
weight far more directly than watching it leave the wrist, at the cost of
instrumenting the furniture.

← [Back to the walkthrough](README.md)
