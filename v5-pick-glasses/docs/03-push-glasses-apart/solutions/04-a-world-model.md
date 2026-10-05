# Solution 4 — a world model, then plan with it

> **What it uses** — PyTorch, and MuJoCo through [the test
> bench](../the-bench.md). Rung one is a small network written for this cell
> and trained here, five copies of it, with no downloaded weights of any kind.
> Rung two would be TD-MPC2, the model-based entry in LeRobot, trained here as
> well. **Rung two is not built**, so no number anywhere in this document is
> its. Neither rung borrows a model from anybody, so the only licences in play
> are the libraries' own.
> **What it does** — it learns what a push does, and then looks for a good push
> by trying candidate pushes against that learned model instead of against the
> table. The model takes the table as the camera measured it and one push, and
> answers with the table afterwards: where every glass moves, whether anything
> topples, and whether the jaw is blocked on the way down. Because the answer
> is a table rather than a score, the same answer can be fed back in as the
> next question, which is what would let this solution plan a *sequence* of
> pushes — move one glass out of the way first so that a second glass has
> somewhere to go. The built planner's horizon is one push, so the sequence is
> an extension this document designs rather than code that runs.
> **How the output is produced** — `look()` hands over one reading per glass;
> the shared topple limit that refuses a glass that tips before it slides
> belongs in front of all of this, and the built planner does not have it yet;
> the readings and a candidate push are encoded
> into one row of numbers in the push's own frame; the five copies of the model
> each answer; a candidate is thrown away if any copy thinks it might topple
> something, or if the predicted table breaks the map; the survivors are scored
> by how much room is still missing afterwards; a sampling search refines the
> good ones and returns the best push; that push is handed to the bench as a
> parameterised push, and the bench's own macro expands it into a jaw
> trajectory.
> **How it differs from the other five** — [one fixed
> nudge](01-one-fixed-nudge.md) has no model at all and finds out what a push
> did by looking afterwards, where this one asks before. [Geometry generates, a
> model ranks](02-geometry-ranked.md) also scores candidate pushes, but its
> candidates come from written geometry and its ranker scores a push without
> ever saying what the table will look like, so it cannot chain two pushes
> together. [Imitation from demonstrations](03-imitation-from-demonstrations.md)
> learns the answer directly and never represents the table afterwards, so it
> is faster to run and cannot be re-aimed at a new goal without new training.
> [SmolVLA as it downloads](05-smolvla-as-it-downloads.md) and [SmolVLA
> fine-tuned](06-smolvla-fine-tuned.md) bring a large pretrained policy to the
> same question; they, too, learn what to do rather than what will happen.
> **What it costs** — pushes made in the simulator and recorded, which is the
> only training data either rung needs and which nobody has to label. Rung one
> trains on an ordinary processor in minutes and needs no rented hardware at
> all. Rung two is reinforcement learning and wants an accelerator: a weekend
> of rented time, of order a hundred dollars, and a month of a small one, of
> order five hundred, if several training seeds are to be run. At run time both
> rungs are the expensive end of the six, because the search asks the model
> about hundreds of candidate pushes before every single push the arm makes.

> **The cell is described once, in [the cell](../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the side,
> all four sensors, and the words this project uses them with. What follows is
> only what is specific to this solution.

## Introduction

This document explains how to answer [problem 3](../problem.md) by learning a
model of what a push does, and then choosing pushes by trying them out against
that model rather than against the table.

The idea worth holding on to while reading is a small one with large
consequences. Every other solution here learns, or writes down, **what to do**.
This one learns **what will happen**, and works out what to do from it. That
single difference is what gives this solution the one capability none of the
other five could have: it can be extended to plan a sequence. It can choose a
push whose only value is that it makes room for the push after it — move one
glass aside so a second glass has somewhere to be pushed to — because a model
that returns a table can be asked again about the table it just returned. A
method that scores a push without saying where the glasses end up has nothing
to ask the second question of.

By the end you will understand five things. You will understand what a forward
model is and why it is a different kind of object from a policy. You will
understand how a push is chosen by sampling candidates and refining the good
ones, which is a search called the cross-entropy method, and why that search
suits a problem where the cost is not smooth. You will understand why a model
that is wrong in small ways is still useful, which turns on planning several
pushes ahead but executing only the first. You will understand why a
disagreement between several copies of the same model is a usable measurement
of the model's own ignorance, which is the most transferable idea in this
document. And you will understand what the two rungs buy against each other:
a small hand-built model that can be inspected, against a stronger off-the-shelf
one that brings a maintained implementation.

Read [the test bench](../the-bench.md) first, because what `look()` hands over
and what `push()` accepts are assumed throughout, and read [pushing without
toppling](../pushing-without-toppling.md), because the refusal rule this
solution adds learned evidence to is stated there.

## The code at the heart of it

Two pieces of rung one carry the whole idea, and they are short enough to read
here. The first is the forward model itself: five copies of a small network
that take a table and a candidate push and answer with what that push would do.
The second is the arithmetic that turns those five answers into a single
decision about one candidate — kept, or thrown away, and at what cost. They are
the heart of this solution because nothing else in it knows anything about
pushing: the model holds all of it, and this arithmetic is the only thing that
reads the model's mind.

The borrowed library does its work in the four `nn.Linear` lines, and
everything around them is the ensemble, in
[`03-push-glasses-apart/04-a-world-model/model.py`](../../../03-push-glasses-apart/04-a-world-model/model.py):

```python
ENSEMBLE = 5
HIDDEN = 256


class PushNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(features.INPUTS, HIDDEN), nn.SiLU(),
            nn.Linear(HIDDEN, HIDDEN), nn.SiLU(),
            nn.Linear(HIDDEN, HIDDEN), nn.SiLU(),
            nn.Linear(HIDDEN, features.OUTPUTS),
        )  # fmt: skip
...
class Ensemble:
    """ENSEMBLE copies, asked together."""
    ...
    def predict(self, x: np.ndarray) -> np.ndarray:
        """(copies, rows, outputs), raw: movements scaled, yes-or-no as logits."""
        with torch.no_grad():
            x_t = torch.as_tensor(x)
            return np.stack([net(x_t).numpy() for net in self.nets])
```

What the five answers are then used for is in
[`03-push-glasses-apart/04-a-world-model/plan.py`](../../../03-push-glasses-apart/04-a-world-model/plan.py),
where every candidate push is scored at once and the unacceptable ones are given
a cost of infinity:

```python
def score(model: Ensemble, seen: list, target, kind: str, heading, offset, travel, rng: np.random.Generator):
    """Expected crowding after each candidate push, and why any were dropped.
    ...
    """
    rows = features.encode(seen, target, kind, heading, offset, travel)
    out = model.predict(rows)
    move = out.mean(0)
    topple = sigmoid(out[:, :, features.TOPPLED]).max(0)
    blocked = sigmoid(out[:, :, features.BLOCKED]).mean(0)
    for _ in range(JITTERS):
        shifted = jittered(seen, rng)
        mine = next(s for s in shifted if s.id == target.id)
        out = model.predict(features.encode(shifted, mine, kind, heading, offset, travel))
        topple = np.maximum(topple, sigmoid(out[:, :, features.TOPPLED]).max(0))
    ...
    cost = blocked * here + (1 - blocked) * crowding + TRAVEL_COST * travel

    dropped = {
        "topple": ~(topple <= TOPPLE_LIMIT),
        "map": ~(inside & reachable),
        "unsure": moved_far,
    }
    cost[dropped["topple"] | dropped["map"] | dropped["unsure"]] = math.inf
    return cost, landing, {k: int(v.sum()) for k, v in dropped.items()}
```

Those two blocks are where this solution's result comes from, in both
directions. The displacements are **averaged** over the copies and the topple
chance is taken as the **worst** of them, and taken again on each shifted copy
of the table, so a push only has to look risky once to be dropped — which is
why this solution racks more glasses than any other answer to this problem, in
the fewest pushes, and why the glasses it gives up on are given up on with a
reason. It is also where the one glass it topples comes from: `topple` is the
model's opinion and nothing else's, so where all five copies are confident and
all five are wrong, there is nothing left in the code above to disagree with
them.

## The problem this solves

The problem is the one [problem 3](../problem.md) states, and this section
narrows it to the single difficulty this solution is aimed at.

Four to six glasses stand on a table, some of them closer together than the
gripper can work with. The arm has to push them apart without knocking any of
them over. [The target layout](../the-target-layout.md) has already settled
where the glasses should end up, because that is plain geometry with no
unknowns in it. What is left is the half that has unknowns in it: **what a
given push will actually do**.

That half is hard for one reason above all others, and [pushing without
toppling](../pushing-without-toppling.md) states it plainly. The rule that
decides whether a glass slides or tips compares the contact height against half
the foot width divided by the friction coefficient, and **nothing in this cell
measures friction**. The bench holds the coefficients privately and never tells
anybody. So any solution that writes the rule down is writing down a rule with a
guessed number in it, and the guess can be wrong by a factor that decides
whether a glass should have been touched at all.

There are two honest ways out of that. One is to guess carefully, act, look at
what happened, and correct — which is what [one fixed
nudge](01-one-fixed-nudge.md) and [geometry generates, a model
ranks](02-geometry-ranked.md) do. The other is the one this document is about:
**never write the rule down, and learn its consequences instead.** Push glasses
thousands of times, record what happened each time, and fit a function to it.
The friction coefficient is then not a number the solution holds. It is a
regularity in the recorded pushes, absorbed along with everything else nobody
wrote down — that the jaw has a body behind its fingers, that a tapered glass
meets the jaw's top edge, that a glass turns as well as travels.

![Whether a push slides a glass or tips it over turns on a friction nothing in the cell measures and on the height the jaw really meets the glass at, which for a tapered glass is the jaw's top edge and not its middle; across the range the friction plausibly covers, the share of drawn glasses that can be pushed at all runs from most of them to none, and a model fitted to recorded pushes absorbs both without ever being told either.](../../../images/03-push-glasses-apart/04-the-friction-it-absorbs.png)

There is a second difficulty, and it is the one the sequence capability
answers. A glass pushed out of one crowd can easily land in another, and a
glass pushed into its own clear spot can block the route the next glass needed.
**Choosing which glass to move, and in which order, needs the whole
arrangement**, not the crowded pair. That is a question about tables rather
than about pushes, and only a method that can say what a table will look like
afterwards can ask it.

## The main idea

The main idea is a separation, and the whole of this solution follows from it.

**Separate knowing what will happen from deciding what to do.** Fit one
function that answers *given this table and this push, what is the table
afterwards*. Keep it completely free of any opinion about what a good push is.
Then write the opinion separately, as plain arithmetic over tables: a table
where every glass has its 70 mm of clear room is good, a table where something
has fallen over is unacceptable, and a shorter push is better than a longer
one. Finally, put a search between the two: propose pushes, ask the model what
each one leads to, score the answers with the arithmetic, and make the best
one.

The reason that separation is worth making is that the two halves have
completely different sources of truth. What will happen is a fact about the
world, and it can only be learned from the world — which here means pushing
glasses in the simulator and recording the result. What counts as good is a
fact about the task, and it is already written down in [the
problem](../problem.md): 70 mm of clear room, nothing knocked over, as few
pushes as possible. Mixing them produces a thing that has to be retrained when
the task changes. Keeping them apart means **the same model serves a different
goal by changing only the arithmetic**. If the task later became spreading the
glasses evenly rather than clearing them, the model would not be touched; a
trained policy would have to be trained again.

![The model's question has one shape: a table as the camera measured it and one push go in, and a table afterwards comes out — a displacement for every glass, plus whether anything toppled and whether the jaw was blocked coming down.](../../../images/03-push-glasses-apart/04-what-a-forward-model-predicts.png)

## What exists in code, and what is a design

Before any of the concepts, it is worth saying which parts of this solution are
running code in this repository and which parts are described here and not
written, because this solution is unusual among the six in how much of it
exists.

**Rung one is built.** It lives in `03-push-glasses-apart/04-a-world-model/`, it
trains on data it collects itself, and it has been run on the bench's held-out
tables with its results recorded in that folder's own `results.json`, and set
beside the other five in `03-push-glasses-apart/results/README.md`. The model is
`model.py`, what it is shown is `features.py`, and the search and the loop
around it are `plan.py`. Everything this document says about those three files
is a description of code.

**The sequence capability is a design.** The planner that exists chooses one
push at a time: it scores each candidate by the table one push later, makes the
best push, and then looks again. It never asks the model about a push that
follows another push. The *model* is what makes planning a sequence possible,
because its answer is a table and a table is a legal question, and this document
explains how that extension works and what it would buy. But the horizon in the
built planner is one push, and the reason it is one push is given below under
compounding error.

**Rung two is a design, and it claims nothing.** It is not wired to this bench
and it has not been trained or run here, so every number in this document
belongs to rung one. One thing about it is worth settling before anybody starts:
the library this project uses elsewhere ships **TD-MPC**, the earlier method,
and not TD-MPC2. So rung two means fetching TD-MPC2 from its own project, and
the convenience of everything living in one library, which solutions 3, 5 and 6
enjoy, does not apply here. The
two bench pieces an off-the-shelf policy needs are no longer the obstacle: the
straight-down rendered view and the path that accepts waypoints were built for
[imitation from demonstrations](03-imitation-from-demonstrations.md), as
`bench/top_view.py` and `Bench.follow`. What is still missing is the wiring and
the training.

## What a forward model is

Start with the object everything else here rests on.

A **forward model** is a function from a situation and an action to the
situation afterwards. Written as a signature it is `(state, action) -> state`.
Nothing more. It does not know what the action was for, it has no preference
between the states it returns, and it cannot be asked what to do. It can only
be asked what happens.

The programming comparison is exact and it is worth taking seriously, because
it explains both the power and the danger. A forward model is a **pure
function**: given the same arguments it returns the same value, it has no side
effects, and — this is the important part — **you may call it as often as you
like without consequences**. That is what makes it a thing you can search
against. Calling the real world is not free: every push risks a glass. Calling
the model is arithmetic. So the model is a cheap, repeatable, consequence-free
copy of an expensive, irreversible world, and a search that would be reckless
against the table is ordinary against the model.

The second half of the comparison is that a pure function returns a value of
the same type it took. `(state, action) -> state` can be composed with itself.
Feed the returned state back in with a second action and you have the state two
actions later. **That composability is the whole of the sequence capability**,
and it is a property of the type rather than of the quality of the fit.

It is worth naming what a forward model is *not*, because the contrast is the
cleanest way to see the six apart. A **policy** is a function from a situation
to an action, `state -> action`. It answers *what should I do*, which is the
question you actually want answered, and it answers it in one pass with no
search. [Imitation from demonstrations](03-imitation-from-demonstrations.md) and
the two SmolVLA solutions are policies. The trade between the two kinds is
discussed at the end of this document, but the short form is that a policy is
fast and narrow, and a forward model is slow and general.

## What this model is shown, and what it answers

Given that shape, the only real design question for rung one is what to put in
the two states and the action, and the answer is: exactly what the arm has, and
nothing else.

**In go thirty-four numbers.** The table's one known kind, as four yes-or-no
columns. The pushed glass's height, its width at its widest and its width at
its foot — the three measurements `look()` reports, carrying problem 2's error.
The push itself as two numbers: how far across the glass the jaw meets it, and
how far it pushes. And then up to five other glasses, nearest first, each as
where it stands relative to the pushed glass, how wide it is and how tall it
is. Six glasses on a table is the most the bench ever draws, so five others is
everyone.

**Out come fourteen numbers.** A displacement for the pushed glass. A
displacement for each of the five other glasses, because a push moves
neighbours as well as its target and a model that only predicted its target
would be blind to the way one glass shoves another. And two yes-or-no answers:
did anything topple, and was the jaw blocked on the way down before it ever
pushed.

Three things about that list are worth dwelling on.

**It is only what the arm has.** No friction, no mass, no tipping rule, no
record from the simulator. Whether a push slides a glass or tips it over is not
given to the model in any form; it is a regularity in the data that the model
either finds or does not.

**The two yes-or-no answers carry most of the value.** A displacement that is a
few millimetres out costs a repeated push. A topple that was not predicted costs
a glass, and nothing in this project can stand a glass back up. So the model is
not really a predictor of displacements with two extras attached; it is a safety
check with a displacement predictor attached, and the training reflects that.
Toppling is rare, and a model trained on rare events will quietly learn to
answer "no" to all of them and be right almost always. The fit therefore weighs
the toppling examples up until the two sides count the same, so that answering
"no" to everything is no longer a cheap way to score well.

**The labels come from two looks, not from the truth.** An example is made by
looking at the table, pushing, and looking again, and the answer recorded is the
difference between the two looks. So the model learns to predict what the
*camera will report*, error and all, rather than what the world will do. This
is the right choice, because what the camera will report is what the planner
will see next, and a model that predicted a truth the arm can never observe
would be predicting the wrong thing.

## The push's own frame, and why direction carries no information

One decision inside those thirty-four numbers deserves a section of its own,
because it is the clearest example in this project of making a problem smaller
by choosing coordinates well.

Every position in the inputs, and every displacement in the outputs, is measured
**in the push's own frame**: one number along the way the jaw moves, and one
number across to its left. Nothing is measured in the table's north and east.

The consequence is that **a push to the north and the same push to the east are
one example rather than two**. A glass 40 mm ahead of the target and 20 mm to
its left is the same input row whichever way round the table the jaw happens to
be pointing, so the model sees the two situations as what they are, which is
one situation.

The justification is a fact about the cell rather than a trick: **the table's
friction is the same everywhere and the same in every direction**. There is no
grain, no slope and no patch that is stickier than the rest. So the direction a
push points in carries no information about what the push will do, and encoding
it would mean asking the model to learn, separately for every heading, a
relationship that does not vary with heading. That is a waste of data in the
most expensive currency this solution has, which is recorded pushes.

The physics comparison is a conserved symmetry. When a system behaves the same
way under a rotation, its description should not change under that rotation
either. Writing the inputs in the table's frame would be writing a description
that changes when the thing being described does not.

There is a second, smaller gift in the same idea. Since the physics has no
preferred direction, it also has no preferred handedness in any way that
matters here: a push and its mirror image, left and right swapped, are both
true pushes. So every recorded push can be used twice, once as it happened and
once reflected, which doubles a small training set with examples that are not
invented but real.

The honest limit is worth stating with it. **The frame only removes the
information it was right to remove.** The reach of the arm and the edges of the
glass zone are emphatically not the same in every direction, and the model knows
nothing about either. That is why the map — where a glass may stand and where
the arm can reach — stays as written-down arithmetic outside the model, and is
checked against the model's predicted table rather than learned.

## Ensembles as a measure of ignorance

The hardest thing to get from a trained model is not an answer. It is an honest
statement that it does not know, and this section is the most transferable idea
in the document.

A plain network always answers. Shown a push unlike anything in its training
data it does not hesitate, decline or warn; it returns numbers in exactly the
same format and with exactly the same confidence as for a push it has seen a
thousand times. That is a serious problem for a planner, because **a search is
an adversary against its own model**. It tries hundreds of candidates and keeps
the one the model likes best, so it systematically finds the places where the
model is wrong in a favourable direction. A model that is right on average and
badly wrong in a few places will have those few places chosen for it.

The fix used here is simple to describe and hard to improve on. **Train the
same network several times from different starting weights on the same data,
and keep all the copies.** Rung one keeps five. Where the five agree, the
training data pinned the answer down, which means the model has seen pushes like
this one. Where they disagree, the data did not pin it down, and each copy
filled the gap with whatever its own starting weights happened to lead to. So
**the spread between the copies is a measurement of what the data did not
say**, and it costs nothing but the training of four more small networks.

The planner then uses that spread in a specific and deliberately asymmetric
way. For the displacements it takes the copies' average, because there the
spread is only accuracy and the loop will correct it. For toppling it takes
**the worst copy's chance, not the average**. If any one of the five thinks a
push might tip something over, the push carries that copy's number. A push the
model is unsure about therefore counts as a risky push, and a push gets through
only when all five agree it is safe. The limit is one in a hundred: any copy
giving a push more than a 1% chance of toppling something takes it out of
consideration.

That asymmetry is the right one because the two errors it trades are not
comparable. Refusing a push that would have been fine costs a refusal, which
[the problem](../problem.md) counts as a result rather than a failure. Making a
push that tips a glass costs the glass, permanently, and the arm carries on
working beside it.

The search's adversarial pressure is answered a second time, in a way worth
knowing because it generalises as well as the ensemble does. A search over
thousands of candidates will find a push that looks safe because of a
millimetre of luck in the measurements. So every candidate is also checked
against four copies of the table with every reading moved by about the camera's
error, and the worst topple chance over all of them is the one that counts. **A
hole in the model narrow enough to be found by luck does not survive being
shifted by a millimetre.** A genuinely safe push does.

## Planning by sampling: the cross-entropy method

With a model that answers and an honest signal for where it does not know, the
remaining question is how to find a good push, and the answer is the plainest
one available: try a lot of them.

A candidate push here is three numbers: which way the jaw points, where across
the glass it meets it, and how far it travels. **Sampling** means drawing many
candidates at random from the allowed range, asking the model what each one
leads to, scoring every predicted table, and keeping the best. That alone is
called random shooting and it is already a working planner, but it spends most
of its draws in parts of the range that were ruled out by the first round.

The **cross-entropy method** is random shooting with one addition: use the good
draws to decide where to draw next. It runs in rounds. Draw a batch spread over
the whole allowed range. Score them all. Keep the best few — call them the
elite. Work out the average and the spread of the elite, and draw the next
batch from around that average with that spread. Repeat. Each round the cloud
of candidates contracts onto whatever region keeps scoring well, so the method
spends its later draws where the answer is rather than where it started.

Rung one runs this with six hundred draws in the first round and three hundred
in each of three more, keeping the best thirty each time, which is about fifteen
hundred candidate pushes examined per crowded glass. That sounds extravagant
and costs almost nothing, because a candidate push is one row of thirty-four
numbers through five small networks, and the batch goes through in one call.

![An early round spreads its candidates over the whole range and most are struck out by the filters, on the table the model predicts for them; by round four the draws have collapsed onto one small region, and the score is the room still missing on the table plus a small penalty per millimetre pushed.](../../../images/03-push-glasses-apart/04-planning-against-the-model.png)

Two properties make this search the right one here, and both are worth
remembering for other problems.

**It needs no gradients.** It never asks how the score changes when a push
changes by a hair. It only ever asks which of these candidates scored better,
so it does not care whether the score can be differentiated, whether the model
is differentiable, or whether the arithmetic wrapped around the model is. The
map test, the reach test and the ensemble veto are all plain conditions, and a
gradient method would have to be contorted to accept them.

**It copes with a cost that is not smooth.** This matters more. The cost here
has a cliff in it: a push that topples a glass is not slightly worse than one
that does not, it is unacceptable, and a push that lands a glass a hair outside
the zone is not slightly worse than one a hair inside. A method that follows a
slope downhill needs the landscape to have slopes. This one needs only a
comparison, so a cost of infinity for an unacceptable candidate is an ordinary
value it handles without any special arrangement. Given how many of the rules
in this problem are hard limits rather than preferences, that is not a
convenience but the deciding property.

The score itself is deliberately plain arithmetic over the predicted table, and
it is short enough to state in full. Add up, over every glass, how much clear
room is still missing at the end — how far each neighbour's edge reaches inside
the 70 mm that glass needs. Add a small penalty for each millimetre pushed, so
that the shortest push that does the job wins. Throw the candidate away
entirely if any copy of the model gives it more than the topple limit, if the
predicted table puts a moved glass outside the glass zone or outside the arm's
reach, or if the model predicts a movement longer than the push itself, which
is the model guessing outside anything it has seen. What is left is scored, and
the best push over all the crowded glasses on the table is the one that gets
made.

## Receding horizon: plan several, make one

The search above returns a push, and the natural next thought is to let it
return several and carry them out in order. That thought is wrong in a specific
way, and the correction is a named idea worth having.

**Receding horizon** means: plan several steps ahead, execute only the first,
then throw the rest of the plan away and plan again from a fresh measurement.
The plan reaches further than the arm ever acts, and its far end keeps moving
away as the arm advances — which is where the name comes from.

The reason it is the right answer to a model that is wrong in small ways is a
matter of where the errors land. A plan several steps deep is built on the
model's prediction of a table the arm has never seen. If the arm carried out all
of those steps, each one would be acting on a table a little further from the
truth than the one before, and nothing would ever notice. If instead the arm
makes only the first step and then **looks**, the model's prediction is replaced
by a measurement, and whatever the model got wrong is deleted rather than
inherited. The plan was still useful: it is what made the first push a push
worth making rather than merely a good push in isolation. But only the part of
it that was acted on could possibly have been wrong, and that part is one push
long.

The programming comparison is given in [pushing without
toppling](../pushing-without-toppling.md) and applies exactly here. A plan
carried out in full is a loop unrolled into a fixed sequence because you believe
you know how many times it will run. A receding horizon is a loop that re-reads
its state every pass. The state here is the arrangement of the table, the
re-reading is `look()`, and the loop continues while the state says there is
still work to do.

This is also why the solution is forgiving of a mediocre model. The thing a
model has to be good at is **ranking the pushes available right now**, not
describing the future. It can be several millimetres out about where a glass
lands and still reliably pick the better of two pushes, and being several
millimetres out is corrected for free by the next look. That is a much easier
standard than accuracy, and it is the standard this arrangement actually
imposes.

## Compounding error over a rollout

Receding horizon limits the damage a wrong plan can do. It does not make the
plan right, and this section is about why a plan gets less right the further it
reaches.

A **rollout** is what you get by composing the model with itself: feed its
predicted table back in with a second push to get the table two pushes later,
and again for a third. Each call adds its own error, and — this is the part that
surprises people — **each call also starts from a situation its predecessor got
slightly wrong**. So the errors do not merely add. They compound, because a
model asked about a table slightly unlike anything in its training data answers
slightly worse, which produces a table a little further from anything in its
training data, which it answers worse again.

The size of this is easy to feel with the numbers recorded for rung one. Its
README reports a median error of about four and a half millimetres for where a
pushed glass lands, on tables it never trained on. That is a perfectly useful
one-step model. If that error simply accumulated, a plan rolled three pushes
deep would be starting its third push from a table some thirteen millimetres
out — and the clearances this whole problem turns on are tens of millimetres.
Compounding makes it worse than that straight sum, not better. **So a model
that is good at one step can be useless at five**, and the quality of the
one-step fit says almost nothing about it.

This is why the built planner's horizon is one push. It is the honest horizon
for a model trained the way rung one's is: every training example is a single
push, so the model was never asked to be right about a table that one of its own
predictions produced.

**What is done about it is to train against multi-step rollouts rather than
only single steps.** Instead of scoring the model on how well it predicts the
next table from a measured table, roll it forward several pushes from a measured
table and score it on how well the whole sequence matches what really happened
over those pushes. The error then has somewhere to go: the fit is penalised for
predictions that are plausible one step out and drift two steps out, so it
learns to produce tables that it can itself handle as input. This is the
standard remedy in the learned-world-model literature and it is exactly what
rung two does by construction, which is one of the clearest reasons to want
rung two at all.

Two cheaper habits help as well, and rung one uses both. **Keep the horizon as
short as the task allows**, because the compounding is a function of depth.
And **collect training data from the planner itself**, not only from random
pushes, so that the tables the model sees during training are tables a planner
would really reach. Rung one's second round of data collection does precisely
that: the first model plans, the planner finds the pushes where that model is
wrong in its own favour, those pushes are really made, and what really happened
goes into the training set. That fills exactly the holes the search is going to
exploit.

## Planning a sequence, which only this solution could do

Everything so far has been machinery. This section is the reason the machinery
is worth having, and it is the one capability that is this solution's alone.

Consider a table where glass A is crowded and there is nowhere to push it. Every
direction either runs into glass B, leaves the glass zone, or puts A outside the
arm's reach. Every solution that chooses one push at a time, judged by the table
one push later, will correctly report that no push helps and refuse. And every
one of them is wrong, because the answer is to push B first — not because B
needed moving, and not because moving B makes any glass grippable, but because
moving B opens the route A needed.

**A push whose only value is what it allows the next push to do** is invisible
to a method that scores pushes one at a time. It scores badly on its own terms:
it clears no room and it spends a push. Only a method that can ask *and then
what* can see its value, and asking *and then what* requires a function that
returns a table.

![Pushing one glass at a time, where each push has to leave the glass it moved with full room by itself, takes four pushes on a real four-glass layout; choosing the best pair together takes two, and choosing the second of that pair needs to know where the first one lands.](../../../images/03-push-glasses-apart/04-when-a-sequence-beats-one-at-a-time.png)

The extension to the built planner is small, and it is worth describing
precisely so that it is clear how little the model has to change. The search
currently draws three numbers per candidate. A two-push search draws six — a
first push and a second — rolls both through the model in turn, and scores the
table at the end of the pair. The ensemble veto applies at every step rather
than only the last, so a sequence that topples something halfway through is
thrown away whatever it achieves afterwards. Only the first push of the winning
pair is made, and then the arm looks again, which is the receding horizon doing
exactly its job. Nothing about the model changes at all. What changes is how
many times it is called, and the cost of the search grows quickly with depth,
which is the real reason to want the shortest horizon that can see the answer.

Two honest qualifications belong here, and they matter.

**The depth that is useful is small.** Compounding error sets an upper limit on
how far a rollout can be trusted, and for rung one's model that limit is low.
Two pushes is defensible, three is optimistic, and anything deeper is planning
against a story rather than a prediction.

**On this bench a sequence saves pushes rather than rescuing runs.** The cases
where a sequence wins outright — where a one-at-a-time planner has to refuse and
a two-deep planner succeeds — are real but uncommon on four to six glasses, and
the more usual gain is finishing the same table in fewer pushes. That is worth
something here for a precise reason rather than a general one: **touching a
glass is the only step in this problem that can topple one**, so a run that
spends four pushes instead of six has taken two fewer chances of the single
failure that cannot be undone. It is not worth something because the arm is
short of time.

## The second rung: TD-MPC2 off the shelf

Rung one is a model written for this cell. Rung two asks what a model written
by people who do this for a living would do instead, and the comparison between
them is the point of having both.

**TD-MPC2** is the better known of the two model-based methods of this family,
and it does not come from the library the other borrowed solutions here use;
that library ships its predecessor. Like rung one it learns a model of how the
world changes and plans through it at run time, rather than learning a policy
that maps a situation straight to an action. So the overall shape — learn what
happens, then search over actions against what was learned, then act on only the
first — is the same shape this whole document has described.

The difference is what the model predicts, and it is worth stating honestly
because it is the whole contrast.

**Rung one predicts the next table directly, in the quantities the arm
measures.** Its output is displacements in millimetres and two yes-or-no
answers, and every number in it has a name a person can check against a
photograph.

**TD-MPC2 learns its own internal representation and plans in that.** It
encodes the situation into a vector of its own choosing — a vector whose entries
mean nothing to anybody — learns how that vector changes when an action is
applied, and does all of its planning there, never converting back into
positions and widths. It is trained so that this internal description keeps the
information needed to predict rewards and values rather than the information
needed to reconstruct the table, which is why it can afford to throw away
everything the task does not use.

Each buys something real, and the two lists do not overlap.

**The hand-built one is inspectable and small.** Every input has a name and
every output has a unit. When it is wrong you can print the thirty-four numbers
it was shown, the fourteen each copy answered, and the fourteen that really
happened, and see the disagreement — which is exactly what rung one's tracing
does. It trains in minutes on an ordinary processor, it needs no accelerator,
and its ensemble gives a signal for ignorance that is easy to reason about.
Against that, it is weak where it was not told what matters: it sees five
neighbours and no more, it has no idea the arm has a body, and the one thing it
is good at is pushing glasses on this table.

**The off-the-shelf one is stronger and brings a maintained implementation.**
It is designed to work across many tasks without being retuned for each, it is
trained against multi-step rollouts by construction, which is the direct answer
to compounding error, and the implementation and its defaults have been
exercised by many people on many problems. The code is not this project's to
maintain, and the published results are a reference that a hand-built model
simply does not have. Against that, it is a larger thing to train, it wants an
accelerator, its internal representation cannot be read, and a failure in it is
much harder to attribute than a wrong number with a unit on it.

**Comparing them is a measurement of whether building it yourself was worth
it**, and that is the reason this solution has two rungs rather than one. If
TD-MPC2 clears tables no better than five small networks trained in half an
hour on a laptop processor, then the cell is narrow enough that the hand-built
model was the right call, and the thirty-four numbers chosen by hand were a
better encoding than one learned from scratch. If it clears tables markedly
better, then what the hand-built encoding left out was real, and the places it
was left out are where to look next. Either answer is useful, and neither can be
had from one rung alone. This is the same argument [a network trained here from
scratch](../../02-segment-glasses/solutions/02-train-from-scratch.md) makes in
problem 2, where a model built entirely inside the cell is what makes the
borrowed models' scores readable.

## The pushes are what this contributes

Having chosen a push, this solution hands it over in the form [the test
bench](../the-bench.md) defines, and it is worth being exact about where its
contribution stops.

**It emits a parameterised push.** Which glass to move, where the fingertips
come down, which way the jaw points, how far it feels forward and how far it
pushes. That is what `push()` accepts, and **the expansion of those numbers
into a jaw trajectory is a macro the bench owns**: the descend, the slow feel
forward until contact, the push at a steady speed, the back-off and the lift.
This solution does not write that expansion and gains nothing from it, and
neither does any other solution that thinks in pushes.

Two of the numbers in that push are arithmetic rather than model output, and
saying so keeps the boundary clean. Where the fingertips come down is behind the
glass's widest edge with a margin for the camera's error. How far forward the
jaw feels is far enough to pass the glass's middle, because a stemmed glass is
met at its stem, well inside its widest edge, and a jaw that misses and lifts
under the bowl tips it. Neither number is learned, because neither depends on
anything nobody knows.

**The height is not a choice.** [Pushing without
toppling](../pushing-without-toppling.md) settles that for all six: the jaw
rides as low as the gripper can go, always, so there is nothing to trade and
nothing to tune. What this solution decides is only whether to push at all, and
where to.

**What it does not contribute is the destination.** Where the glasses should
end up is [the target layout](../the-target-layout.md), computed once from the
same measurements and so that no solution aiming at a destination can score
well by aiming at an easier arrangement.

So the whole of this solution's contribution sits in one place: **which push,
out of all the pushes the geometry allows, is the one worth making.** It is
scored on the table afterwards, the same as everything else.

## How the concepts fit together

The pieces have been introduced separately, so here they are in the order they
run, once per push.

**Look.** `look()` returns one reading per glass: where it stands, how tall,
how wide at its widest and at its foot, whether it is standing. Every reading
carries problem 2's error.

**Apply the shared topple limit.** The arithmetic in [pushing without
toppling](../pushing-without-toppling.md) is worked out from each glass's
measured foot width before anything is asked of the model, and a glass that
fails it is refused with that reason. This step is the same for all six and is
the one part of the loop the built planner does not yet have.

**Take anything that can be taken.** Any glass with clear room is lifted off
immediately, with a small extra margin for the camera's error, because a glass
that is gone cannot be toppled and cannot be in the way. The model is not
consulted.

**For each glass still crowded, search.** Draw candidate pushes, encode each
one with the table into a row in the push's own frame, ask all five copies of
the model, average their displacements, take the worst copy's topple chance,
and repeat the topple question on four copies of the table shifted by about the
camera's error.

**Throw away everything unacceptable.** Any candidate over the topple limit.
Any candidate whose predicted table puts a moved glass outside the glass zone or
outside the arm's reach. Any candidate whose predicted movement is longer than
the push, which is the model answering about something it has not seen.

**Score the survivors and refine.** The score is the room still missing on the
predicted table, plus a small penalty per millimetre pushed. Keep the best
thirty, draw the next round around them, and repeat four times in all.

**Make one push.** The best push over every crowded glass on the table is
expanded by the bench's macro and carried out. The jaw reports what it felt.

**Then look again**, and begin at the top with the arrangement as it now is.
The loop ends when every glass has been racked, when the table's push budget is
spent, or when no push the model expects to help survives the filters — and
each glass left behind is reported with the reason it was left.

Two guards sit around that loop and are worth naming because they are what stop
it running for ever. A glass may be pushed only a few times before it is
reported as refused, and the table has a budget of pushes for the whole run.
Both are plain counters, both belong to the loop rather than to the model, and
the budget must be the same number for all six or the push counts on the
scorecard cannot be compared.

## When a glass cannot be pushed safely

Every solution in this set has to answer this question, and this one answers it
twice over, which makes it the most interesting place to look at what learning
the physics really buys.

[Pushing without toppling](../pushing-without-toppling.md) gives the written
rule, and it is shared by all six without exception: a glass slides while the
contact height is below half its foot width divided by the friction
coefficient, and tips above it. A glass whose limit is below the jaw's top edge
cannot be pushed safely at any height the gripper can reach, and the only
correct answer for it is to refuse. That arithmetic is applied before any model
is consulted, so no model here can cause the failure this problem cares most
about, and because the friction in it is a guess it is evaluated across the
range a glass on a dry wooden top plausibly covers rather than at one value.

**The built planner does not evaluate that rule, and that is a gap in it rather
than a second opinion.** It holds no friction value and no tipping formula, so
the shared gate belongs in front of it and is not there yet. What it adds —
and this is what learning the physics buys — is a **second** refusal, which
comes from the evidence rather than from the rule: a glass is refused when
**every push the search asked about was turned down**, and the planner reports
which kind of rejection dominated. If most candidates died on the topple limit,
the glass is reported as one where every push the model was asked about might
tip something over. If most died on the map, it is reported as having nowhere
inside the zone and within reach to push it to. Two further refusals come from
the loop rather than the model: a glass that has been pushed its allowed number
of times and still has no room, and a table whose push budget is spent.

A refusal reached this way is a stronger statement than it first appears,
because of how it was reached. Fifteen hundred candidate pushes were examined,
each by five independently trained copies of the model, each also on four copies
of the table shifted by the camera's error. "No push survived" means no push
survived all of that. **A glass refused here is a glass for which the search
could not find a single push that five separately trained models and five
slightly different tables all agreed was safe**, which is a different claim
from the one-line inequality with a guessed number in it, and an addition to
that inequality rather than a replacement for it.

The honest weakness has to be stated with it, because it is this solution's
worst one. **The model can be confidently wrong.** The ensemble measures
disagreement, and disagreement only appears where the training data was thin in
a way the copies noticed. A kind of failure that is absent from the training
data altogether can produce five copies that agree, agree confidently, and agree
wrongly. Rung one's own results record exactly this: one glass went over on the
fifty held-out tables and one on a hundred tuning tables, and the model had
rated as safe every topple it missed. The three causes recorded there are
instructive, because all three are
things the thirty-four numbers cannot express — the jaw meeting a stemmed glass
at its stem and lifting under the bowl, the jaw's body clipping a neighbour
behind the target, and a tapered glass tipping on its own.

Lowering the topple limit does not fix that. A limit only moves the line among
pushes the model has an opinion about, and these are pushes the model is
confident about. What fixes it is more examples of exactly those situations,
which is an argument for more data collection and, for the body clipping a
neighbour, an argument for telling the model that the jaw has a body at all.

And the limit that cannot be fixed by either is the one [pushing without
toppling](../pushing-without-toppling.md) states for all six: **nothing in this
loop stands a toppled glass back up.** That is why the topple test is a veto
rather than a cost to be weighed against the value of moving the glass. A risk
worth taking is one whose bad outcome the system can absorb, and this one it
cannot.

## A worked example

The clearest way to see the whole arrangement run is on one of the bench's
held-out tables, and rung one can be traced step by step on any of them.

Take a table of six glasses of one kind. The first look reports six readings.
Several pairs are closer than the 70 mm of clear room the gripper needs, so
nothing can be taken yet, and the planner goes to work on every crowded glass
in turn.

For the first of them, the search draws six hundred candidate pushes spread over
every heading, every offset across the glass and every travel from a centimetre
to ten. All of them go to the five copies, and most die on the table that comes
back: the predicted landing is outside the glass zone, or the jaw's own path
leaves the arm's comfortable reach, or the predicted movement is longer than
the push itself. A further batch is struck out by the topple veto — some
because a short jab at a wide part of the glass genuinely looks like tipping
it, and some because the five copies simply disagree, which counts the same
way. What is left is scored by how much clear room is still missing on the
table afterwards.

Three more rounds contract the cloud of candidates onto the region that scored
best, and the winner is a push of a few centimetres that moves the target
glass away from its nearest neighbour without pushing it towards any other. The
same search runs for each of the other crowded glasses, and the single best push
over all of them is the one made.

The jaw comes down behind the glass, feels forward until it touches, pushes, and
backs off. Then the arm looks again — and this is the step that makes the whole
arrangement work, because the glass has not landed exactly where the model said
it would, and the planner neither knows nor cares, since it re-plans from the
measurement rather than from the prediction.

After this push one glass has room and is taken. Two pushes later the rest are
clear and are taken as well, and the table finishes done.

Not every table finishes that way, and the two interesting endings are both
recorded in rung one's traces. On one, a push is blocked on the way down — the
jaw touches something before reaching the table, goes straight back up without
pushing, and the loop simply looks again and plans afresh, so a blocked push
costs a push and nothing else. On another, two pushes are made and then no
further push survives the filters, so three glasses are reported refused with
their reasons and the table finishes **correct but incomplete**, which [the
problem](../problem.md) counts as a correct outcome rather than a failure.

Across the fifty held-out tables as a whole, rung one's recorded results — read
from its own `results.json` — are two hundred and two of two hundred and
fifty-one glasses racked in a hundred and fourteen pushes, thirty-one tables
finished, and the glasses that were left all reported with a reason. **That is
the most glasses any of the six racks, and it is done in the fewest pushes.**
It is also the one line where this solution is worse than the geometry it is
measured against: **one glass went over**, which makes that table wrong and
makes this the only one of the three push-parameter solutions to topple
anything at all — [one fixed nudge](01-one-fixed-nudge.md) and [geometry
generates, a model ranks](02-geometry-ranked.md) both topple none. The section
above on refusals says why it can happen: the model can be confidently wrong,
and the shared topple gate that would have caught the rest is not in front of
this planner yet. Those numbers are read against the other solutions on
the shared scorecard, and against the displacement floor from [the target
layout](../the-target-layout.md), which says how little movement the task
needed in the first place.

## What it needs

**A physics engine and thousands of pushes in it.** This is the real cost, and
it is a cost no other solution in this set pays in the same currency. Every
training example is one push really made: look, push, look again. Rung one's
README records thirty-eight thousand of them, collected in two rounds — a first
round of random pushes on thousands of tables, and a second round of pushes
chosen by the planner using the first round's model, which is what fills the
holes the search would otherwise exploit. **Nobody labels any of it.** The
answer to every example is what the second look found, so the data costs
simulator time and no human time at all, which is the single biggest practical
advantage this family has over anything trained on demonstrations.

![One training table yields a dozen examples, because the table is built once and the state after each push starts the next and no push has to be a useful one; a real run makes as few pushes as it can, so gathering the same thirty-eight thousand rows from ordinary runs would take thousands of them, where the simulator produces them in under an hour of processor time and nobody labels any of it.](../../../images/03-push-glasses-apart/04-the-data-it-takes.png)

**A training run, before the solution can answer anything.** Rung one trains
five small networks, and its README records the whole of that — the pushes and
the five networks — at about half an hour on a laptop processor. **No
accelerator is needed for rung one at all.** This is unusual among the learned
solutions here and it follows directly from the model being small and the inputs
being thirty-four numbers rather than a picture.

**For rung two, rented hardware.** TD-MPC2 is reinforcement learning, it trains
on far more interaction than a one-step fit needs, and it wants an accelerator.
Renting one for a weekend is of order a hundred dollars, which covers a single
training run. Because [the plan](../solutions-plan.md) requires several training
seeds before any result is a result, the realistic figure is a small accelerator
for about a month, which is of order five hundred dollars.

**Run-time compute, and this is where this solution is expensive.** Every single
push the arm makes is preceded by about fifteen hundred candidate pushes, each
evaluated by five networks, repeated across five copies of the table for the
topple check, for every crowded glass. That is cheap in absolute terms, because
the networks are small and the batch goes through in one call, but it is
hundreds of times the arithmetic a fixed nudge costs, and it is the reason [the
test bench](../the-bench.md) puts a compute column on the scorecard. A
two-push search multiplies it again. On a real arm this still sits comfortably
inside the time one arm movement takes, which is the comparison that matters.

**A file of weights kept in step with the cell.** The code says what the cell
is; the weights say what the cell was like when they were fitted. Change the
jaw, the glass zone, the range of proportions a kind is drawn from, or the
camera's error, and the weights are quietly out of date in a way no test of the
code will notice.

**Libraries, and no borrowed model.** PyTorch for both rungs, MuJoCo through the
bench, and LeRobot for rung two. Neither rung downloads trained weights from
anybody, so there is no model licence to meet in either — the only conditions
are the libraries' own, and LeRobot is Apache 2.0.

**Two additions to the bench, both of which it now has.** [The test
bench](../the-bench.md) listed them as missing: repeats with a spread on the
scorecard, because one run of a trained solution is not a measurement, and the
time per push beside the counts. Both are in `bench/scoring.py` today, as
`Repeats` and as the seconds-per-push the scorecard records. Rung one's runner
uses the plain scorecard, so its results carry the time per push but no spread:
it has been trained once and run once.

## Where it is strong and where it breaks

**It could plan a sequence, and nothing else here could.** That is the
capability this document is built around, and it follows from the model
returning a table rather than a score — though the built planner's horizon is
one push, so the sequence is a design and not yet a result.

**Its model needs no written physics, and so no guessed friction.** There is no
friction value, no tipping formula and no rule about where the jaw fits
anywhere inside it, and the only thing written down in the built planner is the
map — where a glass may stand and where the arm can reach. The shared topple
gate that belongs in front of it is not wired up yet, which is a gap rather
than a virtue. Whatever decides whether a push slides,
tips or is blocked is whatever the model saw happen, which means it also
absorbs the things nobody thought to write down.

**It knows where it is ignorant, cheaply.** Five copies of a small network cost
five times nothing, and their disagreement is a usable signal that the training
data did not cover this push. Most learned methods give no such signal at all.

**Its training data costs no human time.** Every label is what the second look
found. A demonstration-based method needs somebody to produce the
demonstrations; this one needs only the simulator to run.

**The same model serves a different goal.** Change the arithmetic that scores a
predicted table and the solution aims somewhere else, with no retraining. A
learned policy would have to be trained again.

**It can be confidently wrong, and that is its worst failure.** Where the
training data is thin in a way the copies did not notice, five copies agree and
are wrong together. The topples recorded on the tuning tables were exactly
this: the model had rated every one of them safe, and a lower limit does not
catch that.

**Its model is only as wide as its encoding.** Five neighbours, four
measurements each, and no representation of the jaw's body. Anything the
thirty-four numbers cannot express cannot be learned however much data is
collected, and most of the recorded failure causes are of that kind.

**It is slow at run time, and in a different way from a foundation model.**
Hundreds of model calls per push is the price of searching rather than
answering.

**It compounds error over depth**, which caps how far a sequence can usefully be
planned, and the cap for a one-step-trained model is low.

**It cannot be inspected the way written geometry can.** When a written rule is
wrong you can print one number and see why. Here you print thirty-four numbers,
five answers and what really happened, and infer. That is far better than
nothing — and it is better than rung two offers — but it is not an explanation.

**And it is the most machinery of the six.** A data collector, a trainer, an
ensemble, a search and a loop, against [one fixed nudge](01-one-fixed-nudge.md),
which is a page of arithmetic. That difference in setup cost is real and it
should be weighed against the scores rather than hidden behind them.

## The general ideas behind this

Five lines of published work meet in this solution, and they are worth
separating because they are usually run together under the word "learning".

### Model-based against model-free control

A **model-free** method learns what to do. A **model-based** method learns what
will happen and computes what to do from it. The trade is well established in
both directions. Model-based methods need far fewer interactions, because every
interaction teaches them about the world rather than about one goal, and they
can be re-aimed at a new goal without new data. Model-free methods reach a
higher ceiling, because they never have to be right about the world, only about
the action.

It is normally right where interactions are expensive or irreversible and the
goal may change. It is normally wrong where interactions are cheap and plentiful
and the goal is fixed for ever, because then the extra machinery buys nothing a
policy would not have learned anyway. In this cell a topple is irreversible,
which argues for model-based; but simulator pushes are cheap and the goal has
not changed, which argues the other way. That tension is real and it is part of
what the comparison with the other five is meant to settle.

### Fitting a dynamics model to recorded interaction

Nagabandi, Kahn, Fearing and Levine's [*Neural Network Dynamics for Model-Based
Deep Reinforcement Learning with Model-Free
Fine-Tuning*](https://arxiv.org/abs/1708.02596) (2017) is the clearest statement
of the recipe rung one follows: fit a plain network to situation, action and
next situation gathered by random exploration, then control with
model-predictive control on top of it. Its headline result is sample
efficiency — far fewer interactions than a model-free policy needs for the same
task.

It is normally right when the situation can be written down as a short list of
measured numbers, which is exactly this problem after problem 2 has run. It is
normally wrong when it cannot, because then the model has to predict pictures,
which is a far harder fit for a far worse prediction.

### Ensembles, and planning with them

Lakshminarayanan, Pritzel and Blundell's [*Simple and Scalable Predictive
Uncertainty Estimation using Deep
Ensembles*](https://arxiv.org/abs/1612.01474) (2016) is the reference for
training the same network several times and reading the spread between the
copies as uncertainty. Chua, Calandra, McAllister and Levine's [*Deep
Reinforcement Learning in a Handful of Trials using Probabilistic Dynamics
Models*](https://arxiv.org/abs/1805.12114) (2018), usually called PETS, is the
version that plans with the cross-entropy method against such an ensemble and
keeps track of where the copies disagree. **Rung one is a simplified PETS**:
five networks, the cross-entropy method, and a veto driven by the worst copy
rather than the average.

An ensemble is normally right wherever a model will be searched against, because
a search finds a model's blind spots on purpose. It is normally wrong as a
complete account of uncertainty: copies trained on the same data can agree
confidently about a situation none of them has seen, which is precisely the
failure recorded above. For a method that does report when it has left the
region it knows, Bauza and Rodriguez's [*A Probabilistic Data-Driven Model for
Planar Pushing*](https://arxiv.org/abs/1704.03033) (2017) fits a Gaussian
process to pushing data and returns a spread with every value; it is slower to
query and does not scale to tens of thousands of examples, which is the trade an
ensemble takes the other side of.

### The cross-entropy method, and model-predictive control

The search is Rubinstein's **cross-entropy method**, described for a general
audience in de Boer, Kroese, Mannor and Rubinstein's *A Tutorial on the
Cross-Entropy Method* (2005): sample, keep the elite, refit the sampling
distribution to the elite, repeat. Planning a short sequence, executing only its
first step and re-planning is **model-predictive control**, which is decades old
and came from process control long before anybody applied it to robots.

The cross-entropy method is normally right where the action has few dimensions,
the cost is cheap to evaluate and the landscape is awkward — not smooth, full of
hard limits, or both. It is normally wrong where the action has many dimensions,
because the number of samples it needs to cover a space grows with the
dimension, which is why no policy here is searched for this way and only pushes
are. Model-predictive control is normally right whenever the model is imperfect
but the state can be re-measured often, and normally wrong when measuring is
slow or expensive, which would leave the plan running open-loop for exactly as
long as it is unreliable.

### Learned world models with their own representation

Hafner and colleagues' [*Learning Latent Dynamics for Planning from
Pixels*](https://arxiv.org/abs/1811.04551) (PlaNet, 2018) and [*Dream to
Control*](https://arxiv.org/abs/1912.01603) (Dreamer, 2019) established the
other branch: do not predict the observation at all, learn a compact internal
description and predict how *that* changes. Hansen, Wang and Su's
[TD-MPC](https://arxiv.org/abs/2203.04955) (2022) and
[TD-MPC2](https://arxiv.org/abs/2310.16828) (2023) combine such a learned
internal model with planning at run time and a learned value to stand in for
everything beyond the planning horizon, which is how they avoid needing a deep
rollout. TD-MPC2 is rung two, and it reaches this project through LeRobot.

This family is normally right where the situation cannot be written down — raw
pictures, contact-rich manipulation, anything where the useful variables are not
the measured ones. It is normally wrong, or at least wasteful, where the
situation *can* be written down and already has been, which is the case here:
problem 2 has measured the positions and widths, so a learned encoding is being
asked to rediscover information the cell already supplies. That is the honest
prior expectation for rung two on this bench, and it is exactly the expectation
the comparison exists to test.

### Where the push data of record comes from

Finally, for anyone who wants real pushes rather than simulated ones: Yu, Bauza,
Fazeli and Rodriguez's [*More than a Million Ways to Be
Pushed*](https://arxiv.org/abs/1604.04038) (2016) recorded a robot pushing
objects across several different surfaces with the pusher's path, the object's
motion and the contact forces all logged. What it buys is pushes on *more than
one surface*, which is the only way to ask whether a fitted push model transfers
at all — the question this solution cannot ask, because its bench has one table
with one friction. What it costs is a robot, a motion-capture rig and months.

## Where it sits among the other five

This solution is the only one that learns what will happen rather than what to
do, and its place in the comparison follows from that rather than from its
score.

Against [one fixed nudge](01-one-fixed-nudge.md), the comparison is whether any
learning beats no learning. The fixed nudge needs no data, no training and no
weights, it explains every one of its own failures, and on any table where a
small shove in a sensible direction is enough it is the easier tool by a wide
margin. This solution earns its place where choosing the push matters — where a
nudge in the obvious direction moves a glass into a different crowd.

Against [geometry generates, a model ranks](02-geometry-ranked.md), the
comparison is the closest in the set and the easiest to misread. Both search
over candidate pushes and both score them with something fitted. The difference
is what the fitted part returns. A ranker returns a score, which is enough to
choose among the candidates in front of it and not enough to say what the table
will look like, so it can never chain two pushes or be re-aimed at a different
goal. This solution's model returns a table, which costs more to fit and buys
both of those. Note also that the geometric solution is the teacher for the
imitation solutions, and this one is not: it needs no demonstrations, because
its labels come from the second look.

Against [imitation from demonstrations](03-imitation-from-demonstrations.md),
the comparison is the one [the plan](../solutions-plan.md) names as *plan with a
model, or learn the push directly*. A policy answers in one pass with no search,
which makes it far cheaper to run, and it needs no explicit idea of the world at
all. But it needs demonstrations, which somebody or something has to produce; it
inherits whatever its teacher did wrong; and changing the goal means training
again. This solution needs no demonstrations and no teacher, and it can be
re-aimed by editing arithmetic. It pays for that in run-time compute and in
machinery.

Against [SmolVLA as it downloads](05-smolvla-as-it-downloads.md) and [SmolVLA
fine-tuned](06-smolvla-fine-tuned.md), the comparison is between a small thing
that knows only this table and a large thing that has seen hundreds of real
teleoperation datasets and knows almost nothing about this one. Those two are
also policies, so they share the contrast with imitation above. The pair of them
is the sharpest comparison in the whole set — the same model and the same
weights, with the only difference being whether its training was continued
here — and this solution is not part of that comparison at all.

And the comparison inside this solution is its own: five small networks written
for this cell against TD-MPC2 off the shelf, which measures whether building the
model by hand was worth the effort. The honest expectation is that in a cell
this narrow, with the state already measured, the hand-built model is
competitive. Finding out is the point.

← [Imitation from demonstrations](03-imitation-from-demonstrations.md) ·
[SmolVLA as it downloads](05-smolvla-as-it-downloads.md) →
