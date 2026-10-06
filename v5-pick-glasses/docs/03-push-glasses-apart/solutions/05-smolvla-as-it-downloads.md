# Solution 5 — a foundation model as it downloads

> **What it uses** — [LeRobot](https://github.com/huggingface/lerobot), the
> library that holds reference implementations of every learned policy in this
> folder, with PyTorch underneath it, and one borrowed model taken exactly as
> it downloads. The model is shown a picture, told in ordinary words what to
> do, given the arm's own joint readings, and it returns robot actions. That
> model is **SmolVLA**, about 450 million parameters, which uses a few
> gigabytes while answering and runs on a laptop. Not one number in it is
> fitted in this cell.
> **What it does** — it shows the borrowed model the rendered view of the
> table from the top, hands it one instruction written in plain English, hands
> it the arm's joint readings, and carries out the jaw waypoints it returns.
> Then it looks at the table again and asks once more, until every glass has
> its room or the push budget is spent. There is no training step, no data
> collection and no fitted parameter anywhere in the design.
> **How the output is produced** — the view from the top, the instruction and
> the joint readings go into the model; the model returns a run of actions;
> those actions are read as waypoints for the jaw and handed to the examiner,
> which carries them out directly rather than through the push macro it owns.
> So the chain is short: picture and words in, waypoints out, table changed,
> look again.
> **How it differs from the other five** — [solution
> 1](01-one-fixed-nudge.md) uses no model at all and no learned number of any
> kind, and it is the floor this folder is read against. [Solution
> 2](02-geometry-ranked.md) writes the candidate pushes by hand with geometry
> and fits only the small model that ranks them, so what it borrows is
> nothing and what it fits is one component. [Solution
> 3](03-imitation-from-demonstrations.md) fits a policy entirely on
> demonstrations recorded in this cell, borrowing an architecture but no
> weights. [Solution 4](04-a-world-model.md) fits a model of how the table
> behaves and then searches through it at run time, which is the opposite
> trade from this one: it pays heavily per push and owes nothing to anybody
> else's data. [Solution 6](06-smolvla-fine-tuned.md) is this same model, from
> this same library, starting from these same downloaded weights, with its
> training continued on this cell's own pushes, and nothing else varies
> between the pair.
> **What it costs** — no demonstrations, no labels, no training run and no
> weights file to keep in step with the cell. It needs the library, the
> weights the library downloads, and a laptop. The expense that remains is
> time per push, because every decision is a forward pass through a large
> network rather than arithmetic, and that expense belongs on the scorecard
> beside the counts.

> **The cell is described once, in [the cell](../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the
> side, all four sensors, and the words this project uses them with. What
> follows is only what is specific to this solution.

## Introduction

This document describes how [problem 3](../problem.md) could be answered by
downloading a general-purpose robot model and running it, with nothing
collected, nothing trained and nothing fitted in this cell at all. The model is
shown the table from the top, told in words what to do, and asked for actions.
Whatever it returns is carried out.

**This solution is built and has run.** It lives in
`03-push-glasses-apart/05-smolvla-as-it-downloads/`, it downloads the weights
and makes the pushes on the same held-out tables as the rest of the folder,
and its folder's README carries the numbers. What follows was written before
it ran, so where this document says what would probably happen, that is an
argument from what the model was fitted on and what this examiner offers it, and
not a measurement. The measurements are in the README, and the one thing the
design did not foresee is how much weight the reading between the model's
action space and this jaw would have to carry.

The design is worth writing down for two quite separate reasons, and it is
worth separating them at the start because they pull in opposite directions.
The first is that it is the cheapest thing in this folder to try. There is
nothing to collect, so there is no week spent recording pushes, and there is
nothing to train, so there is no accelerator to rent. The second reason is that
it is very likely to do badly. Those two facts are not in tension, because this
solution's value is not its score. Its value is that it is the starting point
of the sharpest comparison in the set: [solution
6](06-smolvla-fine-tuned.md) is this same model with its training continued
here, so the gap between the two measures what that training bought and
measures nothing else.

By the end of this document you will understand what kind of model this is and
what goes into it, where its competence comes from and why that competence is
general rather than local, exactly what is borrowed and exactly what is not,
why the difference between the pictures it learned from and the pictures this
examiner would show it is the central risk, why the instruction it is given
carries almost no information in this problem, why the one channel that
observes friction cannot reach it, and why a poor result here would still be
the most useful thing in the folder.

## The code that does the work

Nothing here is fitted, so the only code this project wrote is the join between
what the borrowed model emits and what this cell's jaw is. That join turned out
to be the whole solution, for a reason the sections below explain at length and
which is worth having in front of the code: the released checkpoint saves its
normalisation statistics under keys the normaliser never looks up, so both the
normaliser and the un-normaliser pass their numbers through unchanged, and the
actions arrive as z-scores with no units in them at all. A scale therefore had
to be **chosen** rather than converted, and the lines that choose it are the
lines to read.

The borrowed library does its work in one call, in
[`03-push-glasses-apart/05-smolvla-as-it-downloads/policy.py`](../../../03-push-glasses-apart/05-smolvla-as-it-downloads/policy.py).
`predict_action_chunk` is LeRobot's; `self.pre` and `self.post` are the
processors the checkpoint ships, which are the ones that do nothing here; and
`to_jaw` is this project's.

```python
    def ask(self, picture: np.ndarray, jaw: Waypoint) -> np.ndarray:
        ...
        batch = {
            CAMERA: torch.from_numpy(picture.copy()).permute(2, 0, 1).float() / 255.0,
            "observation.state": torch.from_numpy(to_state(jaw, self.up)).float(),
            "task": INSTRUCTION,
        }
        with torch.no_grad():
            actions = self.policy.predict_action_chunk(self.pre(batch))
        return to_jaw(self.post(actions)[0].numpy().astype(float), self.up)
```

The scale that `to_jaw` applies is in
[`03-push-glasses-apart/05-smolvla-as-it-downloads/joining.py`](../../../03-push-glasses-apart/05-smolvla-as-it-downloads/joining.py),
and the whole of the choice is one constant and the four lines that spend it.

```python
# Which of SmolVLA's six slots carries what, in the reading above.
ACROSS, OUT, UP, TURN = 0, 1, 2, 4

...

# How many standard deviations of the model's own action space the picture's
# frame covers. Two, because a z-score of two is the edge of what a normally
# spread quantity does, so the whole frame is reachable without the great
# majority of the model's output pinning itself against the edges.
ACTION_SPAN = 2.0

...

def to_jaw(action: np.ndarray, up: float = UP_HIGHER) -> np.ndarray:
    ...
    unit = np.clip(action / ACTION_SPAN, -1.0, 1.0)
    return np.stack(
        [
            VIEW_CENTRE[0] + unit[:, ACROSS] * TOP_VIEW_HALF_FRAME,
            VIEW_CENTRE[1] + unit[:, OUT] * TOP_VIEW_HALF_FRAME,
            PUSH_HEIGHT + (up * unit[:, UP] + 1.0) / 2.0 * (TRAVEL_HEIGHT - PUSH_HEIGHT),
            unit[:, TURN] * math.pi,
        ],
        axis=1,
    )
```

Two things show from that. The only object in this solution that has both a
metric extent and is seen by the model is the frame of the straight-down
picture, so `ACTION_SPAN = 2.0` is the decision that two standard deviations of
the model's output span that frame exactly — which is what lets the model put
the jaw anywhere it can see and nowhere it cannot. And because the examiner
consumes waypoints a fixed period apart, the spacing of the waypoints this
function returns *is* the speed the jaw is asked to travel at, so the same
constant fixes the speed as well as the reach, and the two cannot be chosen
separately.

![Three things go into the borrowed model and only one of them varies: the rendered view from the top changes with every table, while the instruction is the same sentence every time and the jaw's own pose is the same six numbers at all 2,260 asks, because the examiner parks the jaw outside the picture's frame and the reading clips it to the edge of the range; what comes back is fifty waypoints of six numbers whose shipped normalisation statistics are saved under keys the normaliser never looks up, so both the normaliser and the un-normaliser do nothing and the numbers arrive as z-scores with no units in them, which is why four of the six slots have to be read as the jaw's x, y, height and heading by hand and the other two dropped.](../../../images/03-push-glasses-apart/05-the-join-at-both-ends.png)

## The problem this solves

[The problem](../problem.md) asks for a jaw trajectory, and then another, until
every glass on the table has about 70 mm of clear room in every direction and
nothing has been knocked over. Choosing those trajectories is hard for a
reason [pushing without toppling](../pushing-without-toppling.md) sets out in
full: a push does not go where it was aimed, because the contact between a flat
jaw and a curved glass is a patch rather than a point, the friction under the
foot is not the same everywhere on the foot, and the glass turns as well as
travels. Predicting the outcome precisely needs numbers nobody in this cell
has.

Every other solution in this folder responds to that by building something.
Solution 1 builds a rule, solution 2 builds geometry and a ranker, solution 3
builds a policy from recorded pushes, and solution 4 builds a model of the
table and searches through it. Each of those costs work, and three of the four
cost data collected in this cell.

This solution responds differently. It observes that pushing an object across a
flat surface with a gripper is not a task peculiar to this project, that very
many people have recorded robots doing exactly that sort of thing, and that
somebody has already fitted a single model on an enormous pool of those
recordings. So instead of building a method for this table, it borrows a method
for tables in general and asks whether the general thing is good enough for the
particular one. That is a real question with a real answer, and the answer is
worth knowing before anybody spends a week recording demonstrations.

## The main idea

The idea has three steps, and the first two are the whole of the solution.

**First, download the model and run it on the table from the top.** The input
is a picture of the table looking straight down, which [the test
examiner](../the-examiner.md) specifies so that the solutions which read pictures get
the same information as the solutions which read numbers. That picture is the
model's view of the world. The examiner renders it: a fixed camera 750 mm above
the middle of the glass zone, looking straight down, 384 by 384 pixels of
red-green-blue, the same frame on every table.

**Second, tell it in words what to do, and hand it the joint readings.** The
instruction is one line of plain English, the same line every time, saying that
the glasses are too close together and should be pushed apart. The joint
readings are where the arm's own joints are at that moment, which the arm knows
exactly from its encoders.

**Third, carry out what comes back.** The model returns actions. Read as
waypoints for the jaw, those actions are already the shared output the contract
asks for, so they go straight to the examiner. The examiner moves the jaw along them,
the table changes, fresh measurements are taken, and the model is asked again
from the new arrangement.

So this solution contains no fitted numbers, no hand-written geometry and no
search. It contains a download, an instruction and a loop. **That is the point
to hold on to while reading the rest**, because almost every strength and every
weakness below follows from it directly.

## A model that sees, is told, and acts

The kind of model being borrowed needs explaining before anything else,
because the rest of this document depends on what goes into it and what comes
out.

Three things go in together. The first is **what the camera sees**, as an
ordinary picture. The second is **an instruction in ordinary words**, written
the way a person would write it, such as "pick up the red block" or "push the
glasses apart". The third is **the robot's own joint readings**, which say
where each joint is at this moment, so the model knows the shape the arm is
currently in and not only what is in front of it.

One thing comes out: **robot actions**. The model returns targets for the robot
to move to, at the rate a controller consumes them, so a single answer from the
model is a short run of movement rather than a single pose.

A model with those three inputs and that one output is called a
**vision-language-action model**, and the name is simply the three parts listed
in order. The useful thing about the name is that it says where the model sits
in a system. It is not a perception component that reports what it sees and
leaves the acting to something else, and it is not a controller that is handed
a goal in numbers. It takes the raw picture and the human sentence at one end
and emits movement at the other, with nothing in between that a person writes.

That is a genuinely different shape from the other learned solutions in this
folder. Solution 4's learned part is a model of how the world changes, and a
separate search uses it to choose. Solution 2's learned part is a ranker, and
hand-written geometry proposes what it ranks. Here there is one network and it
does the whole job, which is why a single borrowed file can be a complete
answer to the problem, and also why there is no small piece of it that can be
corrected when it is wrong.

## Where such a model gets its competence

A model with no knowledge of this cell can only be worth trying if it knows
something general, so it is worth being precise about where that general
knowledge comes from.

It comes from **pretraining on very many recorded demonstrations, across many
different robots and many different tasks**. Somebody collected an enormous
pool of recordings in which a robot arm was driven by a person through some
piece of manipulation — reaching for things, grasping them, moving them,
putting them down — with the camera picture, the instruction and the joint
readings all recorded together, and the model was fitted on all of it at once.
SmolVLA's pool is **487 community datasets of real teleoperation**, which means
real robots in real rooms, driven by real people.

What a model learns from a pool like that is not any one of those tasks. It is
the shape that manipulation has in general: that an arm approaching an object
slows as it arrives, that a gripper closes when it is on the object and not
before, that movement near a surface stays near the surface, that a push is a
contact followed by travel in one direction rather than a jerk in several. The
comparison from programming is a library of general routines rather than a
program for one job: nothing in it solves your problem, but the parts it offers
are the parts most problems of that family are built from.

**So what this model brings to problem 3 is a general sense of how
manipulation goes, and nothing whatever about this cell.** It has no idea that
this table has a glass zone, that a rack sits in one corner, that the arm
reaches comfortably between 300 and 780 mm from its base, or that pushing a
glass above a certain height tips it over instead of moving it. Those are
facts about this cell, they are published once in [the
cell](../../the-cell.md) and [the problem](../problem.md), and a model fitted
elsewhere has never met any of them.

## What is borrowed, and what is not

That division matters enough to state it flatly, because it is what makes this
solution the baseline it is meant to be.

**Nothing whatsoever is fitted here.** The weights are downloaded and used
unchanged. There is no training run, no fine-tuning, no small correction fitted
on this cell's data, and no threshold tuned on the examiner's training tables. If
a number in this solution came from somewhere, it came from somebody else's
robots.

So the model has never seen this cell. It has never seen these glasses — not
the straight glass, not the tapered glass, not the stemmed glass and not the
short stemmed glass. It has never seen this jaw, which is two fingers and two
pads held closed and level, 30 mm tall, riding as low as the gripper reaches.
And it has never seen a table rendered the way this examiner renders one.

What **is** borrowed is everything else: the architecture, the weights, the
convention by which pictures are read, the convention by which words are read,
and the convention by which actions are emitted. Every one of those was fixed
by somebody else, for somebody else's robots, before this project existed. That
is the trade this solution makes, and the next three sections are the three
places where the trade bites.

## The actions come out in somebody else's units

The first place it bites is at the output, and it is a practical difficulty
rather than a deep one, but it has to be solved before anything can run at all.

A model fitted on recordings of particular robots emits actions in the layout
and the units those robots used. The arm here is a UR5e with a two-finger
gripper, and it is not the arm the recordings were made on. So the numbers the
model returns are not automatically waypoints for this jaw; **turning them into
waypoints is an interpretation, and somebody has to choose it.** Nothing in the
model's pretraining knows this arm's joint layout, its reach, or how high above
the table a height of zero means.

This matters for the comparison in a specific way. A bad interpretation would
make the model look worse than it is, and the result would then be a
measurement of the interpretation rather than of the model. So whatever
convention is chosen has to be **chosen once and used by both solution 5 and
solution 6**, because the pair is only clean while everything except the
training is held still. That convention is now chosen and written down, in
`05-smolvla-as-it-downloads/joining.py`, and the folder's README says what had
to be decided in it and why. It turned out to be a larger decision than this
section expected, because the checkpoint settles less about its own action
space than the section assumed.

It is also worth noting that this is the step the examiner's own arrangement was
designed to allow. [The examiner](../the-examiner.md) accepts a run of
waypoints directly, without the push macro, precisely so that a policy which
thinks in movement is not squeezed into three numbers describing a push. Both
that path and the rendered view from the top now exist in the examiner, and this
solution uses them as they come.

![The only object in this solution with both a size in millimetres and a place in the picture is the frame of the straight-down view, 717 mm across on the table top, so two standard deviations of the model's action space are made to span it exactly and anything beyond that clips back onto its edge; because the examiner consumes one waypoint every 50 ms, the same constant also fixes the speed, and the median gap in the model's own chunks works out at 286 mm/s against the 20 mm/s the examiner's own push macro moves at and the 200 mm/s the arm tops out at.](../../../images/03-push-glasses-apart/05-two-sigmas-span-the-frame.png)

## The instruction is nearly dead weight here

The second place the trade bites is at the input, and it is the one most likely
to be misread, so it needs stating carefully.

A model of this kind earns its middle word by taking **different instructions
for different tasks**. That is the whole reason the language half is there: one
set of weights can be asked to pick a thing up, or to put a thing down, or to
open a drawer, and the sentence is what selects which. The pool it was fitted
on contained a great many different instructions, and the model's ability to
respond to them is a real capability that took a great deal of data to acquire.

**Problem 3 has one instruction.** Every table, every push, every look again:
the same sentence, because the task never changes. A quantity that takes the
same value every time carries no information, in exactly the sense information
is normally meant — knowing the instruction tells you nothing you did not
already know about the situation. So the language half of this model, in this
problem, does no work.

Two consequences follow, and the second one is the important one.

The first is that **the model is being used here as an expensive visuomotor
policy**: a thing that looks at a picture and produces movement. That is
precisely what solution 3 fits from demonstrations, with a far smaller network
and nothing borrowed. So the natural question — what is the extra size buying?
— has an answer that does not involve language at all. It is buying the
pretraining, and only the pretraining.

The second is a warning about reading the result. **A reader should know this
before concluding anything about vision-language-action models in general from
this number.** If this solution scores badly, it has not been shown that
vision-language-action models are a poor idea. It has been shown that one such
model, used with a constant instruction, on rendered pictures unlike its
training pictures, with nothing fitted, scores badly — which leaves the
model's actual selling point untested, because this problem never asks it to
do the one thing the language half exists for. A single-task cell is simply
not where that capability can be seen.

## The force reading has nowhere to go

The third place the trade bites is the most interesting, because it is a
mismatch between what this problem gives a solution and what this model is able
to accept.

[The examiner](../the-examiner.md) is emphatic that the force reading is the
single most valuable thing it reports. Friction is never told to any solution
and nothing in the cell measures it, so how much force it took to start a glass
moving, and how far the glass travelled for that push, are the only evidence
about friction that exists anywhere. The examiner's own words are that every
solution which does better than a blind nudge does so by reading that channel,
either by reasoning about it or by learning from it.

**This model has three input slots, and force is not one of them.** It takes a
picture, a sentence and the joint readings. The jaw's report of what it felt —
whether it was blocked on the way down, how far it travelled before touching,
whether it jammed, the most force it felt, how far the glass moved after
contact — has nowhere to enter. So the one channel through which friction is
observable at all is, for this solution, closed.

That does not leave the solution blind, and it is worth being exact about what
remains. The arm looks again after every push, so the **outcome** of a push is
visible in the next picture: a glass that moved a long way looks different from
a glass that barely moved. What is lost is everything that happened *during*
the push, which is where the force signal lives, and which is the part that
distinguishes a glass that slid from a glass that leaned and settled back. So
this solution can learn nothing from a push except where the glasses ended up,
and it cannot even do that, because it learns nothing at all — it only sees
the new arrangement and answers again.

This is also the clearest statement of what solution 6 has to gain, and of how
little. Continuing the training here cannot add an input slot. What it can do
is fit the model's response on pushes whose outcomes are known, so that this
examiner's own friction ends up absorbed into the weights as a constant. That is
not a way of observing friction, and [solution
6](06-smolvla-fine-tuned.md) names it as a liability away from this examiner
rather than as a repair for the closed channel.

## The domain gap, which is the heart of this document

Everything above assumes the borrowed model works at all on the pictures this
examiner would show it, and that assumption is the one most likely to fail. It
deserves the longest section here, because the difference between what the
model was fitted on and what it would be given is large.

A **domain gap** is the difference between the data a model was fitted on and
the data it is used on. Here the two sides of that gap can be set out plainly.

**What it was fitted on is real teleoperation.** 487 community datasets of real
robots, driven by real people, in real rooms. That means real cameras, with the
noise, the blur and the colour a real lens produces. It means real lighting,
with shadows that say where an object meets the surface it stands on, and
highlights that curve the way a curved surface makes them curve. It means real
scenes, which are cluttered: a workbench with other objects on it, a background
that is a room, texture everywhere, and the particular visual mess that tells a
model what is near and what is far.

**What this examiner offers is a rendered view from the top of pale blue glasses
on a tan table.** The glasses are built as stacks of cylinders and shaded as
solid objects, the table is a flat rectangle, there is nothing else in the
frame, and nothing in the picture was produced by light passing through a
lens. Every glass is the same colour, so nothing in the picture tells one kind
from another. There is no clutter, almost no texture, and nothing of the
transparency a real drinking glass has, which in a photograph is the strongest
single clue that a glass is what you are looking at.

So the model is asked about pictures quite unlike the ones it learned from,
with much of the evidence it learned to use simply absent.

**The way models fail across such a gap is the part that matters.** They do not
usually produce nonsense. Nonsense would be convenient, because nonsense is
easy to detect and easy to refuse. What they produce instead is **confident,
plausible, wrong actions**: movement that looks like a push, aimed somewhere
reasonable, at a sensible speed, that is simply not the push this table needed.
That is worse than nonsense for one specific reason — **nothing downstream
looks suspicious.** The waypoints are well formed, the jaw follows them, the
arm does not fault, the examiner records a push, and the only sign that anything
went wrong is in the arrangement afterwards. There is no error to catch and no
confidence number to put a bar on.

It is worth noticing which direction those mistakes point. A push aimed at the
wrong place is recoverable, because the arm looks again and the next pass
replans from where the glasses really are. A push that topples a glass is not,
because nothing in problem 3 stands a glass back up. So a borrowed model
producing plausible wrong actions is not merely inaccurate; it is inaccurate in
the one way this problem cannot absorb, which is the whole reason the next
section but one takes the topple limit out of the model's hands entirely.

![Measured, the failure across the gap is blunter than confident wrong pushes: the lowest point of a chunk has a median of 209 mm above the table over 2,260 answers, which is more than three times the 65 mm at which a push really lands and clear over the top of all but the tallest glass the kind is drawn at, so 674 of one run's 754 pushes never touched anything at all, nothing was ever blocked coming down because nothing ever came down, and 69 of the 80 pushes that did reach a glass jammed.](../../../images/03-push-glasses-apart/05-the-chunks-come-back-high.png)

## The honest expectation

It follows from all of the above that this solution may well do badly, and it
is better to say so here than to let a reader discover it in the scorecard.

The expectation, reasoned from what the model brings and what it is given, is
roughly this. The model should produce well-formed movement, because producing
well-formed movement is what its pretraining is for and that capability does
not depend on recognising the scene. It should sometimes produce a sensible
push, because a crowded group of upright objects on a flat table is not an
unfamiliar shape and pushing one of them apart from its neighbours is a motion
the pool it learned from certainly contained. And it should often choose the
wrong glass, or the wrong direction, or a distance unrelated to what the
arrangement needed, because choosing correctly needs the picture to be read
accurately and the picture is the part that does not match.

Against [the target layout](../the-target-layout.md)'s yardstick that is a
specific prediction: glasses that end up far from where the push aimed them,
and a total travel that is a large multiple of the displacement floor. A method
whose glasses scatter is succeeding by looking again rather than by predicting,
and this is the solution in the folder most likely to be doing exactly that.

**And that is this solution's job.** It is the baseline for the sharpest
comparison in the set, and a baseline is useful in proportion to how cleanly it
isolates one variable, not in proportion to how well it scores. Solution 6 is
the same library, the same weights and the same examiner, with its training
continued on this cell's own pushes. If this solution scored well, the pair
would measure very little, because there would be little room for training to
improve anything. A poor score here is what gives that comparison its range.

![Put the racking beside the crowding and nothing is left over: 58 of the 251 glasses already had their room at the start and 56 were racked, where any solution that freed a glass would have racked more than 58, because racking one loosens its neighbours; no table of the fifty was finished in any of the three runs, 642 of 754 pushes were repeats, and the one or two glasses a run refused for tipping show that the shared rule hardly binds on these tables, so what is left to explain the shortfall is the pushes.](../../../images/03-push-glasses-apart/05-nothing-is-left-over.png)

## The price of the model, and why this model

Before leaving the model itself, it is worth being clear about what it costs to
run, because the cost is unusually low and that is part of why it is the first
thing to try.

**The model is about 450 million parameters.** It uses a few gigabytes of
memory while answering, and it runs on a laptop. There is no accelerator to
rent to use it, no cluster, and no special hardware of any kind. Combined with
the fact that nothing is collected and nothing is trained, that makes this
**the cheapest of the learned solutions in this folder to try** by a wide
margin: the whole setup cost is a download.

What it does cost is time per push, and that belongs on the scorecard. Every
decision is a forward pass through a large network, which is a different kind
of expense from solution 1's arithmetic and a different kind again from
solution 4's run-time search. The examiner carries a compute column for exactly
this reason, because a solution that wins while taking a hundred times longer
has not obviously won. The honest expectation here is a cost per push far above
the hand-written solutions, and a different kind of expense from a planner that
simulates many candidate actions forward before committing.

**Why this model and not a larger one** is worth answering, because larger
robot foundation models exist and the obvious question is whether a bigger one
would close the domain gap. The alternative considered is π0, which is about
3.3 billion parameters — roughly seven times the size. The difficulty is not
running it but training it, and training it is what [solution
6](06-smolvla-fine-tuned.md) has to do: π0's low-rank fine-tuning needs more
than 22 GB of accelerator memory, and a full fine-tune more than 70 GB. Those
floors decide the matter. A pair of solutions is only worth building if both
halves can actually be built, and **SmolVLA is chosen here because it is the
one whose fine-tuning is affordable**, which makes the 5-against-6 comparison
possible at all. π0.5 appears in this folder only as a further rung inside
solution 6, reached by low-rank adaptation, to ask whether a markedly larger
model is worth it.

## The pushes are what this contributes

It is worth stating plainly where this solution stops, because the boundary is
the same for all six and is what makes them comparable.

The input is fixed by [the examiner](../the-examiner.md). This solution may read
what `look()` returns — where each glass stands, how tall it is, how wide it
is at its widest and at its foot, and whether it is standing, each reading
carrying problem 2's measured error — and the rendered view of the same table
from the top. In practice it reads mostly the picture, because the picture is
what the model takes. It may not read the simulator's record of what was placed,
and it is not told the friction, and neither of those exceptions is relaxed for
a borrowed model.

The output is fixed too: **a jaw trajectory**. This solution emits one
directly, as a run of waypoints, rather than as a parameterised push expanded
by the examiner's macro. Both forms are accepted and the examiner treats them alike,
because **what is scored is the table afterwards rather than the push that
changed it**. That is the only arrangement under which a push described by
three numbers and a run of fifty waypoints can be compared at all.

So this solution contributes only the trajectories, and any difference in its
score belongs to them. It cannot win by aiming at an easier arrangement,
because [the target layout](../the-target-layout.md) is computed once from the
same measurements and handed to all six. It cannot win by marking itself
kindly, because the scorecard is the same counts computed the same way. And it
cannot lose by having its movement squeezed into a shape that does not suit it,
because waypoints are accepted as they come.

One thing about the repeats is specific to this solution and worth noting. The
examiner requires every trained solution to be trained with several seeds and
evaluated over several runs, because training varies with its seed and one run
is not a measurement. **This solution has no training seed**, since it trains
nothing, so the only variation it has is in how its actions are drawn when it
answers. Its spread should therefore be narrower than solution 6's, and the
comparison between the two has to be read with that difference in mind rather
than against it.

## How the concepts fit together

The pieces now connect into one picture, and it is a short picture because the
solution is short.

A model fitted on an enormous pool of real teleoperation across many robots and
many tasks would be downloaded unchanged and shown this examiner's rendered view
of the table from the top, together with one unvarying English sentence and the
arm's own joint readings. It would return actions, which somebody has to
interpret as waypoints for this jaw, because the units and layout it emits were
fixed for other robots. The examiner would carry those waypoints out, the table
would change, fresh measurements would be taken, and the model would be asked
again.

What the model brings to that loop is a general sense of how manipulation goes,
and nothing about this cell. What it is denied is the force reading, because its
three inputs do not include one for force, so the only channel through which
friction is observable is closed to it. And what stands between its general
competence and this particular table is a large domain gap: it learned from
real cameras, real light and cluttered rooms, and it is shown flat pale blue
shapes on an empty rectangle. Across that gap it would most likely produce
confident, plausible, wrong actions, which is the failure that is hardest to
notice because nothing about it looks wrong until the arrangement is examined.

Every one of those is a consequence of one decision: **fit nothing here**. That
decision is what makes the solution free to try, and it is also what removes
every lever that would normally be pulled to fix the problems above. Pulling
exactly one of those levers is [solution
6](06-smolvla-fine-tuned.md).

## When a glass cannot be pushed safely

Every solution document in this folder answers this question, and this one's
answer is the shortest of the six, because **the answer does not involve the
model at all**.

[Pushing without toppling](../pushing-without-toppling.md) sets out the rule. A
glass slides while the height the jaw touches it is below half its foot width
divided by the friction coefficient, and tips above it. The height that counts
is the top edge of the jaw, which is 65 mm rather than the 50 mm the middle of
the jaw rides at, because a glass that is wider higher up meets the top edge
first. For a glass whose limit falls below that, there is no contact height the
arm can offer that is safe, and the only correct answer is to refuse — the run
ends as *correct but incomplete*, the glass stays where it was, and the reason
is reported.

That check is **applied on the measurements, before any model is consulted.**
A glass that fails it is removed from the task and reported, so the model is
never asked to move it. The arithmetic is shared rather than rewritten here:
it is solution 1's `slides`, in `01-one-fixed-nudge/plan.py`, which solutions
2, 3, 6 and this one import rather than rewrite, so those five refuse exactly
the same glasses. [Solution 4](04-a-world-model.md) is the exception: it judges
toppling with its own learned model and says that the shared gate in front of
it is not there yet. It does not live in the examiner, which the second half of
this section comes back to.

**That arrangement is just as well, and the reason is the point of this whole
document.** Nothing in a borrowed model's pretraining knows this cell's jaw or
this kind's foot width. The limit depends on a foot width that problem 2
measures here, on a jaw height that is this gripper's own number, and on a
friction coefficient that nothing in this cell measures at all. A model fitted
on other people's robots has met none of those three quantities, and it has no
way to acquire them from a picture of plain shapes. Asking it to respect a limit
it cannot compute would be asking it to guess, and the one mistake this problem
cannot absorb is a toppled glass. So the refusal is taken out of the model's
hands entirely and made arithmetic that runs first.

There is a second half to this. Removing a glass from the task does not remove
it from the picture, so a model that reads the picture can still aim at a
refused glass, and a solution that emits waypoints freely is also free to emit
a contact higher than the lowest the gripper reaches. Nothing in the model's
pretraining would warn it against either. So the trajectory that comes back is
read rather than trusted: one that would reach a refused glass is thrown away,
and the heights in the rest are bounded into the range the jaw rides at.

Both of those checks are built, in `05-smolvla-as-it-downloads/clear.py` and
`joining.py`. This document expected them to sit in the examiner beside the
refusal, so that they would be identical for all six and not something a model
can argue with. They do not: the examiner grew the straight-down view and the
waypoint path but no shared guard, and the tipping refusal lives in solution
1's folder rather than in the examiner either. So the checks are this solution's
own, written to the same rule, and solution 6 should import them from here
rather than write them again. Between them, this solution cannot topple a
refused glass by choosing badly.

## A worked example

Following one crowded table through makes the expectations above easier to
recognise, because they appear together rather than one at a time.

Five glasses of the tapered kind stand in the glass zone. Two of them are
standing deliberately close together, closer than the gripper can work with but
not touching, which is how [the examiner](../the-examiner.md) builds its tables.
A third stands a little way off and is crowded by accident. The remaining two
are clear of everything. One of the close pair is at the narrow-footed end of
what its kind allows, and the tapered kind is wider higher up by definition, so
that glass meets the top edge of the jaw first and its limit is the tightest on
the table.

**The shared machinery runs first.** It evaluates the topple limit for every
glass from its measured foot width, and the narrow-footed glass of the close
pair fails: its limit falls below the jaw's top edge. That glass is refused with
its reason, and it is removed from the task. Four glasses remain as a question
for the model, though the view it is shown still contains all five, so a push
aimed at the refused glass is rejected rather than carried out. The crowding
around that glass is now a problem nothing can solve, which is a correct
outcome rather than a failure.

**Then the model is asked.** It receives the rendered view from the top, the
unvarying sentence, and the joint readings. What would probably come back is a
run of waypoints that is well formed as movement — smooth, at a sensible
speed, descending and then travelling in one direction, which is the shape a
push has. What is far less certain is whether it is the right push. The most
likely mistakes, reasoning from the gap, are three. It may aim at the wrong
glass, because every glass in the picture is the same colour and nothing in it
says which pair is the tight one, and in a rendered view with no shadows the
cue that would normally say how close two objects are standing is weak. It may
push in a direction that moves the glass out of one crowd and into another,
because the arrangement as a whole is what decides a good direction and
reading an arrangement is the part that needs the picture to be understood.
Or it may push much too far or much too little, because the distance a push
should cover is a property of this table's clearances and nothing in the
model's pretraining knows them.

**Then the arm looks again**, and this is where the loop earns its keep. The
fresh measurements say where the glasses really are, the refused glass is still
refused, and the model is asked once more from the new arrangement. A wrong push
is therefore not fatal, only wasteful, and what it costs is one entry against
the push budget. Repeated often enough, that is the signature this solution
would most likely leave on the scorecard: a run that spends many pushes, moves
the glasses a long way in total compared with the displacement floor, and
clears fewer tables than the solutions that were fitted here.

The instructive part is what the run would *not* contain. There would be no
crash, no fault, no refusal the model generated, and no number anywhere in the
output marked as doubtful. Every push would look like a push. That is the
characteristic failure across a domain gap, and it is why this solution's result
has to be read against solution 6's rather than on its own.

## What it needs

Less than anything else in this folder, which is the whole point.

**Software.** [LeRobot](https://github.com/huggingface/lerobot), licensed
Apache-2.0, which holds the policy as a reference implementation, and PyTorch
underneath it, licensed BSD-3-Clause. Both are permissive, so neither changes
the terms of the project the way [the implementation
notes](../../../implementation-notes.md) describe for a copyleft component. The
weights themselves carry their own terms, which a reader taking this forward
should check before anything is shipped, because a licence on weights is not
the same thing as a licence on the library that loads them. Nothing here says
what those terms are, since nothing in this project records them. What can be
said structurally is that a file produced by continuing their training, as
[solution 6](06-smolvla-fine-tuned.md) produces one, inherits whatever the
borrowed weights carried, so this solution is the half of the pair that leaves
no new file to carry anything.

**The weights.** Downloaded, used unchanged, and about 450 million parameters,
so a few gigabytes while answering.

**Hardware.** A laptop. There is nothing to train, so there is no accelerator
to rent for this solution at all. This document said that solution 6 would pay
for the accelerator while solution 5 paid for nothing, and that turned out to
be wrong about the other half of the pair: [solution
6](06-smolvla-fine-tuned.md)'s low-rank fine-tune of this same model held
**1.02 GiB** while it ran, on this machine's own Metal, so neither half rented
anything. The 22 GB and 70 GB floors quoted above belong to π0, which is
several times larger. The one case where renting would still be sensible is
evaluation throughput rather than capability — the scorecard asks for several
runs per solution, and many forward passes on a laptop take a while. For
scale, renting an accelerator for a weekend costs of order a hundred dollars,
and a small one for a month costs of order five hundred, so even running the
evaluation on rented hardware is at the cheap end of this folder.

**Data.** None. No demonstrations, no labels, no held-out set, and nothing to
keep in step with the cell when the cell changes.

**What the examiner had to grow.** Two things, and both were gates rather than
conveniences: the rendered view of the table from the top, and the path that
accepts a run of waypoints without the push macro. [The test
examiner](../the-examiner.md) now provides both, and both are shared with solutions
3 and 6, so the cost was paid once for three solutions rather than for this
one.

## Where it is strong and where it breaks

The strengths all come from the same source, which is that nothing is fitted.

There is nothing to collect, nothing to train and nothing to keep in step with
the cell, so this solution could be tried in an afternoon once the examiner's two
missing parts exist. It needs no accelerator. It gives the folder a reading on
what a borrowed robot model is worth before anybody spends a week recording
pushes, which is a decision several of the other solutions depend on. It is a
genuine upper bound on convenience, because no solution here can be cheaper to
set up. And it is the clean half of the folder's sharpest pair, which is the
strength that does not depend on it working at all.

The weaknesses divide into what the borrowing costs and what it cannot be asked
to do.

What the borrowing costs is accuracy and every lever for improving it. The
domain gap is large, the model learned from real cameras and cluttered rooms,
and it is shown flat pale blue shapes on an empty rectangle, so the most likely
outcome is confident, plausible, wrong actions with nothing downstream looking
suspicious. The force reading cannot reach it, so the only channel that
observes friction is closed. The actions arrive in somebody else's units, so an
interpretation stands between the model and the jaw and a poor one would be
blamed on the model. And the language half does no work, because the task has
one instruction, so the model is an expensive visuomotor policy here rather
than the thing it was built to be.

What it cannot be asked to do is anything that needs fitting. It cannot learn
from a push that went wrong, because it does not learn. It cannot be corrected
on the kind of glass it handles worst, because correcting it is training. It
cannot have a threshold tuned, because it has no threshold. The one repair for
all of that is to continue its training on this cell's own pushes, which is a
different solution with a different name, and that is exactly why the two are
written as a pair.

The honest position is therefore that this is among the first things to run and
very unlikely to be the one carried forward. Its value is the comparison it
makes possible rather than the accuracy it would deliver.

## The general ideas behind this

Five named ideas sit under this solution, and each is worth knowing in its own
right, including where it is normally the wrong tool.

### Robot foundation models — one model pretrained for manipulation in general

A **foundation model** is one fitted on a very large and very broad pool of
data, with the intention that it be used on tasks nobody had in mind when it was
fitted. The robot version pools demonstrations from many robots and many tasks,
which is sometimes called **cross-embodiment** pretraining, because the robots
in the pool are not the same machine.
[LeRobot](https://github.com/huggingface/lerobot) carries several, among them
π0, π0.5, GR00T N1.7 and SmolVLA.

This is normally the right move when your task resembles the pool and your own
data is scarce, because you get a competent starting point for the price of a
download. It is normally wrong when your input does not look like the pool's
input, which is the case here, and wrong when the task needs a quantity the
model has no input for, which is also the case here. It is also the wrong thing
to reach for when a few lines of geometry would settle the question, which
[solution 2](02-geometry-ranked.md) is in this folder to demonstrate.

### Zero-shot transfer — using a model on a task it was never fitted for

A model is used **zero-shot** when it is applied with no examples of the new
task at all, relying entirely on what it learned elsewhere. It works when the
new task is genuinely a special case of the old one.

It is normally the right first move whenever a general model exists and data is
expensive, because it costs an afternoon and tells you how hard your problem
really is. It is normally wrong as a final answer when the input differs
visibly from what the model was fitted on, and the standard repair is to
continue the training on your own data, which is [solution
6](06-smolvla-fine-tuned.md). The folder is built to measure exactly that
repair.

### Language conditioning — the sentence that selects the task

Taking an instruction in ordinary words lets one set of weights serve many
tasks, which is what the middle word of the model's name refers to.

It is right whenever the tasks are many and the boundaries between them are
the sort of thing a person can describe in a sentence, because then the
sentence is doing real work and no code has to enumerate the cases. It is
wrong — or rather simply idle — when there is one task, which is the
situation here. A constant input carries no information, so the capability is
paid for and not used, and nothing about this cell can be concluded about
language conditioning in general.

### Action chunking — predicting a run of movement rather than one step

Policies in this family emit a short run of future actions together rather than
one action at a time, which [solution
3](03-imitation-from-demonstrations.md) explains properly, since ACT is named
for it. The reason it matters here is the contract: because these architectures
produce movement in runs, [the examiner](../the-examiner.md) accepts a run of
waypoints directly instead of demanding three numbers describing a push.

Predicting a run is right when the motion is a smooth committed thing, as a
push is, because it keeps the policy consistent across the motion instead of
wobbling from one step to the next. It is wrong when the situation can change
faster than the run takes to execute, because a committed run cannot react
inside itself — which is the gap that [the learned early
abort](../pushing-without-toppling.md) exists to cover, and it is a shared
mechanism rather than anything this solution provides.

### The domain gap, and the honest reading of a failure across one

The difference between the data a model was fitted on and the data it is used
on is the single most common reason a borrowed model disappoints, and the
characteristic symptom is confident wrong output rather than nonsense.

The useful discipline is to say which side of the gap you intend to move before
you measure anything. Moving the model is fine-tuning, which is solution 6.
Moving the data means making the rendered pictures resemble real ones, which is
a large piece of work in its own right and is not attempted anywhere in this
folder. The failure to avoid is concluding that the method is poor when what has
actually been measured is the gap, and the whole reason this document and the
next are written as a pair is to make that confusion impossible.

## Where it sits among the other five

This solution sits at one end of the folder's main axis, and the axis is the
useful way to see all six.

The axis is **where the numbers came from**. [Solution
1](01-one-fixed-nudge.md) has no fitted numbers at all and no model; it is
arithmetic and it is the floor. [Solution 2](02-geometry-ranked.md) writes the
candidates by hand and fits only the ranker, so one small component came from
this cell. [Solution 3](03-imitation-from-demonstrations.md) fits a whole
policy on demonstrations recorded here, borrowing an architecture but no
weights. [Solution 4](04-a-world-model.md) fits a model of the table here and
then searches through it at run time, which is a different kind of expense per
push and owes nothing to anybody else's data. This solution is the only one
whose numbers came entirely from **somewhere else**, and [solution
6](06-smolvla-fine-tuned.md) is the same numbers with this cell's own pushes
added on top.

Read in that order, [the six solutions](overview.md) measure what each kind of
fitting buys, and this one is the borrowed extreme they are read against.

One of those comparisons is sharper than the rest, and it is the reason this
document and the next one should be read together. **Solution 6 is this same
model, from this same library, starting from these same downloaded weights,
with its training continued on this cell's own pushes, running on this same
examiner.** The input is held still, the output is held still, the marking is held
still, the interpretation that turns the model's actions into jaw waypoints is
held still, and the topple refusal runs first in both. Nothing varies between
the pair except the training. So the gap between their scores is a measurement
of what that training bought and of nothing else, and no other pair in this
folder is that clean. One qualification belongs with that claim, and solution 6
makes it in full: the training there adapts the model through a low-rank
correction rather than by moving every weight, so the gap is a lower bound on
what fine-tuning could buy rather than the whole of it.

That is also the closing argument for building this solution despite expecting
it to do badly. A baseline is valuable in proportion to how cleanly it isolates
one variable, and this one isolates fine-tuning exactly. If it scored well,
there would be little room left for solution 6 to show anything, and the
sharpest question in the plan, what does fine-tuning a foundation model buy,
would have no range to be answered in. A poor score here is therefore not a
disappointing result. It is the measurement working.

← [A world model, then plan with it](04-a-world-model.md) · [The same model,
fine-tuned here](06-smolvla-fine-tuned.md) →
