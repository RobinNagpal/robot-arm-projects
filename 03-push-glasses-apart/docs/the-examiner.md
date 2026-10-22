# The examiner — the same question for every answer

## Introduction

This problem is answered several different ways. Answers can only be compared
if they get the same question and the same marking. The examiner is the
program that does both. It draws the crowded tables and holds the physics. It
gives each solution the same measurements, carries out the push that comes
back, and marks the result against what really happened.

This page covers what a solution is given, what the examiner keeps hidden, why
the shared output is a jaw trajectory, why the marking looks only at the
outcome, and the two things this scorecard needs that problem 2's did not.
Read it before any solution document, because every one of them assumes it.

The examiner is built. It lives in `03-push-glasses-apart/bench/`. Every
solution runs on it, and so does problem 5.

## Why there is an examiner at all

The reason is the same as in
[problem 2](../../02-segment-glasses/docs/the-examiner.md#why-there-is-an-examiner-at-all).
The examiner fixes the **input**, the **output** and the **marking**. Only the
part between input and output is left free, and that part is the method. So
when a learned policy clears more tables than a fixed nudge, the difference
comes from the policy, not from an easier table.

## What the examiner draws

The tables come first, because they are the input.

**Every table is crowded on purpose.** It holds four to six glasses of one
kind. The kind and the count change from table to table, so all four kinds
appear in turn: straight, tapered, stemmed and short stemmed. The glasses stand
inside the glass zone. None of them touch.

**The crowding comes from where the glasses stand, not from their shapes.**
The examiner places most glasses close to a glass already down. They are
closer than the gripper can work with, but still not touching. The rest go
anywhere they fit, and some of them are crowded by chance. A table is accepted
only if at least one glass has no room. So doing nothing is never the right
answer.

**A glass has room when no other glass's edge lies within 76 mm of its
middle.** [The problem](problem.md#the-gap-that-matters-is-not-the-gap-between-the-glasses)
explains where 76 mm comes from and why the test is not symmetric.

**The tables are numbered, and the numbers are split.** Each table is drawn
from a single number, so the same number always gives the same table. Any
solution can run on exactly the tables another solution ran on. Numbers above a
fixed line are for testing only. Training draws from below it. So no solution
is marked on a table it was fitted on. This matters here because most of the
solutions are trained.

**The physics is MuJoCo, standing in for Gazebo.** There are two reasons. The
first is speed. A learned solution needs thousands of pushes. Gazebo runs at
real time, so data that MuJoCo makes in hours would take weeks. The second
reason is fairness. Nobody here wrote MuJoCo. If the examiner used a push model
written for this project, a solution built on that same model would win by
knowing the answer. A contact solver nobody here wrote is equally unknown to
every solution.

The glasses are not simplified away. Each one is a stack of cylinders. Each
cylinder is as wide as the glass at its widest point inside it, so the
collision shape is never thinner than the real glass. The bottom cylinder is
the foot, which is the edge the glass tips over.

![Every glass the examiner stands on a table is a stack of cylinders, each one as wide as the glass is anywhere inside it, and the bottom cylinder is the foot it would tip over; the height at which a push starts tipping a glass rather than sliding it follows from that foot and from a friction the examiner keeps to itself.](../images/examiner-the-model-that-was-built.png)

## What a solution is given

With the tables fixed, the next question is what a solution may read from
them.

The examiner offers three calls and nothing else: `look()`, `push()` and
`take()`.

**`look()` returns one reading per glass still on the table.** For each glass:
where it stands, how tall it is, how wide it is at its widest and at its foot,
and whether it is still standing. That is the whole input. It is the same list
that problem 2's camera work produces, so this problem starts where that one
ended.

**Each reading carries problem 2's measured error.** The examiner adds a small
random error to the position, both widths and the height. The sizes come from
what problem 2's programmed solution really scored. The width error is the
largest and the position error is the smallest. The error is new on every
look, so looking twice is useful. But it is drawn from the table's number and
the look's number. So the first look at a table is the same for every solution.

**Solutions that read pictures also get a top-down view of the same table.**
Three of the six read pictures, not numbers. A picture of the same table at the
same moment keeps the input the same information in a different form. It is
built in `bench/top_view.py`. A camera sits 750 mm above the middle of the
glass zone, looking straight down. It returns a 384 by 384 RGB picture of the
whole zone. It is separate from the camera that `film.py` uses, which only
exists for watching a run.

The two are kept apart on purpose. A solution that reads a picture decides from
what is in it. If filming added anything to the world, a filmed table could
differ from the scored table. So the film is drawn in a second world of its
own, which is never stepped. The scored world is the same whether a table is
filmed or not. The bench's tests check this. They run one table both ways and
require every glass to end in the same place.

**A solution is never given the simulator's record.** The examiner knows each
glass's true position, shape and mass, and keeps them. Only the scoring code
reads them, after the run. A learned solution may use them as training labels
on training tables. Nothing reads them while answering.

**A solution is also never given the friction.** The examiner holds three
values privately: glass on table, glass on glass, and the jaw's aluminium and
silicone on glass. Every table uses the same three. They are hidden because
**nothing in the cell measures friction**. This one hidden number is what makes
the problem hard. [Pushing without toppling](pushing-without-toppling.md#the-number-nobody-has)
explains why.

## What `push()` does, and what it reports back

`look()` tells a solution where things are. `push()` is the only way to change
them.

One push runs as a fixed sequence:

1. The closed jaw is held level, pointing the way it will travel.
2. It comes down at the chosen start point, to the lowest height the gripper
   can reach.
3. It moves forward very slowly until the force passes a small threshold. That
   means it has touched something.
4. It pushes the asked-for distance at a steady speed.
5. It backs off a couple of centimetres and lifts clear above the tallest
   glass.

Three things can interrupt this. The jaw can touch something on the way down;
then it goes straight back up without pushing. It can reach the end of its
forward feel without touching anything. Or the force can pass a much higher
threshold during the push; then something is wedged, and the push stops.

**The push then reports what it felt.** This report is the only thing that
comes back. It says whether the jaw was blocked on the way down, how far it
moved before touching (or that it never touched), whether it jammed, the
largest force it felt, and how far it moved after touching.

**The force reading is the only way to observe friction at all.** The topple
limit needs the friction, and a solution cannot know it. But the force needed
to start a glass moving, and how far the glass went, both depend on the
friction. A glass that leaned and fell back felt different from one that slid.
Every solution that beats a blind nudge does it by reading this signal. An
examiner that reported only success or failure would hide the interesting half
of the problem.

`take()` is the third call. It lifts a glass off the table and racks it. This
is problem 1's job, done for free here. The examiner records whether the glass
really had room when it was taken. The marking later uses that record.

**"For free" hides something.** `take()` asks one question: did this glass have
room? If yes, the glass leaves the table. It never asks whether problem 1 could
really pick that glass up. The two questions differ a lot. Problem 1's own grip
rule, asked about each of the 251 held-out glasses with the real gripper's
measurements, **finds somewhere to hold only 97 of them**. The most common
reason is reach, not width. The tool comes in level. The force sensor behind
the fingers hangs below the tool's axis. So the pads cannot go lower than 50 mm
up the glass without the sensor hitting the table. A glass with nothing to hold
between 50 mm and halfway up is refused.

This is a limit of problem 1, not of problem 3.
[known-gaps.md](../../01-rack-one-glass/docs/known-gaps.md) already records it. It is noted here because
the scorecard's word *racked* assumes a pick that often could not happen. No
score depends on it, because every solution is marked the same way. The films
draw the pick as a plain stand-in and say on screen that problem 1 does the
real one.

**Room around a glass is also not the same as a way in for the hand.** This is
the examiner's own assumption. `has_room()` asks whether anything stands within
a radius of the glass. That is the right question for a hand coming straight
down. But the hand comes in level, and it is 266 mm long from fingertips to the
back of the force sensor. So it needs a corridor across the table, not a circle
round one glass. On a crowded table, most sides are blocked by something
outside the radius `has_room()` checks. Over twenty of the fifty tables, every
side was checked for the glasses the examiner says have room. **A clear way in
exists for 14 of 19, and the hand would have to stop short for the other 5.**

The films check the same thing before they draw a pick. They come in from a
clear side when there is one. When there is none, they draw the hand stopping
where it would touch, and say so on screen. Across the six films, eleven picks
are drawn and one stops short. That is fewer than above, because by the time a
glass is racked its neighbours have already been pushed away.

## The shared output, and why it is a jaw trajectory

The input and the physics are now fixed. The last question is what a solution
hands back. The six do not naturally hand back the same kind of thing, so this
is the most important decision here.

**The shared output is a jaw trajectory**: a path for the jaw to follow.

Some solutions think in a **parameterised push**: a few numbers saying which
glass, where to put the fingertips down, which way to point, how far to feel
forward and how far to push. `push()` accepts exactly that and turns it into
the sequence above. So **the examiner owns the step that expands a push into a
trajectory**. Every push is expanded by the same code, so no solution gains or
loses anything there.

Other solutions think in trajectories already. A modern imitation policy emits
an **action chunk**: a short run of waypoints predicted together in one pass.
Those solutions give their waypoints directly, and the examiner carries them
out with no expansion.

The obvious alternative would be to make every solution emit the same few push
numbers. That sounds fair but is not. **It would destroy the action chunking
that makes those policies work.** Chunking is how they stay steady over a
motion instead of wobbling from step to step. Squeeze such a policy down to
three numbers and you measure a damaged version of it. A comparison is only
worth running if each side can be itself.

Both paths are built. `push()` takes the parameterised push. `follow()` takes a
`Chunk` of jaw waypoints and carries them out in the same physics. It reports
the same `Felt` into the same record, so the scorecard cannot tell which path
an action used. The examiner also records the path the jaw really followed on
every action, at a fixed rate. That record turns a parameterised push into a
demonstration that a waypoint policy can learn from.

## The score is the outcome, not the action

Two kinds of output raise an obvious question. If one solution gives three
numbers and another gives twenty waypoints, how can they be compared?

The answer is that **the examiner never marks the action**. It does not judge
the heading or the smoothness of the waypoints. It looks only at the table
afterwards: which glasses have room, which are standing, where each one ended,
and how many pushes it took.

Marking the action would need one fair language for every kind of action, and
there is none. Marking the table needs no such language, because the table is
the same table either way. Both solutions answer the one question the problem
cares about: are the glasses far enough apart, and is everything still
standing?

## What the examiner measures

The scoring code reads the simulator's record after a run. It turns it into one
scorecard, in the same shape for every solution.

**Each table gets one of three outcomes**, as [the problem](problem.md#what-done-means)
defines them. A table is **done** when every glass was racked while it really
had room. It is **correct but incomplete** when some glasses are left, each
with a reason, and nothing went wrong. It is **wrong** when anything went
wrong.

**Each glass is then counted on its own.** A glass may be racked, refused with
a reason, or wrong in one of several ways. The problem names three wrong
endings: **toppled**, **pushed off the table**, and **pushed into the rack**.
The examiner detects toppling by how far the glass leans. The other two are the
same test: the glass **left the glass zone**. The examiner adds two wrong
endings of its own. A glass **picked without room** is one the arm thought it
could grip when it could not. A glass **left with no reason** is one abandoned
in silence.

**Glasses grippable at the end** is the measurement the problem is really
about. The examiner gets it from racking, not from measuring gaps. A glass
counts as racked only if it had real room when taken. So a run that clears the
table has shown grippability, not claimed it.

**Pushes are counted against a budget.** The scorecard records the total
pushes, the repeat pushes on a glass already pushed, and the pushes that went
wrong: blocked on the way down, never touching, or jamming. The budget is a
fixed maximum per glass and per table. After it, the remaining glasses must be
refused. It used to live in each solution's own runner, so the counts were not
comparable. It now lives in the examiner, as `PUSHES_PER_GLASS` and
`PUSHES_PER_TABLE`. One solution predates it: the fixed nudge spends 3 and 15
rather than 4 and 16, because its committed scorecard was measured at those
values.

**Refusals are counted with their reason.** A refusal is a result, not a
failure. The examiner groups refusals by reason. A solution that refuses the
glasses it should refuse scores *correct but incomplete*, which is good. A
solution that leaves the same glasses with no reason scores *wrong*.
[Pushing without toppling](pushing-without-toppling.md#some-glasses-cannot-be-pushed-at-all)
explains why some glasses must be refused.

**The examiner records how far each glass ended from where the push aimed
it.** Every push carries the place the solution expected the glass to arrive.
Once the glass settles, the examiner measures the real distance, and reports
the middle value and the worst. This is **a reference, not a pass mark**. The
problem never asks for glasses to be in a particular place. The number shows
how well a solution predicts a push. Glasses that land near their aim mean the
method understands pushing. Glasses that scatter mean it succeeds by looking
again instead. That is a real strategy too, just a different one.

**The examiner adds up how far the glasses really moved**, over every push and
table. On its own that total says little, because pushing nothing scores best.
It means something next to the **displacement floor**, the least movement any
legal layout of the same glasses needs. [The target layout](the-target-layout.md#the-displacement-floor)
computes the floor and explains how to read a solution against it.

## Two things this scorecard needs that problem 2's did not

Problem 2's examiner could run each solution once. This one cannot, for two
reasons. Both come from most solutions here being trained rather than written.
Both are now in `scoring.py`. `Repeats` holds several evaluation runs and
reports the spread of every number. `Scorecard` reports the time per push
beside the counts.

**One run is not a measurement.** The learned policies here are random: asked
the same question twice, they may act differently. Training also varies with
its random seed, so the same method trained twice gives two policies of
different quality. This variation is sometimes **larger than the gap between
two methods**. Then a single run of each can name the wrong winner, with no
sign of doubt. So each trained solution is trained with several seeds and run
several times, and the scorecard reports the **spread**, not only the middle.
A result without a spread is not a result. A method that wins by less than its
own spread has not been shown to win.

**Running cost differs hugely, so it belongs on the scorecard.** A fixed nudge
is arithmetic and costs almost nothing. A planner with a learned world model
tries many candidate actions through the model before each push. That costs
hundreds or thousands of times more. A foundation model is one large network
pass, which usually needs rented hardware. **A solution that wins while taking
a hundred times longer has not clearly won.** On a real arm it may not be
usable at all. So each solution states what it needs and roughly what renting
it costs, as it states its licence. The time per push sits on the scorecard
beside the counts.

## Where to go next

- [The problem](problem.md): why dragging rather than lifting, the three
  distances that matter, and what "done" means.
- [The target layout](the-target-layout.md): where the glasses should end up,
  and the least movement the task needs.
- [Pushing without toppling](pushing-without-toppling.md): how low a push must
  be, the refusal path, and the loop of plan, feel and look again.
- [The solutions](solutions/overview.md): what each method puts between the
  input and the output.
