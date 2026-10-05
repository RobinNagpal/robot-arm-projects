# Solution 1 — one fixed nudge

> **What it uses** — NumPy for the arithmetic over a handful of positions and
> widths, and nothing else. Carrying the jaw to the places the arithmetic names
> belongs to the cell rather than to this solution: on the test bench the
> physics engine does it, and in the real cell MoveIt does.
> There is no model, no weights file, no training set and no licence
> condition, because not one number in this solution was fitted to anything.
> **What it does** — When a glass has no clear room for the gripper to close
> round it, the method finds the one neighbour whose edge reaches furthest
> into that room, works out how much room the glass is short of, and pushes
> the glass directly away from that neighbour by a fixed fraction of the
> shortfall, at the lowest height the gripper can reach. Then it looks at the
> table again and does the same arithmetic on what it now sees. There is no
> search over directions, no map of the free table, and above all no model of
> what a push does: the method never predicts where the glass will land, so it
> repeats instead of predicting. The repeating ends when every glass has room,
> when the push budget is spent, or when the only honest answer left is a
> refusal.
> **How the output is produced** — from the measurements, compute for each
> glass how much clear room it is short of, measured to each neighbour's edge;
> take the glass with the worst shortfall and the neighbour responsible for
> it; check that glass against the tipping rule and refuse it if it fails;
> point the jaw along the line that runs from the neighbour's middle through
> the glass's middle; set the travel to a fixed fraction of the shortfall; put
> the start point on that same line, a little outside the glass's widest part;
> and hand the result over as one parameterised push, which the bench's own
> macro expands into a jaw trajectory. Then look again and start over.
> **How it differs from the other five** — solution 2 has geometry generate
> many candidate pushes and fits gradient-boosted trees to rank them, so it
> searches where this one computes one answer; solution 3 fits ACT, and then
> Diffusion Policy, to demonstrations and emits a chunk of waypoints rather
> than a push; solution 4 learns a model of what a push does and plans through
> it at run time, which buys exactly the prediction this one refuses to make;
> solution 5 runs SmolVLA as it downloads, so like this one it fits nothing
> here, but it carries 450 million parameters somebody else fitted on 487
> community datasets; and solution 6 is that same SmolVLA with its training
> continued here by low-rank adaptation, which makes it and solution 5 the
> sharpest pair in the set. This one is the only solution that holds no fitted
> numbers at all, and the only one that makes no claim whatever about where a
> pushed glass will go.
> **What it costs** — no data, because nothing learns; no training time, for
> the same reason; no accelerator to rent, so nothing to pay a cloud provider,
> because the whole computation is a few hundred arithmetic operations on four
> to six glasses and it finishes long before the arm has moved; and no licence
> condition, because the two libraries are already in the cell and neither
> constrains what is done with them. The entire cost is arm time, paid in
> pushes and in looks.

> **The cell is described once, in [the cell](../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the
> side, all four sensors, and the words this project uses them with. What
> follows is only what is specific to this solution.

## Introduction

This document describes the simplest thing that can move a crowded glass away
from its neighbour, and then argues that the set of six would be worthless
without it. The method is one subtraction, one multiplication and a loop. It
measures how much clear room a glass is short of, pushes that glass a fixed
fraction of the shortfall straight away from whatever is crowding it, and
looks again. Nothing in it was fitted, nothing in it was searched for, and
nothing in it predicts anything.

The reason to write it carefully rather than wave at it is that it is **the
control**. Four of the other five solutions pay for their answers with
labelled data, training runs and rented hardware, and the fifth carries a
large model somebody else paid for. None of those prices can be judged in the
abstract. They can only be judged against what the same table costs when
nobody pays anything at all, and that is the number this document is here to
define. Every other solution in the set has to beat a fixed nudge, and if it
cannot, it has earned nothing.

By the end you will understand what the shortfall is and why it is measured to
the neighbour's edge rather than to its middle, which makes the test on a pair
of glasses asymmetric. You will understand what closed-loop control is, in
plain words and as a piece of programming, and why this solution is nothing
else. You will understand why pushing a fraction of the gap converges where
pushing the whole gap overshoots, and why that argument rests entirely on
nobody knowing the friction. You will understand why never predicting means
never being wrong about physics the method never claimed to know, and what
that costs, which is pushes rather than error. And you will understand the one
thing this solution cannot do that its nearest neighbour in the set can: it
produces no scored candidates, so it is the teacher for nobody.

Two honest notes before the method starts, because both change how the rest
should be read.

**Part of this solution is built and part of it is a design**, and the two are
separated plainly in [what is built and what is a
design](#what-is-built-and-what-is-a-design). The bench, the room test, the
tipping rule and the loop all exist in this repository and have been run. The
particular rule for choosing a direction and a distance that this document
describes is a design that would sit inside them.

**No glass's size appears below.** The cell's rule is that no glass's
dimensions are written down anywhere, so this document speaks in relations —
wider than its neighbour, standing on the narrowest foot its kind allows — and
quotes numbers only where they belong to the gripper, to the cell, or to a
results file in the repository.

## The code at the heart of it

Two pieces of this solution are written and running in the repository, and they
belong together, so they are worth reading before the prose explains them. The
first decides whether a glass can be pushed at all: a few lines of arithmetic
on the glass's own foot and height that answer "yes", "no" or "not without
trying it". The second is the one small fixed push the method makes when the
answer is the third of those. They are the heart of this solution because the
arithmetic is the piece [solution 2](02-geometry-ranked.md) and three of the
others borrow rather than write again, and because the small push is the only
place in the whole method where the arm reads the world before committing to a
decision rather than after it.

The tipping test, from
[`03-push-glasses-apart/01-one-fixed-nudge/plan.py`](../../../03-push-glasses-apart/01-one-fixed-nudge/plan.py).
No library decides anything in it. The whole of it is a few divisions, two
comparisons and two arctangents from Python's own `math`, which is the plainest
illustration of what this solution being the control means.

```python
# Glass on a dry wooden top is somewhere in here. Nothing in the cell measures
# it, so the tipping check is made at both ends.
MU_LOWEST = 0.2
MU_HIGHEST = 0.5
...
def slides(glass: Seen) -> str:
    """Whether a push at the jaw's top edge slides this glass: "yes", "no" or "try".

    It slides while the push is lower than a / mu: half the foot, over the
    friction. The top edge, because a glass wider higher up meets the jaw
    there first. "try" means it depends on the friction, and a probe is safe.
    """
    half_foot = glass.foot / 2
    if half_foot / MU_HIGHEST > JAW_TOP:
        return "yes"
    if half_foot / MU_LOWEST <= JAW_TOP:
        return "no"
    falls_past = math.atan2(half_foot, CENTRE_OF_MASS_SHARE * glass.height)
    return "try" if math.atan2(PROBE, JAW_TOP) < PROBE_LEAN_SHARE * falls_past else "no"
```

A glass that comes back "try" gets the fixed nudge, which is the same file's
`probe`: the chosen push cut down to one constant length, aimed along the same
line, and looked at before and after. NumPy appears here, and only to turn a
heading into a unit vector.

```python
# A glass that slides only at the low end is tried with a push this long, and
# looked at before and after. Short pushes lose up to 2.5 mm to the contact
# taking up and the glass settling onto its far edge, so this is well over that.
PROBE = 0.005
...
def probe(push: Push) -> Push:
    """The same push, cut down to PROBE."""
    u = np.array([math.cos(push.heading), math.sin(push.heading)])
    middle = np.array(push.aim) - push.travel * u
    aim = middle + PROBE * u
    return Push(push.glass, push.start, push.heading, push.reach, PROBE, (float(aim[0]), float(aim[1])))


def needs_probe(glass: Seen, proven: set[int]) -> bool:
    return slides(glass) == "try" and glass.id not in proven
```

Read together, the two blocks show the whole bargain of this solution in a
dozen lines: where the arithmetic can answer, it answers, and where it cannot —
because the friction is missing from it — the method spends one short push to
find out instead of guessing. Note which fixed nudge this is. The proportional
nudge of [the main idea](#the-main-idea) has no constant in the repository,
while `PROBE` does, so the fixed length above is the one this code really
commits to.

## The problem this solves

[Problem 3](../problem.md) begins where problem 2 ended. The arm knows where
every glass stands, how tall it is, how wide it is at its widest and how wide
it is at its foot, and every one of those readings carries a measurement error
rather than being exact. Some of the glasses stand close enough together that
the open jaw cannot get round one of them without fouling the one beside it,
and the arm has to move them apart by dragging them across the table rather
than by lifting them.

What makes that a problem rather than an exercise is one missing number. A
pushed glass slides while the jaw touches it below a height set by its own foot
and by the friction between the glass and the table, and tips above that
height, which is the whole subject of [pushing without
toppling](../pushing-without-toppling.md). **The friction is never told to any
solution and nothing in the cell measures it.** So how far a glass travels for
a given push is unknown before the push is made, and it stays unknown
afterwards except through what the table looks like next.

Everything the six solutions disagree about follows from that one gap. A
solution can try to fill it, by estimating the friction, by learning a model of
what a push does, or by learning the push itself from examples of pushes that
worked. Or it can refuse to fill it, make no prediction at all, and recover by
measuring. This solution takes the second branch, and it takes it as far as it
can be taken: it predicts nothing, assumes nothing about friction, and keeps
only the one claim about a push that does not need friction to be true.

## The main idea

That one claim is the whole method, so it is worth stating before the
arithmetic. **Pushing a glass away from a neighbour increases the distance
between them, whatever the friction is.** The friction decides *how far* the
glass goes. It does not decide which way. So a method that is confident about
direction and modest about distance is making the only claim the cell can
support, and it can then fix the distance by repeating rather than by knowing.

From that, the method makes four decisions and no others, and each one is a
single line of arithmetic on numbers the arm already has.

**Which glass.** Take the glass that is short of the most room. The next
section defines that shortfall exactly.

**Which direction.** Straight away from the neighbour whose edge reaches
furthest into that glass's room. The heading is the direction of the line that
runs from the neighbour's middle through the glass's middle, continued
outwards.

**How far.** A fixed fraction of the shortfall. The fraction is less than one,
so the push closes part of the gap rather than all of it, and the rest is left
to the next pass.

**How high.** As low as the gripper can reach, always. This is not really a
decision, because there is never a reason to push higher: the lower the
contact, the further the glass is from tipping, so the only question the height
raises is whether even the lowest contact is low enough. That question is
answered in [when a glass cannot be pushed
safely](#when-a-glass-cannot-be-pushed-safely).

Then the arm looks at the table again, and the four decisions are made afresh
from the new measurements. Nothing is remembered from one pass to the next
except how many pushes have been spent.

The word **fixed** in the name needs care, because it does not mean a fixed
number of millimetres. A rule that pushed the same distance every time would
be badly wrong, since the glasses on a crowded table are short of anything
from almost nothing to several tens of millimetres, and one distance cannot
serve both ends of that range. What is fixed is the **fraction**: one constant,
the same for every glass on every table, chosen once by argument and never
changed. That single constant is the only free number in the entire method.

## Open loop and closed loop

The four decisions above are small, and the thing that makes them sufficient is
not their content but the loop they sit inside. That loop has a name in control
engineering, and the name is worth learning because the rest of this document
uses it.

A plan that is computed once and then carried out without reading anything back
is **open loop**. It commits to the whole answer in advance, on the strength of
whatever it believed when it started, and it has no way of noticing that the
world disagreed. A plan that measures, acts, measures again and lets the second
measurement change what it does next is **closed loop**. The three parts of a
closed loop always have the same shape: a **measurement** of how things are, an
**error** that says how far that is from how things should be, and a
**correction** that is meant to reduce the error.

The programming comparison is exact, and it is the clearest way to see the
difference. Open loop is unrolling a loop into a fixed sequence of statements
because you are sure how many times it will run. Closed loop is a `while` loop
whose condition re-reads a value that the body of the loop changes. Written as
code, this solution is one such loop and nothing more: while the table is short
of room, measure the shortfall, push, and measure the shortfall again. The
condition is not a count that was worked out before the run. It is a fresh
reading of the world.

The maths comparison says the same thing from the other side. Newton's method
finds the root of a function without anybody having a formula for the root. All
it needs is a way to measure how wrong the current guess is and a rule that
makes the wrongness smaller, applied over and over. This solution is in exactly
that position. Nobody can write down where a glass will be after a push, but
anybody can measure how much room it is short of, and the rule that makes that
smaller is to push it away from whatever is crowding it.

The three parts map onto the cell directly. The measurement is `look()`, which
the bench provides. The error is the shortfall. The correction is the nudge,
and the fraction that turns the error into the correction is called the
**gain**, which is the standard word for it. A correction that is the error
multiplied by a fixed gain is a **proportional controller**, and that is the
whole of this method's cleverness.

Every one of the six solutions runs inside a loop of this shape, because
[pushing without toppling](../pushing-without-toppling.md) shows that none of
them can do otherwise. What makes this one the control is that in the other
five the loop surrounds something substantial, and here **the loop is the
method**. There is nothing inside it to compare.

## The shortfall, and why it is measured to the neighbour's edge

The loop needs an error, so the error has to be defined before anything else,
and the definition contains the one trap in this problem that catches almost
everybody.

To close on a glass the open jaw has to get round it: a finger and a pad on
each side, with the jaw opened wider than the glass before it closes. Added up
from the glass's middle outwards, that comes to about **70 mm of clear room in
every direction**. Those are the gripper's own numbers, so the project is
allowed to write them down, and the bench holds the 70 mm as a constant and
applies the test like this: **a glass has room when every other glass's edge is
at least 70 mm from its middle.**

Read that sentence twice, because the word *edge* is what makes the test
asymmetric. The 70 mm is measured from one glass's middle out to another
glass's **edge**, and a glass's edge is half its own widest width out from its
own middle. So what a glass needs from a neighbour depends on **how wide the
neighbour is, not on how wide it is itself**. A narrow glass standing beside a
wide one can be badly short of room while the wide one, at the very same
distance, has room to spare, because the wide one's rim reaches much further
into the gap than the narrow one's does.

![The same pair of glasses from the top at four separations, showing that the wide one comes free before the narrow one does: each glass carries the 70 mm ring the open jaw needs, and a glass is blocked while its neighbour's edge is inside that ring, so the narrow glass, whose neighbour's edge reaches further in, is still blocked at a distance where the wide one already has its room.](../../../images/03-push-glasses-apart/01-four-distances-one-pair.png)

From that, the error falls out. The shortfall of one glass against one
neighbour is

    70 mm  +  half the neighbour's widest width  −  the distance between
    their middles

and it is zero or less when that neighbour is not in the way. The glass's own
shortfall is the largest of those values over every other glass on the table,
and the neighbour that produced the largest value is the one whose edge is
nearest to the glass's middle. So **the blocking neighbour and the deepest
intruder are the same glass**, and the method needs no separate rule to find
it.

Two consequences matter, and both are easy to miss.

**The test is on an ordered pair rather than on a pair.** Asking whether A and
B are far enough apart is not a question with one answer. A may be crowded by B
while B is not crowded by A. So the method has to evaluate the shortfall in
both directions for every pair, and a method that compares only the distances
between middles will call a pair fine when one of the two cannot be gripped.
This is the same point [the problem](../problem.md) makes with its three
distances, and [the target layout](../the-target-layout.md) makes again when it
insists that a layout has to use the edge version of the condition.

**The shortfall is already in the repository.** The function `shortfall()` in
[`03-push-glasses-apart/01-one-fixed-nudge/plan.py`](../../../03-push-glasses-apart/01-one-fixed-nudge/plan.py)
computes exactly the expression above and adds it up over the whole table, as a
measure of how crowded the arrangement is. This solution uses the same quantity
one glass at a time, as its error.

## Why the push is a fraction of the shortfall rather than all of it

With the error defined, the only remaining question is how large a correction
to make from it, and the answer is the one place where the missing friction
decides the design rather than merely complicating it.

Start by naming what nobody knows. Call the shortfall `s`, and call the
fraction the method applies to it `k`, which is the gain. The jaw is therefore
commanded to travel `k · s`. What the glass actually does is some other
distance, because the jaw may slip against a curved wall, the glass turns as
well as travels, the friction under its foot is not the same everywhere on that
foot, and the glass may carry on a little after the jaw stops or stop a little
before it. Write that unknown as a factor `g`, so the glass moves `g · k · s`.
**Nothing in the cell measures `g`, and nothing bounds it tightly**, because
every term that would settle it runs through the friction coefficient, and
glass on a dry wooden top plausibly spans a range of more than two to one.

Now the arithmetic. The shortfall after the push is

    s'  =  s − g · k · s  =  s · (1 − g · k)

so the shortfall shrinks whenever the size of `1 − g · k` is less than one,
which happens whenever `g · k` lies between zero and two. That single
inequality is the whole argument for a small gain, and it has two readings.

**A confident push is unstable against the unknown.** Set `k` to one, which is
the obvious choice of aiming to close the whole gap at once, and the method
converges only while `g` stays below two, and overshoots whenever `g` is above
one. Since `g` is not known to within a factor of two, that is a coin toss
rather than a design. An overshoot is not a harmless error either: it carries
the glass past where it needed to be, and the glass has to land somewhere.
Moving one glass out of a crowd can easily move it into a different crowd, so
the push that was meant to end the problem creates a second one, and the extra
travel is extra distance in which something can be knocked over.

**A modest push converges against a wide range of the unknown.** Set `k` well
below one and the product `g · k` stays inside the safe range even when `g`
turns out to be several times what anybody would have guessed. The shortfall
then falls as a geometric sequence: if `g · k` happens to be a half, each push
halves the remaining shortfall, so three pushes take it to an eighth of what
it was and the glass crosses the line. The method does not need to know which
geometric sequence it is on. It only needs the sequence to be decreasing, and
that is what the small gain guarantees.

What the small gain costs is **the number of steps**, because the number of
pushes needed to close a given shortfall grows as the logarithm of the
reduction divided by the logarithm of `1 − g · k`. A smaller gain is therefore
safer and slower in a way that can be written down exactly, and the price is
paid in arm time rather than in risk. That trade is the subject of the next
section.

One more point about the gain, and it is about honesty rather than about
control. The gain could be chosen by trying many values over the training
tables and keeping the best, and that would be **fitting a number to data**,
which this solution is not allowed to do: the plan for the six records that
this solution fits nothing, and a baseline that is quietly tuned until it is
competitive has stopped being a baseline. So the gain is argued instead. It is
chosen small enough that the convergence condition holds across the whole
plausible friction range, and then frozen, and that argument is written down
where anybody can disagree with it.

## Why repeating replaces predicting

The small gain buys convergence, and the loop buys correctness, so the method
can now be stated in its strongest form: it never says where the glass will
land, and therefore **it cannot be wrong about physics it never claimed to
know**.

It is worth being exact about what is and is not claimed. The method claims a
direction, which does not need the friction. It claims that the shortfall is
measurable, which `look()` makes true up to the measurement error problem 2
scored. It claims that a glass pushed away from its neighbour ends up further
from that neighbour, which is true for any friction whatever. It does not claim
how far the glass goes, it does not claim that the glass will not rotate, and
it does not claim to know whether this table is slippery or sticky. Every
solution that fails because its model of pushing was wrong fails on a claim
this one does not make.

The price is arm time, and it should be read as a real price rather than as a
rhetorical one. One push is a sequence: the closed jaw is carried to a start
point, comes down to the lowest height the gripper can reach, feels forward
very slowly until the force it feels passes a small threshold, pushes at a
steady speed, backs off a couple of centimetres and lifts clear. Then the arm
has to take a fresh look. **Every push is seconds of arm time, and the
scorecard counts pushes against a fixed budget**, so the currency this method
pays in is finite. A method that converges in four pushes where another
converges in one has not failed, but it has spent four times the time and four
times the travel, and travel is where a glass gets knocked.

So the honest summary of this solution's position is that it moves its cost out
of error and into time. Every other solution in the set is buying a way to
shorten the loop. Solution 4 buys a model of what a push does and plans
through it, so that one push can be aimed at the answer. Solutions 3 and 6 buy
the same shortening implicitly, by fitting a policy that has seen many pushes
and their outcomes. Solution 2 buys a ranking over many candidate pushes, which
is a way of choosing a better single push without predicting its outcome in
detail. **What the comparison between this solution and the other five
measures is exactly what that shortening is worth.**

And repetition has a floor, which it would be dishonest to leave out. Pushes
are not independent: giving one glass its room can take room from another,
which then needs a push of its own, which can take it back. A loop that is
reduced to repeating can oscillate, and the only thing that stops it is the
budget. [A worked example](#a-worked-example) shows that happening.

## What is built and what is a design

Before the output and the refusals, it is worth saying plainly which of all
this exists as code, because this is one of the few solutions in the set where
real code is involved and it would be easy to over-claim.

**Built, in the repository, and run against the bench:**

- the bench itself, in [`03-push-glasses-apart/bench/`](../../../03-push-glasses-apart/bench/), with the
  crowded tables, the measurement error, `look()`, `push()`, `take()` and the
  scorecard;
- the room test, as `has_room()` in
  [`03-push-glasses-apart/bench/bench.py`](../../../03-push-glasses-apart/bench/bench.py), which holds the
  70 mm as the gripper's constant and applies it to the neighbour's edge;
- the shortfall, as `shortfall()` in
  [`03-push-glasses-apart/01-one-fixed-nudge/plan.py`](../../../03-push-glasses-apart/01-one-fixed-nudge/plan.py);
- the tipping rule, as `slides()` in the same file, evaluated at the top edge
  of the jaw and at both ends of the plausible friction range, together with
  the small test push that settles the glasses the range cannot;
- the loop, in [`03-push-glasses-apart/01-one-fixed-nudge/run.py`](../../../03-push-glasses-apart/01-one-fixed-nudge/run.py):
  look, rack every glass that already has room, choose one push, make it, look
  again, with a budget of pushes per glass and a budget per table;
- the refusal reasons, and the scorecard that counts them with the outcome
  rather than the action.

**A design, not code:**

- the four decisions of [the main idea](#the-main-idea). The planner that
  exists chooses its heading and its distance by searching many headings and
  every distance up to a limit, and keeping the shortest push that frees a
  glass — or, when no push on the table frees one, the push that most cuts the
  table's total shortfall of room, so that the next look starts from a looser
  table. That search is the geometry [solution
  2](02-geometry-ranked.md) generates its candidates with. This solution
  replaces it with one heading and one multiplication, so the parts around the
  rule have been run and the rule itself is the few lines that would sit where
  the search sits;
- the gain, which has no value in the repository;
- the shared target layout, which this solution does not use in any case;
- the rendered view of the table from the top, and the path for a chunk of
  waypoints, neither of which this solution needs;
- the repeats and the compute column that [the bench](../the-bench.md)
  describes for the scorecard.

One measurement from the built code is worth quoting, with its attribution
made clear. The programmed run reports in
[`03-push-glasses-apart/01-one-fixed-nudge/results.json`](../../../03-push-glasses-apart/01-one-fixed-nudge/results.json)
that its pushed glasses stopped a median of 1.0 mm, and at worst 3.9 mm, from
where they were aimed. **That run uses the searching planner rather than this
solution's rule**, so the figure is not this solution's score. What it does say
is something about the bench rather than about any rule: in this simulator, a
glass that is pushed follows the jaw closely, so the unknown factor `g` of the
previous section sits near one here. No solution is told that, nothing in the
cell would reveal it, and on a real table with a real cloth or a real spill it
would not hold. It is a reason to expect this method to converge in few pushes
on the bench, and not a reason to trust it anywhere else.

## It produces nothing anybody can learn from

There is one thing this solution cannot do that its nearest neighbour in the
set can, and because it is the single clearest difference between the two it
belongs here rather than buried at the end.

Solutions 3 and 6 are fitted to demonstrations, which means recorded examples
of the task being done: what the arm saw, and the push that was made from
there. Both of those documents say the examples come from solution 2 for
nothing: solution 2 has geometry generate many candidate pushes for each
crowded glass and then ranks them, so every push it makes is a demonstration
and is also the best of a set that was written down and scored first. It is
what earns solution 2 its place in the set beyond being a second baseline.

**This solution leaves behind nothing of the kind.** It generates exactly one
push per pass and it scores nothing, because there is no alternative to compare
the one push against. A record of its runs would say only that a particular
push was made and that the glass afterwards was in a particular place, with no
indication of whether a better push existed. That is a log rather than a
scored candidate set, so no ranker can be fitted to it, and a policy fitted to
it could learn nothing but the one rule that produced it.

So this solution is a control and only a control. It cannot also be the
teacher. Saying so is not a complaint about it, because a control that also
supplied training data would be doing two jobs and the second job would make
the first one suspect. But it does mean that if the ranked geometry did not
exist, the demonstrations for solutions 3 and 6 would have to be bought
somewhere else, either by a person teleoperating the arm or by writing a second
method for the purpose, and both of those are real costs that the comparison
would then have to carry.

## The pushes are what this contributes

With the method, its loop and its honest extent all stated, what remains is the
thing it actually hands over, and the bench is strict about the shape of that.

**The shared output is a jaw trajectory**, as [the bench](../the-bench.md)
explains, and a solution that thinks in whole pushes does not have to produce
one itself. This solution thinks in whole pushes. What it emits is a
**parameterised push**: which glass is meant to move, where the fingertips come
down, which way the jaw points and travels, how far forward to feel before
giving up on finding the glass, how far to push once it is touching, and where
the glass is expected to arrive. The bench owns the macro that turns those
numbers into the descent, the feel, the push, the retreat and the lift, and
every parameterised push from every solution is expanded by that same macro. So
the simplicity of this solution costs it nothing in the comparison and gains it
nothing either.

The field that names where the glass is expected to arrive deserves a word,
because it looks like a prediction and this document has insisted there is
none. The bench asks for it so that it can measure how far each glass ended
from where it was sent, which is a reading on every solution's own model of
pushing. This solution fills it with the place its fingertips are carried to,
on the assumption that the glass travels with the jaw and no further. That is a
statement of intent rather than a prediction of physics, and the method does
nothing with the answer: it does not compare the outcome with the aim, adjust
anything, or remember. It simply looks again.

The approach to the glass is the one part of the push that is not arithmetic,
and it matters more than it looks. The jaw does not drive to a computed contact
point. It comes down behind the glass, a little outside the glass's widest
part, and then feels forward slowly until the force it feels passes a small
threshold. A motion that is commanded with a sensor condition that stops it
early is called a **guarded move**, and it is used here because the glass's
wall sits at its measured middle minus half its measured width, so the error in
the position and the error in the width add together. A step that drove to that
computed point would either stop short and push nothing or arrive past the wall
at speed, which is a knock. Where the sensor fired beats what the camera said.

The push then reports what the jaw felt: whether it was blocked on the way
down, how far it travelled before touching or that it never touched, whether it
jammed, the most force it felt, and how far it moved after touching. **This
solution reads almost none of that report.** It uses only whether the jaw
touched anything at all. That is a deliberate omission rather than an
oversight, and it is the deepest reason this solution is the floor of the set:
[the bench](../the-bench.md) points out that the force reading is the only
channel through which the friction is observable at all, and every solution
that does better than a blind nudge does so by reading that channel, either by
reasoning about it or by learning from it. This one throws it away and relies on
the next look instead.

Finally, the pushing is what this solution contributes and not the whole run.
The runner racks every glass that already has clear room before it pushes
anything, because a glass in the rack is a glass that is nobody's neighbour,
and that step is shared machinery rather than part of this method. What this
document describes is what happens to the glasses that are left.

## How the concepts fit together

The pieces can now be put in the order the arm meets them, which is also the
order in which each one depends only on what came before.

The **room test** turns a table into a list of glasses that cannot be gripped,
and because it measures to the neighbour's edge it is asymmetric, so it is
applied in both directions for every pair. The **shortfall** turns each of
those glasses into a single number, which is the error a closed loop needs. The
**blocking neighbour** is whichever glass produced that number, and the line
from its middle through the crowded glass's middle is the **direction**, which
is the one claim the method makes that does not need the friction. The **gain**
turns the error into a distance, and it is small so that the sequence of
shortfalls decreases even though the factor relating a commanded push to a
delivered movement is unknown. The **tipping rule** then decides whether this
glass may be touched at all, at the lowest height the gripper can reach, and
refuses it if it may not. The **guarded move** finds the glass without striking
it. And the **loop** closes the whole thing, because a fresh `look()` replaces
every assumption the previous pass made.

Written as the loop it is:

1. Look at the table.
2. Rack every glass that already has clear room, which is shared machinery.
3. For each glass that is left, compute its shortfall against every
   neighbour's edge, and keep the worst.
4. Take the glass with the largest shortfall, and the neighbour that caused it.
5. Check that glass against the tipping rule. If it fails, refuse it with the
   reason and go back to step 3 without that glass.
6. Push it away from that neighbour, a fixed fraction of the shortfall, at the
   lowest height the gripper reaches, feeling forward for the contact rather
   than driving to it.
7. Go back to step 1.

The loop ends when no glass is short of room, when the budget of pushes is
spent, or when every glass that is left has been refused.

## When a glass cannot be pushed safely

Step 5 of that loop is the one that can end a glass's part in the run without
touching it, and it is worth taking slowly, because a refusal here is a correct
answer rather than a failure.

A pushed glass slides while the jaw touches it below a height set by half the
width of its foot divided by the friction between the glass and the table, and
tips above that height. The arm cannot choose that height freely. The middle of
the jaw rides as low as the gripper goes, which is 50 mm above the table,
and the jaw is 30 mm tall, so its **top edge** stands at 65 mm. The height that
counts in the rule is the top edge and not the middle, because a glass that is
wider higher up meets the top edge before any other part of the jaw touches it,
and the tapered glass is wider higher up by definition. So the limit is checked
against 65 mm, and the 15 mm difference is not a rounding question: it falls
entirely in the direction that topples glasses, since every glass the lenient
check wrongly admits is a glass that will be touched above its limit.

![The height at which a push starts tipping a glass, drawn against the foot it stands on, with the jaw's middle at 50 mm and its top edge at 65 mm ruled across it: the push lands on the top edge, those 15 mm cost most of the glasses that the jaw's middle would have been allowed to touch, and the three friction lines, one of which is the simulator's own and none of which the arm is told, give three different answers about the same glass.](../../../images/03-push-glasses-apart/02-the-friction-ceiling.png)

The friction in that rule is the number nobody has, so the check is made at
both ends of the range that glass on a dry wooden top plausibly covers, and the
three possible answers are the three the built code already distinguishes. A
glass whose foot is wide enough to slide even at the high end of the range is
safe to push. A glass that tips even at the low end **is refused**, with the
reason that it tips before it slides, and no amount of looking again helps,
because the refusal is a statement about that glass rather than about the
arrangement. A glass that the range cannot settle is given a small test push
and looked at: a glass that slid has moved, and a glass that leaned and fell
back where it stood has not, so the test answers directly a question no
arithmetic in the cell can answer. That test is the one place in this entire
method where the arm reads the world before committing to a decision rather
than after it.

This method has a second reason to refuse, and it is the one that costs it
most, because it follows from the very decision that makes it simple. The jaw
pushes along the direction it points, so **the approach runs along the same
line as the push**, and pushing a glass straight away from its neighbour means
coming in from the neighbour's side. The tool behind the fingertips is 270 mm
long and its body is 90 mm across, and all of it sits at the height of the
push, so all of it has to miss everything standing on the table. In a tight
group the blocking neighbour is standing exactly where the tool would have to
be. This method has one heading to offer and no way of choosing another, so
when that heading is blocked the only honest answer is to refuse with the
reason that there is nowhere clear to push the glass from. Every solution that
searches over headings can ask for a different approach; this one cannot, and
that is the sharpest statement of what the simplicity costs.

Two rules complete the refusal path, and both are shared with every other
solution. A glass that is already lying on its side ends the run, because
nothing in this project stands a glass back up and the arm does not work next
to one. And **no refusal has a fallback that tries anyway.** A glass that was
refused is still a glass standing on a table, and something later may yet move
it or be told to leave it. A glass that was pushed and went over is finished,
and the arm carries on working beside it.

## A worked example

The method is small enough that one example can show all of it, so this section
follows two tables through the loop: one where the method is sufficient and one
where it is not. Both are described in relations rather than in sizes, as the
project's rule requires, and both hold glasses of the tapered kind, because
that is the kind whose contact is at the jaw's top edge and therefore the kind
the tipping rule bites hardest on.

### A table where it works

Three glasses stand in the glass zone. Call them A, B and C.

| | where it stands | as this kind goes |
| --- | --- | --- |
| A | the middle of the zone | narrow, standing on a broad foot |
| B | close beside A, further from the arm | the widest the kind allows, on a broad foot |
| C | the far corner of the zone, clear of both | middling |

**The room test.** A needs 70 mm plus half of B's widest width, and B is as
wide as the kind allows, so B's rim reaches well inside A's ring and A is short
of room by some tens of millimetres. Turn the test round and B needs 70 mm plus
half of A's widest width, and A is narrow, so B has room to spare at the very
same distance. C is clear of both. **So A alone is on the list**, which is the
asymmetry doing its work: one gap, two different answers, and the glass with
the problem is the narrow one.

**Can A be pushed.** A stands on a broad foot, so half its foot divided by the
highest friction in the plausible range is still above the jaw's top edge. A
slides at every friction worth considering, so no test push is needed and
nothing is refused.

**The push.** The blocking neighbour is B, so the heading is the direction from
B's middle through A's middle, continued outwards. The travel is the gain times
A's shortfall, which is a fraction of what A needs rather than all of it. The
fingertips come down on that line, a little outside A's widest part, and feel
forward until they touch. The push is made, the jaw backs off and lifts.

**Look again.** A has moved most of the commanded distance, so its shortfall is
smaller but not zero. Nothing else on the table changed, because A moved along
the line away from B and C was never near either of them. The second pass does
the same arithmetic on the smaller shortfall and therefore makes a shorter
push, and the third pass finds A's shortfall at or below zero and stops
pushing. A is then racked, and so are B and C.

**What that cost.** Three pushes and four looks, where a method that computed
the right distance in one go would have spent one push and two looks. Each push
was shorter than the one before it, which is what a geometric sequence looks
like on a real table. Nothing was knocked over, nothing left the glass zone,
and no claim about friction was made at any point. That is the whole bargain of
this solution in one table: it pays in arm time and buys immunity from being
wrong.

### A table where it does not

Four glasses, and the difference is that one of them is crowded from two sides.

| | where it stands | as this kind goes |
| --- | --- | --- |
| A | the middle of the zone | middling, on a broad foot |
| B | close beside A, further from the arm | wide |
| C | close beside A on the opposite side, nearer the arm | wide |
| D | a corner of the zone, clear of everything | middling, on the narrowest foot the kind allows |

**A is short of room against both B and C.** The blocking neighbour is whichever
of the two reaches further into A's ring, so say it is B. The heading is
straight away from B, and because C stands on the opposite side, straight away
from B is straight towards C. The push reduces A's shortfall against B and
increases its shortfall against C by about the same amount. The worst of the two
is what the method measures, so the next look finds A short of room against C
instead, asks for a push straight away from C, and undoes the first push. **The
method oscillates between two directions and spends its budget**, and no choice
of gain changes that, because the problem is the direction and not the
distance. When the budget runs out the glasses that are left are reported with a
reason, which scores the table as correct but incomplete rather than wrong.

That is the structural failure, and it is worth seeing why the next solution in
the set does not share it. A push that moved A sideways, along a line that is
away from neither B nor C but out of the gap between them, would free A in one
go. Such a push exists on this table; the information needed to find it is
already in the measurements; and finding it needs a search over directions,
which is precisely what this method gave up in exchange for being one
multiplication.

**The same table also shows the approach failure.** If B and C stand closer to
A than the tool is long, then pushing A away from B asks the arm to put 270 mm
of tool where B is standing, and pushing A away from C asks the same of C's
place. The method has no third heading to offer, so it refuses A with the
reason that there is nowhere clear to push it from. The refusal arrives before
any push is attempted, which is the right order, and the table ends as correct
but incomplete with nothing knocked over.

**And D shows the refusal that is nobody's fault.** D is clear of every other
glass, so it is never on the list at all and is simply racked. But if D had
been crowded, it would have been refused, because it stands on the narrowest
foot its kind allows: half that foot divided by even the low end of the
friction range is below the jaw's top edge, so D tips before it slides at any
friction the cell might have. No method in the set can push D, and the only
correct answer for it is a refusal with the reason.

## What it needs

Everything the method requires is either already produced by problem 2 or is a
constant that belongs to the gripper, which is why it can be built first.

**The measurements, and nothing beyond them.** From `look()` it uses each
glass's position and widest width, which are what the room test and the
shortfall need, and each glass's foot width and height, which are what the
tipping rule and its test push need. It does not use the rendered view from the
top, it does not use the force report beyond whether the jaw touched anything,
and it never reads the simulator's record.

**The gripper's own numbers.** The 70 mm of clear room, the 50 mm the jaw's
middle rides at, the 30 mm height of the jaw that puts its top edge at 65 mm,
the 270 mm of tool behind the fingertips and the 90 mm width of its body. All of
these belong to the hardware rather than to any glass, so the project allows
them to be written down, and none of them is tuned.

**One constant of its own**, the gain, chosen by the convergence argument above
and then frozen. That is the entire configuration of the method.

**One library, and it is NumPy.** The arithmetic over a handful of positions
and widths is all this solution does for itself. Carrying the jaw to the place
that arithmetic names is not part of it, because every solution here hands the
same kind of instruction to the same cell: the test bench carries the jaw with
its physics engine, and the real cell carries it with MoveIt. Both libraries
are permissively licensed, and because nothing is fitted there is no weights
file to redistribute and no licence inherited from somebody else's training
data.

**Compute to rent: none, and the number is zero.** The room test compares a
pair of distances for every pair of glasses, so its cost grows as the square of
the number of glasses, and there are four to six of them. The shortfall, the
heading and the travel are a few arithmetic operations each. The whole decision
is a few hundred floating-point operations, it needs no accelerator, and it
finishes in far less time than the arm takes to move anywhere. On the compute
column that [the bench](../the-bench.md) describes for the scorecard, this
solution is the zero against which the others are read, and solutions that plan
through a learned model at run time or evaluate a large neural network sit
hundreds or thousands of times above it.

**What it does need is arm time.** The honest cost of this method is pushes and
looks, and the budget is what bounds them.

## Where it is strong and where it breaks

The strengths all follow from how little the method claims, and the weaknesses
all follow from the same thing, which is what makes it a clean control rather
than merely a weak solution.

**It cannot be wrong about pushing, because it says nothing about pushing.**
Every other solution has a prediction somewhere that can be wrong. This one has
a direction, which is right for any friction, and a distance that is
deliberately too small.

**Its answer can be read.** Every step is a number that can be printed, so a
wrong answer is something a person reads rather than something they guess at,
and every refusal has a reason that can be checked with a ruler.

**One run of it is a measurement.** Nothing in it was fitted and nothing in it
is drawn at random, so it behaves the same way on the hundredth table as on the
first. The repeats that [the bench](../the-bench.md) requires of the trained
solutions, because their training and their actions both vary, are not needed
here, and that makes it the one solution in the set whose number carries no
spread.

**It exercises the whole contact sequence.** Closing the jaw, dropping to
height, feeling in until the force threshold fires, pushing slowly along a
line, retreating before lifting: every one of those steps is where a real glass
gets knocked over, and this method runs all of them with no planning code in
the way. When something falls over while problem 3 is being built, this method
tells you the fault was in the contact, because there was no plan to be wrong.

**Short pushes are safe pushes.** Every millimetre of travel is a millimetre in
which something can be knocked, so a method whose instinct is to move a glass
as little as possible has a good instinct, and the small gain gives it that
instinct for free.

The weaknesses divide into one that makes the others academic and several that
matter in their own right.

**It has nowhere to stand.** The approach runs along the same line as the push,
so pushing a glass straight away from its neighbour asks the arm to put 270 mm
of tool where the neighbour is. In a tight group that is impossible, and the
method cannot offer a second heading, so it refuses. The honest reading is that
**the approach is a harder constraint than the departure**, and this solution
is the one that cannot choose its approach at all.

**It cannot help a glass that is crowded from two sides.** A push away from one
neighbour is a push towards the other, so the method oscillates or runs out of
budget. No gain fixes it, because the difficulty is in the direction.

**It never looks at the free table.** The shortfall says how far, and nothing
in the method says where to. It does not ask whether the place the glass is
being sent is empty, inside the glass zone, inside the arm's reach or clear of
the rack, and it does not ask whether another glass is standing in the corridor
the glass will travel down. A push that drives one glass into another is the
failure this creates, and it is also the failure that cannot be recovered,
because a collision between two upright glasses is how a glass goes over.

**It does not use the shared target layout.** [The target
layout](../the-target-layout.md) computes where every glass should finish and
reports the least travel the task could possibly need, and this method consults
neither. It pushes away rather than towards, so its total travel will sit well
above the displacement floor, and reading it against that floor is the clearest
way to see what choosing a destination is worth.

**It does not choose the safer glass of a pair.** Of two crowded glasses, the
one standing on the wider foot has the more room under the tipping limit, so it
is the safer one to push. This rule always pushes the glass that is short of
room, which may be the narrower of the two, and when that glass fails the
tipping check the method refuses rather than pushing the other one. That is
safe, but it costs yield, and it is the kind of easy improvement a baseline has
to decline in order to remain a baseline.

**It throws away the force report.** The force the jaw felt and the distance the
glass moved for it are consequences of the friction, so they are the only
evidence about the friction that this cell can produce. The method reads none
of it, which is exactly why every other solution has something to improve on.

**It pays in pushes, and the currency is limited.** The budget bounds the
repetition, so a method whose only recovery is to repeat can run out of
recoveries on a table that needs many.

## The general ideas behind this

Nothing here was invented for glassware. Knowing which older ideas the method
is made of says where it should be expected to work and where it should not.

### Proportional control

A correction that is the measured error multiplied by a fixed gain is a
**proportional controller**, the simplest member of the family usually written
as PID, which adds a term for the accumulated error and a term for its rate of
change. **Where it is normally right:** when the error can be measured, when
the correction is known to act in the right direction, and when the factor
relating the correction to its effect is at least bounded, a small gain is
stable with no model of the system whatever. That is a remarkably weak set of
requirements, and it is the reason proportional control is everywhere. **Where
it is not right:** a proportional controller is slow when an accurate model is
available, because a model lets one step do what the controller does in
several; and it leaves a steady error whenever the system has a constant offset
pulling against it, which is the usual reason for adding the integral term.
Here the second objection does not bite, because the measurement is of position
and the correction moves position, so there is no offset to accumulate against.
The first objection bites exactly, and the whole set of six exists to find out
what an accurate model would be worth.

### Singulation

Separating crowded objects so that they can be picked up one at a time is
called **singulation**, and it is the word to search for. Chang, Smith and
Fox's *Interactive Singulation of Objects from a Pile* (ICRA 2012) named the
problem for manipulation, and it already contains the structure this solution
uses: act on the pile, look again, repeat. **Where it is normally right:** bin
picking and warehouse work, where a pile has to become a sequence of graspable
objects and the only question is access. **Where it is not:** the setting that
work assumes has walls that stop an object leaving the workspace and objects
lying flat that cannot be knocked over. Neither is true on an open table of
upright glasses, so the structure carries over and the safety does not.

### Fixed push policies

Pushing a short fixed distance along a direction chosen by a simple rule is a
real method rather than a straw man. Danielczuk and colleagues' *Linear Push
Policies to Increase Grasp Access in Dense Clutter* (IEEE CASE 2018) is the
clearest statement of it, and its finding is the one this solution relies on:
such pushes are cheap and often sufficient to open enough space for a grasp.
**Where it is normally right:** dense clutter inside a bin, where a push cannot
do much harm. **Where it is not:** here, for the two reasons above and for a
third that is specific to upright objects. A flat object in a bin can be pushed
from a direction the gripper can easily occupy, while an upright glass must be
pushed from the side, and the side is where the neighbour is.

### Quasi-static planar pushing, which this solution deliberately does not use

There is a well developed theory of what happens when an object is pushed
across a table. Mason's *Mechanics and Planning of Manipulator Pushing
Operations* (IJRR 1986) established the result the field rests on, usually
called the voting theorem: which way a pushed object rotates is decided by
where the line of pushing passes relative to the object's centre of friction,
and that can be worked out without knowing the pressure under the object in
detail. Lynch and Mason's *Stable Pushing: Mechanics, Controllability and
Planning* (IJRR 1996) turned it into planned pushes that carry an object along
a chosen path. **Where it is normally right:** when the friction and the way
the object's weight sits on its foot are known or can be measured. **Where it
is not:** here, because nothing in this cell measures either. Yu, Bauza, Fazeli
and Rodriguez's *More than a Million Ways to Be Pushed* (IROS 2016) is the
honest measurement of what that costs: they pushed the same objects the same
way many thousands of times and recorded how far the outcomes scatter, and the
scatter is neither small nor noise that averages away. So the choice is between
a prediction that needs a number nobody has and no prediction at all. This
solution takes no prediction at all. [Solution
4](04-a-world-model.md) takes the other branch and learns the model instead.

### Guarded moves

Ending a motion on a sensed condition rather than at a computed coordinate is a
**guarded move**, and it is one of the oldest ideas in robot assembly.
Lozano-Pérez, Mason and Taylor's *Automatic Synthesis of Fine-Motion Strategies
for Robots* (IJRR 1984) is the reference statement of why: when the position of
a thing is uncertain, a motion that stops on a sensor is reliable where a motion
that stops at a coordinate is not. **Where it is normally right:** every
contact made against an object whose position was measured from a distance,
which is every contact in this project. **Where it is not a complete answer:** a
guarded move tells the arm where the surface is and says nothing about what to
do once it is found, so it removes a class of collisions and solves no part of
the planning.

### Baselines, as a discipline

The last thing this solution is, is a **baseline**: the simplest method that
does the job at all, built first and kept as the number everything else is
scored against. The practice does not come from robotics. It is what keeps a
claim honest, because a method that beats nothing has not been shown to be
good. **Where it is normally right:** whenever several methods are compared,
and especially when some of them are expensive, because a price can only be
judged against a free alternative. **Where it goes wrong:** a baseline that is
quietly improved until it is competitive has stopped being a baseline, and the
improvements are usually small and reasonable one at a time. This method has
exactly one place where that could happen, which is the gain, and that is why
the gain is argued rather than swept over the training tables. The discipline
also requires that the baseline be measured on the same tables with the same
scoring as the methods meant to beat it, which is what [the
bench](../the-bench.md) is for.

## Where it sits among the other five

The plan for the six states the question this solution answers in one line:
**does any learning beat a fixed nudge?** It is answered by comparing this
solution against all five of the others, and that is the only comparison in the
set with this shape, because every other comparison is between two methods that
both cost something.

**Against [solution 2](02-geometry-ranked.md)** the gap is a search and a
ranker. Solution 2 uses the same input, the same room test and the same tipping
rule, and then has geometry generate many candidate pushes for each crowded
glass and gradient-boosted trees rank them. Two of this solution's three
structural weaknesses are weaknesses solution 2 does not have, because a method
that may choose its direction can find a push out of the gap between two
neighbours and can find an approach the tool actually fits into. Solution 2 also
has the one thing this solution does not, which is that its scored candidates
are demonstrations, so it is the teacher for solutions 3 and 6 and this one is
the teacher for nobody.

**Against [solution 3](03-imitation-from-demonstrations.md)** the gap is
everything fitted. Solution 3 fits ACT, and then Diffusion Policy, to those
demonstrations, and emits a chunk of waypoints rather than a push. The
demonstrations themselves are free, so what it pays is a training run with
several seeds. That run was budgeted for a rented accelerator and in the event
needed none, so the price is hours of this laptop rather than money. If it does
not clear more tables than a fixed nudge, every one of those prices bought
nothing.

**Against [solution 4](04-a-world-model.md)** the comparison is the sharpest
statement of what this document is about. Solution 4 learns a model of what a
push does and plans through it at run time, first with the small ensemble
already written in this project and then with TD-MPC2 off the shelf. It is
buying exactly the prediction this solution refuses to make, and it pays twice:
once in training data and once in planning time per push, which the compute
column records. So the pair of them asks the question directly: **is a
prediction worth more than a repetition?**

**Against [solution 5](05-smolvla-as-it-downloads.md)** the two of them are the
only solutions in the set that fit nothing here, which makes the pair worth
reading together even though they have nothing else in common. This one carries
one argued constant. Solution 5 carries SmolVLA as it downloads, which is about
450 million parameters pretrained on 487 community datasets of real
teleoperation, so it fits nothing in *this cell* while resting entirely on
fitting done somewhere else. **Against [solution
6](06-smolvla-fine-tuned.md)**, which is the same SmolVLA weights with their
training continued here by low-rank adaptation, the fixed nudge is the floor
that both halves of that pair have to clear before the difference between them
is worth discussing at all.

The right way to think about this method, then, is as **the first thing to
build and the last thing to ship**. Build it first, because it is the cheapest
way to get a real push happening against a real glass, and because everything
after it needs the same contact sequence and the same refusals. Do not ship it,
because it has one heading to offer, it cannot help a glass crowded from two
sides, and it never asks whether the place it is sending a glass is clear.

And read it in both directions, as problem 2 reads its own written rule. The
usual reading is about the other five: if a model cannot beat a fixed nudge, it
has earned nothing, because it cost data, training time and hardware that this
one did not, so matching it is not a result. The other reading is about the
problem. This method works at all only because the glasses stand upright on a
flat table, because the gripper's clear room is a known constant, because
problem 2 reports a position and a width for every glass, and because a refusal
is an acceptable answer. Each of the other five needs fewer of those promises
than this one does. So a reader who finds a fixed nudge convincing should read
that as a statement about how generous problem 3's promises are, and the value
of the other five is what they do when the promises stop.

---

← [Problem 3 — push the glasses apart](../problem.md) · [Solution 2 — geometry
generates, a model ranks](02-geometry-ranked.md) →
