# Problem 3 — how it would be solved

[`problem.md`](../problem.md) says what is being asked for. This document says how
it would be answered. It is long, because the point of it is to compare five
ways of doing the job properly rather than to announce one.

## Where we are

Problem 2 has finished. The arm knows which pixels are which glass and where
each one stands on the table. Some of those glasses are standing too close
together for the gripper to get round one without fouling its neighbour.

They have to be moved apart. Not by picking them up — **by dragging them across
the table.**

## Why dragging, and not lifting

This is worth restating, because the whole document rests on it.

To lift a glass, the fingers have to close on it in a chosen place. To choose
that place, the arm needs the glass's profile. To measure the profile, it needs
a side-on photograph from 380 mm away. To take that photograph, it needs a
viewpoint that is not blocked — which is exactly what the crowding has taken
away.

So lifting depends on measuring, measuring depends on seeing, and seeing is what
is broken. A push breaks the circle because it needs almost nothing: a position
and a base width, both of which problem 2 already produced. It does not need the
glass's height, its shape, its weight, or where its stem is.

## The words, first

Six terms, used throughout.

A **push** here means moving a glass across the table with the closed gripper,
in contact the whole way. **Dragging** and **pushing** are used
interchangeably.

**Singulation** is the name the robotics literature gives to this job:
separating objects that are touching or crowded so that they can be picked up
one at a time. It is worth knowing the word, because it is what to search for.

**Quasi-static** describes a push slow enough that momentum does not matter.
Let go of a glass mid-push and it stops rather than sliding on. Everything in
this document assumes it, and at the speed an arm pushes it is true.

The **friction cone** is the set of directions in which a finger can push a
surface without sliding across it. Push within the cone and the finger grips
and the object moves. Push outside it and the finger skids across the glass.

![The two things contact mechanics decides about a push](../../../images/problem-3-friction-cone.png)

The **centre of the footprint** is where the glass's circular base sits on the
table. A push whose line passes through it slides the glass roughly straight. A
push that misses it spins the glass as well as moving it.

**Toppling** is the failure that cannot be undone. A pushed object slides while
the contact height is below `a / μ` — half the base width over the friction with
the table — and tips above it. Everything here has to stay below that line.

## Three families, and what "hybrid" means

Every solution below belongs to one of three families. The difference is worth
setting out before the list, because it is not quite the difference most people
expect.

**Programmed.** You state the rule and the computer applies it. No training
data, no model file, no graphics card. It runs in about a millisecond, it works
on an object it has never seen, and when it fails you can usually find out why
by printing one number. Its limit is that somebody has to be able to write the
rule down, and for some questions nobody can.

**Learned.** The behaviour comes from numbers fitted to examples rather than
from a rule anybody wrote. It can do things nobody knows how to state — telling
one object from another in a cluttered photograph, for instance. It pays for
that with a training set, a file of weights that has to be kept in step with
the world, hardware to run it on, and an answer that cannot explain itself.

**Hybrid.** Both, arranged so that the learned part sits inside something
checkable.

The interesting question about a hybrid is not how much of it is learned. It is
**where the learned part sits**, because that is what decides what happens when
the model is wrong — and a model is wrong sometimes, by construction.

![Where the learned part sits decides what happens when it is wrong](../../../images/where-the-learned-part-sits.png)

There are four positions, and only the first is what most people picture when
they hear "we used a model".

**As the decider.** The model takes the input and its answer is the answer. A
wrong answer is acted on, because nothing downstream is in a position to
disagree.

**As a proposer.** The rules find candidates and hand the hard ones to the
model; the model suggests something better; the rules then check the
suggestion. A wrong suggestion is rejected by arithmetic, and the system falls
back to what it had.

**As a ranker.** The rules generate every candidate *and* veto the unsafe ones.
The model only puts the survivors in order. A bad ordering costs one wasted
attempt. It cannot cost anything worse, because every candidate had already
passed the safety checks before the model saw it.

**As a verifier.** The rules act, and the model's job is to check what actually
happened. A wrong check costs one extra measurement.

The last three share a property worth naming, because it is the whole argument
for hybrids in a physical system: **the learned part's mistakes are bounded by
something that does not need the model to be right.** That is not a statement
about model quality. A better model narrows the failures; only the arrangement
caps them.

One practical consequence is worth having in mind while reading. A hybrid is
usually *cheaper* than a full learned solution, not more expensive, because the
learned piece has one narrow job. Learning "is this one object or two, given
this crop" needs a fraction of the data of learning "find all the objects", and
it trains on a laptop.

## Feedback: choosing what to measure next

The second theme running through what follows is that **the number of
measurements does not have to be decided in advance.**

![Deciding what to measure next, rather than measuring once](../../../images/open-and-closed-loop.png)

Most pipelines are open loop. Take the pictures, work everything out, act. The
number of pictures is fixed before the run starts, so if one object turns out
to be unclear, unclear is how it stays. Everything downstream inherits the
doubt without being told there was one.

A closed loop spends its measurements where they are needed. It takes a
picture, works out what is settled and what is not, and if something is not, it
asks a different question: *where would I have to look for this to become
clear?* Then it goes and looks there, and repeats.

Three things are needed to make that work, and a solution that has only two of
them is not really a loop:

1. **A measure of doubt.** Something that distinguishes "settled" from "not
   sure", rather than always producing an answer. A method that cannot be
   unsure has nothing to drive the loop with.
2. **Actions that could reduce it.** A set of measurements the arm could
   actually take — reachable camera poses, a touch, a different angle — and
   some way of guessing which would help.
3. **A budget.** Every extra look costs arm time, which is by far the most
   expensive resource here. Moving the camera and letting it settle costs
   seconds; running any of the models below costs milliseconds. So the loop has
   to stop, and the sensible rule is to stop when nothing is unclear *or* the
   budget is spent, reporting whatever is still doubtful rather than guessing
   at it.

That third point reverses an instinct most developers bring with them. The
thing to economise on is not computation. It is the number of times the arm has
to move.

## Everything here runs in simulation

One rule has been applied to every solution below, and it is worth stating
before the list because it removed some obvious candidates.

**A solution is in this document only if everything it needs can be produced by
Gazebo on the machine this project runs on** — an Apple Silicon Mac with no
NVIDIA graphics card, no robot on a bench, and no real-world data. Four
conditions:

1. **No artefact from outside.** Any model has to be trainable from what the
   simulator renders. A downloaded file of weights fitted to photographs of the
   real world is not reproducible here, however good it is.
2. **No sensor the simulator does not have.** This cell has a depth camera, pad
   contact sensors and a wrist force-torque sensor. Anything else is a purchase
   order.
3. **No graphics card it has not got.** Anything needing compiled CUDA kernels
   is out.
4. **Hours, not days.** A method needing a week of continuous simulation to
   train cannot be iterated on, and a method you cannot iterate on will not get
   debugged.

That rule is not a view about learned methods. Several good answers fail it,
and they are written up in full in
[`learned-with-hardware.md`](learned-with-hardware.md) beside the condition
each one fails — a promptable foundation model, a fine-tuned instance
segmenter, and the rest. None of them needs a different *algorithm* to become
usable. They need a different *setup*.

The rule does have one consequence worth seeing coming. It pushes the learned
solutions towards **small models trained from scratch on synthetic data**, and
away from the fine-tune-a-big-model recipe that is the default advice
everywhere else. For a cell that handles one kind of object, under one lighting
setup, through one camera, that turns out to be less of a sacrifice than it
sounds — and the sections below say where it does cost something.

## The eleven solutions, at a glance

Four programmed, four hybrid, three learned — and every one of them buildable
inside the simulator.

| | Solution | Family | Where the learned part sits | Closed loop? | Verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | [Do not drag at all](#solution-1--do-not-drag-at-all) | programmed | — | **yes** | **chosen — try this first** |
| 2 | [One fixed nudge](#solution-2--one-fixed-nudge) | programmed | — | no | the right baseline |
| 3 | [Plan, feel, look again](#solution-3--plan-the-destination-feel-for-the-glass-look-again) | programmed | — | **yes** | **chosen — the core** |
| 4 | [Predict the slide](#solution-4--predict-the-slide-with-pushing-mechanics) | programmed | — | no | correct theory, missing inputs |
| 5 | [A learned residual on the push model](#solution-5--a-learned-residual-on-the-push-model) | hybrid | proposer | **yes** | trains itself as it runs |
| 6 | [Geometry generates, a model ranks](#solution-6--geometry-generates-a-model-ranks) | hybrid | ranker | partly | safe, and worth little here |
| 7 | [A learned change-verifier](#solution-7--a-learned-change-verifier) | hybrid | verifier | **yes** | **the first learned thing worth adding** |
| 8 | [A learned early-abort](#solution-8--a-learned-early-abort) | hybrid | verifier, during the act | **yes** | the only one that can *prevent* a topple |
| 9 | [Identify the contact parameters](#solution-9--identify-the-contact-parameters) | learned | proposer | **yes** | gives the physics its missing number |
| 10 | [Learn a forward model, then plan](#solution-10--learn-a-forward-model-then-plan-against-it) | learned | decider | **yes** | the best of the three learned ones |
| 11 | [Search a push strategy](#solution-11--search-a-push-strategy) | learned | decider | partly | hours, where reinforcement learning wants days |

Every one is written to the same plan. What it is. Why anyone does it that way.
How it would work in this cell. **The feedback loop**, if it has one. A worked
example with real numbers. What it needs. What it is good and bad at. How it
fails. And when it would be the right choice.

---

## Solution 1 — do not drag at all

*Programmed, and a loop of a simple kind. Question the premise first. Every
object racked is an object removed from the table, so the crowding thins by
itself. Take the ones already reachable, look again, and only drag what is
left.*

### What it is

Every other answer here accepts the premise of problem 3: the glasses are too
close, so the arm shoves them apart. This one questions it, on one observation.

**A glass that has been picked up and racked is gone from the table.** The rack
is on the far side of the arm, and a glass standing in it is nobody's neighbour
any more. So the table never gets more crowded than it started. Every pick makes
it less crowded.

Some of the crowding therefore clears itself, and the method is to wait for it.
Find a glass that *already* has the room the gripper needs and a viewpoint the
camera can use. Pick it, rack it, look again. Repeat until the table is empty or
no glass qualifies. Only then is there anything to drag. Call it **peeling from
the outside**: take the ones at the edge, and the crowd shrinks inwards.

### Why anyone does it this way

When several things have to come out of a shared space, the *order* can decide
whether the job is possible at all. Getting a car off a full drive is the same
problem.

In manipulation the idea goes under names like **accessibility ordering** or
**reachability ordering**: take whatever is reachable now, and let the reachable
set grow as things leave. I am not sure either is *the* standard name, so treat
both as descriptions. The family is better established — rearrangement problems,
where feasibility depends on the sequence alone.

### How it would work here

The test runs on what problem 2 already produced: a position and a rough
footprint width per glass. The jaw needs about **70 mm of clear room measured out
from the glass's middle** in the direction it comes in — clear of *material*, not
of a middle. So a neighbour `n` is in the way of a target `t` when

    distance(t, n)  <  70 mm + (footprint of n) / 2

Footprints run 45 to 105 mm, so the threshold runs from 92.5 mm for the
narrowest neighbour to 122.5 mm for the widest. Two average glasses give the
**140 mm between middles** in [`problem.md`](../problem.md), the symmetric case of
70 mm each.

**The formula is not symmetric.** A narrow glass beside a wide one is crowded
long before the wide one is. That asymmetry is the engine of the method, and it
is invisible if you only use 140 mm. Sightlines are not symmetric either: a glass
blocks the view of what is behind it, not in front.

So a glass qualifies when no remaining neighbour is in the way, a rack slot is
free, and one viewpoint 380 mm back is clear. Pick it, rack it, drop it from the
list, recompute.

### A worked example

Five glasses, millimetres from the arm's base, inside the 320 x 360 mm zone and
the 300 to 780 mm reach, footprints from the 45–105 mm range.

| Glass | Position | Footprint |
| --- | --- | --- |
| A | (330, −110) | 70 mm |
| B | (630, −110) | 80 mm |
| C | (330, −410) | 60 mm |
| D | (630, −410) | 105 mm |
| E | (530, −410) | 45 mm |

Every pair except D–E is at least 200 mm apart, clearing even the 122.5 mm
threshold. A, B and C qualify at once. D and E are 100 mm apart: the crowded pair.

**Racking A, B and C does nothing for D and E.** That is forced, not bad luck.
They were never in D or E's way — had they been, they would have been in each
other's way in turn, and would not have qualified. Their removal changes only the
line of sight. Now the pair on its own terms.

- D needs 70 + 45/2 = **92.5 mm** from E. It has 100. **D qualifies.**
- E needs 70 + 105/2 = **122.5 mm** from D. It has 100. **E does not.**

So D is racked. E is then alone, crowded by nothing, and goes too. No drag at
all.

Change one number and it ends differently. Make both glasses 75 mm across. Each
now needs 107.5 mm, both have 100, and **neither qualifies** — with A, B and C
already racked and nothing left whose removal would help.

### What it needs

Nothing the cell lacks: the survey and footprints from problem 2, the rack slot
bookkeeping that already exists, and a loop.

### What it is good at

It is free. No push means no toppling, no guessed friction, no glass shoved into
a third glass or out of reach, and no glass that tips before it slides. Every
failure mode of problem 3 is skipped for every glass that qualifies, and a glass
is only touched after its room has been checked.

### What it is bad at

**More surveys.** One survey at the start becomes one per pick, up to five. Each
is arm motion and camera frames, and the arm has to stand somewhere that does not
block its own camera. That cost is paid on every run, including the ones where no
drag was ever needed.

### How it fails

One condition, exactly: **a crowded pair with nothing else left to do.** Two
glasses inside each other's threshold, everything else racked, no third glass
whose removal could help. The recompute returns the same answer forever. A loop
that does not notice this spins; one that does reports a stall. The second case
above is that failure, and two equal glasses 100 mm apart is ordinary, not
contrived.

### When it would be the right choice

Always, and never alone. This is not an alternative to dragging. It is a
**prefix** to it. Peel first, take every glass already free, hand the residue to
the pushing logic. The residue is smaller, sometimes empty, and the pushes left
have more free table to aim into. Dragging is strictly easier after a peel than
before one, so there is no case for doing it first. The change is to sequencing
in `task.py`: survey, pick what qualifies, then decide what still needs moving.

---

## Solution 2 — one fixed nudge

*Programmed. For a pair that is too close, push one of them a computed
distance directly away from the other. The simplest thing that could work.*

### What it is

Take a pair of glasses that are too close. Draw the line joining their two
middles. Pick one of the two and push it along that line, away from the other,
by a distance worked out from the 140 mm figure. Then stop and look.

That is the whole method: no destination search, no map of the free table, no
score. A *middle* is the centre of the circle a glass stands on, and problem 2
gives a middle and a footprint width for every glass, so the nudge needs nothing
new from perception.

### Why anyone does it this way

The hard part of problem 3 is not choosing where a glass should go. It is
touching one at all without knocking it over: getting low enough that it slides
rather than tips, finding its wall when the camera's idea of it carries error,
and moving slowly enough that contact is a press and not a knock. A fixed nudge
exercises all of that in Gazebo Harmonic, and is simple enough that when a glass
falls over you know it was the contact and not the plan. It also gives the
cleverer methods a number to beat.

### How it would work here

**Which of the pair to move.** A pushed glass slides while the contact height
`h` stays below `a / μ`, where `a` is half its base width and `μ` its friction
with the table. The gripper body is a 90 mm box and cannot go below about 50 mm
above the table, so `h` is 50 mm and fixed. The wider base has the larger `a`,
so the most room under that limit. Push that one.

**How far.** Two glasses need 140 mm between their middles before the jaw fits
round either, so if the measured distance is `d`, the shortfall is `140 − d`.
That alone lands the pair exactly on the line, and a push never lands where it
was aimed, so add 20 mm:

    nudge = 140 − d + 20

**What the gripper does.** Close the fingers: a closed jaw is one stiff object
of known shape, where an open jaw is two thin fingers that catch on a rim. Drop
to 50 mm above the table, behind the glass on the push line. Creep forward in
2 mm steps until something fires — the pad contact sensors, or a sideways
reading at the wrist, which feels 9.5 N of gripper weight and nothing horizontal
until the pad meets glass. Push from there, slowly, in a straight line, with
`compute_cartesian_path` in MoveIt 2. Retreat backwards along that line before
lifting; lifting with the pad still against the wall drags it up the glass.

**Why feel forward rather than drive to a number.** The wall sits at the middle
minus half the footprint width, and both were measured, so the errors add. Drive
to that point and you either stop short and push air, or arrive past it at
speed, which is the knock. Creeping until a sensor fires is a guarded move, and
where it fired beats what the camera gave.

### A worked example

Three glasses, millimetres from the arm's base, all inside the 300 to 780 mm
reach.

| Glass | Position | Footprint |
| --- | --- | --- |
| P | (380, −380) | 90 mm |
| Q | (460, −320) | 90 mm |
| R | (560, −220) | 90 mm |

P to Q: dx = 80, dy = 60, so d = √(80² + 60²) = 100 mm. Under 140: crowded. The
unit vector from P towards Q is (0.8, 0.6), and the nudge is
140 − 100 + 20 = 60 mm.

Can Q be pushed? `a / μ` = 45 / 0.5 = 90 mm even on a pessimistic μ of 0.5, well
above the 50 mm the gripper is stuck at, so Q slides rather than tips. A 45 mm
footprint would give 45 mm and be refused.

Push Q 60 mm along (0.8, 0.6) — +48 in x, +36 in y — to (508, −284). New P–Q
distance: √(128² + 96²) = √25600 = 160 mm. Over 140. Fixed.

Now R. Before the push, Q was √(100² + 100²) = 141.4 mm from R, just over the
line; after it, √(52² + 64²) = 82.5 mm. The nudge fixed one pair and broke
another, worse. Push P instead, 60 mm along (−0.8, −0.6), to (332, −416):
160 mm from Q, 301 mm from R.

### What it needs

Middles and footprint widths from problem 2. A guessed μ. The 140 mm figure.
MoveIt 2 for the straight line, ros2_control for the pad sensors and the wrist
force broadcaster, and fresh overhead pictures after each push.

### What it is good at

A few dozen lines, running the whole contact sequence, so it finds the contact
faults early and cheaply. On two or three glasses that are merely close rather
than piled it is often simply correct. And the shortest push that works is the
safest, because every millimetre of travel is another millimetre in which
something can topple.

### What it is bad at

It sees two glasses and ignores the rest of the table — the zone's edges, the
rack, the arm's reach — so it will happily aim a glass off the table. It uses
the blunt symmetric 140 mm rather than the asymmetric threshold, so it over-
pushes narrow glasses and under-pushes wide ones. And its distance is the
minimum plus a margin, leaving the pair right on the line.

### How it fails

The headline failure is the one in the worked example: the nudge pushes one
glass into a third. Four guards, all arithmetic on numbers already in hand:

1. the destination at least 140 mm from every other middle;
2. the corridor the glass sweeps, and the wider one the 90 mm gripper body
   sweeps behind it, clear of every other glass;
3. the destination inside the zone, and 300 to 780 mm from the base;
4. if neither direction passes, refuse the pair and say why.

The first three ask whether one spot is clear, legal and reachable — most of
what solution 3 does, minus the search. The fully guarded baseline has grown
into the method that replaces it, which is an argument for that method, not
against the baseline.

Pushes are also not independent. Fixing P–Q can break Q–R, and fixing Q–R can
break P–Q again. Nothing notices the cycle, so it needs a cap: eight pushes,
after which the run refuses.

**How many pushes for five.** Three or four of a tight crowd of five have to
move, so three or four pushes is the floor. There is no ceiling from geometry,
because each nudge can create a pair it never considered. Five is near the limit
of the table anyway: the roomiest arrangement that fits is four in a 180 by
220 mm rectangle with one in the middle, √(90² + 110²) = 142 mm from each
corner. That is 2 mm of slack across the zone, and nudging by the minimum will
not find it.

### When it would be the right choice

It is genuinely sufficient when the crowd is small and the table is not. Two or
three glasses, one crowded pair, clear table all round: the nudge solves that on
the first push, and a planner would choose almost the same one. It is also the
right thing to build first — the cheapest way to get a real push happening
against a simulated glass, and afterwards the thing the cleverer methods are
scored against.

It stops being sufficient once the table is crowded rather than merely occupied:
four or five glasses, or a glass near the rack or the edge of the reach. There,
where a glass should go is no longer obvious from its nearest neighbour, and
something has to look at the whole table.

---

## Solution 3 — plan the destination, feel for the glass, look again

*Programmed, and the core loop. Choose a landing spot by checking it against
the whole table. Feel for the object on the way in rather than driving to it.
Push once, then look again and compare.*

![Choosing where to push a glass to](../../../images/problem-3-choosing-a-destination.png)

### What it is

Three ideas joined together, and none of them is clever on its own.

**Plan where the glass should end up**, by treating the table as a map with
obstacles on it and looking for a clear spot. **Feel for the glass** on the way
in, rather than driving to where the camera said it was. **Push once, then look
again**, and compare what happened with what was intended.

The third is the one that carries the weight. This method does not try to
predict where a pushed glass will end up. It makes a short push, takes a fresh
picture, and measures. If the glass went where it was supposed to, carry on. If
it did not, push again from wherever it actually is.

### Why anyone does it this way

Because the alternative needs a number nobody has.

Predicting where a pushed object ends up is a solved problem in the sense that
the mathematics is written down and correct. It is an unsolved problem in the
sense that the mathematics needs the friction coefficient between the glass and
the table, and the way the glass's weight is spread across its base. Neither is
measured anywhere in this cell. A prediction built on two guesses is a confident
number with nothing behind it.

This project has met that shape of problem before and always answers it the same
way. The rim of a glass is not driven to a calculated height; the arm comes down
until it feels the rack. The squeeze is not computed and applied; it is
estimated, then the glass is lifted ten millimetres and weighed, and the
estimate is corrected. The gripping documents call this pattern
[the squeeze sequence](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/05_holding-on.md#1-the-squeeze-sequence):
a cheap guess, checked by a measurement, with the measurement deciding.

A push is the same shape. Guess, push, measure, correct.

### How it would work here

**Choosing the destination.** The table is a rectangle. The glasses are discs
on it with known middles and widths, which problem 2 produced. The rack is a
box. The arm's reach is a ring between 300 and 780 mm from its base. That is a
small enough world to check exactly.

A destination has to pass four tests, and each is a comparison of numbers the
arm already holds:

1. at least 70 mm of clear room from every other glass's edge;
2. inside the zone the glasses may stand in;
3. inside the comfortable reach;
4. clear of the rack.

Check all four *before* scoring anything, not after. Generating pushes, ranking
them by how much they separate, and then discovering the planner will not
execute them is how a cell becomes slow and unreliable with nothing erroring.
The gripping documents name this reordering as the commonest structural mistake
in a grasp pipeline, in
[bounding the search by the gripper's own body](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/03_choosing-a-grip.md#7-bounding-the-search-by-the-grippers-own-body),
and the fix is the same here: put the constraint in the search.

Score what survives by how far the glass has to travel. The shortest safe push
wins, because every millimetre of push is a millimetre of chance to knock
something.

**Choosing the push height.** From the glass's measured base width and the
tipping condition in [the problem](../problem.md): it slides while the contact is
below `a / μ`. Work that out per glass. If the limit is below the lowest the
gripper can reach — about 50 mm above the table — refuse the glass and say so.
Do not push it gently instead. A push that tips a glass tips it whatever the
speed.

**Making the push.** Close the fingers first, so the jaw is one stiff object
rather than two thin ones that can catch on a rim. Move to the push height
behind the glass, on the line through its middle. Then feel forward slowly until
the pad contact sensors or the wrist force say the glass is there. That is
[the guarded move](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#21-what-you-can-actually-do-with-it),
and it is worth using for a second reason beyond safety: the place where contact
happens is a measurement of where the glass's surface actually is, which is a
better number than the camera's. It is the same trick as the width at first
contact in problem 1's step 5.

Push in a straight line to the destination. Retreat along the same line.

**Looking again.** Fresh overhead pictures, problem 2's separation run over
them, and a comparison:

- the glass moved about as far as intended — go on to the next crowded pair;
- it moved much less — friction is higher than assumed, or it is heavier; push
  again from the newly measured position;
- it is somewhere no glass should be, or there is one group of points where
  there were two — something has toppled or been knocked. Stop and report.

### A worked example

Two glasses, 75 mm across. Glass A at (0.40, −0.30), glass B at (0.49, −0.28).
Their middles are 92 mm apart. Each needs 70 mm of clear room from its middle,
so they need 140 mm. They are 48 mm short.

*Which one moves.* Both are the same kind and the same width, so the tie-break
is the shorter push. B is nearer the empty part of the zone, so B moves.

*How low.* B's base is 62 mm across, so `a` is 31 mm. Taking μ = 0.3 gives a
limit of 103 mm. The gripper can reach 50 mm. 50 is below 103, so the push is
safe with room to spare. At μ = 0.5 the limit would be 62 mm, still above 50.
It would take μ above about 0.62 for this glass to be unpushable, which is
higher than glass on wood is likely to be — but it is a guess, and the document
says so.

*Where to.* The line from A through B, extended. B needs to reach 140 mm from
A, so it must travel 48 mm along that line. Check the landing spot: (0.535,
−0.269). Nearest other glass, 210 mm. Inside the glass zone, which runs to
x = 0.64. Distance from the arm's base, 601 mm, inside the 300–780 mm ring.
Clear of the rack, which is at y = +0.35. All four pass.

*The push.* Close the fingers. Go to 50 mm above the table, on the line from A
through B, 60 mm short of B's edge. Feel forward at 10 mm/s. Contact at 57 mm
of travel — 3 mm further than the camera predicted, which is the measurement
the guarded move buys. Push 48 mm. Retreat.

*Look again.* B is now at (0.531, −0.271). It went 46 mm of the 48 asked for,
and 4 mm off the line. A and B are 138 mm apart, which is 2 mm short of the
140 needed. Push again, 10 mm this time, or accept it if the margin is within
the measurement error. Either is defensible and the report should say which was
chosen.

### What it needs

Nothing new in hardware. The pad contact sensors and the wrist force sensor are
already in the cell and already used by problem 1's set-down. MoveIt's
`compute_cartesian_path` already makes the straight lines. Problem 2's
separation is the "look again".

New code: the destination search, the tipping check, a sideways version of the
existing `descend_until_contact`, and the comparison after the push.

### What it is good at

**It needs no number nobody has.** μ appears once, in a safety check that is
deliberately conservative, and nowhere in the path.

**It degrades gently.** A push that falls short is a push that gets repeated.
Nothing depends on the first one being right.

**It refuses honestly.** A glass that tips before it slides, or has nowhere to
go, produces a sentence rather than an attempt.

**Every number in it can be printed.** The destination search is four
comparisons. The report can say which one a rejected spot failed.

### What it is bad at

**It is slow.** Every push costs a full survey afterwards. Five glasses with two
crowded pairs could be six or eight pushes and as many surveys.

**It does not plan ahead.** The destination is chosen against the arrangement as
it stands. Moving a second glass can undo the first, and the loop only notices
afterwards.

**It can run out of table.** Five glasses each needing 140 mm of separation in a
zone 320 by 360 mm is near what fits. With six it may not be solvable at all,
and the honest output is to name the glasses it could not separate.

**It assumes the glass slides rather than rolls or rocks.** A glass with a
slightly convex base can rock, and the guarded move will feel that as contact
without the glass having moved.

### How it fails

**A glass pushed into a place that is clear now and crowded later.** Replanning
after each push keeps this from compounding, at the cost of more pushes.

**A push that rotates the glass instead of sliding it,** because the contact was
not through the middle. The look afterwards catches it. The damage is a wasted
push.

**Contact felt on the wrong thing.** The jaw could touch a neighbouring glass
before the target. The wrist force cannot tell the difference. The picture
afterwards can.

**μ higher than assumed on one particular glass,** so the push that was checked
as safe tips it. This is the failure that cannot be recovered, and it is the
reason to push as low as the gripper reaches, always, rather than at the
computed limit.

### When it would be the right choice

When the objects are few, their positions are already measured, and knocking
one over is expensive. That is this cell exactly. It is the wrong choice for a
cluttered bin, where there are too many objects to plan against individually and
the value of any one of them is low enough to justify learning by trying.

---

## Solution 4 — predict the slide with pushing mechanics

*Programmed. Use the classical theory of planar pushing to work out in
advance where the object will end up, and plan a single push that puts it
there.*

### What it is

Classical mechanics answers exactly the question this problem asks: push a
flat-bottomed object across a table, and where does it end up? The subject is
**quasi-static planar pushing**, and it is a set of theorems rather than a
heuristic. Three terms first.

**Quasi-static** means slow enough that momentum does not matter. Push a glass
and stop; it stops when you stop. It does not coast. So at every instant the
forces balance: push force equals friction from the table, push torque equals
friction torque. That turns a differential equation into algebra, and for a
250 g glass at the few centimetres a second this arm moves it holds easily.

**The friction cone at the contact** comes from
[friction cones and the antipodal test](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/03_choosing-a-grip.md#3-friction-cones-and-the-antipodal-test).
The glass pushes back along the surface normal, friction adds at most `μ` times
that sideways, so the force the contact can transmit lies in a cone of
half-angle `arctan(μ)` about the normal. Here `μ` is silicone against glass —
the pair the grip already uses 0.6 for, giving 31 degrees either side.

**The limit surface** is the part nobody meets elsewhere. The table's friction
is limited, and that limit is not one number, because the glass can slide, spin,
or both at once. Take a space whose three axes are the two components of
horizontal force and the twisting moment about the glass's centre. Every load
the table can just sustain is a point on a closed surface around the origin:
the limit surface. Its decisive property is that **the glass's motion is
perpendicular to that surface where the load sits on it** — so it says not only
whether the glass moves but which way. Goyal, Ruina and Papadopoulos established
this in the early 1990s; in practice people use Howe and Cutkosky's ellipsoidal
approximation, which reduces it to a line of algebra.

### Why anyone does it this way

Because a push needs no grasp, and the naive alternative is plainly wrong: push
a glass off-centre and it turns rather than following the finger. Two results
earn their keep.

**Mason's voting theorem** (Matthew Mason, 1986) says which way a pushed object
rotates, by a vote between three lines: the line through the contact along the
**push direction**, and the **two edges of the friction cone** there. Each
passes to the left or the right of the object's centre of friction and votes
accordingly. **The majority wins.**

It is useful because of what it does not need: no mass, no pressure
distribution, no coefficient for the table. It gives a sign, not a magnitude —
but when all three lines pass the same side the direction is certain however
badly the other numbers are guessed, and a planner can choose pushes where that
holds.

**The motion cone** is the second. For a given contact there is a cone of push
directions for which the finger **sticks** and the object moves rigidly with it;
push outside it and the finger slides across the glass instead. Lynch and Mason
built stable pushing on this: keep the contact sticking and the object is, for
the duration, part of the arm.

### How it would work here

The glasses are round, and that is a large gift: closed-form limit surfaces
exist for very few pressure distributions, and a **uniform disc** is the best
known. For a disc of radius `R` carrying weight `mg` uniformly, the largest
friction moment is `M_max = (2/3) μ m g R` and the largest force is `μ m g`.
Their ratio is a length,

    c = M_max / (μ m g) = (2/3) * R

the characteristic length of the pressure distribution. It is the only thing
about the base the model needs, and `μ` cancels out of it.

The usable rule: if the push line misses the centre by a perpendicular distance
`d`, then under the ellipsoidal approximation with the contact sticking the
glass turns about a point `r = c² / d` from its centre, on the far side of the
push line. Large `r` is nearly straight sliding; small `r` is a spin. So you aim
through the footprint centre, which problem 2 already measures, making `d` zero
and the slide straight — and the theory tells you how much aiming error you can
afford.

### A worked example

A middling glass here: footprint 70 mm across, so `R` = 35 mm, mass 250 g,
pushed 60 mm to take a crowded pair from 105 mm apart past the 140 mm line.

Uniform disc: `c` = (2/3) × 35 = **23.3 mm**. Say the push line misses the
centre by 5 mm, about what problem 2's circle fit plus placement error gives.
Then `r` = 23.3² / 5 = 109 mm. Over 60 mm the glass turns 60/109 = 0.55 rad,
about **31 degrees**, and its centre drifts off the intended line by roughly
60²/(2 × 109) = **17 mm**. The 31 degrees does not matter — the glass is round.
The 17 mm does.

Now change one assumption. A drinking glass's base is usually slightly concave,
so the weight rests on its **rim**. For an annulus `c = R` = 35 mm, giving
`r` = 245 mm, 14 degrees of turn, and **7 mm** of drift.

Same glass, same push, same `μ`. Two plausible guesses about how the weight sits
on the base. Answers a factor of two apart.

### What it needs

- **The contact friction cone**, silicone on glass. This input exists.
- **`μ` between glass and table.** Not measured anywhere in this cell. Needed
  for the force the push must supply and for the tipping bound `h < a / μ`.
- **The pressure distribution over the base.** The real one. Uniform disc,
  supporting rim, three high spots where the glass rocks — all plausible, none
  visible from an overhead camera.
- **Straight-line execution**, which `compute_cartesian_path` gives, and contact
  that matches the model, which Gazebo Harmonic supplies with friction numbers
  that are plausible rather than measured.

### What it is good at

Signs, cheaply and robustly. The voting theorem survives bad inputs by
construction, and it identifies pushes that are *safe by geometry*: a push
through the centre of a round footprint is straight under every pressure
distribution, because `d` is zero and `c` drops out. That conclusion needs none
of the missing numbers. It is also fast — arithmetic, no search, no simulation —
and it explains its answers, which a learned forward model cannot.

### What it is bad at

Magnitudes. Every number it produces is sound mathematics fed guesses. It also
assumes a rigid object, a flat table and a point or line contact. A wet ring
under a glass is outside the model entirely, and a drying rack is where wet
glasses are guaranteed.

### How it fails

Quietly, and with a number attached. A planner built on this returns "the glass
finishes 62 mm along the push line and 7 mm to the left", and the 7 mm is a
guessed pressure distribution wearing a decimal point. The run places the glass
on that basis, does not look, and finds out later.

The specific failure here: a rim-supported base predicted with the uniform
model, drifting about 10 mm further sideways than planned on every push. Ten
millimetres is well inside the 70 mm clearance, so it is invisible once and
compounds over three.

Table `μ` enters the tipping bound directly too. Guess it low, `a / μ` comes out
generous, the planner authorises a push higher up the glass than it should, and
the result is the one failure this problem exists to prevent.

### When it would be the right choice

When the pressure distribution is known or controlled — a machined part on a
fixture, a puck with a ground flat base, a part on a conveyor — or when the
outcome is needed *before* acting, because the workspace is occluded or the push
cannot be undone. There the inputs are real and the theory earns what it claims.

This cell is the opposite. A fresh overhead pair after each push costs about a
second, and a measurement beats a prediction whose inputs are guessed. The
honest position is to keep the qualitative half and drop the numerical half:
push through the footprint centre, keep the contact inside the friction cone,
then look. That is what [decision 2](solution-overview.md) already does. What it
should not do is dress the guess up as a prediction.

Literature, naming only what is certain: Mason's 1986 work on the mechanics of
pushing, which contains the voting theorem; Goyal, Ruina and Papadopoulos on the
limit surface; Howe and Cutkosky's ellipsoidal approximation; and Lynch and
Mason on stable pushing. MIT also published a large empirical dataset of real
objects being pushed on real surfaces, whose headline finding is that outcomes
scatter more than the deterministic theory predicts — this section's objection
measured rather than argued. For tools, Drake models quasi-static planar pushing
directly, and Gazebo, Bullet and MuJoCo will simulate the contact with whatever
coefficients you supply.

---

## Solution 5 — a learned residual on the push model

*Hybrid, with the model as a proposer. Keep the physics as the backbone and
learn only the difference between what it predicted and what actually happened.
Every push the arm makes in normal operation is a free labelled example.*
### What it is

[Solution 4](#solution-4--predict-the-slide-with-pushing-mechanics)'s weakness
is not its mathematics. It needs two numbers the cell does not have: `μ`
between glass and table, and how the glass's weight sits on its base. This
solution keeps the mathematics and adds a small model that learns **the error
the physics makes**.

For a proposed push the analytical model predicts travel, sideways drift and
rotation. Call that `f(x)`; call what the camera measures afterwards `y`. The
difference `y − f(x)` is the **residual**, and a second model learns it:

    prediction  =  f(x)  +  learned_residual(x)

The physics carries the structure. The learned part absorbs only what the
physics could not know: this table, these glasses, these bases.

The pattern is **residual learning**, also called a **learned error model** or
a **grey-box** model: a white box, derived from first principles, with a small
fitted black box on its output.

### Why anyone does it this way

The two halves fail in opposite directions. An analytical model **generalises
but is biased**: it answers for any push, wrongly by some consistent amount,
because its inputs are guesses. A learned model **fits but does not
generalise**, and solution 5 shows what that costs alone — tens of thousands of
episodes on a machine with no NVIDIA GPU.

Zeng and colleagues' *TossingBot* named the arrangement **residual physics** —
a ballistic model throws, a network corrects for drag and shape — and Ajay and
colleagues did the same for planar pushing. I am confident of both pieces of
work, not of their identifiers, so I give none rather than invent one.

### How it would work here

**The inputs**, all already measured or chosen: `d`, the signed perpendicular
distance from the push line to the footprint centre; `L`, the commanded push
distance; `2a`, the measured base width, 45 to 105 mm; `h`, the contact height,
near 50 mm today but kept so the model survives a gripper change; and the push
direction, since a damp patch sits somewhere in particular.

**The outputs** are three residuals: measured minus predicted travel, sideways
drift and rotation. Rotation matters least, the glasses being round.

**The labels come free.** Solution 3 already photographs the table after every
push and re-runs problem 2's separation over it, because that is how it decides
whether to push again. So the before-position, the commanded push and the
after-position exist for every push the arm has ever made, at no extra cost.
**Every push in normal operation is a labelled example, and the system trains
itself as it runs.**

**How much data.** The learned half never has to discover that pushing moves
things; that is in `f(x)`. A smooth correction over five inputs is learnable
from the low hundreds of examples, not the tens of thousands a policy needs.
Five glasses give three to eight pushes a run, so fifty runs is two to four
hundred labelled pushes.

**The models** stay small. **Ridge regression** from scikit-learn
([scikit-learn.org](https://scikit-learn.org/), BSD-3-Clause) is a linear fit
with ten printable coefficients. A **Gaussian process**, also scikit-learn
([the GP module](https://scikit-learn.org/stable/modules/gaussian_process.html),
BSD-3-Clause), fits a smooth function *and* returns a standard deviation with
every prediction — what the feedback half needs. A **small network** in
PyTorch ([pytorch.org](https://pytorch.org/), BSD-3-Clause) is overkill until
the dataset runs to thousands. Start with ridge; move to the GP for its error
bars, not its accuracy.

### The feedback loop

A residual model is trustworthy only where it has seen data. Two hundred pushes
on 70 mm glasses say nothing about a 105 mm one, and the model will not say so
unprompted.

**Detecting extrapolation.** A GP gives it directly, as the standard deviation
from `predict(X, return_std=True)`. With ridge, use the distance to the
fifth-nearest training row in scaled inputs.

**The response.** Set a threshold: a standard deviation above 4 mm, or a
neighbour distance beyond the 95th percentile of the training set's own. Above
it, **discard the residual** and use `f(x)` with solution 4's conservative
assumption about the base; **pad the destination**, taking the 140 mm line plus
the full 20 mm margin; and **take the picture**. Below the threshold a push may
occasionally be chained without a survey. Above it the look-again is mandatory,
and it returns a labelled row in exactly the region the model was short of, so
extrapolation triggers the measurement that cures it.

### A worked example

Solution 4's glass: footprint 70 mm, so `R` = 35 mm, 250 g, pushed 60 mm, the
push line missing the centre by 5 mm.

Uniform disc gives `c` = 23.3 mm, `r` = 109 mm and 60² / (2 × 109) = **17 mm**
of drift. An annulus gives `c` = 35 mm, `r` = 245 mm and **7 mm**. Nothing in
the cell sees which is true.

Push it and look. The glass lands 8 mm off the line, so the residual against
the uniform-disc backbone is 8 − 17 = **−9 mm**. Thirty such rows, fitted with
ridge, might return roughly `−0.5 × predicted_drift` — what a rim-supported
base looks like. The corrected prediction for the next 70 mm glass is **8 mm**,
not 17.

What was learned is not a friction coefficient. It is that these glasses, on
this table, drift about half of what the model says — the number nobody could
measure, obtained without measuring it.

Now a 105 mm glass arrives, and only two of the thirty rows were wider than
85 mm. The GP returns 6 mm of standard deviation against the 4 mm threshold, so
the residual is dropped, the full margin is used, and a picture is taken after
the push. No worse than solution 3 — and one more wide glass in the dataset.

### What it needs

Solution 4's analytical model, callable. Solution 3's look-again, which
supplies every label. A CSV of past pushes, holding inputs, prediction,
measurement and uncertainty. scikit-learn, a small pure-Python dependency with
no CUDA in it. Retraining between sessions, not mid-run. No new hardware, no
simulator time, no GPU.

### What it is good at

**It turns operation into improvement.** The arm gets better at pushing by
pushing, with no training phase and no labelling work.

**There is a floor under it.** With the fallback, the worst case is solution
3's behaviour.

**It stays explainable.** A report can say "predicted 17 mm, corrected to 8 mm,
because past pushes drifted about half what the model said".

### What it is bad at

**It needs the backbone to be nearly right.** A correction to a badly wrong
prediction is a second model in disguise. If a glass rocks rather than slides,
`f(x)` is not wrong by a smooth amount — it is not describing the event.

**It is silent about drift.** A table wiped with a different cloth changes `μ`,
and the old residuals go stale. Only rising prediction error shows it.

**It cannot supply the missing measurement.** `μ` stays unknown; its effect on
displacement is learned tangled with the pressure distribution.

### How it fails

**By being trusted outside its data.** That is the whole risk, and the
uncertainty threshold with its fallback is the whole mitigation. A model with
no uncertainty output should not be wired into the planner.

**By learning a bug.** If problem 2 mislocates a glass by 3 mm, the residual
absorbs that as physics and keeps it until the dataset is cleared. A push that
half-toppled a glass is the same trap; reject those rows.

**The failure that must be designed out.** The tipping check `h < a / μ` stands
between the arm and a broken glass. **The residual must never touch it** — not
to raise the allowed height, not to relax the guessed `μ`, not to argue that
this glass has been pushed safely twenty times. Enforce that structurally: the
function choosing push height takes the measured base width and a fixed
conservative `μ`, and does not import the residual model at all. The residual
may make a push *more* conservative, shorter or better aimed, and nothing else.
It may improve aim. It may not grant permission.

### When it would be the right choice

Once solutions 1 and 3 are built and the push log holds a few hundred rows. Not
before: there is no backbone to correct, and no data to correct it with.

It earns its place when surveys are the bottleneck. Solution 3's complaint is
that every push costs one, and a residual good to a few millimetres lets two
pushes be chained before looking.

It would be wrong if pushing were rare, or if the table and glasses changed so
often that no dataset stayed valid.

---

## Solution 6 — geometry generates, a model ranks

*Hybrid, with the model as a ranker. The planner enumerates every safe push and
vetoes the unsafe ones; the model only decides which of the survivors to try
first. A bad ranking costs an extra push and can never cost a toppled object.*
### What it is

Solution 3 chooses its destination by a rule fixed in advance: of the spots
passing its four tests, take the shortest travel. This hybrid changes only that.

The geometric planner is asked for **every** safe push rather than the best one
— every direction, every distance, each already filtered for the tipping limit,
reachability, the zone, the rack and a clear corridor. Every survivor is safe. A
**learned model then puts them in order**, and the top one is pushed.

**Geometry proposes. Geometry vetoes. The model only orders.** It cannot add a
candidate and cannot overrule a rejection. A bad ranking costs an extra push — a
few seconds and a re-survey. It can never cost a toppled object, because every
candidate was cleared by arithmetic first.

### Why anyone does it this way

It is the safest shape available for a learned component in a physical system,
and the contrast with [reinforcement learning](learned-with-hardware.md#learn-to-push) is exact. There the policy's output *is* the
action. A policy has no field for "never topple", so safety has to come through
the reward, and a fine is a price — a trade the policy may take. Bolt a
geometric check on at run time and that check is doing the safety work anyway.
Here the output is a
**permutation of a set that is already safe**, and no value it can emit is an
unsafe push.

Ordering is also the part geometry is bad at. Enumerating safe pushes is easy.
Saying which survivor helps most needs the friction and the pressure
distribution that solution 4 shows nothing here measures.

### How it would work here

**The candidate set.** For one chosen object, sweep directions at 15° (24 of
them) and distances of 20, 40, 60 and 80 mm: 96 candidates. Run solution 3's
tests on each. A handful to a couple of dozen survive.

**The model's input,** per candidate: the push, as a unit direction, a distance
and the moving object's footprint width; the arrangement now, as either the
object list — five centres and five footprint widths — or an occupancy grid, the
320 x 360 mm zone at 10 mm cells, 32 x 36, with 1 where a disc covers a cell;
and the crowding that would remain, the clearances recomputed with the object at
its destination.

**What "helps most" means.** One scalar the model predicts. Best is **how many
further pushes the run will need after this one**: that is what the run is
scored on, and it credits a push which opens nothing now but sets up the next.
Cheaper is **how many objects become grippable**, needing no rollout. Only the
ordering of the outputs is used.

**Training data.** Gazebo spawns a random legal arrangement of five objects,
footprints 45–105 mm, masses 150–400 g. The planner enumerates the survivors,
each is simulated from that same start, and the result labelled. This is
**supervised learning, not trial and reward**: every simulated push is one
labelled row, nothing has to explore, and no real arm is involved. At four
seconds a push, 300 arrangements at 15 survivors each gives some 4,500 rows in
roughly five hours — an estimate, not a measurement.

**Model families**, for a few dozen inputs and a few thousand rows:

- **gradient-boosted trees** — shallow decision trees, each correcting the
  running total of the ones before it. The best default at this size, and it
  reports which features mattered. scikit-learn (https://scikit-learn.org/,
  BSD 3-clause), XGBoost (https://github.com/dmlc/xgboost, Apache 2.0), LightGBM
  (https://github.com/microsoft/LightGBM, MIT);
- **a small multilayer perceptron** — a few fully connected layers of perhaps 64
  units, needed if the input is the grid. PyTorch
  (https://github.com/pytorch/pytorch, BSD 3-clause) runs on Apple Silicon;
- **a graph neural network** — each object a **node** holding its position and
  footprint, each pair an **edge** holding their separation, every node
  repeatedly updating itself from a sum over its neighbours. The answer then
  ignores the order the objects were listed in, and one set of weights covers
  four objects or eight. PyTorch Geometric
  (https://github.com/pyg-team/pytorch_geometric, MIT). Whether that beats
  boosted trees on five objects is **uncertain**.

### The feedback loop

Solution 3's re-survey happens after every push regardless. It is the true
outcome, so the chosen candidate and what it achieved form a new labelled row —
free, because the measurement was being taken for safety anyway. **The ranker
improves with use,** including on real friction rather than Gazebo's configured
constant.

**A flat ranking is itself an answer.** If the top candidates score within the
model's own error of each other, the model is saying it does not much matter
which is picked. That is information, not a failure. Stop asking the model and
let the **geometric tie-break** decide — shortest push, because every millimetre
of travel is another millimetre in which something can be knocked.

### A worked example

Five objects, millimetres from the arm's base, in a zone running x 320–640 and
y −410 to −50.

| Object | Position | Footprint |
| --- | --- | --- |
| A | (340, −120) | 70 mm |
| B | (470, −140) | 80 mm |
| C | (560, −250) | 60 mm |
| D | (400, −250) | 105 mm |
| E | (500, −360) | 45 mm |

By solution 1's asymmetric rule — `n` is in the way of `t` when
`distance(t, n) < 70 + footprint(n)/2` — three pairs are crowded: A–B at
131.5 mm, B–D at 130.4 mm, C–E at 125.3 mm. B is in two of them, so B moves.

**Geometry proposes.** B's `a` is 40 mm, so even at μ = 0.5 it tips only above
80 mm, well over the 50 mm the gripper is stuck at. Of the 96 candidates,
seventeen survive. The other 79 are gone before the model runs.

**The model orders,** predicting further pushes needed: 60 mm along (0.91, 0.41)
scores 1.15, 40 mm along the same line 1.22, 60 mm along (0.97, 0.26) 1.28.

**The tie-break decides.** Those are 0.13 apart. If the held-out error is around
0.4 — illustrative, not measured — that spread is noise, so geometry chooses
among them and shortest wins: 40 mm.

B lands at (506.4, −123.6): 166.4 mm from A, 165.2 mm from D, 137.3 mm from C,
246 mm from E, all clearing their thresholds, at 521 mm reach and inside the
zone. Both crowded pairs fixed in one push.

**The loop closes.** The re-survey finds B moved 37 mm, 5 mm off the line. C–E
still needs a push, so the true label is 1 against a predicted 1.22, and the row
is stored.

### What it needs

Everything solution 3 needs, plus an enumerator where solution 3 has a chooser,
a feature function, a Gazebo data-generation script, a weights file, and
somewhere to append real outcomes. No NVIDIA GPU: small tabular regression fits
this machine where a policy network does not.

### What it is good at

**The learned part cannot cause the unrecoverable failure.** Toppling, running
out of reach, hitting the rack and leaving the zone are settled before the model
is consulted.

**It degrades to solution 3.** Delete the weights file, rank by shortest push,
and the run still works, slightly worse.

**It is checkable.** Every candidate can be printed with its score, and
refusals remain geometry's.

### What it is bad at

**It does not transfer by object count.** A ranker trained on five objects has
never seen the crowding eight produce, and nothing errors when it is out of
range. The object-list input is worst here, because its length changes.

**It cannot invent a candidate.** If the sweep is too coarse, or a test rejects
something that was in fact fine, the model can only order what it is handed. The
ceiling is the enumerator's quality, not the model's.

### How it fails

**Quietly, as a slower run.** A badly trained ranker orders candidates roughly
at random, and the symptom is six pushes where four would have done. Nothing
errors. Measure pushes-per-run against plain shortest-push on seeded
arrangements, and keep the simpler one if it wins.

**Confidently outside its training range.** Fed eight objects it still emits
numbers, and they may not be flat. Outside the trained range, ignore the model.

**Feedback that narrows it.** Only the chosen candidate is ever measured for
real, so the model learns most about the region it already prefers.

### When it would be the right choice

When solution 3 already runs and the measured complaint is the number of pushes
rather than the number of topples. It is also right whenever a learned component
is wanted in this cell at all: constraining it to an ordering over a pre-vetted
set is how to have one without putting an unexplainable function in charge of
the only action that can break something.

It is the wrong choice before solution 3 exists, and the wrong choice if the
arrangements are easy — one crowded pair on an open table, where every survivor
is about as good as every other.

---

## Solution 7 — a learned change-verifier

*Hybrid, with the model as a verifier. After each push, a small model comparing
the before and after pictures answers three questions the geometry answers
badly — did it move as intended, did anything else move, and has anything
fallen over.*
### What it is

Solution 3 pushes, then looks again. This **hybrid** replaces only the
looking. Everything before it stays as written; the last step becomes one
question put to a small learned model: what happened?

**Change detection** is the field: comparing two pictures of the same scene,
taken at different times, to say what differs. It grew up in satellite
imagery, on ground photographed months apart.

The obvious method is **pixel differencing** — subtract one picture from the
other. It works only if the camera has not moved. Here it is on the wrist, and
the planner that returns it to the photographing pose is repeatable rather
than exact. Shift a 320x240 picture by two pixels and every edge lights up —
rims, joints, shadows — and the glass that moved is buried in it. Telling the
method about the motion is the general case of change detection, and it is
hard. **This cell is not the general case.**

### Why anyone does it this way

**The geometry answers the wrong questions.** Re-running problem 2's
separation gives new footprint circles. They answer the first — did the target
move as intended — crudely but honestly. The second, did anything *else* move,
is swamped by spurious differences across five circles. The third it barely
answers: to the separation stage a toppled glass is a group of points that is
not a circle, and so is a glass half hidden behind its neighbour.

**The camera pose is known exactly.** The joint encoders and forward
kinematics give it at both pictures, and `tf2`
([github.com/ros2/geometry2](https://github.com/ros2/geometry2), BSD-3-Clause)
publishes it. The camera is RGB-D, so the before picture carries depth and can
be **reprojected into the after camera's frame**: each pixel pushed out to its
3-D point and photographed again from where the camera stands now. What comes
back is the scene as it would have looked had nothing changed, so the two
pictures agree on geometry and every difference left is real. The arm masks
out too: the joint angles say which pixels are gripper.

### How it would work here

**Three outputs, not a score.** A three-way classifier, run per glass:

1. **moved as intended** — carry on;
2. **moved unexpectedly** — short, sideways, or a neighbour shifted; push
   again from the newly measured position;
3. **fallen** — stop and report.

"Fallen" earns its own class rather than an anomaly score. An anomaly score is
one number meaning *unusual*, and unusual covers a glass 15 mm short, a
lighting change, and a glass on its side — three cases with three different
correct actions. Nor can an anomaly detector be taught what a topple looks
like: it sees normal data only. Gazebo will make topples all day.

**The model.** A **twin-branch**, or **siamese**, network: two copies of one
small convolutional network sharing a single set of weights, one fed the
before crop and one the after crop. Their outputs are subtracted and a small
head turns that into the three numbers. Shared weights stop the branches
forming different ideas of what a glass looks like. Concretely: a 96x96 crop
at the glass's known position, colour plus depth; a pretrained ResNet-18
backbone from [torchvision](https://github.com/pytorch/vision) (BSD-3-Clause);
trained in [PyTorch](https://pytorch.org/) (BSD-3-Clause) on the Metal
backend, because **this is an Apple Silicon Mac with no NVIDIA GPU**.

**Classical alternatives, built first and beaten.** Aligned differencing with
a threshold, in [OpenCV](https://opencv.org/) (Apache-2.0); structural
similarity in [scikit-image](https://scikit-image.org/) (BSD-3-Clause); and
three numbers per glass — change in footprint area, in the tallest point's
height, and in width over height — in a logistic regression from
[scikit-learn](https://scikit-learn.org/) (BSD-3-Clause). A toppled glass
loses height and gains width, so that last is already decent.

**Training data** comes labelled from Gazebo Harmonic
([gazebosim.org](https://gazebosim.org/), Apache-2.0), which knows where it
put each glass. The trap is **class imbalance**: a topple is rare, one push in
a few hundred, so a model trained on that mixture learns the cheapest rule
going — "nothing ever falls over" — which is right almost every time and
worthless. Generate topples **deliberately** until one training pair in five
is one, and score on topples caught, never on accuracy, which the lazy rule
wins.

### The feedback loop

The verdict is **uncertain** when the largest of the three probabilities is
below a bar, or the top two are close. It is the model's most valuable output,
because it alone triggers an action: another picture, from a pose chosen to
settle the doubt.

**Why a chosen pose.** Overhead is the worst angle for telling a standing
glass from a fallen one: both are a blob of roughly the right area. Side-on
they are nothing alike — standing is a tall narrow silhouette, fallen a long
low one. The missing information has a direction, and the camera can move into
it.

**How it is chosen.** **Height:** about 80 mm above the table, looking roughly
horizontally, so the glass is seen against the background, not the table top.
**Azimuth:** score the viewpoints at working range round the glass by how many
others lie in the line of sight, and take the clearest one in reach. **A
second azimuth,** 90 degrees round, if needed: it covers a glass fallen
straight towards the camera, which foreshortens into a standing one.

**How many looks.** Two, then stop — a few seconds each, under ten in all.
Still uncertain after the second, the arm does not guess. It reports.

**The safety asymmetry.** A false "everything is fine" leaves the arm working
beside fallen glass nothing here can stand back up; a false alarm costs a
stopped run. So bias the threshold deliberately, twice. Weight the training
loss so that missing a topple is penalised several times more heavily than
inventing one. Make the run-time bars asymmetric: accept "moved as intended"
only above about 0.9, treat "fallen" as live from about 0.2 upwards, and let
everything between buy a look rather than a decision. The principle carries:
**make the model eager to ask for another picture and reluctant to say
everything is fine.**

### A worked example

Solution 3's glass B, pushed 48 mm.

*The routine look.* Forward kinematics says the camera is 3.1 mm and 0.4
degrees from where it stood before — far too much for pixel differencing. So
the before picture is reprojected and a crop taken.

*The verdict.* Moved as intended 0.55, moved unexpectedly 0.31, fallen 0.14.
Nothing clears 0.9: uncertain. The geometry would have said "fine", because
B's circle still fits.

*The chosen look.* B's only neighbour within 200 mm is A, 138 mm away, so the
arc away from A is clear. The arm goes 380 mm out on that side, 80 mm up.
About 4 seconds.

*The second verdict.* Side-on, the crop is a tall silhouette with a rim on
top. Moved as intended 0.94, fallen 0.01. Accept, and go on. Had it come back
fallen 0.88, the run stops — four seconds to learn what overhead could not.

### What it needs

No new hardware. New code: the reprojection, a training script, a weights
file, the viewpoint chooser, and the two-look cap.

### What it is good at

It answers the two questions geometry cannot, from one comparison rather than
a full survey. It turns doubt into an action, which nothing else here does.
Its errors fall on the side that costs seconds, not a glass.

### What it is bad at

**Explaining itself.** The rules refuse with a sentence containing two
numbers. This returns 0.14, which has no parts.

**Depending on the alignment.** A wrong camera pose means the model sees
changes that are not there. Exact in simulation, less so on a real arm.

**Generalising.** It knows only the glasses it was shown.

### How it fails

**On a case nobody generated.** A glass leaning against its neighbour is
neither standing nor lying, and the model will pick one anyway.

**By being right too often.** A verifier that says "fine" on 199 pushes in 200
stops being read, and the 200th mattered.

**Outside the crop.** It follows the pushed glass, so run it on all of them.

### When it would be the right choice

When the routine check is cheap, the failure it must catch cannot be undone,
and more information can be bought on demand. That is this cell exactly.

It is the wrong choice with a fixed camera, where an uncertain verdict has
nowhere to go, or wherever a wrong answer is cheap.

---

## Solution 8 — a learned early-abort

*Hybrid, with the model as a verifier acting during the push rather than after
it. The force trace tells a clean slide from an object about to tip, and
stopping is the only thing that can prevent a topple rather than report one.*

### What it is

[Solution 7](#solution-7--a-learned-change-verifier) looks once the push is
over and says what happened. This one watches the wrist *during* the push and
stops it. Every other solution decides beforehand or measures afterwards; the
push is the only place a topple can be prevented rather than detected.

The evidence is the **force trace**: the horizontal force at the wrist during
contact. A clean slide is a ramp to a steady level, then flat. An object about to tip climbs, keeps climbing, then drops away as it
goes over. A jam against a neighbour climbs and never stops.

### Why anyone does it this way

No reading separates them.

Objects here weigh 150 g to 400 g. Keeping one sliding takes `μ m g`: 0.44 N
for the lightest at μ = 0.3, 1.96 N for the heaviest at μ = 0.5. Starting a
tip about the front edge of the base, pushed at height `h`, takes `m g a / h`
— for a 150 g object on a 60 mm base pushed at 50 mm, **0.88 N**. The force
that tips the lightest object is below the force that ordinarily slides the
heaviest, so no threshold sits between them. Weight would separate them, and
nothing here has weighed anything.

Behaviour over time does. 0.9 N means nothing; 0.9 N that has risen for 60 ms
while the arm kept moving means the object is not sliding.

A **time series classifier** takes a window of signal — here the last 20
samples — rather than one reading, and returns a label: sliding, tipping or
jamming.

### How it would work here

**Try thresholds first, and mean it.** Two rules on the horizontal force:
abort above a level, abort above a rate of rise. If they catch every
deliberate topple on seeded Gazebo runs at a tolerable false-abort rate, **use
them and stop reading.** I invent no figure for how well they do. Their
failure is the arithmetic above: the bar that is safe for a 400 g object is
not the bar that is safe for a 150 g one.

**The learned version.** A sliding window over the six wrist channels and the
pad flags, one decision per sample. Twenty samples is 200 ms, or 6 mm of
travel at 30 mm/s. From it, ten features: means, spreads and fitted slopes of
force and torque, over the window and over its last five samples.

Feed those to **gradient-boosted trees** — scikit-learn
(https://scikit-learn.org/, BSD-3-Clause), LightGBM
(https://github.com/microsoft/LightGBM, MIT), XGBoost
(https://github.com/dmlc/xgboost, Apache-2.0). The alternatives read the raw
trace: a **tiny 1-D convolutional network**, or a **small recurrent model**
carrying a summary forward sample by sample, both in PyTorch
(https://pytorch.org/, BSD-3-Clause) on the Metal backend. Take the trees:
seconds to train on a laptop CPU, microseconds to predict.

**The labels are free, and they are the good part.** Gazebo knows the pose of
everything it spawned, so read the final roll and pitch — past 30 degrees is a
topple — then replay the trace and label each window by **what happened
next**: positive if a topple starts within 300 ms. The label is not what the
window shows but what it precedes, which makes this a warning rather than a
report.

**Imbalance.** A topple is one push in a few hundred, so a classifier scored
on accuracy learns "nothing ever tips" — right 99.7% of the time and worth
nothing. Make topples on purpose: push at 120 mm rather than 50, or a tall
object on a narrow base. Free in simulation, unthinkable on a real table.
Generate until one push in four topples, and score on topples caught, never on
accuracy.

**Latency decides the design.** A model too slow to act is worthless however
accurate. The project's usual wrist reading, the median of 32 samples at
100 Hz, is 320 ms of lag and 9.6 mm of travel — longer than the tipping event
itself. A 5-sample median costs 50 ms and 1.5 mm; features
plus a tree stay under 1 ms; the monitor sits beside the controller and zeroes
a velocity command rather than cancelling a plan. Budget 50 ms from evidence
to brake. How much time there is before an object is past recovery is
**uncertain**.

### The feedback loop

An abort is a measurement, not a failure.

**Stop and retreat** 20 mm along the push line. Never lift: that finishes the
topple just prevented.

**Take a picture.** Force says something went wrong and cannot say what. Here
solution 7 is the other half of a pair, not a rival.

**Write the row back.** The window that fired, plus the camera's verdict, is
a labelled example from the real table, and a false alarm is the most valuable
row of all, because simulation makes so few.

**Feed the tipping check.** An abort confirmed as a real tip, at h = 50 mm on
an object with a = 31 mm, is evidence that μ exceeds 31 / 50 = **0.62**, not
the 0.3 assumed. Raise the μ the refusal rule uses. One rule guards this:
**the evidence may only make the check stricter, never looser.**

### A worked example

A 150 g object, 60 mm footprint so `a` = 30 mm, pushed at the gripper's floor
of 50 mm at 30 mm/s. At the assumed μ = 0.3 the limit `a / μ` is 100 mm, so
the plan says yes. A damp ring makes μ ≈ 0.7 locally and the real limit 43 mm:
sliding would need 1.03 N, tipping 0.88 N. It tips.

*The trace.* Contact at t = 0, steady at 0.35 N for 200 ms, where the detector
arms. Then 0.44 N, 0.60, 0.72, heading for 0.88 — about **8 N/s**, against a
slide's zero plus noise. A bar at 2.5 N, the only level that leaves a heavy
object's ordinary 1.96 N slide alone, never fires.

*The model.* At t = 240 ms: slope 5.1 N/s, 8.0 N/s over the last five samples,
torque rising. Tipping at 0.34 against a bar of 0.15. Abort. The chain is
10 ms of sample, 50 ms of median lag, 1 ms of model and 35 ms of ramp — 45 ms
and 1.4 mm more travel, and it settles back.

*The loop.* Retreat, photograph, confirm. μ for this kind is raised to 0.62,
making `a / μ` = 48 mm, below the gripper's 50 mm floor. **This object is now
refused, correctly, for every future run.**

### What it needs

The wrist and pad sensors, already simulated by Gazebo Harmonic
(https://gazebosim.org/, Apache-2.0). A monitor node beside the controller
that can zero a velocity command. A script spawning objects across the
45–105 mm and 150–400 g ranges and pushing them at deliberately unsafe
heights. No GPU, no pretrained weights, no real data.

### What it is good at

**It acts inside the failure**, alone here. **It measures μ** — every
confirmed abort is one real observation of the number the tipping check rests
on. **It degrades to nothing**: delete the weights and the thresholds
remain.

### What it is bad at

**It cannot see.** Without a camera afterwards, an abort is a shrug.

**It is trained on a contact solver.** The shapes should transfer; the levels
and rates will not.

**It has no parts.** A threshold refuses with a number, this with 0.34.

### How it fails

**Too late.** The model is right and the arm cannot stop in time.

**On a case nobody generated.** An object rocking on a convex base gives a
rising force that is not a tip, and will be called one.

### When it would be the right choice

When the failure cannot be undone, the action is slow enough to interrupt,
and a sensor already watches the contact. That is this cell.

The asymmetry settles how far to bias it. A false abort costs five or six
seconds. A missed topple costs the object and ends the run. So weight a missed
topple twenty times a false abort in the training loss, and set the run-time
bar near **0.15**, not 0.5. The limit is usability: if clean
runs abort more than about one push in five, the bar is too low to ship, and
the fix is a better model, not a higher bar.

It is wrong on a fast push, or where a topple is a nuisance, not a loss.

---

## Solution 9 — identify the contact parameters

*Learned, as a proposer to the physics. Solution 4 guesses the friction it
needs. This estimates it, and the spread of the base's weight, from what the
arm's own pushes actually did — and hands back a number with physical meaning
that the tipping check can use.*

### What it is

Solution 4 has the right mathematics and two inputs nobody has: `μ`, the
friction between object and table, and how the object's weight sits on its base.
It guesses both. Solution 5 keeps the mathematics and learns **the size of the
error** those guesses cause. This solution does neither. It learns **the missing
inputs themselves**, from what the arm's own pushes did. A residual is a
correction, useful only to the model that made the prediction. This produces a
**number with physical meaning** that the rest of the system can use, starting
with the tipping check `h < a / μ`.

The technique is **system identification**: fitting the parameters of a model
you already believe, rather than fitting an arbitrary function to data. Only the
constants are in question.

### Why anyone does it this way

It sits between the two families this document compares. **Analytical
modelling** takes its constants from a handbook, and is wrong by whatever the
handbook is wrong by. **Machine learning** supplies no equation, so it needs a
great many examples: it must find the shape of the answer as well as its size.

System identification keeps the equation and fits only the constants — a handful
of unknowns instead of thousands of weights. So it needs data counted in tens.
Its weakness is the equation's: a wrong model gives confident wrong constants.
It is the standard method in control engineering.

### How it would work here

Every push already produces a before picture, a commanded displacement and an
after picture, so each gives a displacement and a rotation. The wrist sensor
adds the force that kept it sliding. **Three things could be identified from
that, and they are not equally identifiable.**

*The weight's spread, cleanly.* Solution 4 reduces the pressure distribution to
one length `c`, between `(2/3)R` for a uniform disc and `R` for one resting on
its rim. A push missing the centre by `d` turns the object about a point
`r = c² / d` away, so a measured turn gives `r`, and `c = √(r d)`. `μ` cancels
out.

*`μ` at the table, only as far as the mass allows.* In steady sliding the wrist
reads `F = μ m g`. Nothing here weighs anything, so the force gives the
**product** `μ m`, which the 150 to 400 g range turns into an interval. An
object pushed at `h` that did **not** tip adds a free bound, `μ < a / h`.

*`μ` at the finger, barely.* Silicone on glass is not glass on table, and a push
reveals finger friction only when the pad **slips**. Sticking proves it was at
least enough, not how much more. Treat this one as bounded.

**The estimator.** Stack one row per push and solve a least-squares fit.
Better, make it **recursive**: carry the estimate with a measure of how sure it
is, and nudge both when a push arrives, instead of redoing the whole solve over
every push ever made. A surprise moves it a lot, a confirmation a little. The
standard family is **recursive least squares** and the **Kalman filter**, with a
*forgetting factor* so a wiped table is tracked, not averaged away.

**The interval is what makes the tipping check honest.** Today it uses a guessed
`μ`. Use the **pessimistic end** instead — the largest `μ` the data still
allows. That is not a more accurate system. It is a **safer** one.

### The feedback loop

A wide interval points at its own cure. When it is too wide to decide something
— the pessimistic `μ` refusing an object the optimistic `μ` would allow — the
answer is a **deliberately informative push**: 10 mm, at the gripper's lowest
reach, into clear table. Its purpose is not to separate anything, but to
measure.

This is an **experiment the robot designs for itself**, and the design is not
obvious. The most informative push for `c` is deliberately **off-centre**, since
a push through the centre makes `d` zero and produces no rotation to learn from.
The pushes made while doing the job teach least. In control this is **persistent
excitation**: the inputs must vary enough for the parameters to separate.

**When to spend one.** Only when it can change a decision, because a probe
costs fifteen to twenty seconds of arm motion: at the start of a run on a stale
table, and when the interval straddles the refusal line for an object that has
to move.

### A worked example

A 70 mm footprint, so `a` = 35 mm, pushed at the gripper's floor of 50 mm.

*The force.* The wrist reads 0.74 N. From `F = μ m g`: at 400 g,
`μ` = 0.74 / 3.92 = **0.19**; at 150 g, `μ` = 0.74 / 1.47 = **0.50**. So `μ`
lies in **[0.19, 0.50]**, and the no-tip bound adds `μ < 35 / 50 = 0.70`.

*The check, run pessimistically.* `a / μ` = 35 / 0.50 = **70 mm**, against the
50 mm the gripper is stuck at. Push, with 20 mm of earned margin.

*The same arithmetic on a narrow object.* A 45 mm footprint gives `a` = 22.5 mm.
At the guessed `μ` = 0.3 the limit is 75 mm and the push is authorised. At the
identified pessimistic `μ` = 0.50 it is **45 mm**, below 50, and the object is
**refused**. The guess would have pushed it. The measurement will not.

*The spread.* The same push turned 0.30 rad about a 5 mm offset, giving
`c` = **31.6 mm**: a rim-supported base.

### Per object, or per table

`μ` at the table belongs to **a pair of surfaces**, so with one kind of object
on one table it is one number, and every push is evidence about it. Pool them:
three pushes per object is noise, thirty across ten objects identifies one
shared `μ` well. `c` is per object, because it depends on that base.

A mix wants **partial pooling** — a shared estimate plus a per-object offset
held near zero until that object's own pushes argue otherwise. A damp ring under
one glass then shows as disagreement with the pool.

### What it needs

**NumPy** ([numpy.org](https://numpy.org/), BSD-3-Clause) for the solve;
**SciPy** ([scipy.org](https://scipy.org/), BSD-3-Clause) if the fit goes
nonlinear; **scikit-learn** ([scikit-learn.org](https://scikit-learn.org/),
BSD-3-Clause) for a Bayesian linear fit that returns an interval directly.

**There is no training run** — no data campaign, no weights file, no GPU, just
a few numbers and a covariance in a CSV. **Gazebo Harmonic**
([gazebosim.org](https://gazebosim.org/), Apache-2.0) is *told* its friction
coefficients, so the estimator can be scored against a true value it never saw.

### What it is good at

**It produces a number other things can use**, starting with the tipping check.
**It is small**: tens of pushes, because only the size of the answer is fitted,
not its shape. **It carries its own doubt**, which drives the pessimistic check
and the decision to probe.

### What it is bad at

**Separating quantities that arrive multiplied.** `μ m` is one measurement and
two unknowns. Without weighing, `μ` stays an interval as wide as the mass
range, a factor of 2.7 here — a limit of the cell, not of the method.

**Surviving a wrong model.** An object rocking on three high spots is not
sliding on a flat base, so the fitted `c` describes nothing — and still returns
a number.

### How it fails

**By being believed.** A guessed `μ` is treated with suspicion; an identified
one carries a decimal point and an implied authority. Bias it — by a survey
mislocating objects by 3 mm, by rows from half-toppled pushes — and the check is
confidently wrong where it was cautiously guessed.

The mitigation is structural. **The identified `μ` may be used at its
pessimistic end only, and never below a fixed floor** until the interval is
narrow. Loosening the check needs more evidence than tightening it: too tight
wastes a refusal, too loose breaks an object.

**It also drifts quietly.** A wiped table changes `μ` and announces nothing.

### When it would be the right choice

When one unmeasured constant is used by several decisions and a safety check
depends on it. Both hold here, and no friction meter is coming to this cell. It
is wrong when the parameter can simply be measured on a tilting plate.

It composes rather than competes: it hands solutions 3 and 5 the inputs they
were guessing.

---

## Solution 10 — learn a forward model, then plan against it

*Learned, as the decider, and model-based rather than model-free. Learn what
will happen rather than what to do, then let an ordinary planner search over
candidate pushes using it.*

### What it is

[reinforcement learning](learned-with-hardware.md#learn-to-push) learns *what to do*. This one learns *what will happen*, and leaves
the deciding to arithmetic on top.

A **forward model**, or **learned dynamics**, is a function fitted to recorded
experience. Give it the arrangement now and a push you are considering; it
returns the arrangement afterwards. It is the physics solution 4 could not fill
in, fitted rather than derived.

Deciding happens outside it. Propose many pushes, ask the model what each would
do, execute the one that scores best. The same model serves any goal, because
only the scoring changes. A policy serves the one goal it was rewarded for. That
is the distinction between model-based and model-free learning.

Two flavours. **State prediction** maps the ten measured numbers plus a push to
the new positions. **Image prediction** — **video prediction**, or **visual
foresight** — returns a predicted camera frame instead, for tasks with no state
you can write down. You cannot list a towel's coordinates.

**State prediction is the only sane choice here.** The state is ten numbers and
problem 2 has measured it; the camera is 320x240, or 230,400 values in colour.
Predicting a quarter of a million numbers to recover ten already in hand loses
accuracy, and video models want a big NVIDIA GPU for days.

### Why anyone does it this way

**The data needs no reward.** A reinforcement learning episode needs a score, and
a score needs someone to have decided what a topple is worth. Push at random,
record what moved, and every push is a usable example. Reinforcement learning's hardest
problem, a reward that cannot be gamed, never arises — and the search over
candidates stays code you wrote, which can say why one was rejected.

### How it would work here

**The model.** A small network from (ten state numbers, four action numbers) to
each glass's *change* in position, so glasses far from the push get zero. On ten
numbers a gradient-boosted tree ensemble competes fairly.

**The data.** Gazebo Harmonic, headless, pushing repeatedly in the same world:
the state after one push starts the next, so reset and settle amortise over a
dozen samples. At four seconds a push, **twenty thousand pushes is twenty-two
hours** — under six across four instances, against reinforcement learning's eleven days.
Random pushes suffice, with the simulator's friction varied between runs.

**Planning against it** is **model predictive control**, or MPC: search for the
next push using the model, execute only the first part of the answer, discard the
rest, search again from a fresh measurement. The simplest search is **random
shooting** — draw a few hundred candidates, roll each through the model, score
the predicted arrangements, execute the best.

**The cross-entropy method**, or CEM, is random shooting three times over. Draw
200 candidates from a broad Gaussian over start point, direction and length.
Score them, keep the best 20 — the **elite set** — refit the Gaussian to those 20
and draw again. After three rounds the elites' mean is the push: 600 batched
passes, milliseconds of CPU.

**Hard constraints stay outside the model.** The tipping check `h < a / μ`, the
zone edges, the 300–780 mm reach ring and the rack filter candidates *before*
scoring, as in solution 3. The model gets no vote on safety.

### The feedback loop

This is not an implementation detail. It is the method.

The model is trusted **one push ahead and no further**. The plan is computed, the
first push executed, everything downstream discarded. The arm takes fresh
pictures, re-runs problem 2's separation, and gets the real arrangement. The next
plan starts from that. A prediction is never fed into another prediction on the
real robot.

So the model is not asked to be right, only right enough to *rank* a few hundred
candidates once, before the world is measured again. A model 6 mm out on every
push still knows that pushing away from a neighbour beats pushing into it, and
each measurement resets the error to zero. **Replanning every step is what makes
a mediocre model useful.**

### A worked example

Five glasses, millimetres from the arm's base, inside the 320 x 360 mm zone.

| Glass | Position | Footprint |
| --- | --- | --- |
| A | (350, −420) | 70 mm |
| B | (430, −190) | 65 mm |
| C | (520, −150) | 90 mm |
| D | (600, −330) | 105 mm |
| E | (500, −380) | 45 mm |

Two pairs are under 140 mm: B–C at 98.5 mm, D–E at 111.8 mm.

**The filter first.** E's base is 45 mm, so `a / μ` at μ = 0.5 is 45 mm, below
the gripper's 50 mm floor. **E is refused by arithmetic**, before the model is
consulted, so D–E can only be fixed by moving D.

**Planning B–C.** CEM draws 200 candidates around C, drops those outside the zone
or inside another glass's clearance, and scores the rest by the smallest pairwise
margin left. The winner pushes C 55 mm along the line from B through C. The model
predicts C lands at **(568, −130)**: 52 mm of travel and 3 mm of drift, not the
straight 55 mm the geometry asked for.

**Execute, then look.** C is actually at **(564, −134)**. The model was 5.7 mm
out. B–C is now 145.2 mm. One push, done.

**Replan from scratch.** D–E is planned from this survey, not from anything
decided before the C push. Pushing D straight away from E lands it on the zone
edge at x = 640, and the filter kills that. Sampling the full circle instead
proposes D pushed 60 mm along (0.6, 0.8), to **(636, −282)** — 167.6 mm from E,
164.6 mm from C. No fixed nudge proposes that direction.

Rolled three deep, push three would start from a state carrying 15 to 20 mm of
error — a quarter of the 70 mm clearance, and why the horizon is one.

### What it needs

**Data.** Twenty thousand simulated pushes, though two thousand may fit a state
this small. Uncertain; a learning curve would settle it.

**Tooling.** [PyTorch](https://pytorch.org/) (BSD-3-Clause) for the network; its
MPS backend uses the Apple Silicon GPU, though a model this small trains on CPU
in minutes. [scikit-learn](https://scikit-learn.org/) (BSD-3-Clause) for the tree
baseline. [Gazebo Harmonic](https://gazebosim.org/) (Apache-2.0) for the data, or
[MuJoCo](https://github.com/google-deepmind/mujoco) (Apache-2.0), native on
Apple Silicon. CEM is thirty lines of NumPy.

**What this machine rules out.** Isaac Sim and Isaac Lab are CUDA-only with no
macOS build; MJX wants JAX on an NVIDIA GPU or a TPU. Video prediction goes with
them, and the published visual-foresight systems are research code, not
libraries, with licences to be read rather than assumed.

### What it is good at

**No friction coefficient and no pressure distribution.** Solution 4's two
missing numbers are absorbed into the fitted weights.

**It improves from real pushes for free.** Every real push yields a
(state, action, next state) triple with no reward and no annotation — exactly the
training data. A policy needs reward-driven retraining; this needs only rows.

### What it is bad at

**Compounding error.** Predictions degrade the further they are rolled, for two
reasons that stack. Each step's error adds to the last, and a predicted state
sits off the states the model was trained on, so step two is asked about a world
it never saw. Hence: plan short, replan often.

**No guarantee.** Solution 4's voting theorem holds for every μ. This holds only
for the pushes it was shown — no bound, no proof, no way to ask how sure it is
short of training an ensemble to disagree. It also learns the simulator's contact
solver, which is reinforcement learning's sim-to-real objection at the same cost.

### How it fails

**Confidently wrong outside what it saw**, and silently. A sixth glass, a 120 mm
footprint, a 150 mm push: the network returns a number with no warning. A rule
refuses; a model extrapolates. The mitigation is a sanity envelope — reject a
predicted displacement larger than the push.

**Plausible-but-wrong ranking.** A mediocre push goes first and is wasted; the
survey catches it, and the next plan comes from the real table.

### When it would be the right choice

When the physics is genuinely unknown *and* the state is short enough to write
down: mixed kinds, objects that rock, wet rings under glasses. There solution 4's
algebra has no inputs, and a fitted model knows what nothing else supplies.

Not here. On five discs of one known kind, what a push does is not the hard part.
The hard part is that it does not land where it was aimed, and the answer to that
is to look afterwards — which solution 3 already does, for one picture.

It is, though, the right *learned* solution for this cell if one is ever wanted:
far cheaper to train than [reinforcement learning](learned-with-hardware.md#learn-to-push), no reward function, safety left in
arithmetic.

---

## Solution 11 — search a push strategy

*Learned, as the decider, without gradients or a neural network. Write the
strategy down with a dozen numbers in it, then search over those numbers in
simulation until it works.*

### What it is

Write the push strategy down as a rule with a handful of numbers in it, then let
the computer choose the numbers. Solution 3 is already such a rule, and its
eight numbers were guessed, not measured.

**Black-box optimisation**, also called **derivative-free optimisation**, is the
tool for that. *Black box* means you can put numbers in and get a score out, and
that is your whole access: you cannot differentiate the function, because
between the numbers and the score sit a motion planner, a contact solver and
five sliding glasses. So you do the only thing left. Try candidates, keep what
works, try more like them. No weights, no gradients, no reward attached to
states — the output is eight numbers you can read.

### Why anyone does it this way

The cost of a search is set by how many free numbers it has, not by how hard the
task is. [reinforcement learning](learned-with-hardware.md#learn-to-push) searches over the weights of a
policy network — hundreds of thousands of them, from noise, with the strategy
itself among the things to be discovered. Hence tens of thousands of episodes.
This starts with the strategy written and leaves eight numbers free. A dozen
parameters rather than a million weights means hundreds of evaluations rather
than tens of thousands, which is hours rather than days. It lets the simulator
pick numbers nobody can guess, because they turn on friction nothing here
measures.

### How it would work here

**The parameters.** Eight, each bounded: which pair first, tightest against
nearest to free space (0–1); which glass of it moves (0–1); overshoot past
140 mm (0–30 mm); clearance above 70 mm (0–25 mm); mm travelled against mm
gained (0–2); standoff (30–90 mm); longest push before it splits (20–80 mm); mm
short of 140 that still counts as done (0–8 mm).

**What is deliberately not a parameter.** The destination tests, the tipping
refusal, the 50 mm floor and the guarded move all stay, and every range above is
one-sided, so a setting can only ask for more margin. The search tunes
preferences *inside* a planner that keeps its vetoes, so **no candidate can
produce an unsafe push, however badly it scores**. A neural policy emits a push
directly and can propose anything, so the geometry is bolted on afterwards — and
that solution grants that the veto, not the policy, then does the safety work.

**The methods**, all CPU-only Python, which matters on a machine with no NVIDIA
GPU.

- **Random search.** Draw settings uniformly, keep the best. Run it first,
  always: it sets the number to beat, and shows whether the score moves with the
  parameters at all.
- **Nelder-Mead.** Nine points crawl downhill by reflecting the worst through
  the middle of the rest. SciPy — https://github.com/scipy/scipy, BSD 3-Clause.
  It sticks on a noisy score.
- **CMA-ES** (covariance matrix adaptation evolution strategy). Hold a cloud of
  probability over the parameters, sample a batch, keep the better half, move
  the cloud towards what helped. The standard answer for five to fifty noisy
  parameters, so the default here. `pycma` — https://github.com/CMA-ES/pycma,
  BSD 3-Clause.
- **Bayesian optimisation with a Gaussian process.** Fit a model of score
  against parameters, with error bars, and evaluate next where it predicts a
  high score or great uncertainty. Fewest evaluations of any of them.
  scikit-optimize — https://github.com/scikit-optimize/scikit-optimize,
  BSD 3-Clause, though maintenance has been intermittent: **uncertain**.
- **Optuna** — https://github.com/optuna/optuna, MIT. Several of these behind
  one interface, with parallel workers and resume.

**The objective.** Reinforcement learning's reward, used as a score: a point per pair
crossing 140 mm, a large fine for a topple, a small fine per push, plus the
shortfall in mm to keep it continuous. A reward is paid per step and must carry
credit back to the action that earned it. This is summed over a whole run, so
nothing needs shaping and nothing can be gamed by it.

**Fixed seeds, and this is the mistake to avoid.** Score every candidate on the
*same* arrangements, drawn once and frozen. Redraw them and a candidate given
easy tables beats a better one given hard tables, so the search follows luck.
Fixed, the gap between two scores is the gap between two strategies. Check the
winner on thirty unseen arrangements too: twelve tables flatter the strategy
tuned on them.

### The feedback loop

The search need not stop when the run starts. Keep the tuned numbers as the
**champion** and a variant as the **challenger**, assign one at random to each
real run, and switch if the challenger is ahead. That is A/B testing, not
training: two fixed strategies on the arrangements that actually occur.

Be concrete, because this is the weak half. Separating a difference of `d`
standard deviations takes about `16 / d²` runs per side: half a standard
deviation is 64 each way, a third is 145 each way — nearly 300 runs. At a
handful of runs a day that is months, and a rare event cannot be tested this way
at all, since telling a 1% topple rate from a 2% one takes thousands. Hence the
continuous score. The loop catches slow drift — a new surface, a worn pad —
eventually, not this week.

### A worked example

Five glasses in the 320x360 mm zone, footprints 45 to 105 mm, 150 to 400 g.

*The budget.* One episode is about twenty seconds, so twelve seeded arrangements
is 240 s: four minutes per candidate on one simulator, **60 s per candidate**
across four headless Gazebo instances. CMA-ES on eight parameters uses a
population of ten, so forty generations is 400 candidates — 24,000 s, **six
hours forty minutes**, 4,800 episodes. Random search first, 100 candidates, is
**under two hours**.

*Against reinforcement learning.* 50,000 episodes at twenty seconds is 1,000,000 s, about
**eleven and a half days**, or 2.9 days across the same four instances. 4,800
episodes against 50,000 is **ten times fewer** — one night against three days —
and that section called 50,000 a floor, so the real gap is probably wider.

*What comes out.* Overshoot 18 mm rather than 20, clearance 6 mm, longest push
35 mm — so two 24 mm pushes with a look between beat one 48 mm push, a claim
nobody at the keyboard could have made.

### What it needs

Solution 3 working, with its constants in one settings object. A headless Gazebo
scenario that resets, spawns from a seed and reports the score, which a policy
would need too. One pip install, no CUDA, one overnight window.

### What it is good at

It is cheap, its cost is known in advance, and it keeps every safety property
the programmed solution has, because it changes no veto. Its output is eight
numbers in a file: readable, diffable, revertible. It tunes against friction it
never measures — what the learned solutions are really selling — and it cannot
be reward-gamed, the score being a whole-run summary.

### What it is bad at

**It cannot invent anything.** A tuned strategy is only as good as the strategy
somebody wrote down. If the right behaviour is to pin a glass against the zone
edge and pivot it, no setting of eight numbers expresses that, and the search
contentedly reports the best of a set that did not contain it. A policy could
in principle find it.

**It is tuned to the simulator's friction constant**, as a policy is, though
milder here, because the vetoes survive a wrong number.

### How it fails

**Overfitting to the batch.** Twelve arrangements are few, and the held-out
thirty are what catch a strategy that has learnt their quirks. The symptom is
twenty good generations that do not reproduce.

**A parameter that sneaks past a veto.** Let the search tune the assumed μ, or
the 70 mm clearance downwards, and the safety argument evaporates.

### When it would be the right choice

Whenever a programmed solution already works and its constants were guessed —
this project's position the day solution 3 runs end to end. It is the cheapest
thing here that gets real benefit out of simulation, and it can be thrown away
if it beats nothing.

It is wrong when the strategy itself is in doubt. If nobody can write a rule
that is even approximately right, there is nothing to tune, and the argument
moves to [reinforcement learning](learned-with-hardware.md#learn-to-push)'s jumble.

## The decision

**Solution 1 first, then solution 3. Solution 7 is the first learned thing
worth adding and solution 8 the second. Solution 9 is what would make the
tipping check honest. Solutions 10 and 11 are the sim-only learned answers, and
neither is needed yet.**

### Do the free thing before the risky thing

Solution 1 is chosen first because it costs nothing and removes work. Every
object racked is an object off the table, so a crowd of five with one bad pair
may solve itself after three ordinary picks. **Touching an object is the only
step in this problem that can topple one**, so doing it fewer times is worth
more than doing it better. It is a prefix, not an alternative.

### Then plan, feel, and look

Solution 3 is chosen over solution 2 for one reason that matters: **a fixed
nudge can push an object into a third object.** Checking the landing spot
against every other object, the zone, the reach and the rack costs four
comparisons of numbers already in hand. It is not more *accurate* — neither
predicts anything, both push and then look.

### Why the verifier first, and the early-abort second

These two are the same idea a second apart, and the second apart is the whole
difference.

**Solution 7** watches what happened after the push. It answers the three
questions the geometry answers badly — moved as intended, moved unexpectedly,
fallen over — and its "I cannot tell" is what sends the arm to a low, side-on
viewpoint that settles it.

**Solution 8** watches the force *during* the push. That makes it the only
thing in this document that can **prevent** a topple rather than report one,
and for a failure that cannot be undone that distinction is worth a great deal.
It is second rather than first only because it is harder: it has a latency
budget, and a model too slow to stop the arm is worthless however accurate.

Both have free labels in simulation, and both need topples produced on purpose,
because they are rare in normal running and the model has to have seen some.

### Why the parameter estimate is the quiet one to want

The tipping check — slide while `h < a / μ` — decides which objects may be
pushed at all, and it currently runs on a **guessed** μ. **Solution 9 replaces
the guess with an estimate and an interval**, and then the check can use the
pessimistic end of the interval.

That is not a more accurate system. It is a *safer* one, and it is the only
entry here that improves a safety decision rather than a performance one.
Solution 5 is its close relative and the difference is worth keeping straight:
solution 5 learns the model's error, solution 9 learns the model's missing
input. The second hands back a number every other part of the system can use.

### What solutions 10 and 11 are for

**Solution 10**, a learned forward model, is the best of the three learned
entries, because a forward model serves any goal while a policy serves the one
it was rewarded for, and because replanning every step makes a mediocre model
useful. If a learned approach were taken here, this would be it.

**Solution 11**, searching a parametric strategy, is the pragmatic one. A dozen
numbers rather than a million weights means hundreds of evaluations rather than
tens of thousands — hours rather than the eleven days that put reinforcement
learning in [`learned-with-hardware.md`](learned-with-hardware.md). And because
the parameters live inside the geometric planner, which keeps its vetoes, no
candidate the search proposes can be unsafe. It is the cheapest way to find out
whether the hand-chosen constants are anywhere near right.

### What would be built, in order

1. **The reachability test** — solution 1. A handful of comparisons, and on
   most runs it may remove the need for everything below it.
2. **The tipping check** from the measured base width. It must exist before
   anything touches an object.
3. **The push**, as a sideways guarded move with the fingers closed.
4. **The destination search** — solution 3's four tests.
5. **The look-again comparison**, geometric to begin with.
6. **The change-verifier** — solution 7 — once runs have been scored and the
   numbers say the geometric comparison misses topples or false-alarms.
7. **The parameter estimate** — solution 9 — after enough pushes have been
   logged, which is the point: it cannot be built first even if you wanted to.
8. **The early-abort** — solution 8 — last, because it is the one with a
   real-time constraint and the most ways to be subtly wrong.

Steps 1 to 5 are programmed. The ordering of 6 to 8 is the argument:
**measure which failure you actually have before choosing a component to fix
it**, and take the cheap observer before the thing that has to act in
milliseconds.

### How it would be known to work

Against the simulator's own record of what it spawned:

- how many objects ended up with the room they need and a usable viewpoint;
- how many pushes it took, and how many were repeats because the first fell
  short;
- how far each object ended up from where the push aimed it — which is also
  solution 5's training signal;
- how many were refused, and for which reason: it tips before it slides, or
  there is nowhere clear to push it to;
- **how many were toppled, which should be none** — and separately, how many
  topples were *caught* by solution 7 and how many were *prevented* by solution
  8. Those are three different numbers and all three matter.
## Where the chosen solution can fail

**μ is guessed, so the tipping check is guessed.** The arithmetic is sound and
one of its two inputs is not measured. Pushing as low as the gripper can reach,
always, is the mitigation. It is not a proof.

**A glass can be pushed somewhere that is clear now and crowded later.** The
destination is chosen against the arrangement as it stands. Replanning after
every push keeps this from compounding, at the cost of more pushes.

**The arm can run out of table.** Five glasses each needing 140 mm of separation
in a zone 320 by 360 mm is close to what fits. With six it may not be solvable
at all, and the honest output is to name the glasses that could not be separated
rather than to shuffle for ever.

**Pushing changes the viewpoints as well as the spacing.** A glass moved to make
room for the gripper can block the line of sight to another one. The loop
catches it, because it re-runs the whole separation each time — but it means the
number of pushes is not bounded by the number of crowded pairs.

**Nothing measures the glass's mass before touching it.** A push is applied to
an object of unknown weight. In the simulator that is harmless. On a real table
a heavy glass resists and a light one skates, and the difference is the same
factor of three that problem 1's step 5 has to weigh for.

← [The problem](../problem.md) · [Problem 4 — several kinds at once](../../problem-4) →

← [The problem](../problem.md) · [The ones that need more than a simulator](learned-with-hardware.md) · [Problem 4 — several kinds at once](../../problem-4) →
