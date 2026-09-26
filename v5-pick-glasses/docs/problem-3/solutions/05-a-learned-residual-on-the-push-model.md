# Solution 5 — a learned residual on the push model

*Hybrid, with the model as a proposer. Keep the physics of
[solution 4](04-predict-the-slide.md) as the prediction, and learn only the
error it makes. Every push the arm takes in normal running is a labelled
training example, produced for nothing, because the arm photographs the table
before and after the push anyway.*

> **The cell is described once, in [the cell](../../the-cell.md)** — the layout,
> the two places the camera works from, all four sensors, and the words this
> project uses them with. [The problem](../problem.md) says what is being asked
> for. What follows is only what is specific to this solution.

## Introduction

This document explains how to put a small learned component inside a physics
model without letting it take the physics model's place. The arrangement has a
name in the literature — residual physics, or residual learning — and it is
worth understanding properly, because it is the cheapest way to get a learned
part into a physical system and the easiest to get structurally wrong.

The problem it addresses is the one [solution
4](04-predict-the-slide.md) ends on. The mechanics of pushing a flat-bottomed
object across a table are settled mathematics, and this cell cannot supply two
of the numbers that mathematics needs. So the prediction is sound reasoning fed
guesses, and nobody can say by how much it is wrong without pushing something
and looking.

The idea here is to push something and look, and then keep the answer. The
physics predicts where the glass will finish. The camera measures where it
actually finished. The difference between those two is called the **residual**,
and a small model learns that difference as a function of the things the arm
already measured. The physics supplies the structure, and the learned part
supplies only what the physics could not know.

By the end you will understand why learning the error is a smaller problem than
learning the whole mapping, how many training examples a run of the arm
produces, what happens on the first run when there is no model at all, why the
one arithmetic check that stands between the arm and a broken glass must be kept
out of the learned part's reach entirely, and — the conclusion this document
ends on — why improving the landing prediction turns out to improve the wrong
number.

Two things in this document are measurements rather than descriptions, and it
is worth saying at the start which. **No residual model exists in this repository.**
`problem-3-learned/` holds a working learned pipeline, and it is
[solution 10](10-learn-a-forward-model-then-plan.md) rather than this one: a
forward model that predicts a push's whole outcome with no physics underneath
it. So the design below is a design. **The residual it would have to learn,
though, was measured** — on this project's own physics bench, over 248 real
pushes made by this project's own planner. It turns out to be about 1.3 mm.
That does not make the arrangement wrong, and it does change the verdict, so it
is reported in full rather than left out.

## The problem this solves

[Solution 4](04-predict-the-slide.md) builds a prediction out of quasi-static
planar pushing: push a glass with the closed jaw, and the theory says how far it
travels, how far it drifts sideways, and how much it turns. The theory is
correct. It needs two numbers that nothing in this cell measures.

The first is **μ**, the friction between the glass and the table. It sets how
much force the push has to supply, and it sets the height above which a push
tips the glass instead of sliding it.

The second is the **pressure distribution** over the glass's base — whether the
weight rests evenly across the foot, or on a ring near its rim, or on three high
spots where the glass rocks. All three are ordinary ways for a real drinking
glass to stand, none of them is visible from an overhead camera, and solution 4
shows they give answers a factor of two apart.

So solution 4 produces a number with a decimal point in it, and part of that
number is a guess wearing the decimal point. The arm cannot tell which part.

### The obvious alternative, and what it costs

The obvious alternative is to stop deriving and start fitting: show a model many
pushes and their outcomes, and let it learn the whole mapping from a push to
what the push does. That is [solution 10](10-learn-a-forward-model-then-plan.md),
and this project has built it in `problem-3-learned/`, so the price is known
rather than estimated.

`features.py` there settles what the model is being asked for. Its outputs are
where the pushed glass moves and where each other glass moves, in the push's own
frame, plus two yes-or-no answers about toppling and about the jaw being
blocked. Those are absolute movements, not corrections to anything. There is no
`f(x)` under them, which is what `README.md` means when it says the approach
carries no tipping formula, no friction value and no rule about where the jaw
fits.

`README.md` also records the training set. Round one was 24,759 random pushes on
4,000 tables. Round two was 13,253 further pushes on 5,000 new tables, chosen by
a planner using the round-one model. That is **38,012 pushes** in total, every
one of them simulated, over 31 minutes of laptop processor time, to learn a
mapping whose first and largest lesson is that a pushed glass moves roughly the
way the jaw moved.

That lesson is not worth 38,012 pushes, because it is already written down.
Newtonian mechanics knows it. What nobody has written down is the small
correction on top of it, and that correction is all this solution tries to fit.

There is a measured number attached to that argument, and it is worth stating
plainly. `train.py` in `problem-3-learned/` scores its trained model on
validation tables it never saw, and `README.md` records the result: **the
pushed glass lands 4.5 mm from where the model predicted, at the median**. The
prediction this document proposes to correct — the glass finishes where the jaw
took it — lands 1.20 mm out at the median over the 248 pushes measured below,
with no model at all. Two cautions go with that comparison. The two are scored
on differently drawn pushes: solution 10's validation set includes random pushes
into other glasses, where this document's set is the pushes the geometric
planner actually chose. And the 4.5 mm figure lives only in that README, printed
by `train.py` at the end of a training run; `results.json` beside it holds the
scored run rather than the model's own accuracy, and carries no date or
description of its own. Neither caution changes the direction of the result.

### Three things the residual arrangement buys

**Less data.** The learned part never has to discover that pushing moves things.
It only has to learn the leftover. Measured below, most of what there is to
learn here arrives in the first forty examples.

**An interpretable failure.** When a residual model is wrong, the report can say
so in one line: the physics said 60.0 mm, the correction said 58.7 mm, the glass
went 59.1 mm. A model that learned the whole mapping cannot be interrogated that
way, because there is no separate physics answer to compare it against.

**A floor.** Delete the weights file and the system is solution 4 with solution
3's look-again behind it, which is the system that would have been built anyway.
A learned mapping has no such floor: delete its weights and there is no
prediction at all.

## What a residual is

**Residual** here means the part of a measurement that a model did not account
for — what is left over after the model has said its piece. It is an ordinary
word in statistics for the difference between an observed value and a fitted
one, and robotics uses it in exactly that sense.

Write the push and everything measured about it as `x`. Write the analytical
prediction as `f(x)`: where solution 4 says the glass will finish. Write what
the camera measures afterwards as `y`. Then

    residual  =  y  −  f(x)

and this solution fits a second, small model `g` to that quantity, so that the
prediction used by the planner becomes

    prediction  =  f(x)  +  g(x)

`f` is the white box: derived from first principles, correct in structure,
missing two inputs. `g` is the black box: no structure at all, fitted to
examples, and asked for one small number rather than for the answer. The
combination is called a **grey-box** model, and the reason for the name is
exactly the picture it suggests.

![A residual is the gap between the prediction and the measurement. On the
left, one crowded table of five drawn tapered glasses, laid out by the rule
`problem-3-sim/bench.py` uses, with the push that gives one of them its room and
the circle where the prediction puts it. At that scale the prediction and the
outcome are the same circle. On the right, the same landing spot magnified: the
average gap measured over 248 real pushes, and the scatter around that
average.](../../../images/problem-3/05-what-a-residual-is.png)

The left panel of that picture is a real table at true scale, and the right
panel is the same landing spot magnified about forty times. That difference in
scale is the honest headline of this document, and the sections below measure
it.

## The main idea

The main idea is a division of labour between a thing that generalises badly and
a thing that generalises well.

An analytical model **generalises but is biased**. Ask it about a push it has
never seen, in a direction nobody has tried, on a glass of a size that has never
been on the table, and it answers sensibly, because it is reasoning from
mechanics rather than from memory. It answers wrongly by some fairly consistent
amount, because its inputs are guesses.

A fitted model **matches but does not generalise**. Inside the range of pushes
it was trained on it can be very accurate, because it is not reasoning at all,
only remembering with interpolation between the memories. Outside that range it
answers with the same confidence and no basis.

Put the fitted model where the bias is and the two failures do not add. The
analytical model carries every push, including the strange ones. The fitted
model corrects it where there is evidence and is switched off where there is
not. What is learned is not a friction coefficient and not a pressure
distribution. It is the combined effect of both on this table, which is the
number nobody could measure, obtained without measuring it.

## What the backbone predicts, and what is left over

### The inputs

Everything the model is shown is already measured or already chosen. Nothing new
has to be sensed for this solution to exist.

| input | where it comes from | why it might matter |
| --- | --- | --- |
| `L`, how far the push was commanded to go | the planner chose it | a longer push has longer to go wrong |
| `d`, how far the push line misses the footprint centre | problem 2's circle fit, plus placement error | solution 4's theory says the glass turns about a point `c² / d` away |
| the glass's foot width | measured this run | it sets the contact patch and the tipping limit |
| the glass's widest width and its height | measured this run | they say how the weight sits above the foot |
| the push direction on the table | the planner chose it | a damp patch or a wear mark sits somewhere in particular |

Read that table as a list of columns in a log file, one row per push. The left
column names the column, the middle says which part of the run already produced
it, and the right says why it is worth showing to the model rather than left
out.

One input the overview lists is worth removing, and correcting it is worth a
paragraph because the same mistake matters much more further down this document.
The overview names `h`, the height at which the jaw contacts the glass, as a
model input. In this cell the jaw always rides as low as it can, because the arm
is not told `μ` and low is the safe choice, so `h` is the same on every push and
carries no information at all.

The value of that constant `h` is **65 mm, not 50 mm**. The jaw's middle rides
at `LOWEST_GRIP`, which is 50 mm, but the jaw is 30 mm tall and a glass that is
wider higher up meets its top edge 15 mm above that. Keep the column in the log,
because a gripper change would make it vary. Do not expect the model to learn
anything from it today.

### The outputs

Three numbers, in the push's own frame rather than the table's: the error along
the push, the error across it, and the error in the glass's rotation. Using the
push's own frame means a push to the north and the same push to the east are one
example rather than two, which is worth doing because the table's friction is
the same in every direction. Rotation matters least here, because the glasses
are round and a round glass that has turned is in the same place it was.

### What the residual actually is in this cell

This is the part the overview could not supply, so it was measured.

The measurement uses the project's own physics bench, `problem-3-sim/bench.py`,
and the project's own geometric planner, `problem-3-programmed/plan.py`. For
each of the 250 tables numbered 10100 to 10349, the arm looks, `plan.choose`
returns the push it would really make, the push is made, and the position the
simulator records afterwards is compared against `push.aim`, which is where the
planner expected the glass to finish. 248 of those tables produced a push that
touched a glass. The backbone being corrected here is the simplest one there is
— the glass finishes where the jaw took it — which is also what solution 4
predicts once the push line passes through the footprint centre, because then
`d` is zero and the sideways drift term drops out.

Over those 248 pushes, the glass finished **1.31 mm short** of where the push
aimed it, on average, with a standard deviation of 1.12 mm. Sideways it finished
0.05 mm off, with a standard deviation of 0.54 mm. The distance between the aim
and the landing had a median of 1.20 mm, a ninetieth percentile of 2.95 mm, and
a largest value of 5.26 mm. Nothing toppled.

That shortfall is not noise. It is a real, repeatable loss at the start of every
push, and `plan.py` already names its cause in a comment: the contact has to
take up and the glass has to settle onto its leading edge before it starts to
travel. The measurement says how big that is, and it says something more useful
still.

![What there is to learn: a fixed loss at the start of every push. On the left,
the average shortfall per kind of glass over the same 248 measured pushes, with
one standard deviation as whiskers. On the right, that fixed loss expressed as a
share of the push it was taken from, against how far the push was commanded to
go.](../../../images/problem-3/05-the-loss-is-a-fixed-cost.png)

**The loss does not grow with the push.** Over the 248 pushes the correlation
between the shortfall and the commanded distance is −0.021, which is nothing.
Fit a straight line and the slope comes out at −0.12 mm per 100 mm of travel,
against an intercept of −1.29 mm. So this is a fixed cost paid once when the jaw
first bears on the glass, not a slip that accumulates along the way.

**The loss differs by kind.** A straight glass loses 0.49 mm on average, a short
stemmed glass 0.99 mm, a tapered glass 1.32 mm, and a stemmed glass 2.44 mm.
That ordering is not a coincidence: the jaw meets a stemmed glass at its stem,
well inside the bowl above it, so there is more of the glass to be set in motion
after the contact has taken up. This is precisely the sort of thing a residual
is good at absorbing, because it is systematic, small, and impossible to derive
without knowing how the weight is arranged inside a glass the arm has only seen
from outside.

**The loss matters most on the shortest pushes.** The planner takes the
shortest push that frees the glass, so over these 248 pushes the median
commanded distance was 2 mm, nine in ten were under 36 mm, and the longest was
132 mm. A fixed 1.3 mm loss on a 2 mm push is most of the push. Measured
directly, the median loss was 57 per cent of the commanded distance over the 160
pushes of 5 mm or less, and 2 per cent over the 64 pushes of 20 mm or more.

## The feedback loop

A residual model is only trustworthy where it has seen data, and it improves
only if data keeps arriving. Both halves of that are a loop, and this solution
has an unusually good one.

### Every push is already a labelled example

[Solution 3](03-plan-feel-look-again.md) photographs the table after every push
and re-runs problem 2's separation over the new picture, because that is how it
decides whether to push again. So for every push the arm has ever made, three
things already exist in the run: where the glass stood before, what push was
commanded, and where the glass stood afterwards. That is an input, an action and
an outcome, which is a complete labelled training row.

Nobody labels it. No simulator has to be asked what it spawned. The row is a
by-product of a measurement the run was making anyway for its own reasons. That
is what makes this solution nearly free to collect for, and it is the strongest
single argument in its favour.

### How many examples a run produces

Two measurements answer this, and they agree.

The first counts the work a table starts with. `scene(seed)` in
`problem-3-sim/bench.py` is the generator for problem 3's tables, and over the
200 tables numbered 10000 to 10199 it produced four to six glasses each, 1001
glasses in all. Counted with bench's own `has_room`, **760 of those 1001
glasses lacked room** — 76 per cent — which is **3.80 crowded glasses per
table**, and every one of the 200 tables had at least one.

The second counts the pushes actually made. `problem-3-programmed/results.json`
records the geometric approach clearing 50 held-out tables holding 251 glasses,
190 of them crowded at the start, with 212 pushes. That is **4.24 pushes per
run**, and the 190 over 50 tables is the same 3.8 per table the first
measurement found.

One warning about where these numbers cannot come from. The spawner used
elsewhere in the project, `random_glasses` in `glasses/spawn.py`, keeps every
pair of glasses at least `MIN_SEPARATION` apart, and `MIN_SEPARATION` is
150 mm. Over 200 of its arrangements of four to six tapered glasses — 1001
glasses, the same count as the bench's 200 tables — the closest pair was
150.0 mm apart at worst, and `has_room` found **not one** glass short of room.
It cannot
produce a crowded table, so it cannot be used to count crowded pairs or pushes.
`bench.scene` is the generator to use, and it places each glass either somewhere
free or deliberately close to one already down, between touching and having
room.

At that rate, the size of the dataset against the number of runs it takes is
easy to state. Read this table as the answer to "how long before it is worth
anything".

| labelled pushes | runs of the arm | what the fit is worth there |
| --- | --- | --- |
| 0 | 0 | nothing; the system is exactly solution 4 |
| 5 | about 1 | worse than nothing, measured below |
| 20 | about 5 | most of the bias removed |
| 40 | about 9 | within 7 per cent of the floor |
| 124 | about 29 | the floor |

Two or three days of ordinary operation, in other words, if the arm clears ten
tables a day. That is the strongest practical fact about this solution: the
waiting is measured in days of normal work rather than in hours of dedicated
data collection.

### What the examples actually buy

The curve below is measured, not assumed, and the way it was measured matters.
The 248 pushes were shuffled, 124 held out, and a ridge regression fitted to the
first `n` of the remaining 124. Ridge regression is ordinary least squares with
a penalty on large coefficients, which is what keeps a fit on five rows from
being wild. The fit was shown the commanded distance, the glass's foot width,
widest width and height, and which kind of glass the table held. It was scored
on the held-out 124 by the root mean square distance between the corrected
prediction and where the glass really went. The whole thing was repeated over 40
shuffles and averaged.

![What the examples buy. Held-out error against the number of labelled pushes
the residual was fitted on, measured over 124 held-out pushes and 40 shuffles.
The upper dashed line is the prediction with no model at all; the lower one is
the floor this fit reaches. The top axis converts training pushes into runs of
the arm at the 4.24 pushes a run really
makes.](../../../images/problem-3/05-what-the-examples-buy.png)

Three things in that curve are worth naming.

**It starts at 1.83 mm and ends at 1.05 mm.** That is the whole prize. The
residual removes 0.78 mm of error from a prediction that was already good to
about a millimetre and a half, in a planner that pads every destination by
10 mm.

**Five examples are worse than none.** At five training rows the held-out error
is 1.87 mm, slightly above the 1.83 mm of no model at all, because a fit on five
noisy rows follows the noise. This is the cold start showing up as a number
rather than as a caution, and it is the reason the fallback described below is
not optional.

**One number gets most of the way.** A correction that is simply the average
loss, fitted on 40 pushes and applied to everything, scores 1.25 mm against the
ridge fit's 1.12 mm. So about three quarters of what this solution achieves is
the single observation that a glass finishes about 1.3 mm short, and the
per-kind and per-size terms are the last quarter.

### The cold start, said plainly

On the first run there is no data, so the residual is zero, so
`f(x) + g(x) = f(x)`, so the arm behaves exactly as [solution
4](04-predict-the-slide.md) behind [solution 3](03-plan-feel-look-again.md)'s
look-again. That is not a limitation to be worked around. It is the design
working: the floor under this solution is the system it was added to, and on day
one the arm is standing on the floor.

The thing to design is what happens between the first run and the fortieth. The
rule is that the residual applies only where the model has evidence, and the
model has to be able to say where that is.

### Knowing when the model is outside its data

Two ways, and they differ in what they cost.

A **Gaussian process** returns a standard deviation with every prediction, from
`predict(X, return_std=True)`. A Gaussian process is a fit that treats the
unknown function as a distribution over smooth functions rather than as one
curve, so it can say how much the plausible curves disagree at a point it has
not seen. The
[scikit-learn implementation](https://scikit-learn.org/stable/modules/gaussian_process.html)
is BSD-3-Clause licensed and pure Python over NumPy. Why this rather than the
obvious alternative of a neural network: the network gives no honest uncertainty
without being trained several times over, and here the uncertainty is the point
rather than the accuracy. What it costs: fitting is cubic in the number of
training rows, which is irrelevant at a few hundred rows and fatal at a hundred
thousand.

**Ridge regression** gives no uncertainty, so the distance to the fifth-nearest
training row in scaled inputs stands in for one.
[Ridge](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)
is also scikit-learn and BSD-3-Clause. Why this rather than the Gaussian
process: ten coefficients that can be printed in a report, a fit that takes
microseconds, and no kernel to choose. What it costs: the neighbour distance is
a cruder signal than a standard deviation, and a linear fit cannot represent a
correction that bends.

Start with ridge, and move to the Gaussian process for its error bars rather
than for its accuracy. A small network in [PyTorch](https://pytorch.org/) is the
third option and is not worth it until the dataset runs to thousands of rows,
which at 4.24 pushes a run is several hundred runs away.

One correction to the overview's account belongs here. It proposes discarding
the residual whenever the predicted standard deviation exceeds 4 mm. Measured,
the residual's own scatter about its average is 1.12 mm along the push and
0.54 mm across it, so a 4 mm threshold would never fire and the fallback would
never run. Set the threshold from the measured scatter — two standard
deviations, so about 2.5 mm — or the safety argument is decoration.

**The response when the threshold fires** has three parts. Discard the residual
and use `f(x)` with solution 4's conservative assumption about the base. Pad the
destination, requiring `has_room` to pass with the planner's full 10 mm margin
rather than with a corrected estimate of it. Take the picture, rather than
chaining a second push on a prediction. The third part is what closes the loop:
the picture
produces a labelled row in exactly the region the model was short of, so
extrapolation triggers the measurement that cures it.

## A worked example

Take the arrangement in the first picture: five tapered glasses drawn from the
kind's own range and laid out the way `bench.scene` lays out a table, with all
five of them lacking room. One of them stands 101 mm from a neighbour 81 mm
across, and the test that decides this is worth stating exactly, because it is
easy to get backwards.

**The room test is asymmetric.** `has_room` in `problem-3-sim/bench.py` asks
whether every *other* glass's edge is at least `GRIP_ROOM` — 70 mm — from this
glass's middle. So the distance a glass needs from a neighbour is 70 mm plus
half the *neighbour's* width, not half its own. A narrow glass beside a wide one
is crowded while the wide one beside it is not, which is exactly right: the jaw
has to fit round the glass being picked up, and what is in the way is the
neighbour's body. The glass in the picture therefore needs 70 + 40.5 = 110 mm
from that particular neighbour and has 101 mm.

The 140 mm that [the problem](../problem.md) quotes is the symmetric worst case
— two of the widest glasses of a kind — and it is a useful single number to hold
in mind. It is not the test the code runs, and using it instead gets the count
of crowded glasses wrong.

The planner chooses to push that glass straight away from its neighbour, far
enough that `has_room` passes with the planner's own 10 mm margin on top.

**Run one.** There is no dataset, so the residual is zero. The prediction is the
analytical one: the glass finishes where the jaw took it. The arm pushes, looks,
and finds the glass about 1.3 mm short of that. It takes a second look, confirms
the pair is now far enough apart, and writes one row to the log. The run
behaved exactly as solution 3 does today, and the only difference is the row.

**Run ten.** The log holds about 42 rows. A ridge fit on them returns an
intercept near −1.1 mm along the push and coefficients on the glass's
measurements that are small but real. Applied to the next push, the prediction
becomes "the glass will finish 1.1 mm short", and the held-out measurement says
that prediction is right to about 1.1 mm rather than 1.8 mm. The planner's
destination moves by a millimetre. Nothing else in the run changes.

**Run thirty.** The log holds about 127 rows, and the fit has reached its floor
of 1.05 mm. It has also learned something a person could have guessed but nobody
could have quantified: that a stemmed glass loses 2.44 mm where a straight glass
loses 0.49 mm, because the jaw meets a stemmed glass at its stem. The report can
now print that sentence, with its standard deviations, from a log file.

**The honest accounting.** Across those thirty runs the residual removed 0.78 mm
of prediction error from a planner that pads every destination by 10 mm and
photographs the table after every push regardless. It changed no outcome. The
mechanism worked exactly as advertised; the quantity it had to work on was
small.

### The case where the residual has something larger to do

The residual is small because the planner always aims its push line through the
measured footprint centre. `plan.along` in `problem-3-programmed/plan.py` starts
the jaw at the glass's measured centre, backed off along the push direction by
the glass's radius and a small approach gap, with no sideways offset at all. So
the miss distance `d` is zero by construction, and solution 4's sideways-drift
term is zero with it.

To find out what the residual would have to absorb if that were not true, the
same 30 tables numbered 10000 to 10029 were pushed four times each: once as the
planner intended, and once with the jaw's descent point shifted 10 mm, 20 mm and
−20 mm across the push line, keeping every other part of the push identical.
Of those 120 attempts, 111 had a descent point clear of every other glass and
were made; all 111 touched the glass, and none toppled anything. The nine that
were not made are the shifted descent points that would have come down on a
neighbour, which is itself a reminder of how little room a crowded table
leaves. The table below reports how far the glass finished from where the push
aimed it. Read each row as one offset, and read the last column as the worst case
rather than the typical one.

| how far the push line missed the centre | pushes | median error | ninetieth percentile | worst |
| --- | --- | --- | --- | --- |
| 0 mm, as the planner aims | 30 | 1.0 mm | 2.5 mm | 3.0 mm |
| 10 mm | 30 | 1.0 mm | 2.7 mm | 2.8 mm |
| 20 mm | 24 | 2.9 mm | 13.1 mm | 40.2 mm |
| −20 mm | 27 | 1.4 mm | 12.1 mm | 15.7 mm |

Two conclusions follow, and the second is the more important.

**Aiming through the centre is worth more than any correction.** Ten millimetres
of aiming error costs nothing measurable. Twenty millimetres costs tens of
millimetres of outcome error. Solution 4's qualitative advice — aim through the
footprint centre, where the answer is the same under every pressure distribution
— is doing the work that the residual is being proposed to do.

**Where the error is large it is not smooth.** The 40.2 mm case is not a glass
that drifted 40 mm sideways. It is a glass that slid off the corner of the jaw
part way through the push and stopped travelling: the error is almost all along
the push, and it is the difference between a glass that was carried and a glass
that was dropped. No smooth function of the inputs can represent that, because
it is not a smooth event. A residual model fitted over such rows will average a
carried glass and a dropped one and be wrong about both.

That is the precise condition under which residual learning fails, and it is
worth stating as a rule. **A residual is only learnable where the backbone is
wrong by a smooth amount.** Where the backbone stops describing the event at all
— the glass rocks rather than slides, the contact is lost, the jaw catches a
neighbour — the difference between prediction and outcome is not an error term.
It is a different event, and it needs a classifier, which is
[solution 7](07-a-learned-change-verifier.md), or a stop, which is
[solution 8](08-a-learned-early-abort.md).

## What it needs

Solution 4's analytical model, callable, so there is something to correct.
Solution 3's look-again, which supplies every label. A log file of past pushes
holding the inputs, the prediction, the measurement and the uncertainty. One
small pure-Python dependency, scikit-learn, with no CUDA anywhere in it.
Retraining between sessions rather than during a run, so that no run's behaviour
changes half way through it. No new hardware, no simulator time, no graphics
card.

It also needs one thing that is easy to leave out: a rule for throwing rows
away. A push that half-toppled a glass, a push where the glass was lost off the
jaw, and a push where problem 2 mislocated the glass are all rows that will be
absorbed as physics if they are kept.

## Where the idea comes from

Residual learning in robotics is about ten years old as a named pattern, and
three pieces of work between them cover the design space. Each is given here
with what it buys and what it costs, because the three are not
interchangeable.

### Residual physics — a learned correction on an analytical prediction

Zeng, Song, Lee, Rodriguez and Funkhouser, [*TossingBot: Learning to Throw
Arbitrary Objects with Residual Physics*](https://arxiv.org/abs/1903.11239)
(2019). A robot arm throws objects into bins. A ballistic model supplies the
release velocity for a given target, and a network predicts a correction to that
velocity, learned from where the objects actually landed.

**What it buys.** The ballistic model carries every target, including distances
the robot has never thrown to, so the network only ever learns about drag, shape
and the way an object leaves the fingers. The authors report that this
generalises to new objects and new target locations, which the paper reports and
a network learning the whole throw does not manage.

**What it costs.** It needs the analytical model to be nearly right, which for
a thrown object means the object has to be roughly ballistic. It also needs a
lot of throws — this is a physical robot throwing for days — because the
correction is a function of the object's appearance as well as its geometry.

This is the closest published relative of what is proposed here, and the
difference is the data. TossingBot's residual is learned over a whole visual
appearance; the residual here is learned over five measured numbers, which is
why a few dozen examples are enough rather than a few hundred thousand.

### Learned residuals on a simulator — putting the correction inside the model

Ajay, Wu, Fazeli, Bauza, Kaelbling, Tenenbaum and Rodriguez, [*Augmenting
Physical Simulators with Stochastic Neural Networks: Case Study of Planar
Pushing and Bouncing*](https://arxiv.org/abs/1808.03246) (2018). This is planar
pushing specifically — the same mechanics solution 4 uses — with a neural
network learning the residual between an analytical simulator's prediction and
what a real object did.

**What it buys.** The residual here is *stochastic*: the network learns a
distribution over the error rather than a single correction, so the model says
how uncertain the outcome is as well as what it expects. That is the right shape
for planar pushing, because the headline empirical finding about real pushing is
that outcomes scatter more than deterministic theory predicts.

**What it costs.** A distribution is a harder thing to fit than a mean, so it
needs more data than a point correction, and it needs a planner that can use a
distribution rather than a number. For this cell that is the wrong trade today:
the measured scatter about the average is 1.12 mm, and a planner that already
carries a 10 mm margin has nothing to do with a better estimate of it.

### Residual policy learning — correcting a controller rather than a prediction

Silver, Allen, Tenenbaum and Kaelbling, [*Residual Policy
Learning*](https://arxiv.org/abs/1812.06298) (2018), and Johannink, Bahl, Nair,
Luo, Kumar, Loskyll, Aparicio Ojea, Solowjow and Levine, [*Residual
Reinforcement Learning for Robot Control*](https://arxiv.org/abs/1812.03201)
(2018). Both take an existing hand-written controller and learn an additive
correction to its *actions* by reinforcement learning, rather than a correction
to a prediction.

**What it buys.** The hand-written controller does the easy nine tenths of the
task from the first episode, so the reinforcement learning never has to discover
the basics by exploration, which is where most of its cost normally goes. Both
papers report large improvements on tasks where the scripted controller alone
performs poorly and pure reinforcement learning fails to get started.

**What it costs.** It is still reinforcement learning. It needs episodes, a
reward function, and an exploration schedule, and it can only be trained where
failures are cheap. It is also the one of the three with no floor: the learned
correction is applied to the action, so a bad correction produces a bad action
directly, and nothing downstream is in a position to disagree. That is the
opposite of what this cell wants, where the failure to avoid cannot be undone.

The distinction worth carrying away is **what the residual is added to**.
Added to a *prediction*, as here and in the first two papers, a wrong residual
costs a slightly wrong plan that the next photograph corrects. Added to an
*action*, as in the third, a wrong residual moves the arm. The arrangement is
named the same in both cases and the consequences are not comparable.

## The line the residual may not move

Everything above concerns where a glass finishes. One thing in problem 3 is not
about where a glass finishes, and the residual must be kept away from it
entirely.

A pushed object slides while the push height `h` is below `a / μ`, where `a` is
half the base width and `μ` is the friction with the table, and it tips above
that. So a glass whose tipping limit falls below the height the jaw contacts it
at has no safe place to be pushed at all, and the only correct answer for it is
to refuse.

**That contact height is 65 mm, not 50 mm, and the difference decides the
answer for half the kind.** `LOWEST_GRIP` is 50 mm, and that is where the
*middle* of the jaw rides. The jaw is 30 mm tall, so its top edge is 15 mm
higher, and `problem-3-sim/bench.py` says in as many words that a glass wider
higher up meets that top edge first, so `JAW_TOP` rather than `PUSH_HEIGHT` is
how high it is pushed. Every tapered glass is wider higher up, by the definition
of the kind. So the height to compare the tipping limit against is 65 mm.

![The tipping limit is not the residual's to correct. On the left, two glasses
of one kind at proportions inside the kind's declared range, with the height
above which each tips at the two friction values this project brackets with, and
the band below the jaw's top edge in which no safe push exists. On the right,
the share of 400 drawn tapered glasses that can be pushed at all, against
friction, drawn twice: against the jaw's top edge at 65 mm, which is where a
tapered glass is really met, and against its middle at 50 mm, which is not. The
marked 0.35 is the simulator's own table, which the arm is never told.](../../../images/problem-3/05-the-line-the-residual-may-not-move.png)

The right-hand panel is the reason this section exists, and the numbers in it
were measured with the project's own spawner: 400 tapered glasses drawn by
`family("tapered_glass", 400, seed)`, five times over, for seeds 1 to 5. Read
the table below as the share of those glasses with any safe push height at all,
with one row per friction value and one column per contact height; the 65 mm
column is the real one and the 50 mm column is what the same arithmetic gives if
the 15 mm of jaw is forgotten.

| friction | contact at 65 mm, the jaw's top edge | contact at 50 mm, its middle |
| --- | --- | --- |
| 0.30 | 52.0 to 59.0 per cent | 92.0 to 94.8 per cent |
| 0.35 | 23.8 to 28.8 per cent | 71.8 to 76.0 per cent |
| 0.40 | 8.2 to 11.5 per cent | 47.8 to 52.5 per cent |
| 0.50 | **none at all** | 13.2 to 17.2 per cent |

A glass with the median foot of those draws, 39.5 mm, stops being pushable above
μ = 0.30 at the real contact height, where the same glass would survive to
μ = 0.39 at the jaw's middle. The widest foot in the 400, 59.5 mm, stops above
μ = 0.46. That is why the 0.50 row is empty rather than small: at that friction
no tapered glass this cell can draw has a tipping limit above 65 mm.

That is a cliff, and `μ` is the coordinate along it.

Two senses of "unknown" have to be kept apart here, and the rest of this section
depends on the difference. `problem-3-sim/bench.py` sets `TABLE_FRICTION` to
0.35, so **the simulator knows `μ` exactly**. It is ground truth, the number a
run is scored against. **The arm is never told it.** Nothing the arm measures
reveals it, no input to any decision the arm makes contains it, and the tipping
check runs on a conservative guess instead. Every figure quoted in this document
that involves friction is a statement about the physics of the table, not about
anything the arm has in its hand.

The comment beside that constant says glass on a dry wooden top is somewhere
between 0.2 and 0.5, which is the whole range of the cliff above. So the arm is
operating somewhere on a curve that runs from half the glasses pushable to none
of them, and it does not know where.

### Why the residual does not transfer to another table

A residual fitted on this table has absorbed this table's `μ`, tangled together
with the way these glasses' weight sits on their feet. It cannot separate them,
because it was never given a term for either. Move the arm to a table with a
different surface, or wipe the same table with a different cloth, and the
residual is a correction for a world that is no longer there. The model will not
say so. It will keep returning corrections with the same confidence, and only a
rising prediction error over several runs reveals what happened.

[Solution 9](09-identify-the-contact-parameters.md) is the close relative that
does not have this problem, and the difference is worth keeping straight.
**Solution 5 learns the model's error. Solution 9 learns the model's missing
input.** Solution 9 comes back with an estimate of `μ` itself, with an interval
around it, which the tipping check can then use at its pessimistic end — and
which every other part of the system can use too, because it is a physical
quantity rather than a correction term. Solution 5 comes back with a number that
means nothing outside the dataset that produced it.

### The rule, enforced structurally

**The residual must never touch the tipping check.** Not to raise the allowed
push height, not to relax the guessed `μ`, and not to argue that this particular
glass has been pushed safely twenty times.

Enforce that by construction rather than by discipline. The function that
chooses the push height takes the measured base width and a fixed conservative
`μ`, compares the tipping limit against the height the glass is really met at
rather than the height the jaw's middle rides at, and does not import the
residual model at all. Then no future change can
wire the two together by accident, because the wiring does not exist.

The residual may make a push more conservative — shorter, better aimed, with a
larger margin at the destination. It may not make one permissible. **It may
improve aim. It may not grant permission.**

## Where it is strong and where it breaks

The strengths come from the arrangement rather than from the model.

**It turns operation into improvement.** The arm gets better at pushing by
pushing. There is no training phase, no labelling work and no data collection
campaign, because the labels are a by-product of a measurement the run was
making anyway.

**There is a floor under it.** With the fallback wired in, the worst case is the
behaviour of solution 3 with solution 4's prediction, which is the system this
was added to.

**It stays explainable.** A report can print the physics prediction, the
correction, the outcome and the reason, as four numbers on one line.

**It is small.** Ten coefficients, a CSV file, and a dependency with no CUDA in
it. That is a different order of commitment from the 38,012 pushes and the
five-model ensemble that solution 10 needs.

The weaknesses divide into what it cannot do, what it cannot survive, and what
it is not worth here.

**It needs the backbone to be nearly right.** Measured above: where the push
line misses the footprint centre by 20 mm, the error stops being a smooth
function and becomes the difference between a carried glass and a dropped one. A
correction to a badly wrong prediction is a second model in disguise.

**It cannot supply the missing measurement.** `μ` stays unknown to the arm. Its
effect on where a glass finishes is learned tangled with the pressure
distribution, and neither can be recovered from the other.

**It is silent about drift.** Change the table and the old residuals go stale
with no announcement. The only signal is prediction error rising over several
runs, which means somebody has to be watching a number that nothing depends on.

**It will learn a bug.** If problem 2 mislocates a glass by 3 mm in some
repeatable way, the residual absorbs that as physics and keeps it until the
dataset is cleared. Fixing the perception then makes the pushing worse for a
while, which is a confusing failure to debug.

**And in this cell it is not worth much.** The measurement is 1.83 mm of error
before the residual and 1.05 mm after, in a planner that pads every destination
by 10 mm and photographs the table after every push regardless. The mechanism
works. The margin it improves was not the binding constraint, and the next
section shows what the binding constraint actually is.

### Where the overview's account needs correcting

Five things in the overview's section on this solution need correcting, and they
are listed here rather than quietly fixed.

Its worked example has the glass drifting 17 mm sideways under one assumption
about the base and 7 mm under another, and a residual of −9 mm learned from the
difference. Nothing in this cell produces errors of that size when the push line
goes through the footprint centre: over 248 measured pushes the largest total
error was 5.26 mm, and over the 212 pushes in the project's scored run the worst
was 3.9 mm. The 17 mm is what the theory gives for a 5 mm aiming error, and the
planner's aiming error is not 5 mm.

Its estimate of the data rate — three to eight pushes a run, so fifty runs is
two to four hundred pushes — is about right at its low end. The measured rate is
4.24 pushes a run, so fifty runs is about 212.

Its threshold for discarding the residual, a predicted standard deviation above
4 mm, is larger than the whole residual. Set from the measured scatter it should
be about 2.5 mm.

Its argument that a residual good to a few millimetres is what would let two
pushes be chained before looking has the causation backwards. The backbone is
already good to 1.2 mm at the median with no residual at all. What stops pushes
being chained is not prediction error; it is that the second push's destination
has to be checked against an arrangement that the first push changed.

And it declines to give identifiers for the published work it names, on the
grounds that it is sure of the work and not of the references. The four
references are given in full above, and every link was checked before this
document was written.

## Landing accuracy is not what the task is scored on

Everything above improves one number: how close a glass finishes to where the
push aimed it. This section is the check on whether that number is the one that
matters, and the answer is no.

Two complete pipelines in this repository clear the same 50 held-out tables.
Read the table below as one column per pipeline; the first three rows are the
result the problem asks for, and the last two are how accurately each pipeline
predicted where its pushes would put a glass.

| | `problem-3-programmed` (geometric) | `problem-3-learned` (solution 10) |
| --- | --- | --- |
| glasses racked, of 251 | 199 | **208** |
| glasses refused | 52 | **43** |
| pushes made | 212 | **113** |
| repeat pushes | 90 | **15** |
| landing error, median | **1.0 mm** | 1.7 mm |
| landing error, worst | **3.9 mm** | 24.8 mm |

Both figures come from the `results.json` beside each pipeline, and both files
record the same 50 scenes, the same 251 glasses and the same 190 glasses crowded
at the start, so the two ran on identical tables. Neither toppled anything and
neither pushed a glass out of the zone. One caution about the source: both files
hold the same seven top-level keys and **neither carries a date, a commit, or
any description of what produced it**, so they are trustworthy as a record of
the scoring code's output and not as a record of when.

The pipeline that is worse at predicting landings — 1.7 times worse at the
median and six times worse at its worst — racks nine more glasses using 99 fewer
pushes, with a sixth as many repeats.

**So the accurate predictor is the one doing more work for less result.** The
geometric planner already knows where a glass will land to about a millimetre,
which is better than this document's residual could ever make it, and it still
has to push 90 times over. The reason is not that its aim is off. It is that
**knowing where a glass lands does not tell you which push will make room.** A
push can land exactly where it was aimed and leave the glass still crowded,
because the room a glass needs depends on the neighbour it is measured against
and on where every other glass stands. That is the quantity the task is scored
on, and it is a different function of the same inputs.

The learned pipeline predicts that different quantity. `features.py` shows what
it is asked for: where the pushed glass moves *and where every other glass
moves*, plus whether anything toppled and whether the jaw was blocked. From
that, its planner can score a candidate push by how much room the whole table
would still be short of afterwards. It is worse at the millimetres and better at
the question.

Three cautions keep this from being a controlled experiment. The two pipelines
differ in more than their model: the learned one searches over headings, contact
offsets and distances with the cross-entropy method, while the geometric one
takes the shortest freeing push from a fixed set of headings and applies
corridor checks the learned one has no equivalent of. Their refusals differ in
kind as well as in number — the geometric one refuses 52 glasses for "nowhere
clear to push it to", the learned one refuses 42 because no push it can imagine
is expected to make room. And the learned pipeline is the weaker on the failure
that cannot be undone: its own README records one topple across 100 tuning
tables, where the geometric one has a tipping check that does not depend on a
model being right.

None of those change the direction of the result, and none of them are needed
for the conclusion that matters here. **The residual improves a number that was
already better than the winning pipeline's, in the pipeline that loses.** If
something learned is going to be added to the push, the quantity worth learning
is whether a push will leave the glass with room — not by how many millimetres
the glass fell short.

## Where it sits among the other solutions

The clearest way to place this solution is against the three it is most easily
confused with.

Against [solution 4](04-predict-the-slide.md), it is the same prediction with a
correction on the end. It adds a dependency and a file of weights, and it
removes 0.78 mm of error. If solution 4 is not built, this is not buildable.

Against [solution 9](09-identify-the-contact-parameters.md), it learns the error
where solution 9 learns the missing input. Solution 9's answer transfers to
another table, improves a safety decision, and can be used by every other part
of the system. Solution 5's answer does none of those things. Where both are
affordable, solution 9 is the one to want.

Against [solution 10](10-learn-a-forward-model-then-plan.md), it is the same
ambition at a hundredth of the cost, with a floor underneath it. Solution 10
needed 38,012 pushes and five trained networks. This needs about 40 of the arm's
own pushes and ten coefficients. Solution 10 pays for that by having no answer
at all when its weights are deleted — and it buys something this solution cannot
represent at any price: where the *other* glasses go, and therefore whether the
push makes room. On the same 50 tables that is worth nine more glasses racked
and 99 fewer pushes, while being worse at every millimetre. Cheapness is this
solution's advantage over solution 10. Usefulness is not.

And against [solution 7](07-a-learned-change-verifier.md), which the overview
picks as the first learned thing worth adding, the comparison is about what
failure is being addressed. This solution makes a good prediction slightly
better. Solution 7 catches the case where the arm believes a push worked and it
did not. For a problem whose one unrecoverable failure is a toppled glass, the
second is worth more.

So the honest position is the one [solution 4](04-predict-the-slide.md) arrives
at from the other direction. Build [solution 1](01-do-not-drag-at-all.md) and
[solution 3](03-plan-feel-look-again.md). Keep the log they produce, because it
costs nothing and it is the training set for everything else here. Then measure
which failure you actually have before choosing a component to fix it.

Measured, that failure is not aim. It is that 90 of the geometric pipeline's 212
pushes are repeats, made by a planner whose aim is already good to a millimetre.
So the lesson this document ends on is not about residuals at all: **check that
the quantity you are about to improve is the quantity the task is scored on.**
The residual arrangement is sound, it is cheap, it trains itself out of ordinary
running, and here it sharpens the one number that was never in the way.

It would be the right choice somewhere else. On a table where pushes are long
rather than short, where the destination margin is tight rather than generous,
or where looking again after every push is expensive rather than nearly free, a
correction that turns 1.8 mm into 1.0 mm changes outcomes. In that setting
everything above applies unchanged, and the feedback loop is still the best part
of it. Here it does not change outcomes, and the way to find that out was to
measure it.

---

← [The problem](../problem.md) · [Solution overview](solution-overview.md) ·
[Solution 4 — predict the slide](04-predict-the-slide.md) ·
[Solution 6 — geometry generates, a model ranks](06-geometry-generates-a-model-ranks.md) →
