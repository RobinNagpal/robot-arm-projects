# The test bench — the same question for every answer

## Introduction

This problem is answered six different ways, and six answers are only
comparable if they were asked the same question and marked by the same
examiner. The test bench is that examiner. It draws the crowded tables, holds
the physics the glasses slide and tip in, hands each solution the same
measurements, carries out whatever push comes back, and then marks the result
against what it knows really happened. By the end of this document you will
understand what a solution is given, what the bench keeps to itself, why the
shared output is a jaw trajectory rather than a push, why the marking looks at
the outcome and never at the action, and which two things this scorecard needs
that problem 2's did not.

Read this before any of the solution documents, because every one of them
assumes it.

The bench is built. It lives in `03-push-glasses-apart/bench/`, and all six
solutions run on it, as does problem 4.

## Why there is a bench at all

Without one, each of the six would arrive with its own tables, its own idea of
a good push and its own way of counting success, and nothing could be concluded
by setting their results side by side. The bench exists to remove every
difference between the six except the one being studied.

It does that by holding three things fixed. The **input** is the same
measurements of the same tables, in the same order. The **output** is the same
kind of thing, carried out by the same machinery. The **marking** is the same
set of counts, computed the same way. Everything a solution is free to change
sits between the input and the output, and that middle part is exactly what we
want to compare. So when a learned policy clears more tables than a fixed
nudge, the difference belongs to the policy and not to a kinder table or a
gentler scorecard.

## What the bench draws

The tables are the first of those three fixed things, so they come first.

**Every table is crowded on purpose.** It holds four to six glasses of one
kind, with the kind and the count cycling from one table to the next so that
all four kinds are met in turn — the straight glass, the tapered glass, the
stemmed glass and the short stemmed glass. The glasses stand inside the glass
zone, and none of them touch: there is always a little daylight between any
two.

**The crowding comes from where the glasses are stood, not from their
shapes.** When the bench places a glass, it mostly stands it deliberately
close to a glass already down — closer than the gripper can work with, but
still not touching. The rest go anywhere on the glass zone they fit, which
crowds some of them as well by accident. A table is only accepted if at least
one glass on it has no room, so there is never a table where the right answer
is to do nothing.

**Having room is a test on a pair, and it is not symmetric.** A glass has room
when no other glass's edge lies within 70 mm of its middle. That 70 mm is the
gripper's own number, described in [the problem](problem.md): half the widest
jaw opening, a finger and a pad on each side, and a little to spare. Because
the test measures to the neighbour's *edge*, a narrow glass standing beside a
wide one is crowded before the wide one is, and a solution that only looks at
distances between middles will get that case wrong.

**The tables are numbered, and the numbers are split.** Each table is drawn
from a single number, so the same number always gives the same table, and any
solution can be run on exactly the tables another was run on. Numbers above a
fixed dividing line are for testing only; training draws from below it. This
means no solution is ever marked on a table it was fitted on, which matters
here more than it did in problem 2, because four of the six solutions are
trained.

**The physics is MuJoCo, standing in for Gazebo.** There are two reasons, and
the bench's own description gives both. The first is speed: a learned approach
needs thousands of pushes, and Gazebo runs each one at the speed of real time,
so a training set that MuJoCo produces in hours would take weeks. The second
reason is fairness, and it is the more interesting one. MuJoCo is physics that
neither approach wrote. If the bench pushed glasses around using a push model
written for this project, then a programmed solution built on that same model
would win by knowing the answer, and the comparison would measure nothing. A
contact solver nobody here authored is a thing both sides are equally ignorant
of.

The glasses in it are not simplified away. Each one is built as a stack of
cylinders, each cylinder as wide as the glass is at its widest anywhere inside
it, so the collision shape is never thinner than the real glass. The bottom
cylinder is the foot, which is the edge the glass tips over.

![Every glass the bench stands on a table is a stack of cylinders, each one as wide as the glass is anywhere inside it, and the bottom cylinder is the foot it would tip over; the height at which a push starts tipping a glass rather than sliding it follows from that foot and from a friction the bench keeps to itself.](../../images/03-push-glasses-apart/04-the-model-that-was-built.png)

## What a solution is given

Given those tables, the next fixed thing is what a solution may read off them.

The bench offers exactly three calls and nothing else: `look()`, `push()` and
`take()`.

**`look()` returns one reading per glass still on the table.** For each glass:
where it stands, how tall it is, how wide it is at its widest, how wide it is
at its foot, and whether it is still standing. That is the whole input. It is
the same list of facts problem 2's camera work produces, which is why this
problem can begin where that one ended.

**Each reading carries problem 2's measured error.** The numbers are not the
true ones. The bench adds a small random error to the position, to both widths
and to the height, with sizes taken from what problem 2's programmed solution
actually scored — the width error being the largest of the three, and the
position error the smallest. The error is fresh on every look, so looking twice
is worth something, but it is drawn from the table's number and the number of
the look, which means the first look at a given table is identical for all six
solutions. Nobody gets an easier first measurement than anybody else.

**Solutions that read pictures also get a rendered top-down view of the same
table.** Three of the six read pictures rather than numbers — an imitation
policy trained on images, and the two vision-language models — so a list of
numbers is not an input they can use. Giving them a picture rendered by the
bench, of the same table at the same moment, keeps the input the same
information in a different form. This is now built, in `bench/top_view.py`: a
camera fixed 750 mm above the middle of the glass zone, looking straight down,
returning a 384 by 384 RGB picture that frames the whole zone. It is separate
from the camera `film.py` uses, which looks steeply down from the arm's side
and exists only for watching a run by eye.

**What a solution is never given is the simulator's record.** The bench knows
each glass's true position, its true shape and its mass, and it keeps all of
it. Only the scoring code reads those, and only after a run has finished. A
learned solution may use them as training labels on the training tables, but
nothing reads them while answering, because a solution that read the truth
would not be answering this problem.

**It is also never given the friction.** The bench holds three coefficients
privately: glass on the table, glass on glass, and the jaw's own aluminium and
silicone on glass. Every table uses the same three. They are hidden because
hiding them is honest — **nothing in the cell measures friction**. There is no
sensor for it, and there is no way to find it out. This single omission is
what makes the problem hard, for the reason the next section explains.

## What `push()` does, and what it reports back

`look()` tells a solution where things are; `push()` is the only way it can
change them.

One push runs as a fixed sequence. The closed jaw is held level, pointing the
way it will travel. It comes down at the start point the solution chose, to the
lowest height the gripper can reach. It then feels forward very slowly
until the force it feels passes a small threshold, which means it has touched
something. From there it pushes the asked-for distance at a steady speed, backs
off a couple of centimetres, and lifts clear to a travel height above the
tallest glass. Three things can interrupt this: the jaw can touch something on
the way down, in which case it goes straight back up without pushing at all; it
can reach the end of its forward feel without ever touching anything; or the
force can pass a much higher threshold during the push, which means something
is wedged, and the push stops where it is.

**The push then reports what it felt**, and this report is the only thing that
comes back. It says whether the jaw was blocked on the way down, how far
forward it travelled before touching or that it never touched, whether it
jammed, the most force it felt at any moment, and how far it actually moved
after touching.

That force reading is more important than it looks, and it is worth being
precise about why. The rule that decides whether a pushed glass slides or tips
over compares the push height against half the glass's base width divided by
the friction coefficient — and the height that counts is the **top edge of the
jaw**, not its middle, because a glass that is wider higher up meets the top
edge first. A solution can measure the base width, because `look()` gives it.
It knows the jaw's top edge, because that is the gripper's own number. The one
term it cannot have is the friction. So the rule gives a limit that is only as
good as a guessed number.

**This means the force reading is the only channel through which friction is
observable at all.** How much force it took to start the glass moving, and how
far the glass went for that push, are consequences of the friction, so they are
indirect evidence about it. A glass that leaned and fell back where it stood
felt different from one that slid. Every solution that does better than a blind
nudge does so by reading that channel, either by reasoning about it or by
learning from it, which is why a bench that reported only success or failure
would have made the interesting half of this problem invisible.

`take()` is the third call. It lifts a glass off the table and racks it, which
is problem 1's job done for free here, and the bench quietly records whether
the glass really had room at the moment it was taken. That recording is how the
marking later knows whether the arm's own belief about room was correct.

## The shared output, and why it is a jaw trajectory

The input is now fixed and the physics is fixed, so the remaining question is
what a solution hands back. This is the most important decision in the whole
arrangement, because the six do not naturally hand back the same kind of thing.

**The shared output is a jaw trajectory**: a path for the jaw to follow.

Some of the six do not think in trajectories at all. A geometric solution
thinks in a **parameterised push** — a handful of numbers saying which glass
to move, where to put the fingertips down, which way to point, how far to feel
forward and how far to push. That is exactly what the bench's `push()` already
accepts today, and `push()` itself is the machinery that turns those numbers
into the descend, feel, push, back off and lift described above. So **the
expansion from a push into a trajectory is a macro the bench owns**, not
something a solution writes. Every parameterised push is expanded the same way,
by the same code, so no solution gains or loses anything in that step.

Other solutions think in trajectories natively. A modern imitation policy does
not emit one target at a time; it emits an **action chunk**, which is a short
run of consecutive waypoints predicted together in one forward pass. Those
solutions emit their waypoints directly, and the bench carries them out without
an expansion step, because there is nothing to expand.

It is worth saying plainly why the obvious alternative would be worse. The
bench could insist that every solution emit the same small set of push
parameters, which sounds like the fairest possible rule. It would in fact be
the unfair one, because **it would destroy the action chunking that makes those
policies work**. Predicting a chunk is not a convenience in these
architectures; it is the mechanism by which they stay consistent over a motion
instead of wobbling from one step to the next. Squeeze such a policy down to
three numbers and you have not made it comparable, you have crippled it — and
what you then measure is a damaged version of the method rather than the method
that exists. A comparison is only worth running if each side is allowed to be
itself.

Both paths are now built. `push()` takes the parameterised push and owns its
expansion; `follow()` takes a `Chunk` of jaw waypoints and carries them out in
the same physics, reporting the same `Felt` into the same record, so the
scorecard cannot tell which door an action came through. The bench also writes
down the path the jaw really followed on every action, sampled at a fixed rate,
which is what turns a parameterised push into a demonstration a policy that
emits waypoints can be trained on.

## The score is the outcome, not the action

Allowing two different kinds of output raises an obvious objection: if one
solution hands over three numbers and another hands over twenty waypoints, how
can their results be compared at all?

The answer is that **the bench never marks the action**. It does not ask
whether a push was the push it would have chosen, whether the heading was
sensible, or whether the waypoints were smooth. It looks only at the state of
the table afterwards: which glasses have room, which are still standing, where
each one ended up, and how many pushes it took to get there.

This is what makes the two outputs comparable. A score that looked at the
action would need a single language to express every action in, and there is no
such language that is fair to both a three-number push and a learned chunk of
waypoints. A score that looks at the table needs no such language, because the
table is the same table either way. Both solutions are asked the one question
that the problem actually cares about: are the glasses far enough apart now,
and is everything still standing?

## What the bench measures

The scoring code reads the simulator's record after a run has finished and
turns it into one scorecard, in the same shape for every solution.

**Each table gets one of three outcomes**, which are the three
[the problem](problem.md) defines. A table is **done** when every glass was
racked, and each one was racked while it really had room. It is **correct but
incomplete** when some glasses are still on the table, each one reported with a
reason, and nothing went wrong. It is **wrong** when anything went wrong at
all.

**Each glass is then counted individually**, which is where the detail lives.
A glass may have been racked; or refused with a reason; or it may have gone
wrong in one of several ways. The problem names three wrong endings — a glass
**toppled**, a glass **pushed off the table**, and a glass **pushed into the
rack** — and the bench detects all three with two tests. Toppling it decides
by how far the glass leans from upright. The other two are the same thing
geometrically, because in both the glass has ended up outside the region it
was allowed to be in, so one test covers them: the glass **left the glass
zone**. The bench adds two more wrong endings of its own. A glass **picked
without room** is one the arm believed it could grip when it could not, which
is a mistake the arm would not otherwise notice. A glass **left with no
reason** is one abandoned on the table in silence.

**Glasses grippable at the end** is the measurement the problem is really
about, and the bench gets it from racking rather than by measuring gaps. A
glass is only counted as racked if it had genuine room at the moment it was
taken, so a run that clears the table has demonstrated grippability rather than
asserted it.

**Pushes are counted against a budget.** The scorecard records how many pushes
were spent in total, how many of them were repeat pushes on a glass already
pushed, and how many went wrong in each of the ways a push can: blocked on the
way down, never touching anything, or jamming. The budget itself — a fixed
maximum per glass and per table, after which the remaining glasses must be
refused — used to live in the code that drives each run, so the counts were not
comparable. It now lives in the bench, as `PUSHES_PER_GLASS` and
`PUSHES_PER_TABLE`, so all six are given the same number. One solution predates
it: the fixed nudge spends 3 and 15 rather than 4 and 16, because its committed
scorecard was measured at those and would change under the shared budget.

**Refusals are counted with their reason, and a refusal is a result rather
than a failure.** Some glasses cannot be pushed safely at all, because they tip
before they slide, and for those the only correct answer is to refuse. So the
bench groups refusals by the reason given and reports the groups. A solution
that refuses the glasses it should refuse scores *correct but incomplete*,
which is a good outcome; a solution that quietly leaves those same glasses with
no reason scores *wrong*. Saying "I cannot do this, and here is why" is part of
the answer.

**Finally, the bench records how far each glass ended from where the push aimed
it.** Every push carries the place the solution expected the glass to arrive,
and once the glass has settled the bench measures the real distance between the
two, reporting the middle value and the worst. For most of the six that
expected place comes from [the target layout](the-target-layout.md), which
computes where the glasses should end up. This number is a **reference and not
a pass mark**. A push that lands some way from its aim is not wrong, because
the problem never asked for the glasses to be anywhere in particular — only
far enough apart. What the number is good for is reading a solution's own
model of pushing: a method whose glasses land close to its aim understands
what a push does, and a method whose glasses scatter is succeeding by looking
again rather than by predicting, which is a real strategy but a different
one.

## Two things this scorecard needs that problem 2's did not

Problem 2's bench could run each solution once and read the result. This one
cannot, and there are two reasons. Both are consequences of four of the six
solutions being trained rather than written, and both are now in `scoring.py`:
`Repeats` holds several evaluation runs and reports the spread across every
number, and `Scorecard` reports the time per push beside the counts.

**One run is not a measurement.** The learned policies here are stochastic:
asked the same question twice they may act differently, because the action is
drawn rather than computed. On top of that, training itself varies with its own
random seed, so the same method trained twice gives two different policies of
different quality. The uncomfortable part is that this variation is sometimes
**larger than the gap between two methods**, which means a single run of each
can easily report the wrong winner — and report it with no sign that anything
is uncertain. So each trained solution has to be trained with several seeds and
evaluated over several runs, and the scorecard has to carry the **spread** and
not only the middle. A result quoted without a spread is not a result. A method
that wins by less than its own spread has not been shown to win.

**Running cost differs by orders of magnitude, so it belongs on the
scorecard.** The six are not equally expensive to run for a single push, and
the range is enormous. A fixed nudge is arithmetic and costs essentially
nothing. A planner that uses a learned world model searches over candidate
actions at run time, simulating each one forward through the model before
committing, so its cost per push is hundreds or thousands of times the
arithmetic. A foundation model is a large neural network forward pass, which
is a different kind of expense again, and one that usually needs rented
hardware. Leaving this out would make the scorecard misleading, because **a
solution that wins while taking a hundred times longer has not obviously
won** — on a real arm it may not be runnable at all, and the honest comparison
is not "which scored best" but "which scored best for what it cost". So each
solution reports what it needs and roughly what renting that costs, in the same
way its licence is stated, and the time per push sits on the scorecard beside
the counts.

## Where to go next

- [The problem](problem.md) — why dragging rather than lifting, the three
  distances that matter, and what "done" means.
- [The target layout](the-target-layout.md) — where the glasses should end up,
  computed rather than learned, and the least movement the task needs.
- [Pushing without toppling](pushing-without-toppling.md) — how low the push
  has to be, why that is a property of the glass, the refusal path, and the
  loop of plan, feel and look again.
- [The six solutions](solutions/overview.md) — what each method puts between
  the input and the output.
