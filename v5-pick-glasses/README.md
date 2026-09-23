# pick-glasses

A robot arm looks at the drinking glasses on a table, measures each one, picks
it up, turns it upside down, and stands it on a drying rack.

Everything runs in simulation. One command starts it.

```
make run
```

The first run downloads the environment, which is a few gigabytes.

## Start here

[**`problem-statement.md`**](problem-statement.md) is the document to read
first. It says what the task is and why glasses were chosen over something
easier. It says what the arm is allowed to know, what counts as done, and what
counts as a glass fairly left alone. Everything else in this project follows
from it, and none of the rest will make much sense without it.

It all comes back to one sentence: **the shapes are known and the sizes are
not.** The arm knows what a wine glass is — a bowl on a stem on a foot. It does
not know how tall this one is, because two wine glasses from different sets do
not share proportions. So there is no table of measurements anywhere in this
project. There are rules about shapes, applied to a profile the camera measured
a second earlier. Adding a new kind of glass means writing a sentence, not
measuring a glass.

## Where this actually is

Worth knowing before you run it. The walkthrough describes a task that is
designed all the way through, and the code does not yet finish it.

**Everything up to setting the glass down works.** On a good run the arm finds
the rack and surveys the table. It measures a glass to within a few millimetres
of its real size, names its kind, and works out where to hold it. It closes the
fingers on it to better than a millimetre, lifts it, weighs it, carries it to
the middle of the table, and turns it over.

**No glass has been stood in the rack yet.** The set-down comes up short. The
arm lowers the glass the full sixty millimetres it is allowed and never feels
the rim touch. So the rim is not where the geometry says it should be, once the
glass has been turned. There is a specific suspect, written up under *Decisions
still open* in the problem statement.

**Runs also fail in different places from one attempt to the next.** Every
stage works. But several are close to the edge of what the arm can reach, and
a run has to get through all of them in a row.

The six walkthrough documents each end with what went wrong at that step and
what was done about it, which is the honest history of getting this far.

## How it works

Every glass goes through the same six steps.

**1. Find the glasses.** Pictures from above. The glasses are opaque — that is
an assumption, set out in the problem statement — so the depth camera sees
them. A glass is then a patch of the picture whose points stand above the table
top.

Two pictures are taken at each place the camera stops, a known distance apart.
One picture can only say which direction a glass lies in, not how far away it
is: a glass stands above the table, and laying its outline down on the table
puts it too far out. The pair fixes that.

What comes back is a position on the table and the width of each glass's
footprint. Deliberately nothing else, because from directly above a tall glass
and a short one look the same.

**2. Measure one, from the side.** The arm carries the wrist camera to a point
beside the glass and takes one picture. A drinking glass is a solid of
revolution, so the outline seen from any side is the whole shape: the width on
screen at some height *is* the diameter at that height. The result is a
**profile** — a width for every height up the glass, in millimetres.

Pixels become millimetres because the distance to the glass is known. It is
known because the arm chose how far back to stand and put the camera there
itself. The arm never needs a depth reading of the glass at all — which is the
one part of this that would still work on real, clear glassware.

**3. Decide what kind of glass it is — from the measurement.** A kind here is a
shape. The profile is a description of the shape. So a few tests read the kind
straight off it. Is there a waist? Then it is stemmed, and where the waist sits decides
whether the stem is a long one or a short one. No waist? Then the question is
whether the wall leans, which decides between a tumbler and a tapered glass.

There is no trained classifier in this project, and none is needed.

**4. Choose where to hold it.** Each kind has one rule, and the rule is a
sentence about the profile:

| Kind | Rule | In words |
| --- | --- | --- |
| Straight glass | `lowest_vertical_section` | the lowest stretch of wall that is upright enough for a flat pad |
| Tapered glass | `flattest_in_band` | a cone has no upright wall anywhere, so take the flattest band low down |
| Wine glass | `narrowest_below_widest` | the narrowest point below the widest point, which is the stem |
| Short-stemmed glass | `narrowest_below_widest` | the same rule, looking lower, because the stem ends sooner |

The rule returns a height. The finger opening is then *read off the
measurement* at that height — it is the diameter the camera saw there, and it
is never a number from a file.

**5. Pick it up and find out what it weighs.** The fingers close gently until
they touch, and the width at first contact is checked against the width the
camera predicted. If those two disagree by more than four millimetres, the
grasp is not where it was supposed to be and the glass is put back.

Then the squeeze goes to the estimate, the glass is lifted ten millimetres, and
the wrist sensor says what it actually weighs. If it is heavier than it looked,
it is set down and re-gripped harder — increasing the squeeze while holding it
arrives as a shock. If it is heavier than that kind of glass can take, it is
refused.

**6. Turn it over and stand it down.** The glass is first leaned over twenty
degrees while the finger gap is watched. Fingers that creep closed mean the
glass is sliding, and twenty degrees is a lean it can be brought back from. If
it holds, the arm turns it the rest of the way. It rotates about the grip point
itself, so the glass turns in place rather than swinging through an arc.

Then it comes down over a free slot and *feels* for the rack, rather than
driving to a calculated height. Both the glass's height and the height it is
held at were measured, and both carry error. When the rim touches, the arm
checks that the weight really has transferred before opening its fingers. A
glass caught on a peg still hanging from the gripper would otherwise be
dropped.

## The slot the glass can use

A glass in a rack slot has a few millimetres of room each side. Tilt eats that
room far faster than sideways error does, because a glass is tall. How much
tilt a glass can afford is

    atan(clearance / height)

An 80 mm glass in slots 100 mm apart has 10 mm of clearance a side. That is
6.3 degrees at 90 mm tall, 3.3 degrees at 175 mm, and 1.6 degrees if the glass
is 90 mm wide as well. The arm holds about 3 degrees. So a glass that is both wide and tall
gets the slot beside it left empty, which doubles the spacing and turns 1.6
degrees into 17.4.

This is decided per glass, from the measurement, and it is why the rack holds
six glasses on one run and four on another.

## What it looks like when it runs

This is a real run, with one straight glass on the table so that one thing is
being watched at a time:

```
rack found, 6 slots
surveying from 3 stations, each picture covering 519 x 390 mm, of which 424 x 175 mm is in both
--- glass_0 ---
measuring glasses from 380 mm back
the side view puts it 17 mm from where the survey did
measured 159 mm tall, 80 mm at its widest
that shape is a straight_glass
holding it 57 mm up, fingers 77 mm apart
it weighs 267 g
giving up on glass_0: came down 60 mm without touching anything, so the glass
is not where it was thought to be
```

Two lines are worth stopping on. **"fingers 77 mm apart"** is not a number from
a file. It is the width the camera measured at the height the rule chose, a
second earlier, and on a different glass it would be a different number. **"it
weighs 267 g"** could not have been known by looking at all, because wall
thickness is invisible. It comes from lifting the glass ten millimetres and
reading the wrist.

The last line is where the project currently stops, and the report the run
leaves behind in `runs/` shows the pictures the arm was working from when it
did.

## The cell

| Piece | What it is |
| --- | --- |
| Arm | **UR5e**, a 6-axis arm from Universal Robots. The model comes from their own `ur_description` package. |
| Gripper | A two-finger parallel gripper with silicone pads, defined in this repo. The pads matter: a rigid pad touches a curved glass at one point, a soft one spreads over a patch. |
| Sensors | An RGB-D camera on the wrist, a contact sensor on each pad, and a force sensor between the flange and the gripper. |
| Table | 1.6 m by 1.4 m, top at 75 cm. The arm stands on it, at the middle of one long edge. |
| Rack | Six slots, 100 mm apart, on the arm's left. Its shape is fixed and known, and it stands square to the table; where along the table it stands is not known, and the arm reads a marker on its base to find out. |
| Glasses | Four kinds, in random proportions within each kind, standing on the arm's right. `SEED` picks the set; no two runs get the same glasses. |

Everything in it is open source:

| Layer | Tool |
| --- | --- |
| Simulator | [Gazebo](https://gazebosim.org) Harmonic |
| Middleware | [ROS 2](https://docs.ros.org) Jazzy |
| Motion planning | [MoveIt 2](https://moveit.ai) |
| Joint control | [ros2_control](https://control.ros.org) |
| Perception | [OpenCV](https://opencv.org) and NumPy |
| Glass meshes | [trimesh](https://trimesh.org), which spins an outline into a solid |
| Environment | [pixi](https://pixi.sh), with ROS packages from [RoboStack](https://robostack.github.io) |

## Commands

```
make            # list everything you can run
make run        # build if needed, then start the cell and run the task
make cell       # start the cell but leave the arm alone, for poking at by hand
make test       # run the tests
make doctor     # print versions of everything that matters
```

`make run` takes settings:

```
make run GLASSES=6 SEED=12   # six glasses, a different set
make run GUI=false           # no Gazebo window, for a machine without a display
make run RVIZ=true           # also open RViz to see what MoveIt is planning against
```

Four is the number the table is sized for. Six fits, but the glasses are close
enough together that the arm has to approach some of them from a particular
side. Above six they cannot be spaced far enough apart to be sure the
silhouettes do not overlap, and the run stops before it starts rather than
measure two glasses as one.

## Adding a kind of glass

This is the thing the project is built to make easy, so it is worth showing how
short it is. A record in `glasses/spec.py`:

```python
"short_stemmed_glass": Kind(
    name="short_stemmed_glass",
    grip_rule=NARROWEST_BELOW_WIDEST,
    # A short stem sits lower, so the band stops sooner.
    search_band=(0.04, 0.40),      # fractions of the glass's own height
    min_band_height_m=0.008,       # how much wall a pad needs to sit on
    min_opening_m=0.006,           # narrower than this is not a stem
    max_opening_m=0.045,           # wider than this is not a stem either
    wall="thick",                  # a category, not a thickness
    expects_handle=True,
),
```

Every number there is either a fraction of the glass's own height or a limit
belonging to the gripper. None of them is the size of a glass, and the file
says so at the top:

> This file may hold rules and limits. It may not hold the size of any glass.

Then `make test` draws forty examples of the new kind at proportions spread
across the plausible range, and checks that every one of them gets a grip the
gripper can actually make. That is the test that catches a rule which works on
the glass you had in mind and fails on the glass someone else owns.

## What is not settled

The design questions that are genuinely open — the last few millimetres of
aim, whether short glasses can be picked up by this gripper at all, whether
the task should be planned as a whole, and where the arm ought to stand — are
written up under *Decisions still open* in
[`problem-statement.md`](problem-statement.md), where they sit next to the
reasoning they come from.

## Reading further

- [`problem-statement.md`](problem-statement.md) — what the task is, why it is
  worth doing, what the arm is allowed to know, and what is still undecided.
  Read this one first.
- [`docs/`](docs/) — a walk through one run, one document per step. Each ends
  with what went wrong at that step and how else that step could have been
  done. For steps 1, 2 and 4 that last part has a document of its own.
- [`pseudocode.md`](pseudocode.md) — what every file and function is for, and
  what calls what when you type `make run`.
- [`architecture.md`](architecture.md) — the folder layout, and why the pieces
  are split up the way they are.
- [`implementation-notes.md`](implementation-notes.md) — why each choice was
  made, and what breaks it.

