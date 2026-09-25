# Solution 3 — move the camera

*Programmed, and a closed loop. Instead of working harder on the pictures you
happen to have, go and take better ones — choosing where to stand by a rule you
can print.*

## In one paragraph

A camera that can move is a different instrument from one that cannot, and this
solution treats it that way. Separating objects and finding a viewpoint are two
different difficulties: no processing of a picture in which one object stands
behind another produces the side-on outline the next step needs. So the arm
goes and stands somewhere better. Three independent tests decide where — a
clear line of sight, a standoff point inside the 300 to 780 mm reach, and a path
the arm can fly — and the first two are arithmetic, so they run before the
motion planner is asked anything. An object with no viewpoint left is not an
error. It is the handover to problem 3.

## The problem this solves

[`problem.md`](../problem.md) asks for one set of pixels per object, a place on the
table for each, and an honest list of the ones that could not be separated. The
objects in this cell are drinking glasses, but nothing in this solution depends
on that, so the word "object" is used except where the cell itself is meant.

The problem statement names two difficulties, and the point worth pressing is
that they are **two**, not one wearing two hats.

![The two difficulties](../../../images/problem-2/03-two-difficulties.png)

Read the three panels left to right. Panel 1 is the merge: a camera at survey
height sees two objects whose silhouettes overlap, and the flood fill returns
one patch. Panel 2 is the answer to that, which is
[solution 2](solution-overview.md#solution-2--cluster-on-the-table): throw the
pixels back onto the table as points, group them there, and the two objects come
apart cleanly, 150 mm from each other. Panel 3 is the difficulty panel 2 does
not touch. The camera has moved down to the side-on pose the profile
measurement needs — 380 mm back, level, 120 mm above the table — and from
there the second object is 11.0 degrees off the line of sight when two
silhouettes at that range meet at 13.8. The outline that comes back is one
shape belonging to two objects.

**Nothing you do to panel 3's picture fixes panel 3.** This is worth being
exact about, because it is the reason this solution exists as a separate thing
from solution 2.

Separating objects in a picture is a question about *labelling* — which pixel
belongs to which thing — and the information needed to answer it is sometimes
still in the picture, in the depth channel, in the shading, in the width of the
patch. Clustering on the table recovers it because the depth reading survives
the projection.

Finding a viewpoint is a question about *what was measured at all*. The
profile step reads an object's outline against the background, row by row, and
turns rows into heights. If a second object stands in the same part of the
frame, the outline it reads is the union of two objects, and no amount of
cleverness recovers where one stopped and the other started, because the
measurement was never taken. The only fix is to take a different measurement.

That is the whole argument. Separation is about interpreting a measurement;
viewpoint is about making a good one. The two barely overlap, and a cell that
answers only the first has answered half the problem.

## The idea, in plain words

If you cannot see something from where you are standing, walk round.

That is the entire intuition. The arm holds the camera on its wrist, so the
camera can be put almost anywhere within reach, pointing almost any way. A
viewpoint that hides one object behind another is an accident of where the arm
happened to be — and an accident of geometry is exactly the kind of thing an
arm can undo.

The work is in choosing *where* to walk to, and the useful surprise is that
most of the choosing is arithmetic rather than perception. The cell already
knows where every object stands and roughly how wide it is: the survey produced
that. Given a footprint circle for each object and a candidate camera position,
whether one object would land on top of another in the picture is a few lines
of trigonometry. No picture has to be taken to find out. No planner has to be
consulted. The question is settled before anything moves.

## Where it comes from

Two named ideas sit behind this, and they arrived within a few years of one
another in the 1980s.

**Active perception.** The idea that a sensor which can be moved and adjusted
is not the same instrument as a fixed one, and that the *choosing* is part of
the measurement rather than a preliminary to it. The name is R. Bajcsy's, from
*Active Perception* (Proceedings of the IEEE, 1988). The argument there is
that many vision problems which are ill-posed from one fixed viewpoint — you
cannot recover the answer, however good the maths — become well-posed once the
observer may move, because a second viewpoint supplies exactly the constraint
the first one was missing. Y. Aloimonos, I. Weiss and A. Bandyopadhyay made a
closely related argument in *Active Vision* (International Journal of Computer
Vision, 1988). Bajcsy returned to it with Aloimonos and J. Tsotsos in
*Revisiting Active Perception* (Autonomous Robots, 2018), which is the easiest
modern entry point.

The word "active" is doing a specific job here and it is often misread. It does
not mean an active sensor in the physics sense — a laser or a sonar that emits
something. It means the *observer* is active: it decides what to measure next.

**Next best view.** If the camera can move, the next question is where. The
term is C. I. Connolly's, from *The Determination of Next Best Views* (ICRA,
1985), which was about building a model of an unknown object by repeatedly
asking which viewpoint would reveal the most of what is still unknown. W. R.
Scott, G. Roth and J.-F. Rivest surveyed the field in *View Planning for
Automated Three-Dimensional Object Reconstruction and Inspection* (ACM
Computing Surveys, 2003), which is still the clearest map of the territory.

The two names describe a general capability and a specific loop. This solution
is the specific loop, cut down until it fits a cell where the doubt is a short
list of questions rather than a whole unknown world.

One point of history is worth carrying forward. Almost all of the classical
next-best-view work is about *reconstruction*: you do not know the shape, and
you want to reduce how much of it is unknown. That is a much harder question
than the one here. This cell knows the kind of object, knows roughly where each
one stands, and has one specific thing it wants — a clear side-on look at a
named object. Scoring "how much unknown volume would this resolve" is the right
tool when you know nothing. It is the wrong tool when your doubt has a name.

## How it works, step by step

### What a viewpoint has to satisfy

Three tests, and it is worth insisting that they are **independent**. They ask
different questions of different things, they can fail in any combination, and
they cost wildly different amounts to evaluate.

1. **The line of sight must be clear.** No other object may land in the same
   part of the frame as the target. Decided from the footprint circles and the
   candidate camera position. Cost: a handful of arithmetic operations per
   pair.
2. **The standoff point must be inside the arm's working reach**, which in this
   cell is 300 to 780 mm from the base, measured flat on the table. Closer than
   300 mm and the arm is folded over itself; further than 780 mm and it is
   stretched straight out with nothing left for the wrist. Cost: one square
   root. This test has a second, sharper level: an inverse-kinematics query
   asks whether the arm can hold that exact pose at all, which MoveIt 2 answers
   in milliseconds. Both levels are still far cheaper than the third test, so
   both run before it.
3. **The arm must be able to get there without crossing over something.** The
   camera rides on the wrist, so putting the camera somewhere means putting the
   whole arm somewhere, and the path may sweep an elbow across an object that
   is standing in the way. Cost: a motion planning query — orders of magnitude
   more than the other two, and the only one that can fail for reasons no
   formula predicts.

A viewpoint has to pass all three. Passing two is worth nothing.

### Occlusion is geometry, not image processing

The first test is the one people expect to be hard, and it is not, because of
one fact this problem hands over for free: **every object's footprint is a
circle of known size, standing on a known plane.**

![Occlusion as geometry](../../../images/problem-2/03-occlusion-as-geometry.png)

The left panel is the test itself. From a camera at a given point, each object
fills a certain angle of the frame. Half of that angle is `atan(r / d)`, where
`r` is the object's radius and `d` is how far away it is. Two objects share the
frame — their silhouettes touch or overlap — when the angle between their
centres, measured at the camera, is smaller than the sum of their two half
angles. That is one cross product, one dot product, and three arctangents. No
picture is involved.

Judging it as an angle at the camera, rather than as a distance from the line
of sight, matters more than it looks. An object well off to one side but twice
as far away subtends the same part of the frame as one just beside the target.
A sideways-distance test would wave it through; the angular test does not. This
is what `_blocked()` in `task.py` already computes.

Note also what the test deliberately does *not* check: whether the other object
is **nearer** than the target. It does not matter. The profile measurement
reads a silhouette against the background, so an object standing behind the
target ruins the outline exactly as thoroughly as one standing in front of it.
"Shares the frame" is the right question; "occludes" is too narrow.

The middle panel takes the same test and asks it of every direction at once.
Sit a long way `D` from a pair of objects `d` apart, at an angle `θ` off the
line joining them, and sweep round. The angle between them at your eye shrinks
like `d·sin(θ)/D`, while their combined angular width shrinks like
`(rA + rB)/D`. The distance `D` cancels. What is left is a statement about
direction alone:

    the pair overlap when   sin(θ) < (rA + rB) / d

so each neighbour casts a **wedge** of blocked directions, of half-angle
`asin((rA + rB) / d)`, along the line joining the two objects and along its
opposite. With the equal footprints of one known kind that is `asin(2r/d)`.
This is the shape people mean when they draw an occlusion shadow, and here it
has a closed form.

The right panel is why that formula is worth having. Two objects at the
closest spacing the problem allows, 150 mm, with the widest footprint the cell
handles, 105 mm, give a half-angle of 44.4 degrees. That is 89 degrees of
blocked directions — a quarter of the circle — **from one neighbour**. With
four neighbours and a reach limit as well, running out of viewpoints stops
being a freak event and becomes something to plan for.

### Bound the search before you score it

This is the structural point, and it is the part that survives even if every
other detail here is replaced.

![Bound, then score](../../../images/problem-2/03-bound-then-score.png)

Two orderings of the same work, with the counts from the five-object
arrangement used throughout this document. On the left: enumerate every
candidate, drop the ones outside the reach, drop the ones with a blocked line
of sight, score what is left, and only then call the motion planner, best
first. Forty-five candidates become twenty-five become five, and the planner is
asked at most five questions, every one of them about a pose worth flying to.

On the right: score all forty-five and let the planner sort it out. Two things
go wrong, and only one of them is obvious.

The obvious one is speed. The planner is the expensive call, and it is now
being made up to forty-five times instead of five, most of them about poses
that arithmetic could have rejected in microseconds.

The one that matters is the other one. **The planner has no opinion about lines
of sight.** It knows where the objects are — this cell puts every object into
the planning scene as a cylinder, so a path that would sweep an elbow through
one is refused — but a camera pose that looks straight through object B at
object A is a perfectly good pose as far as it is concerned. It plans to it and
reports success. The arm flies there, takes a picture with two objects in it,
measures them as one, and hands a confident wrong answer downstream. Twenty of
the forty-five candidates are like that.

So the failure mode of score-then-reject is: **slow, and quietly wrong, with
nothing erroring.** That is the worst combination available. A cell that is
slow gets noticed. A cell that is wrong gets noticed. A cell that is slow *and*
believes itself does not, until something downstream tries to grasp an object
that is two objects.

The general rule behind it: **order the tests by what they cost, cheapest
first, and let each one shrink the set the next one has to look at.** Arithmetic
is free; inverse kinematics is nearly free; the planner is not free; the arm is
the most expensive thing in the building.

There is a second benefit, and it is not obvious until you have the numbers.
Because the filter is nearly free, you can afford a much finer set of
candidates than you would otherwise dare to enumerate. That turns out to matter
a great deal, and the last section of this document is about it.

### What is left to score

Once the filter has run, whatever survives is safe to visit, and scoring only
decides the order. That bounds what a bad score can cost: one wasted move, not
a wrong measurement.

For this cell the score is a rule, not a model:

1. Prefer the viewpoint whose frame holds the doubtful object and nothing else.
   After the filter every survivor already satisfies this, so in practice the
   rule breaks ties among clear viewpoints.
2. After that, prefer the least turn away from the line back to the arm's own
   base — because standing between the object and the base is the direction
   with the least reach in it, and reach is the other thing that kills
   candidates.

The textbook alternative is **information gain**: carve the room into small
cubes marked free, occupied or unknown, cast a ray per pixel from each
candidate pose, and count how much unknown volume the picture would resolve.
[OctoMap](https://octomap.github.io/) (Hornung et al., *Autonomous Robots*,
2013) is the standard implementation of the map, and MoveIt 2 already keeps one
through its occupancy map monitor. Isler et al. (ICRA 2016) and Delmerico et
al. (*Autonomous Robots*, 2018) work through the variants. It is all CPU ray
casting, so it needs no graphics card.

It is also more than this cell needs, and the reason is the shape of the doubt.
Information gain is the right score when you do not know what you are looking
for. Here the doubt is a short list of named questions — *is that 260 mm patch
one object or two?* — and a score that answers a named question beats a score
that measures unknown volume in general.

## How it works here

### What already exists

The cell is not starting from nothing. It already runs a fixed sweep, and this
solution is the tail of that sweep rather than a replacement for it.

![The fixed sweep](../../../images/problem-2/03-the-fixed-sweep.png)

The left panel is the sweep as it stands. The camera works out from its own
lens how much table one picture covers at the 450 mm survey height — 520 by
390 mm, which is 1.62 mm per pixel — and `survey_stations()` in
`arm/dimensions.py` spreads as few stations as will cover the 320 by 360 mm
object zone with overlap to spare. For this cell that comes to three, in a line
at x = 480 mm, 93 mm apart in y. The useful part of each station is not the
whole picture but the strip both of its pictures share, 425 by 175 mm, and
93 mm between stations leaves 47 per cent of that strip in common with the
next, so nothing lands only on an edge.

The right panel is why each station is a pair rather than a single picture. One
picture from above cannot say how far away anything is; it can only lay each
silhouette down on the table, and an object stands *above* the table, so the
laid-down point is wrong. Move the camera 120 mm sideways and take a second
picture, and the top of a 260 mm object lays down 164 mm away from where it did
in the first. The ratio between those two numbers is the height, and the height
is what fixes the position.

So six pictures, from three places, before any of this solution runs. What
comes out is a position and a rough width for every object it managed to pair
up — and a list of the ones it is not sure about.

### What this solution adds

The doubtful list is the input. For each object on it:

1. Enumerate candidate standoff poses. `_standoffs()` in `task.py` already does
   this: nine directions, 40 degrees apart, centred on the line back to the
   arm's base, each one putting the camera 380 mm from the object, level,
   120 mm above the table.
2. Drop the ones whose standoff point falls outside 300 to 780 mm.
3. Drop the ones where another object would share the frame.
4. Sort the survivors, least turn first.
5. Hand them to the motion planner in that order and take the first that plans.
6. If nothing survives step 3, report the object with its reason and stop. Do
   not guess.

Where does 380 mm come from? Not from a constant. The camera looks level from
120 mm above the table, so the frame has to reach 120 mm down to catch the foot
and 140 mm up to catch the rim of the tallest object the cell allows for, which
is 260 mm. (Objects themselves run 65 to 230 mm tall; 260 is the limit the
frame is sized against, so that a tall one still fits with margin to spare.)

Both are angles, so how far back that puts the camera is a fact about the lens.
Half a frame is 120 / 277.1 = 0.4331 of a radian; 85 per cent of that is the
margin left for the arm not arriving exactly where it was sent; and
140 / (0.4331 × 0.85) comes to **380 mm**. One pixel there covers
380 / 277.1 = 1.37 mm of the object.

Two details of this cell bite, and both are easy to get wrong:

**The camera is not the tool.** It is bolted 85 mm to one side of `tool0` and
15 mm up, so that the fingers stay out of shot. Sending `tool0` to the standoff
point puts the *camera* 85 mm away from it, and the offset turns with the tool,
so it has to be subtracted in the tool's own frame. This is why
`_measure_from()` commands `eye - rotation @ CAMERA_OFFSET` rather than `eye`.

**The roll has to be pinned.** The profile is measured row by row, with a row
meaning a height. A picture that comes out rolled measures the object across
instead of up. Looking level along the table, the default "up" hint gives a
different roll depending on which side of the object the arm is standing, which
is exactly the thing that varies here.

## A worked example

Five objects in the zone, none nearer than 150 mm to another, which is the
closest the problem allows:

| | x (m) | y (m) | from the base |
| --- | --- | --- | --- |
| A | 0.40 | −0.30 | 500 mm |
| B | 0.52 | −0.39 | 650 mm |
| C | 0.32 | −0.16 | 358 mm |
| D | 0.58 | −0.14 | 597 mm |
| E | 0.64 | −0.30 | 707 mm |

A and B are 150 mm apart; B and E are 150 mm apart; nothing else is closer than
160 mm. All five footprints are taken at 105 mm, the widest the cell handles,
which is the hardest case.

Take A as the target.

![The three tests on one plan view](../../../images/problem-2/03-three-tests.png)

The ring in the left panel is every direction round A at 380 mm, coloured by
what it fails: grey where the standoff point falls outside the 300 to 780 mm
annulus, red where another object would share the picture, green where it
passes both. The nine crosses, circles and stars are the nine directions the
cell actually tries. The table on the right is the same nine written out.

Three fail on reach alone. Standing between A and the base, facing 143.1
degrees, puts the camera at (0.096, −0.072), which is **120 mm** from the base —
well inside the 300 mm minimum, so the arm would be folded over itself. The two
directions nearest the A-to-B line, at 303.1 and 343.1 degrees, both put it
**867 mm** out, past the 780 mm limit. Those three never reach the occlusion
test at all, which is the ordering working as intended: the cheapest test spends
the least and removes a third of the candidates.

Four of the six that remain are blocked. Facing 103.1 degrees, at 321 mm, both
B and C land in the frame. Facing 183.1 degrees, also 321 mm, B and E do.
Facing 223.1, D does; facing 263.1, C does.

Two survive: **63.1 degrees at 573 mm** and **23.1 degrees at 764 mm**. Sorted
by least turn, the planner is asked about 63.1 first. If it plans, the arm
flies there and takes the picture. If it does not — an elbow over B, say — the
planner is asked about 23.1. If that fails too, A has no viewpoint, and A is
reported rather than guessed at.

Nine candidates, six inside the annulus, two clear, one planner call in the
good case. Across all five objects the same arithmetic gives **45 candidates,
25 inside the annulus, 5 clear**: 20 die on reach, 20 die on occlusion, 5
survive. That 5 out of 45 is the number in the bound-then-score picture above,
and it is the whole argument for the ordering.

One footnote on the geometry. The exactly perpendicular direction to the A-to-B
line — the one you would reach for by hand — is at 53.1 degrees. It is not one
of the nine, because the nine sit on a 40-degree grid. The nearest candidate,
63.1 degrees, is 10 degrees off it and works fine. But this is the first hint
that the grid, and not the geometry, is what decides some of these cases.

## The feedback loop

This solution has a real loop, which is what distinguishes it from
[solution 1](solution-overview.md#solution-1--split-the-blob-in-the-picture)
and [solution 2](solution-overview.md#solution-2--cluster-on-the-table). It
takes a measurement, works out what is still unclear, decides where it would
have to look for that to become clear, goes and looks, and repeats.

A loop needs three things, and a solution with only two of them is not a loop:

**Something to be unsure about.** The circle fit from solution 2 provides it. A
cluster whose fitted footprint is wider than any single object of this kind can
be, or an object seen from only one station, is doubtful. An object whose
circle fits inside the allowed range is settled and gets no extra look.

**Somewhere to go that would help.** The candidate poses, filtered by the three
tests. If the filter returns nothing, there is no action that would help, and
that fact is itself the answer.

**A budget**, because the loop has to stop.

![The budget](../../../images/problem-2/03-the-budget.png)

The unit on the left panel's axis is a **station-equivalent**: one plan, one
move, one settle, and the two pictures 120 mm apart that the parallax needs.
That is about what one more survey station costs, which makes it the natural
unit here and saves inventing a number for the move itself. The sweep is three
of them. An extra look is one more.

What a unit actually costs in seconds is the one number that has to be measured
rather than argued about, and it should be timed from `_survey()` rather than
guessed in a document. The right panel says why it does not much matter which
of the plausible values it turns out to be. The ceiling is "tens of seconds" —
call it 60 for the sake of drawing a line. If a unit costs 4 seconds, 60
seconds buys 15 units. At 6 seconds it buys 10. At 8 seconds, 7.5.

Against that:

- the sweep alone is **3 units**, and fits under every one of those;
- the sweep plus a cap of **four extra looks is 7 units**, a little over twice
  the survey on its own, and still under every one of them;
- six extra looks is **9 units**, which fits at 4 or 6 seconds a unit and
  breaks the ceiling at 8;
- two looks for each of five objects is **13 units**, which breaks it at
  every value.

So the cap is four. Not because four is a nice number, but because four is the
largest budget that fits whatever a unit turns out to cost. Six would be a bet
on the measurement coming out at the cheap end, and there is a reason not to
place it: the objects that most want a second look tend to be the crowded ones,
and crowding is exactly what removes their viewpoints — so the extra budget is
the part most likely to be spent on looks that get refused.

Alongside the run-wide cap of four goes a per-object cap of **two**. One object
must not be able to eat the whole budget. Without that, a single stubborn
cluster pulls look after look and the run never ends — and the reason a cluster
is stubborn is usually that its neighbours are where they are, which no number
of looks will change.

The loop stops when nothing is doubtful, or when the budget is spent. Whatever
is still doubtful at that point is **reported as doubtful**, not guessed at. A
report that says "these two could not be separated, here is why" is a result.
A report that guesses is a failure that looks like a result.

One number is worth logging from the start: **how many extra looks were spent,
and how many changed the answer.** A loop whose extra looks never change
anything is a loop worth deleting, and you will not know which you have until
you count.

## What it needs

**Libraries.** Nothing that is not already in the cell.

- [ROS 2 Jazzy](https://docs.ros.org/en/jazzy/) — Apache License 2.0. The
  plumbing.
- [MoveIt 2](https://moveit.ai/) ([source](https://github.com/moveit/moveit2))
  — BSD 3-Clause. Two parts are used: an inverse-kinematics query, to ask
  whether a pose can be held at all, which is milliseconds; and the motion
  planner, which is the expensive call. It also keeps the planning scene the
  objects go into as cylinders.
- [Gazebo](https://gazebosim.org/) (Harmonic) — Apache License 2.0. The
  simulator.
- [NumPy](https://numpy.org/) — BSD 3-Clause. The three tests are a few dozen
  lines of it.

If the score were ever upgraded to information gain, that would add
[OctoMap](https://octomap.github.io/)
([source](https://github.com/OctoMap/octomap)) — the mapping library is under a
BSD licence; the `octovis` viewer that ships beside it is GPL, so check which
you are linking. Bircher et al.'s receding-horizon next-best-view planner
([source](https://github.com/ethz-asl/nbvplanner), ICRA 2016) is the
open-source exploration planner people usually start from; its licence is
uncertain — read the repository before depending on it.

**Data.** None. There is nothing to train and no weights to keep in step with
the world. Every number in this document comes out of the cell's own
dimensions.

**Hardware.** The depth camera and the arm. No graphics card. Everything here
runs on an Apple Silicon Mac with no NVIDIA card, which is the rule the whole
overview is written under.

**A belief to start from**, which is the one real prerequisite and the one
chicken-and-egg problem. You cannot predict what a viewpoint would show without
knowing roughly what is on the table, and knowing what is on the table is the
job. The way out here is that the fixed sweep already supplies it. The sweep
assumes nothing, covers the zone, and hands back a coarse map; this solution
runs on the doubtful entries in that map only. It is the tail of the survey, not
a replacement for it.

(The other way out is to score unknown volume rather than named objects, which
works from nothing because at the start everything is unknown. That is what
exploration planners do. It is the right answer when there is no opening sweep
to build on. Here there is one, so it is not needed.)

**Time.** Seconds of arm motion per extra look, capped at four per run.
Microseconds of arithmetic per candidate. The arithmetic is free and the arm is
not, which is the whole reason the ordering is what it is.

## What it is good at

**Merges caused by where the camera happened to be** — which is most of them.
A merge of this kind is an accident of geometry, and geometry is the one thing
an arm can change. Changing it costs seconds and no risk.

**Being auditable.** When the cell says an object had no viewpoint, it can say
exactly which of three tests each of nine candidates failed, with the numbers.
Nothing in this solution is unexplainable, and nothing about it changes between
runs. That makes it the baseline against which any learned viewpoint chooser
has to justify itself.

**Degrading honestly.** Every path out of this solution is either a measurement
or a named reason for not taking one. There is no branch in which it invents an
answer.

**Costing nothing when it is not needed.** On a table where every object has a
clear line of sight, the filter passes everything, the loop fires zero times,
and the run is exactly the fixed sweep.

## What it is bad at

**It spends the most expensive resource in the cell.** Every extra look is
seconds of arm time to buy certainty, and the budget section exists because
that runs out fast. Six objects each wanting two confirming looks is twelve
extra stations, which is four times the survey and well over the ceiling this
cell has to stay under.

**It is heavier than the problem strictly needs.** A bounded search with a
fixed scoring rule — steps 1 to 4 above, with no loop at all — gets most of the
benefit. The loop earns its place only when there is a measure of doubt good
enough to fire it selectively, which is why
[solution 5](solution-overview.md#solution-5--a-learned-verifier-over-the-clusters)
is the natural thing to add next.

**Its belief can be wrong in a way its score cannot see.** Occlusion is
predicted from footprint circles that the survey produced. If the survey merged
two objects into one wide circle, the prediction is made from a fiction: the
loop picks a viewpoint it believes is clear and finds it is not. The check is
cheap — take the picture and see whether more than one object is standing up in
it — but the first attempt is wasted.

**It assumes the depth reading works.** Everything here starts from positions
and widths that came out of a depth camera. On real glassware, which a depth
camera reads badly or not at all, there is no belief to reason about. That is a
statement about this whole family of solutions, not about this one.

## How it fails

**No candidate survives the filter.** The interesting failure, and not really a
failure.

![No usable viewpoint](../../../images/problem-2/03-no-viewpoint.png)

The left panel is object E from the worked example. Four of its nine directions
fall outside the annulus, five are blocked, and none survives — so on the grid
the cell uses, E is handed to problem 3. But look at the ring: there is a 10
degree stretch of green on it, and the nine directions, sitting 40 degrees
apart, step straight over it. **E is stranded by the grid, not by the
geometry.**

That is not an isolated accident. The clear arcs for the five objects in this
arrangement come to A 34 degrees, B 16, C 110, D 7 and E 10. With nine
directions 40 degrees apart, the only arc *guaranteed* to be hit is C's. The
others are hit or missed depending on where the grid happens to fall.

The fix is free, and it is the second benefit of bounding before scoring. The
filter is arithmetic, so the candidate set can be made as fine as you like:
seventeen directions, thirty-three, sixty-five. The right panel counts how much
that buys, over 600 arrangements of four to six objects drawn in the zone at the
problem's own spacing rule. With 105 mm footprints, going from 9 directions to
65 takes the share of objects with no usable viewpoint from 45 per cent to 14.
With 75 mm footprints it goes from 18 per cent to 1. With 45 mm footprints the
problem has essentially vanished by 17 directions.

Two things follow. First, **most of the 45 per cent is the grid, and refining
the grid costs nothing but arithmetic** — this is the single cheapest
improvement available in this solution, and it should be the first thing done.
Second, it never reaches zero, and the middle panel is why. There, object S
stands 556 mm out with four neighbours round it, and its ring has **no clear
direction at all**, at any resolution. No grid helps. Something has to move.

That is the handover to [problem 3](../../problem-3/problem.md), and it is a
result rather than an error. The right output is the object, the reason, and a
stop — never an attempt made anyway. This is the same rule the project
runs on: a refused object is a result, and a fallback that has the arm try
regardless is how neighbours get knocked over.

**The planner refuses everything that survived.** Rarer, because a pose that is
in reach and clear is usually plannable, but it happens when the arm is boxed in
by its own current configuration. Same outcome: report it, hand it on.

**It thrashes.** Without the per-object cap, one doubtful cluster pulls look
after look and the run never ends. The cap is not an optimisation; it is what
makes the loop terminate.

**The belief is wrong where the score cannot see it.** Covered above: a merged
pair modelled as one wide circle predicts its own occlusions wrongly.

**Real glassware removes the belief.** A depth camera reads clear glass badly.
Everything here starts from depth, so on real glassware there is nothing to
start from. This is the condition the whole overview is honest about.

## When it would be the right choice

When scoring a viewpoint is cheap next to moving to it, and the doubt has a
name.

Both halves matter. If scoring were expensive — a learned model over a big
candidate set, say — the case for enumerating finely would weaken, and the
arithmetic filter would stop being free. If the doubt had no name — an unknown
scene, unknown object kinds — a rule that says "prefer the frame holding the
doubtful object and nothing else" would have nothing to work with, and a
volumetric information-gain score would earn its weight instead. That is
exactly what happens at [problem 4](../../problem-4/problem.md), where several
unknown kinds mean the doubt stops being a short list.

Here, both halves hold. The concrete recommendation is to build it in two
pieces, because the first is worth more than the second:

1. **The filter, with a fine candidate set.** Reject unreachable and blocked
   poses before asking the planner anything, and report objects with no
   viewpoint left. No loop. This is pure safety and pure speed, it is about
   twenty lines on top of what already exists, and the rate curve above says
   the fine grid alone takes a large bite out of the handovers to problem 3.
2. **The extra look**, with a rule for the score and a budget of two per object
   and four per run. Only once the first piece is running and the report says
   how often a doubtful cluster actually appears.

## The general methods behind this

This solution is an instance of a named research programme, not a trick. The
idea that a camera should be *moved on purpose* rather than read passively has
forty years of literature behind it, and the pieces below are the standard
vocabulary.

### Active perception — treating the sensor's pose as something to choose

Classical vision takes a picture as given and asks what can be recovered from
it. **Active perception** (Bajcsy, *Proceedings of the IEEE*, 1988) and **active
vision** (Aloimonos, Weiss and Bandyopadhyay, *IJCV*, 1988) reframe it: the
observer controls the sensor, so the question becomes *where should I look
next?* Problems that are ill-posed from one viewpoint frequently become
well-posed from two.

- **Mostly used for** robots with the sensor on a movable body — arms, mobile
  bases, drones, pan-tilt heads — and for inspection, where an object must be
  checked from several sides anyway.
- **Rarely right for** fixed installations where moving is impossible or slow
  relative to the value of the answer: a conveyor line at speed, a static
  security camera, or any case where an extra viewpoint costs more than being
  wrong occasionally.
- **More:** [active perception](https://en.wikipedia.org/wiki/Active_perception).

### Next-best-view planning — scoring candidate viewpoints before visiting them

Generate candidate poses, predict what each would reveal, take the best, repeat
until the gain stops being worth the move. The first formulation is Connolly's
*The Determination of Next Best Views* (ICRA, 1985), and the field has run on
variations of it since.

- **Mostly used for** 3D reconstruction and inspection, where coverage is the
  goal and the object is unknown — scanning a part, mapping a room, exploring
  with a drone.
- **Rarely right for** scenes small and known enough that a fixed sweep covers
  everything anyway. Planning a viewpoint costs thought; visiting three fixed
  ones may cost less. *This cell sits on that line*, which is why the score here
  is a printed rule rather than an information-theoretic objective.
- **More:** [nbvplanner](https://github.com/ethz-asl/nbvplanner), a
  receding-horizon implementation for aerial exploration.

### Occupancy mapping and ray casting — reasoning about what is hidden

Divide space into cells, mark each as free, occupied or unknown, and trace rays
from a candidate camera to see which unknown cells it would resolve. **OctoMap**
(Hornung et al., *Autonomous Robots*, 2013) is the standard implementation, a
probabilistic octree that keeps the memory tolerable.

- **Mostly used for** mobile robots and drones, where "what have I not seen yet"
  is the whole task, and as the substrate under most next-best-view scoring.
- **Rarely right for** a small scene of a few known objects, where a handful of
  geometric tests answer the same question exactly and far more cheaply. A
  5 mm grid over this cell's zone is about three million cells to decide what
  five circle-versus-wedge tests already settle.
- **More:** [occupancy grid mapping](https://en.wikipedia.org/wiki/Occupancy_grid_mapping);
  [OctoMap](https://octomap.github.io/).

### Bounding a search by feasibility before scoring it

Not a vision method but a structural pattern, and the one most often got wrong:
put the hard constraints *inside* the search rather than filtering afterwards.
Generating viewpoints, ranking them by how much they would reveal, and only then
discovering the arm cannot reach them is how a cell becomes slow and unreliable
with nothing ever erroring.

- **Mostly used for** any pipeline where candidates are cheap to generate and
  expensive to execute: grasp planning, motion planning, view planning.
- **Rarely wrong**, which is why it is worth stating. The only cost is that the
  feasibility test must itself be cheap — here inverse kinematics at
  milliseconds, before the motion planner at tens of milliseconds.

## Where it sits

This solution answers a different difficulty from **cluster on the table**, and
the two are chosen together for exactly that reason: clustering separates
objects that a picture merged, and moving the camera gets a picture worth
measuring in the first place. Neither substitutes for the other, and **split
the blob in the picture** substitutes for neither.

It is also the baseline for three solutions that replace only its score.
**Learned doubt steers the next picture** puts a learned estimate of
uncertainty where the "which cluster is doubtful" rule sits. **Learn which
viewpoints pay off** puts a learned prediction where the "which viewpoint is
best" rule sits. **A learned verifier over the clusters** supplies a better
measure of doubt to fire the loop with, and is the first of the three worth
adding. All three inherit the filter unchanged, because the filter is what
keeps a wrong score cheap — the worst a bad ordering can do is waste one move,
and that is true only because every candidate it ranks has already passed all
three tests.

---

← [The problem](../problem.md) · [Solution overview](solution-overview.md) ·
[Problem 3 — moving them apart](../../problem-3) →
