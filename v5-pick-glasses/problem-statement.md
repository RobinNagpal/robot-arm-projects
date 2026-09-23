# Problem statement: pick up a glass and stand it upside down

## The idea in one paragraph

Drinking glasses stand on a table, the way they would after a meal. A robot
arm takes each one, turns it upside down, and stands it on a drying rack. It
has to do that without being told anything about the glasses beforehand — not
how tall they are, not how wide, not how heavy, not even which of them is a
wine glass and which is a tumbler. It works all of that out by looking, one
glass at a time, and if what it works out does not add up to a safe grip, it
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
to hold — and that knowledge works on a wine glass they have never seen,
because it is knowledge about the *shape*, not about any particular glass. It
has to be, because glasses do not share proportions: a 150 mm wine glass is
not a 190 mm one scaled down, since the stem is a different fraction of the
height and the bowl a different fraction of the width. So a robot given a
table of measurements works on the glasses whoever wrote the table owned, and
fails on the next set. The only thing worth storing is the sentence — hold the
narrowest part below the bowl — and the only way to use it is to measure the
glass in front of you, now.

That premise would be a small thing on its own. What makes it a project is
that a glass fights every ordinary way of measuring it.

**It is invisible to a depth camera.** Most of the light goes straight through
and the rest is bent by the curved wall, so where the glass is, the depth
picture has a hole in it. Every technique that begins "take the point cloud"
begins by not working.

**Its weight cannot be seen.** Wall thickness is invisible from outside, and
two glasses with the same outline can differ in weight by a factor of three.
Since how hard to squeeze depends on weight, the squeeze cannot be worked out
from a picture at all — it has to be corrected once the glass is in the air.

**There is usually exactly one place to hold it.** A glass is round and its
walls are rarely parallel, and flat pads on a sloping wall slide. On a wine
glass that place is the stem, a few millimetres across; on a tumbler it is a
band near the base. Finding it means finding a *feature*, not a coordinate.

**And dropping one costs more than trying again.** Broken glass leaves shards,
and an arm that carries on working moves through them. This is the thing that
shapes the whole design: anywhere else a robot may try and fail cheaply, and
here it may not, so a doubt has to end the attempt rather than be pushed
through.

## The setup

- **A table**, 1.6 m by 1.4 m, with its top 750 mm off the floor.
- **One UR5e arm**, the same arm as the earlier projects, bolted to the table
  at the middle of one long edge and 400 mm in from it. Everything happens
  within about 780 mm of its base, which is what it can reach comfortably.
- **A two-finger parallel gripper** with silicone pads, defined in this repo.
  It opens to 95 mm and the pads are 14 mm tall. The pads are not a detail:
  a rigid pad touches a curved glass at a single point, while a soft one
  spreads over a patch, and that is the difference between holding a glass and
  polishing it.
- **Three sensors**, and each one exists because a particular thing cannot be
  seen: an RGB-D camera on the wrist, a contact sensor in each pad, and a
  force sensor between the flange and the gripper.
- **The glasses**, standing on the arm's right, at least 150 mm apart so that
  the arm can get to any of them. Each run draws them fresh from four kinds —
  straight, tapered, stemmed and short-stemmed — with the proportions of each
  one drawn at random inside a plausible range. A seed picks the set, so a run
  can be repeated exactly, and no two seeds give the same glasses.
- **The drying rack**, on the arm's left: six slots 100 mm apart, each with a
  short peg to stand a glass over. Its shape is fixed and known. Where along
  the table it stands is not, and the arm finds that out by reading a printed
  marker on its base.

Everything runs in simulation, in Gazebo.

## The task, written out precisely

For each glass on the table, in turn:

1. **Find it.** Work out where it stands and roughly how wide it is, from
   above.
2. **Measure it.** Go round to the side and measure a width at every height up
   the glass.
3. **Name its shape.** Decide from that measurement which of the four kinds it
   is. Deciding "none of them" is allowed and is a real answer.
4. **Choose where to hold it**, from the rule for that kind, and how far apart
   the fingers have to be, from the width measured at that height.
5. **Pick it up and weigh it.** Lift it ten millimetres — far enough to know
   what it weighs, near enough that nothing has happened yet — and correct the
   squeeze if the estimate was wrong.
6. **Turn it over and stand it in a free slot**, lowering it until the rim
   touches rather than driving it to a calculated height.

A glass is **done** when it is standing mouth-down over a slot peg with the
fingers open and the arm clear of it. A glass is **left standing** when any
step above cannot be completed safely, and every one of those ends with a
sentence saying which step and why.

**Leaving a glass standing is a success, not a failure.** This is the rule
that most shapes the code. A run that racks four glasses and refuses one with
a reason is working correctly; a run that racks five by pushing through a
doubt is the one to worry about, and it is worth less even when nothing
breaks, because the doubt it ignored will be there next time.

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
is on the second, because it is true of exactly one glass, and a program that
contains that sentence is a program that has to be rewritten for the next set
of glassware.

The arm may not read the simulator's own state. Everything it knows about the
glasses it has to have measured, and the one place that rule is bent — making
the simulated depth camera fail on glass the way a real one does — is
described in [`docs/step1-finding-the-glasses.md`](docs/step1-finding-the-glasses.md)
and stops at the camera.

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
- **Glasses that are stacked, lying down, or touching each other.** They are
  set out standing and apart.
- **Putting them anywhere but the rack**, and taking them out again.
- **More than one arm**, which is v6.

## Decisions still open

**The last few millimetres of aim.** The arm finds a glass from two pictures
taken half a metre away, and the answer is out by enough that the fingers
sometimes arrive beside the glass rather than around it. A close-up look down
the fingers now corrects that just before they close, which works — but the
underlying survey is still about 30 mm out along one axis, and it has not been
established why. Until it is, the correction is covering for an error rather
than there being no error.

**Whether some glasses are pickable at all.** The gripper's body is a 90 mm
box that comes in level, so it cannot hold a glass lower than about 50 mm
without going through the table, and a glass cannot be held above half its own
height or it cannot be turned over. Glasses shorter than about 120 mm
therefore have nothing left in between, and the generator draws straight
glasses as short as 55 mm. Either the generator should not draw them, or the
gripper needs a slimmer body, or short glasses need picking up a different
way. Nothing has been decided.

**Whether the task should be planned as a whole.** At the moment each step is
planned when it is reached, so a choice made early — which way round to grip —
can make a later step impossible, and several of the failures recorded in the
walkthrough are exactly that. MoveIt Task Constructor is already a dependency
and is built for this, and using it would turn the sequence in `task.py` into
a tree.

**Where the arm should stand.** It is bolted to the table 400 mm in from one
edge, which puts its lower joints near the table surface and makes low reaches
tight. A fair share of the marginal planning may come back to that, and moving
or raising it is a change to the cell rather than to the code.
