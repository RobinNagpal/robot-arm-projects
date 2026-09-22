# pick-glasses

A robot arm looks at the drinking glasses on a table, measures each one, picks
it up, turns it upside down, and stands it on a drying rack.

Everything runs in simulation. One command starts it.

```
make run
```

The first run downloads the environment, which is a few gigabytes.

## The problem

Glasses of several shapes stand on a table. For each of them the arm has to:

- measure it, because nobody has told it how big this one is;
- work out where on the glass it can be held;
- work out how hard to squeeze, without knowing what the glass weighs;
- pick it up, turn it through 180 degrees, and stand it mouth-down in a free
  slot on the rack.

The interesting constraint is in the first line, and it is worth being precise
about it.

**The shapes are known. The sizes are not.** The arm knows what a wine glass is
— a bowl on a stem on a foot. It does not know how tall this wine glass is, how
wide its bowl is, or how thick its stem is, and it cannot be told, because two
wine glasses from different sets do not share proportions. A 150 mm glass is
not a 190 mm glass scaled down: the stem is a different fraction of the height
and the bowl is a different fraction of the width.

So there is no table of measurements anywhere in this project. What the project
holds instead is a set of **rules** — "hold a stemmed glass on its stem, which
is the narrowest part below the widest part" — and those rules are applied to
what the camera measured a moment ago. The consequence is that adding a new
kind of glass is writing a rule, not measuring a glass, and a rule can be
checked against forty randomly proportioned examples in a second.

One thing is assumed: the glasses stand apart from each other, upright, and not
inside one another.

## Why a glass is harder than a box

The earlier projects in this repo move cuboids and table parts around. A
cuboid is generous: it is opaque, so the camera sees it; it has flat parallel
sides, so the gripper has somewhere obvious to go; it is solid, so its weight
follows from its size; and dropping one costs nothing.

A glass takes all four of those away.

**A depth camera cannot see it.** Most of the light goes straight through and
the rest is bent by the curved wall, so the depth picture has a *hole* where
the glass is. This project reads the hole. That is not a way of cheating the
simulator — it is the same signal a real depth camera gives, and building on it
means the pipeline meets the same difficulty a real one would.

The glasses in the simulator are painted solid colours, a different one each,
so that a person watching can tell them apart. That is a change to what a
person sees and to nothing else. Gazebo's depth camera can see through
nothing, transparent or not, so the hole is put into the depth picture by the
wrist camera, from a segmentation camera that says which pixels are glass —
see [`implementation-notes.md`](implementation-notes.md). The arm is no better
off for the paint.

**Its walls are not parallel.** A flat gripper pad on a sloping wall slides.
Finding a grip means finding somewhere the wall is upright over at least the
height of a pad, and on a wine glass there is exactly one such place.

**Its weight does not follow from its size.** Wall thickness is invisible from
outside, and a thin-walled 190 mm flute weighs less than a squat tumbler. So
the arm estimates a squeeze, lifts the glass ten millimetres, weighs it on the
wrist sensor, and adjusts — a two-stage grip, because one stage cannot be done.

**Getting it wrong costs more than a retry.** A dropped glass leaves shards,
and the arm will carry on moving through them. So every step that could be
wrong has a check after it, and a glass that fails a check is left standing on
the table with a reason written next to it. A run that racks three glasses and
refuses one is working correctly.

## How it works

Every glass goes through the same six steps.

**1. Find the glasses.** One picture from above. The glasses are the holes in
the depth picture that have something visible through them. This gives each
glass a position on the table and the width of its footprint — and deliberately
nothing else, because from directly above a tall glass and a short one look the
same.

**2. Measure one, from the side.** The arm carries the wrist camera to a point
beside the glass and takes one picture. A drinking glass is a solid of
revolution, so the outline seen from any side is the whole shape: the width on
screen at some height *is* the diameter at that height. The result is a
**profile** — a width for every height up the glass, in millimetres.

Pixels become millimetres because the distance to the glass is known, and it is
known because the glass stands on the table and the table has been measured.
The arm never needs a depth reading of the glass itself, which it could not
get.

**3. Decide what kind of glass it is — from the measurement.** A kind here is a
shape, and the profile is a description of the shape, so a few tests read it
off. Is there a waist? Then it is stemmed, and where the waist sits decides
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
degrees while the finger gap is watched: fingers that creep closed mean the
glass is sliding, and twenty degrees is a lean it can be brought back from. If
it holds, the arm turns it the rest of the way — rotating about the grip point
itself, so the glass turns in place rather than swinging through an arc.

Then it comes down over a free slot and *feels* for the rack rather than
driving to a calculated height, because both the glass's height and the height
it is held at were measured and both carry error. When the rim touches, the arm
checks that the weight really has transferred before opening its fingers. A
glass caught on a peg still hanging from the gripper would otherwise be
dropped.

## The slot the glass can use

A glass in a rack slot has a few millimetres of room each side, and tilt eats
that room far faster than sideways error does, because a glass is tall. How
much tilt a glass can afford is

    atan(clearance / height)

which for an 80 mm glass in slots 100 mm apart is 10 mm of clearance — 6.3
degrees at 90 mm tall, 3.3 degrees at 175 mm, and 1.6 degrees if it is also 90
mm wide. The arm holds about 3 degrees. So a glass that is both wide and tall
gets the slot beside it left empty, which doubles the spacing and turns 1.6
degrees into 17.4.

This is decided per glass, from the measurement, and it is why the rack holds
six glasses on one run and four on another.

## What it looks like when it runs

The numbers below come from the project's own functions, run on the glasses
`SEED=7` puts on the table:

```
[glass_task]: rack found, 6 slots
[glass_task]: --- glass_0 ---
[glass_task]: measured 164 mm tall, 63 mm at its widest
[glass_task]: that shape is a straight_glass
[glass_task]: holding it 14 mm up, fingers 61 mm apart
[glass_task]: it weighs 244 g
[glass_task]: --- glass_1 ---
[glass_task]: measured 134 mm tall, 77 mm at its widest
[glass_task]: that shape is a stemmed_glass
[glass_task]: holding it 31 mm up, fingers 7 mm apart
[glass_task]: it weighs 77 g
...
[glass_task]: finished: 4 racked, 0 left standing
[glass_task]:   1. glass_0: straight_glass, 164 mm tall, 63 mm wide, 244 g, held 14 mm up, slot 5
[glass_task]:   2. glass_1: stemmed_glass, 134 mm tall, 77 mm wide, 77 g, held 31 mm up, slot 4
[glass_task]:   3. glass_2: tapered_glass, 124 mm tall, 82 mm wide, 175 g, held 12 mm up, slot 3
[glass_task]:   4. glass_3: short_stemmed_glass, 144 mm tall, 72 mm wide, 260 g, held 19 mm up, slot 2
```

The line worth looking at is the second glass: 77 mm wide, held with the
fingers 7 mm apart. That is the stem. Nothing told the arm this glass had a 7
mm stem, or that its stem was 31 mm up; both came out of a picture taken a
second earlier.

On `SEED=1` the report has a different shape, because one of the glasses there
is 100 mm across — wider than the rack's slot spacing — and it takes two slots.

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

## Open items and questions

What is not finished, roughly in the order it is worth picking up. The faults
that *were* fixed are written up at the step each one belongs to in
[`docs/`](docs/).

**No glass has been placed in the rack yet.** The arm finds the rack, surveys
the table, measures a glass to within a few millimetres, names its kind, works
out where to hold it, reaches in, closes on it, lifts it, weighs it at 267 g,
carries it to the middle of the table, turns it over and lowers it onto a slot
— and then comes down the full 60 mm without feeling anything. The arithmetic
says the rim should touch after about 10 mm: it hangs 102 mm below the grip,
the grip is put 132 mm above the slot, and the rack's base stands 20 mm above
the plane the slots are measured in. So the rim is not where the geometry says
it is once the glass has been turned over.

**The likeliest cause of that is a second fault in how a held glass is
attached.** In the same run the planner reported the arm's own forearm to be
in collision with the held glass, which means the shape standing in for that
glass is not where the glass is. One fault of that kind has already been fixed
— the glass's position taken from before the lift and the tool's from after it
— and this looks like another in the same place, most probably the glass's
orientation after the turn rather than its position. It can be checked without
the simulator by comparing the attached shape's pose against the tool's pose
immediately after `turn_over()`.

**The survey is out by about 30 mm along one axis.** Across four runs of the
same table it placed a glass within 4 mm along one axis every time and about
30 mm out along the other, and the axis it is wrong about is the one the two
pictures step along — which is the very thing the second picture is there to
measure. The side-on view happens to correct most of it, which is why the
error stayed invisible so long and why that correction is always about the
same size. The shrink figure the arithmetic produces, 0.868 where the geometry
says about 0.826, accounts for only a few millimetres of it, so most of the
error is in finding the middle of the outline or in merging the stations
rather than in the arithmetic that follows. The clean test is to compare each
single picture's answer against the truth before any correction is applied.

**Runs fail in different places from one attempt to the next.** Every stage
works, but several are close to the edge of what the arm can do and a run has
to get through all of them, so recent attempts have stopped at the measuring
view, at the reach in, at the grip rules and at the set-down. The honest
summary is that each stage works most of the time and that end to end is
therefore much less often. Whether to attack that stage by stage or by giving
the arm more room to work in is undecided.

**The arm is bolted to the middle of the table.** Its base sits at table
height, so its lower links are near the surface and graze the table whenever
it reaches low, which is genuinely the case rather than a modelling error and
makes low reaches tight. A good deal of the marginal planning above may come
back to this. Moving the arm to the edge of the table, or raising it, would be
a change to the cell rather than to the code and wants to be a deliberate
decision.

**Short glasses cannot be picked up at all.** Below `LOWEST_GRIP` the
gripper's body is through the table, and above half its own height a glass
cannot be turned over, so anything under roughly 120 mm tall has no band left
to grip. The arm says so clearly and leaves the glass standing, which is the
right behaviour, but it does mean part of the range this project generates can
never be handled by this gripper. Either the generator should not draw them,
or the gripper wants a slimmer body, or such glasses want picking up a
different way.

**A full table has not been tried since any of this was fixed.** All of the
recent work was chased with one glass on the table, which was the right way to
do it, but the survey, the collision scene and the slot bookkeeping all behave
differently with five or six. That is the obvious next test once a single
glass goes in reliably.

**The measured width comes out a little under the truth.** A glass really
71 mm across its widest measured 66, and one really 78 mm across measured 77.
It has not caused a failure, because the fingers close on the glass and check
the width by touch before anything is lifted, and it may be no more than the
outline being found a pixel inside the glass on each side. It has not been
looked into.

**Lint does not pass on the project as a whole.** Ten files were already
failing the formatter before this work started and none of them are files it
touched, so they are left alone — but it does mean `make lint` cannot be used
as a gate until somebody decides whether to reformat them.

## Reading further

- [`docs/`](docs/) — a walk through one run, one document per step, with the
  arithmetic for the parts that are hard to see in the code.
- [`pseudocode.md`](pseudocode.md) — what every file and function is for, and
  what calls what when you type `make run`.
- [`architecture.md`](architecture.md) — the folder layout, and why the pieces
  are split up the way they are.
- [`implementation-notes.md`](implementation-notes.md) — why each choice was
  made, and what breaks it.

