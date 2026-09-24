# Problem statement: pick up a glass and stand it upside down

## The idea in one paragraph

Drinking glasses stand on a table, the way they would after a meal. A robot
arm takes each one, turns it upside down, and stands it on a drying rack. The
design document this grew out of is [standing an empty glass upside down on a
drying rack](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/10_one-arm-training/07_case-study/01_place-glass.md); what follows is the version that was actually built, and
it differs from that one, most of all in assuming the glasses are opaque. It
has to do that without being told anything about the glasses beforehand. Not
how tall they are. Not how wide, not how heavy. Not even which of them is a
wine glass and which is a tumbler. It works all of that out by looking, one
glass at a time. And if what it works out does not add up to a safe grip, it
leaves the glass where it is and says why.

## Why glasses

Each project in this repo picks one hard thing and pushes on it. v1 is about
seeing: measure a box and act on what you measured. v2 is about several parts
that have to agree with each other. v4 is about learning to see instead of
being told, and v5-learn-pick-place is about learning to move. This project is
about a gap that none of them have to face, which is the gap between knowing
what a thing *is* and knowing what a thing *measures*.

**The shapes are known and the sizes are not.** A person asked to pick up a
wine glass knows exactly what to do without having measured anything. They
know a wine glass is a bowl on a stem on a foot, and that the stem is the part
to hold. That knowledge works on a wine glass they have never seen, because it
is knowledge about the *shape*, not about any particular glass. It has to be,
because glasses do not share proportions. A 150 mm wine glass is not a 190 mm
one scaled down: the stem is a different fraction of the height, and the bowl a
different fraction of the width. So a robot given a
table of measurements works on the glasses whoever wrote the table owned, and
fails on the next set. The only thing worth storing is the sentence — hold the
narrowest part below the bowl — and the only way to use it is to measure the
glass in front of you, now.

That premise would be a small thing on its own. What makes it a project is
that a glass fights most of the ordinary ways of handling it, even once you
assume — as this project does — that you can at least see the thing.

**Its weight cannot be seen.** Wall thickness is invisible from outside, and
two glasses with the same outline can differ in weight by a factor of three.
How hard to squeeze depends on weight. So the squeeze cannot be worked out from
a picture at all. It has to be corrected once the glass is in the air.

**There is usually exactly one place to hold it.** A glass is round and its
walls are rarely parallel, and flat pads on a sloping wall slide. On a wine
glass that place is the stem, a few millimetres across. On a tumbler it is a
band near the base. Finding it means finding a *feature*, not a coordinate.

**And dropping one costs more than trying again.** Broken glass leaves shards,
and an arm that carries on working moves through them. In the language of
[how hard to squeeze](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/03_choosing-a-grip.md#42-the-other-bound-which-is-the-one-that-actually-bites),
the binding limit here is not the friction that stops a glass slipping. It is
the force at which the glass breaks, and the right response to needing more
than that is to refuse. This is the thing that shapes the whole
design. Anywhere else, a robot may try and fail cheaply. Here it may not. So a
doubt has to end the attempt rather than be pushed through.

## The setup

- **A table**, 1.6 m by 1.4 m, with its top 750 mm off the floor.
- **One UR5e arm**, the same arm as the earlier projects, bolted to the table
  at the middle of one long edge and 400 mm in from it. Everything happens
  within about 780 mm of its base, which is what it can reach comfortably.
- **A two-finger parallel gripper** with silicone pads, defined in this repo.
  It opens to 95 mm and the pads are 14 mm tall. It is the commonest kind of
  gripper there is, and what its datasheet numbers mean is
  [how to read a gripper datasheet](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/02_grippers-and-hardware.md#1-how-to-read-a-gripper-datasheet). The pads are not a detail. A
  rigid pad touches a curved glass at a single point. A soft one spreads over a
  patch. That is the difference between holding a glass and polishing it.
- **Three sensors**, each one there because a particular thing cannot be seen.
  An RGB-D camera on the wrist. A contact sensor in each pad. And a force
  sensor between the flange and the gripper.
- **The glasses**, standing on the arm's right. How many, of how many kinds,
  and how close together is what the five problems below vary. They are opaque and each is a different
  solid colour, which is an assumption rather than an accident — see below. Each run draws them fresh from four kinds —
  straight, tapered, stemmed and short-stemmed — with the proportions of each
  one drawn at random inside a plausible range. A seed picks the set, so a run
  can be repeated exactly, and no two seeds give the same glasses.
- **The drying rack**, on the arm's left: six slots 100 mm apart, each with a
  short peg to stand a glass over. Its shape is fixed and known. Where along
  the table it stands is not, and the arm finds that out by reading a printed
  marker on its base.

Everything runs in simulation, in Gazebo.

## What we assume

Two assumptions make this a task that can be finished rather than a research
project. Both are deliberate. Both make the problem easier than the real world.
Both are written here so that nobody has to work out from the code which
difficulties are being faced and which are being stepped around.

**The glasses are opaque and plainly coloured.** Each one is painted a solid
colour, a different colour per glass, and you can see it in the window and in
every picture the arm takes. It is not see-through, and nothing in this
project has to cope with looking through one glass at another.

That assumption removes a real difficulty, and it is worth being honest about
which one. A depth camera works by sending light out and timing what comes
back. Real glass sends almost none of it back: most of the light goes straight
through, and the rest is bent away by the curved wall. So pointing a depth
camera at a real glass gives no distance reading at all for the pixels the
glass covers. The depth picture comes back with a glass-shaped gap in it, where
every other object would have had a distance. Every method that starts with
"take the point cloud" starts, on real glassware, by not working. This is not
particular to one sensor: [all four sensing principles](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#11-how-the-four-sensing-principles-fail)
fail on it, for four different reasons.

That gap is also a signal, and it can be used as one. Treating the missing
depth as the measurement rather than as the obstacle is a real technique with a
name — [the depth hole](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#17-the-depth-hole-for-glass-and-chrome) —
and it is what this project used to do; `docs/step1-finding-the-glasses.md`
records why it went. What has replaced it in the field is learned [depth
completion for transparent and shiny objects](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/04_models-that-find.md#17-transparent-and-shiny-objects),
whose licensing is worse than its accuracy.

Assuming the glasses are opaque means the camera simply sees them, the way it
sees the table and the rack. The arm can then find a glass by noticing that its
points stand above the table top. That is a much easier problem, and it is the
one this project solves. Dropping the assumption later means replacing one
function: the one that decides which pixels are a glass. The ways of doing that
are compared in
[`docs/step1-approaches.md`](docs/step1-approaches.md).

**The glasses stand apart, upright, and separate.** None is lying down, none
is inside another, and none is being held. A tray of glasses jumbled together
is a different task.

The *apart* half of that is the one the problems below take away by degrees.
Problem 1 has one glass, so it does not arise. Problems 2 and 4 set them out at
least 150 mm from each other, which is far enough for the arm to reach any of
them. Problem 3 is the one that removes it: the glasses may be standing close
enough to foul each other, and moving them apart is the whole of that problem.

Upright, however, is assumed throughout. A fallen glass is out of scope in all
five.

## Five problems, in order of difficulty

The task above is not one problem. It is five, and they get harder in a
particular way: each one takes away something the one before it was allowed to
assume. Taking them in order is deliberate, because each answer is a thing the
next problem can stand on, and because it keeps clear which difficulty is being
solved at any moment.

![The five problems, and what each one adds](images/the-five-problems.png)

| | The problem | What is new in it | Where it is worked out |
| --- | --- | --- | --- |
| **1** | One glass on the table | everything, from an empty start | [`docs/problem-1/`](docs/problem-1/) — **built** |
| **2** | Many glasses of one kind | telling them apart, from few viewpoints | [`docs/problem-2/`](docs/problem-2/) — designed |
| **3** | Glasses standing too close | moving one without lifting it | [`docs/problem-3/`](docs/problem-3/) — designed |
| **4** | Several kinds at once | a different rule per glass, in one run | [`docs/problem-4/`](docs/problem-4/) — stated |
| **5** | Kinds whose proportions are unknown | a rule that has never seen this glass | [`docs/problem-5/`](docs/problem-5/) — stated |

Each has its own folder under [`docs/`](docs/), with the problem written out
in full and the solution worked through. What follows is the short version of
each.

### Problem 1 — one glass, start to finish

One glass stands on the table. The arm has to find it, work out its
dimensions, pick it up, turn it over and stand it on the rack. Nothing about
the glass is known in advance.

This is the whole pipeline at its simplest, and it is the one that is built.
Every hard thing in the project is already present — the shape has to be
measured, the grip has to be chosen from that measurement, the weight cannot be
seen, and the set-down has to be felt rather than driven. What is *absent* is
everything to do with there being more than one glass. Nothing can occlude
anything. Nothing has to be told apart from anything. The arm can walk all the
way round the glass and photograph it from any side it likes.

**Done** means the glass is standing mouth-down over a slot peg, with the
fingers open and the arm clear of it.

### Problem 2 — many glasses of one kind, seen from few viewpoints

Several glasses of the *same* kind stand on the table. The arm photographs
them and has to work out which pixels belong to which glass.

The new difficulty is not the naming; they are all the same kind and the kind
is known. It is that with several glasses on a table, **the arm can no longer
photograph each one from whichever side it likes.** Walking round a glass means
putting the camera where another glass may already be, or where the arm cannot
reach without crossing over a third. The side-on view that problem 1 depends on
is not always available.

So this problem is about perception, and only perception. It stops at a set of
pixels per glass. It does not pick anything up.

### Problem 3 — glasses too close together, moved apart by dragging

Given the pixels from problem 2, some of the glasses are standing close enough
together that the arm cannot get the gripper round one without fouling its
neighbour.

The arm has to **separate them by dragging them across the table**, not by
lifting them. Dragging is the point: a lift is a grasp, and a grasp is the
thing that is not possible yet. Pushing a glass along the table needs only a
contact and a direction.

This problem is about separation, and only separation. It starts from pixels
and ends with glasses far enough apart to be picked up. It does not pick
anything up either.

### Problem 4 — several kinds at once

A few kinds of glass stand on the table together. The arm has to measure each
one, decide which kind it is, pick it up, invert it and rack it — one at a
time, until the table is clear.

This is problems 1, 2 and 3 joined up, plus the part neither of them has:
**the rule changes per glass.** A wine glass is held by the stem and a tumbler
low on its wall, so naming the kind is now load-bearing, and naming it wrongly
means holding a glass in a place that was never checked.

### Problem 5 — kinds whose proportions are not known

The same as problem 4, except that the glasses are not drawn from proportions
anybody wrote down. A wine glass may have a stem that is a third of its height
or a tenth of it. The arm still has to pick each one up and invert it.

This is the problem the whole project exists for, and the reason every earlier
problem refuses to write a measurement down. A rule that says *hold the
narrowest part below the widest* survives this. A table of grip heights does
not.

## What "done" means, for all five

A glass is **done** when it is standing mouth-down over a slot peg with the
fingers open and the arm clear of it. A glass is **left standing** when any
step cannot be completed safely, and every one of those ends with a sentence
saying which step and why.

**Leaving a glass standing is a success, not a failure.** This is the rule
that most shapes the code. A run that racks four glasses and refuses one with a
reason is working correctly. A run that racks five by pushing through a doubt
is the one to worry about. It is worth less even when nothing breaks, because
the doubt it ignored will still be there next time.

## What the arm knows

The rule from v2 holds here: **an arm knows itself, and the rules, and nothing
else about the world.**

It knows:

- where its own base is, and how its arm, gripper, camera and sensors are
  built;
- the table's height, since it is bolted to it;
- the rack's shape — six slots, 100 mm apart — and that it stands square to
  the table;
- what the four kinds of glass *are*, as sentences about shape: a tumbler is a
  tube, a wine glass is a bowl on a stem on a foot.

It does not know:

- the height, width, shape or weight of any glass on the table;
- which kind any of them is;
- where the rack is standing;
- where the glasses are.

The line between those two lists is the whole project. "A wine glass has a
stem below its bowl" is on the first list because it is true of every wine
glass ever made. "This wine glass is 190 mm tall and its stem is 9 mm across"
is on the second, because it is true of exactly one glass. A program that
contains that sentence has to be rewritten for the next set of glassware.

The arm may not read the simulator's own state. Everything it knows about the
glasses, it has to have measured. There is no exception to that anywhere in the
code. The world builder does write down what it spawned, but only so that the
run report can score the measurements afterwards, and nothing the arm runs ever
reads that file.

## How we tell whether it worked

Every run writes an account of itself into `runs/`: a markdown file with the
pictures the arm took beside the sentences, saying what it was about to do and
what came of it. At the end it prints both columns with the same weight —
what was racked, and what was left standing and why.

Counting racked glasses alone would be the wrong measure, because it rewards
pushing through doubt. The things worth reading are:

- how many glasses were racked, and how many were left standing;
- for each one left standing, which step gave up and what it said;
- whether the measurements matched the glasses that were really put out, which
  the report can show because the world builder writes down the truth before
  the arm sees anything;
- whether anything was knocked over or dropped, which should be nothing.

## What is out of scope

- **Real hardware.** Everything is simulated, and the notes at the end of
  [`implementation-notes.md`](implementation-notes.md) list what simulation
  will not tell us.
- **Dirty, wet or greasy glasses.** Friction is assumed constant and clean.
- **Glasses that are stacked or lying down.** They are set out standing.
  Glasses standing *close* to each other are not out of scope — that is
  problem 3.
- **Putting them anywhere but the rack**, and taking them out again.
- **More than one arm**, which is v6.

## Decisions still open

**The last few millimetres of aim.** The arm finds a glass from two pictures
taken half a metre away. The answer is out by enough that the fingers sometimes
arrive beside the glass rather than around it. A close-up look down the fingers
now corrects that just before they close, and that works. But the underlying
survey is still about 30 mm out along one axis, and it has not been established
why. Until it is, the correction is covering for an error rather
than there being no error.

**Whether some glasses are pickable at all.** The gripper's body is a 90 mm box
that comes in level. So it cannot hold a glass lower than about 50 mm without
going through the table. And a glass cannot be held above half its own height,
or it cannot be turned over afterwards. Glasses shorter than about 120 mm
therefore have nothing left in between, and the generator draws straight
glasses as short as 65 mm. Either the generator should not draw them, or the
gripper needs a slimmer body, or short glasses need picking up a different
way. Nothing has been decided.

**Whether the task should be planned as a whole.** At the moment each step is
planned when it is reached. So a choice made early — which way round to grip —
can make a later step impossible. Several of the failures recorded in the
walkthrough are exactly that. MoveIt Task Constructor is already a dependency
and is built for this, and using it would turn the sequence in `task.py` into
a tree.

**Where the arm should stand.** It is bolted to the table 400 mm in from one
edge, which puts its lower joints near the table surface and makes low reaches
tight. A fair share of the marginal planning may come back to that, and moving
or raising it is a change to the cell rather than to the code.
