# Solution 6 — the same foundation model, fine-tuned here

> **What it uses** — LeRobot, with PyTorch underneath. The model is SmolVLA,
> with the same downloaded weights as [solution
> 5](05-smolvla-as-it-downloads.md). Its training is continued here by
> low-rank adaptation, on pushes made on the examiner's tables. The training
> ran on this laptop's own Metal GPU.
> **What it does** — it keeps the borrowed numbers and learns a small
> correction to them. The correction is fitted on pushes made in this cell.
> The model then emits action chunks, and those chunks are this solution's
> answer to problem 3.
> **How the output is produced** — the model gets the view of the table from
> the top, one instruction in plain English and the arm's pose. It returns an
> **action chunk**: a short run of jaw waypoints predicted in one pass. The
> shared geometry refuses the glasses that tip before they slide. A chunk whose
> path reaches one of those is not carried out. The examiner carries out the
> other chunks directly. The arm looks again, and the loop repeats until the
> table is done or the push budget is spent.
> **How it differs from the other five** — [solution
> 1](01-one-fixed-nudge.md) fits nothing and computes one push by fixed
> arithmetic. [Solution 2](02-geometry-ranked.md) makes pushes by geometry
> and fits only a ranker. Its pushes are this solution's demonstrations.
> [Solution 3](03-imitation-from-demonstrations.md) learns from the same
> demonstrations, but from random numbers. [Solution
> 4](04-a-world-model.md) learns how the table changes and searches at run
> time. [Solution 5](05-smolvla-as-it-downloads.md) is this exact model with
> no training here. It is this solution's matched partner.
> **What it costs** — the demonstrations are free, because solution 2 makes
> them. The training fits in 1.02 GiB on a laptop, so nothing was rented. A
> run costs one large forward pass per chunk, the same as solution 5. The
> fine-tuned file inherits the terms of the borrowed weights, so read them
> before anything leaves the project.

> **The cell is described once, in [the cell](../../../01-rack-one-glass/docs/the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the
> side, all four sensors, and the words this project uses them with. What
> follows is only what is specific to this solution.

## Introduction

This document answers problem 3 with a borrowed robot model whose training is
continued on pushes made in this cell. That method is called
**fine-tuning**. It is the usual way to put a borrowed model to work on one
job. It is written out here so that its value can be measured.

**This solution is one half of a matched pair.** [Solution
5](05-smolvla-as-it-downloads.md) is the same model with no training here.
The [examiner](../the-examiner.md) holds the input, the output and the
marking the same for both. The two solutions share the library, the model and
the starting weights. Only the training differs. So the gap between the two
scores measures what the training bought.
[Whether anything but the training differs](#whether-anything-but-the-training-differs)
checks that claim.

[Problem 2](../../../02-segment-glasses/docs/problem.md) asked the same question
about a model that finds glasses in pictures. Here the model chooses what the
arm does. Training can help a model see a cell and still not help it act in
the cell. Choosing a push needs a sense of what a push does, and no picture
holds that.

**Most of it is built.** The code is in
`03-push-glasses-apart/06-smolvla-fine-tuned/`. It records demonstrations from
the teacher, fits the correction, and has been scored on the held-out tables.
The examiner provides the straight-down view in `bench/top_view.py` and
carries out a chunk with `Bench.follow()`. Three things are still plans, not
code: **DAgger**, the **second way on π0.5**, and **several training seeds**.
One seed was fitted.

**The measured result is bad: the fitting made the score worse.** The model
learned the height of a push. Its chunks now come down to the push height,
where the borrowed model's never came near the glasses. It did not learn where
to put the jaw down. So **223 of the 369 pushes in its middle run are blocked
on the way down**: the jaw lands on a glass instead of behind it. That leads
to **40 toppled glasses a run** and 36 of 50 tables marked *wrong*. Solution 5
has 12 toppled and 9 wrong. Nothing here stands a glass back up. So a policy
that never reaches a glass scores better than one that reaches the wrong part
of it. [Where it sits among the other five](#where-it-sits-among-the-other-five)
reads this gap in full.

![The examiner places the jaw clear above a chunk's first waypoint and brings it straight down onto that waypoint before carrying out any of the rest, so a first waypoint behind a glass gives a push and a first waypoint over one puts the jaw on the rim, which is reported as blocked and sends it straight back up with nothing pushed; that is where 223 of this solution's 369 pushes in a run end, against none at all for solution 5, which never came down, and from it follow 33 glasses over against 10 and 31 tables wrong against 6, with one more table finished and half again as many glasses racked on the other side of the ledger.](../../images/06-the-jaw-comes-down-on-the-glass.png)

By the end you will know what fine-tuning and low-rank adaptation are. You
will know what the demonstrations cost and what they cap. You will see which
of solution 5's weaknesses the training fixes, and how training on one cell
goes wrong. Last, you will see why a larger model is only a second way here.

## A film of one table

Here is this solution on one table, recorded in the simulator at one and a
half times real speed.

[Watch the film (12 s)](../../videos/06-smolvla-fine-tuned.mp4)

The table is number 10025 of the held-out fifty. All six solutions are filmed
on it. It was chosen to be **typical rather than flattering**, by the rule
[solution 1](01-one-fixed-nudge.md#a-film-of-one-table) gives. It holds six
glasses where the average is five. Five of its six glasses have no room at the
start. Over the fifty tables, 203 of the 251 glasses begin without room.

In the film the jaw comes down to the right height, which the fine-tuning
bought. It also comes down onto a glass, which the fine-tuning did not fix.
Four pushes are made. One glass is racked and one is knocked over, so the
table is marked *wrong*. That is this solution's commonest outcome: 36 of its
fifty tables end that way.

This solution draws its answer at random, so the film is one draw. The scored
runs on this table all ended *wrong*, with six pushes and two glasses racked
on average. `results-tables.json` holds every row.

The hand stays shut while it pushes, and the pick at the end is drawn, not
simulated. [The examiner](../the-examiner.md#what-push-does-and-what-it-reports-back)
explains the drawn pick. [The bench](../../bench/README.md)
explains why the hand is drawn twice. How each solution does over all fifty
tables is in [the comparison](../../results/README.md).

## The code that does the work

Everything shared with [solution 5](05-smolvla-as-it-downloads.md) is imported
from it. What is left is the fitting itself, in two pieces. The first piece
says which parts of the borrowed model the correction may touch. The second
turns a real push into a training example.

The correction is in
[`03-push-glasses-apart/06-smolvla-fine-tuned/correction.py`](../../06-smolvla-fine-tuned/correction.py).
`LoraConfig` and `get_peft_model` come from PEFT, the library that defines the
adapters. LeRobot trains whole policies and has no low-rank adaptation of its
own. The three constants are this project's choice of where the correction
goes.

```python
RANK = 16
SCALING = 32
# The tables the correction is added to: attention's four projections.
TABLES = ("q_proj", "k_proj", "v_proj", "o_proj")

...

def with_correction(policy, rank: int = RANK, scaling: int = SCALING):
    ...
    from peft import LoraConfig, get_peft_model

    policy.model = get_peft_model(
        policy.model,
        LoraConfig(r=rank, lora_alpha=scaling, lora_dropout=0.0, bias="none", target_modules=list(TABLES)),
    )
    return policy
```

The training target is built in
[`03-push-glasses-apart/06-smolvla-fine-tuned/chunks.py`](../../06-smolvla-fine-tuned/chunks.py).
It invents nothing. It cuts the recorded push down to its flat pushing part. It
resamples that to the fixed number of waypoints the model emits. It checks that
the result survives a round trip through solution 5's convention. Then it
writes it in the model's units.

```python
def demonstration(path: tuple[Waypoint, ...]) -> np.ndarray | None:
    ...
    part = pushing_part(path)
    if len(part) < 2 or across(part) < LEAST_ACROSS:
        return None
    waypoints = resampled(part)
    if drift(waypoints) > FAITHFUL:
        return None
    action = as_action(waypoints)
    ...
    return action
```

`TABLES` names the four projections of every attention layer and nothing
else. So the correction can change what the model attends to. It cannot change
the feed-forward tables. `as_action` and `drift` call `to_state` and `to_jaw`,
which are solution 5's own. `partners.py` re-exports them, with solution 5's
`clear` loop. `correction.py` declares `class Fitted(Downloaded)`, so the
asking is inherited too. The targets are therefore in the same units as the
partner's answers, written by the same code.

## The problem this solves

Problem 3 asks for jaw trajectories until every glass has about 76 mm of clear
room, or the rest are refused with a reason. [The problem](../problem.md)
explains why that is hard. The hardest part is friction: nothing in the cell
measures it.

A learned policy deals with that by seeing many pushes and what they did.
Solution 5 borrows a model fitted that way on real robot motion. The question
here is narrower: **having borrowed a policy, what is still wrong with it, and
does training here fix it?**

Solution 5 has three problems, and they have one cause. The model was fitted on
487 datasets of real teleoperation. This cell shows it a rendered view of
opaque glasses on a bare table. So the pictures are unlike anything it saw. Its
actions are on the scale of other robots. And it has never seen what a push
does on this table. [Solution 5's section on the domain
gap](05-smolvla-as-it-downloads.md#the-domain-gap-which-is-the-heart-of-this-document)
explains this in full. Training on pushes made here is the standard fix for
all three.

## The main idea

Keep the borrowed numbers, and learn a small correction to them from pushes
made on the examiner's tables. Three things follow.

**The numbers do not start from nothing.** SmolVLA holds about 450 million
weights. The borrowed weights already know that edges matter and that motion
should be smooth. Training continues from them.

**The pushes are this examiner's pushes.** The model is trained on this
examiner's views and pushes. So at run time it sees the kind of input it was
fitted on. The difference between two kinds of input is the **domain gap**.
Fine-tuning is how a domain gap is closed.

**Only a small part of the model changes.** Every borrowed number stays where
it is. A small correction is learned beside them. That is **low-rank
adaptation**, and it has its own section below.

Everything else is unchanged. The one instruction still carries nothing,
because the task has one instruction. The arm's pose still carries nothing,
because the jaw is parked between actions. The model still commits to a chunk
of fifty waypoints. It still cannot refuse a glass.

## Fine-tuning — continuing somebody else's training

Fine-tuning is the one thing that separates this solution from its partner,
so here it is in plain words.

**Training** shows a network an example, compares its output with the wanted
answer, and nudges every weight a little towards that answer. **Training from
a random start** begins with weights that are noise. **Fine-tuning** begins
with weights that another training run already settled. So the nudges have
much less to do.

Every weight is a number the data has to pin down. A weight the data cannot
pin down gets fitted to accidents in the examples. So the data needed grows
with the number of weights fitted from nothing. With fine-tuning, most weights
already work, and the data only adjusts them. It is like adjusting a
polynomial that already fits a similar curve, instead of finding every
coefficient from nothing.

It also saves time. The early layers of a picture model detect edges and
shading, and those carry over well. A rendered glass on a bare table has a
strong edge. The motion layers know that a path is smooth and that a jaw
approaches before it touches. Those carry over too. Only the later judgement
must change: which glass to push, which way, and how far.

That later judgement carries over worst. It was fitted on other rooms, other
grippers and mostly other tasks. So fine-tuning has more to do here than
usual, but still far less than a random start.
[Solution 3](03-imitation-from-demonstrations.md) tests that from the other
side. It fits a policy from random numbers on the same demonstrations.

## Low-rank adaptation — a small correction instead of a large change

Full fine-tuning moves every weight, which is costly at this size. Low-rank
adaptation is the cheap way, and this solution uses it.

A layer takes a list of numbers in, multiplies it by a table of weights, and
gives a list out. Full fine-tuning changes every number in every table.

**Low-rank adaptation keeps every borrowed number and adds a learned
correction to it.** The correction has the same size as the table. But it must
be the product of two thin tables. The first squeezes the input down to a few
numbers. The second expands them back to full width. So the two thin tables
hold far fewer numbers than the table they correct.

A table can be written as a sum of simple patterns. The number of patterns
needed is its **rank**. The squeeze forces the correction to use only a few
patterns. That is like approximating a curve with the first few terms of a
series.

**The practical gain is memory.** Training must hold each changing weight's
gradient and the optimiser's running averages. Those add up to several times
the model's size. With low-rank adaptation only the correction changes. So
only it carries gradients and optimiser state. Memory is then the model's size
plus a little.

On π0, about 3.3 billion parameters, a low-rank fine-tune needs more than
22 GB of accelerator memory. A full fine-tune needs more than 70 GB. SmolVLA
is about 450 million parameters and uses a few gigabytes at inference. The
training below measured 1.02 GiB, so it ran on this machine with nothing
rented.

**The cost is that it adapts less deeply.** The correction uses only a few
directions in each table. A change that needs the whole table cannot be
expressed. When the new task is near the old one, that costs nothing. This
cell is far from the borrowed data: rendered pictures, one gripper, one motion,
and an outcome no borrowed dataset held. So **the gap this pair measures is a
lower bound on what fine-tuning could buy**. If low-rank fine-tuning buys
little, that does not prove fine-tuning buys little.

After training, the two thin tables can be multiplied out and added into the
borrowed table. The fine-tuned model is then exactly as large and as fast as
the downloaded one. **So this solution and its partner cost the same to run.**

![Every one of the model's 453,859,552 borrowed numbers stays frozen where it is, and a correction forced through a squeeze down to sixteen numbers and back out to full width is added beside the query, key, value and output projections of every attention layer, the feed-forward tables being left alone entirely; that is 3,813,376 numbers, 0.84 per cent of the model, and because only they carry gradients and optimiser state the whole training held 1.02 GiB against the 22 GB the same trick needs on a model seven times the size — and once the two thin tables are folded back in, the fitted model costs 283 ms a push and so does its partner, agreeing to the millisecond.](../../images/06-where-the-correction-goes.png)

## Where the demonstrations come from, and what they cost

The demonstrations are [solution 2](02-geometry-ranked.md)'s pushes on the
training tables, recorded with what was seen beside what was done.
[Solution 3's section on demonstrations](03-imitation-from-demonstrations.md#where-the-demonstrations-come-from)
explains why they are free and what that means. Here the observation is the
view from the top, the one instruction and the arm's pose. The action is the
path the jaw really followed.

**Which tables changed after the main result was measured.** A demonstration
band must stay below the held-out tables. It should also leave out the tables
the teacher was fitted on, because the teacher does best there. The first band
started at table 0. Solution 2 is fitted on tables 0 to 199, so a quarter of
that band was the teacher's own ground. The band now starts at table 1,000 and
holds 5,200 tables. Those are exactly [solution
3](03-imitation-from-demonstrations.md)'s tables, so the two solutions learn
from the same material. [Was it the data?](#was-it-the-data) gives the result
on the new band.

The original band gave, measured: **800 training tables, 19 minutes of
simulator time on this laptop, 1,074 demonstrations from 430 of those
tables.** The teacher made 2,766 pushes. **Most of them are not
demonstrations**: 1,663 were 5 mm test pushes that belong to the shared
tipping check. Of the other 1,103 pushes, **29 were thrown away**: 13 toppled
a glass, 12 jammed, 3 pushed one out of the zone and 1 was blocked coming
down. That is 2.6 per cent.

**On 370 of the 800 tables the teacher found nothing it could push at all.**
With the earlier invented blade, it found something on all but 60. A table the
teacher never pushes on is a table the student never sees. So the real hand
halved the demonstrations by refusing whole tables.

The teacher works from the numbers `look()` gives. The student works from the
picture of the same table. So the student must recover from pixels what its
teacher got as numbers. The jaw's force report arrives after the chunk is
chosen. So it is in the recording, but not in the model's input.

**Its ceiling is solution 2.** This is behaviour cloning, which
[solution 3](03-imitation-from-demonstrations.md#behaviour-cloning--learning-a-policy-by-copying)
explains. Nothing ever shows the policy a better push than the teacher's. So
a win over solution 2 would need explaining.

**Filtering to successes leaves out the teacher's hard cases.**
[Solution 3](03-imitation-from-demonstrations.md#choosing-which-demonstrations-to-keep-and-the-bias-it-buys)
explains this bias. Here it is small: 29 discards. The hard cases are rare
mostly because the teacher seldom meets one. **DAgger** is still the fix,
because it puts the *learner* in states the teacher never visits.
[Solution 3's section on compounding error](03-imitation-from-demonstrations.md#compounding-error)
explains DAgger. It is a plan here, not code.

**What can fine-tuning add beyond its teacher?** Not better pushes. It can add
**robustness where the teacher is brittle**. Where the teacher's choice
between two pushes is nearly arbitrary, averaging over many tables gives a
steadier choice. Where a reading is a few millimetres out, a policy fitted on
real outcomes may still act sensibly. The borrowed weights also add a general
sense of how a push moves, which the teacher's macro does not have.

Both this solution and solution 3 learn from the same demonstrations. So that
pair holds the data still and tests whether borrowed weights are worth having.
This solution is in two pairs, and they ask different questions.

## Whether anything but the training differs

A matched pair is only clean if nothing but the training differs. [Problem
2's own pair](../../../02-segment-glasses/docs/solutions/04-yolo-fine-tuned.md) faced
the same check. There, fine-tuning also replaced the model's category list,
and that document showed the change came with the training. Here the check
must be made again.

Most of the contract is plainly the same. The tables, the readings and their
error, the view from the top, the chunk output, the scorecard and the topple
check are shared. The instruction is the same one sentence. A better-worded
instruction for the fine-tuned model would add a second variable.

**At the output there is something that looks like a second change.** The
model's numbers must be read as waypoints for this jaw.
[Solution 5](05-smolvla-as-it-downloads.md#the-actions-come-out-in-somebody-elses-units)
sets that convention, and **both solutions use it**. The training does not
change the convention. It changes whether the model has learned to speak in
it. Solution 5's numbers are never fitted, so nothing sets their scale. This
solution's targets are real pushes in that convention, so its scale is this
cell's scale. **That is a property of the trained weights, not a second
change.** So **nothing varies between the two that the training did not
bring**.

**One effect of the convention reaches into the physics.** A chunk holds fifty
waypoints. The examiner takes them a fixed period apart, so a chunk is two and
a half seconds of motion. The teacher's push is a hundred waypoints or more,
because it feels forward at 10 mm/s and pushes at 20. Resampling it into a
chunk makes the student's jaw travel about 32 mm/s. So **the student makes
its teacher's pushes faster.** The examiner caps a commanded path at the
jaw's top speed of 200 mm/s. A chunk the model invents can reach that cap.
The other options were to change the model's own chunk length, or to ask the
model several times in one push. The second would spend several pushes from
the budget. Solution 5's chunks are two and a half seconds too, so the pair
stays fair.

**One thing could make the pair unfair.** A careless convention hurts
solution 5 much more, because this solution's training can absorb it. Then the
gap would mix what training bought with what the convention cost. So the
convention is chosen as well as possible, recorded with solution 5, and left
alone.

## What fine-tuning closes, and what it cannot touch

This is the section the pair exists for. It takes solution 5's weaknesses one
at a time and says which the training fixes.

**The domain gap closes.** A model used across a domain gap gives confident,
plausible, wrong answers.
[Solution 5](05-smolvla-as-it-downloads.md#the-domain-gap-which-is-the-heart-of-this-document)
explains that failure.

**The gap was measured.** Before the first training step the correction is
zero, so the model is exactly solution 5. On tuning tables its waypoints were
a median of **331 mm** from the teacher's, and 574 mm at worst. The glass zone
is 320 mm by 360 mm. So the borrowed model's answer is a motion somewhere else
on the table, not a push at the wrong glass.

Fine-tuning closes the gap by construction. The model is fitted on the same
kind of picture it is asked about: pale blue glasses, a tan table, one kind of
glass to a table.

**The scale of the actions is no longer left to chance**, because the targets
are real pushes on this examiner.

**That is two claims, and only one held.** The *height* was learned. Solution
5's chunks come no lower than 217 mm above the table, so its jaw never reaches
the glasses. This solution's chunks come down to 75 mm, which is the push
height. That is the clearest sign that the domain gap closed.

The *length* was not learned. One chunk still covers about 320 mm of table,
where the teacher's covered 78. It moves at about 92 mm/s, where the teacher
pushed at 20. That is better than solution 5's 868 mm, and still about four
times too far. A push four times too long on a crowded table hits a
neighbour. The toppled count in the folder's README comes from that.

![Measured the same way by the same code, the borrowed model's chunks come no lower than 217 mm above the table while the fitted model's come down to 75 mm, which is exactly the height its teacher's pushes were recorded at and the height the gripper pushes at, so the height was learned; the length was not, because one fitted chunk still covers 320 mm of a glass zone that is only 320 mm across, against the teacher's 78 mm, and it travels at 92 mm/s where the teacher's recorded pushes run at 20 and even their resampled chunks at 32.](../../images/06-the-height-was-learned-the-length-was-not.png)

**Something like friction is absorbed.** The examiner uses the same three
friction values on every table. Every demonstration was made under them. So
the policy can learn how far a glass goes for a given push, without any term
for friction. That helps on this examiner and hurts anywhere else. It is a
memorised constant, not a way of measuring one. On a different table it would
be wrong in the direction that topples glasses.

Now the weaknesses that stay.

**The force reading still has nowhere to go.** The model's inputs are a
picture, a sentence and the joint readings. Training cannot add a fourth.
[Solution 5](05-smolvla-as-it-downloads.md#the-force-reading-has-nowhere-to-go)
explains this.

**The instruction is still nearly dead weight.** Every training example has
the same instruction. So nothing stops the model from learning to ignore it.
[Solution 5](05-smolvla-as-it-downloads.md#the-instruction-is-nearly-dead-weight-here)
explains this. The model still pays for language in size and run time.
[Solution 3](03-imitation-from-demonstrations.md)'s ACT policy has no language
part and is far smaller.

**The refusal is still not the policy's.** A policy has no field for a rule.
So the topple check stays where [pushing without
toppling](../pushing-without-toppling.md) puts it, outside all six solutions.
The training set has no glass that must not be pushed, because the teacher
refused those. So the policy proposes pushes on such glasses, and the shared
check stops them. The safety work is done by the geometry in both solutions.

**It still cannot explain a refusal.** Solution 2 can print why a glass tips.
A policy that was stopped has nothing to say. So the reason comes from the
shared check in both solutions.

**A surprise in the middle of a chunk is still carried out.** The model
commits to a whole chunk. Fine-tuning makes surprises rarer. It does not
change what happens when one comes.

**The early abort is not built.** It is a design in [pushing without
toppling](../pushing-without-toppling.md#an-early-abort-acting-during-the-push).
The examiner only stops at a jam. Below that force, `follow()` carries out the
chunk as given. This affects both solutions equally, so the pair stays fair.

**The run-time cost is unchanged.** It is one large forward pass per chunk in
both, because the correction folds into the weights.

**The input's error is unchanged.** Both get readings with problem 2's
measured error. Training can make the policy cope with a slightly wrong
reading. It cannot make the reading right.

## Two ways training on one cell's pushes goes wrong

Fine-tuning is cheap, but it has two named risks.

**Catastrophic forgetting.** Training on a narrow set moves the weights away
from their general answer. The model gets better here and worse elsewhere.
Low-rank adaptation softens this, because the borrowed numbers are never
overwritten. The correction can be removed to get the original back. But the
corrected model is the one that runs, and it would be a poor policy for any
other robot or task. Here that is no loss, because it only ever sees this
examiner's tables. It does mean the correction must be kept in step with the
cell.

**Overfitting.** A model fitted on few examples can learn the examples instead
of the skill. Here it would learn the tables instead of the pushing. The
examiner guards against this in two ways. Table numbers are split, so no
solution is marked on a table it learned from. And demonstrations cost only
simulator time, so the training set can be large.

Longer training closes the domain gap further. It also makes forgetting and
overfitting more likely. So there is a sensible amount of training, and the
held-out tables decide it.

![What was actually spent is one part in 320 of the compute LeRobot's own SmolVLA fine-tune asks for — a thousand steps at a batch of four against twenty thousand at a batch of sixty-four — and it took 47 minutes of this laptop's Metal while 1.02 GiB was held, so memory was never the obstacle at this size and time was; on tuning tables nothing was fitted on, the distance from the teacher's own waypoints fell from 331 mm at step zero, where the correction is still zero and the model is therefore exactly solution 5, to 107 mm at step 500 and 85 mm at the end, and the last of those three steps is inside the noise, because the same distance rose rather than fell in two of the three later fits made on six times the data.](../../images/06-a-thousandth-of-the-recipe.png)

The policy draws its action at random, so the same question can get two
answers. Training also varies with its seed. [The examiner](../the-examiner.md)
asks for several training seeds and several runs, and the scorecard carries
the spread. **This matters most here**, because this document measures a gap.
A gap smaller than either solution's spread has not been shown to exist.

## Was it the data?

Demonstrations here cost only simulator time. So if the model failed for lack
of pushes, that can be measured.

It was measured. Same model, same correction, same thousand steps, same
held-out tables, and **six and a half times as many demonstrations**. Only the
amount of data changed.

There are three columns. The first try at the larger set used the old tables
at the new size. That gives a control: it separates *how much* the student
learns from *where* it learns. The table reads left to right, from the
original band to the matched one. Each cell is the middle value with its
spread.

| | the original band | as much data, wrong band | as much data, matched band |
|---|---|---|---|
| Demonstrations | 1,074 | 6,907 | **6,935** |
| The teacher's own tables inside the band | a quarter of it | a tiny part of it | **none of it** |
| Glasses racked, of 251 | 56 (±7.6) | 52 (±3.8) | 53 (±2.1) |
| Glasses toppled | 40 (±5.6) | 40 (±3.6) | 42 (±3.6) |
| Tables marked wrong, of 50 | 36 (±2.9) | 36 (±2.9) | 36 (±1.5) |
| Pushes that came down onto a glass | 227 (±8.9) | 217 (±32) | 229 (±45) |

**The data was not the problem.** Every difference between the first and last
columns is under two standard errors of the difference. That is this folder's
bar for calling something a change. Most are under one. So "no change was
detected". A small gain could hide in this noise. A large one could not, and
only a large one would matter here.

The later columns come from **three separately trained policies**. The first
column is one policy run three times. So the later columns include the
variation between fits, and they are still no worse. Removing the teacher's
own tables changed nothing either. So the teacher's best ground was not what
held this solution back.

On the wrong band, refusals rose by ten standard errors. On the matched band
they fell back. So that effect came from particular tables and fits, not from
the amount of data. **This is why no number here is quoted without its
spread.**

So the explanation holds, now backed by measurement. The jaw comes down onto
glasses. More demonstrations of good pushes cannot fix that, because the
teacher never comes down onto a glass. A policy learns to recover only by
seeing recoveries. DAgger provides those. Plain behaviour cloning never will.

## A second way: the same fine-tune on a larger model

Would a much larger foundation model do better? That is this solution's second
way.

**The way is the same fine-tune on π0.5.** Same demonstrations, same low-rank
adaptation, same examiner and marking, with a much larger model. The gap
between the two ways would measure what size is worth. LeRobot already
includes π0.5, so it is the same training loop on a different policy. It is
not affordable here, so it stays a plan.

**It would cost a weekend on a rented accelerator, of order a hundred
dollars.** π0 is in the same family, holds about 3.3 billion parameters, and
needs more than 70 GB for a full fine-tune. So no full fine-tune of a model
that size appears here. Low-rank adaptation is the only way to reach it.

**It is a second way because of where mistakes are found.** Most mistakes are
in the pipeline, not the model: the view, the recording format, the action
space, the training length, and the evaluation. Each is found by a failed run.
On SmolVLA, on a laptop, those runs cost nothing. On the large model each
would cost rented hours.

So the order is: make the small model work end to end, measure it against
solution 5, and only then rent. If the small fine-tune buys little, the large
model is the next thing to try. A full fine-tune is the other option, and it
is not affordable here.

## The pushes are what this contributes

**This solution contributes action chunks and nothing else.** [The target
layout](../the-target-layout.md) computes where the glasses should go, for all
six. The topple check and the loop of plan, feel and look again are shared.
This solution emits waypoints, so it never uses the push macro. The examiner
carries the waypoints out as they are.

[The examiner](../the-examiner.md#the-score-is-the-outcome-not-the-action)
scores the table afterwards, not the action. So a three-number push and a
fifty-waypoint chunk are compared fairly. **A difference in the score belongs
to the chunks.** Both this solution and solution 5 contribute only chunks, so
the gap between them is readable.

## How the concepts fit together

A model fitted on other people's teleoperation is downloaded, and its numbers
are kept. Solution 2 runs over the training tables. Each push is recorded with
the view from the top, the instruction and the joint readings. Failed pushes
are dropped. Training fits a small low-rank correction until the model's
chunks look like the teacher's pushes. The correction is then folded into the
weights, so the model keeps its size and speed.

That closes the domain gap and puts the actions on this cell's scale. It does
not give the model new inputs, anything the teacher never did, or anything the
shared machinery owns.
[What fine-tuning closes](#what-fine-tuning-closes-and-what-it-cannot-touch)
takes those one at a time.

## When a glass cannot be pushed safely

[Pushing without toppling](../pushing-without-toppling.md#some-glasses-cannot-be-pushed-at-all)
explains the limit once. The height that counts is the jaw's **top edge** at
107 mm, not the 75 mm its middle rides at. A glass with a narrow enough foot
has no safe height and must be refused with a reason. That marks the run
*correct but incomplete*, not wrong. The check is **arithmetic applied before
any model is consulted** in five of the six solutions.

**Here the two halves of the pair are sure to behave the same.** The same code
reads the same readings. Any difference in refusal counts comes from their
pushes leaving glasses in different places.

The check must sit outside the policy for three reasons. A policy cannot be
told a rule. Its training set has no refusals. And the costs are not equal: a
refused glass can be tried again later, while a toppled glass is finished.

The check needs the friction, and nobody has it. The early abort is **a design
and not code**. So in both solutions, only the limit computed before the jaw
moves protects a glass.

## A worked example

Follow one table through both solutions.

**The table.** Five tapered glasses stand in the glass zone, at different
heights. Two stand as close as the examiner allows, so the narrower one lacks
its 76 mm of room. A third glass stands alone, with a foot so narrow that its
limit is below the jaw's top edge. The readings carry problem 2's error.

**What solution 5 would do.** It sees a kind of picture it has never seen and
returns a smooth chunk on another robot's scale. The chunk may land in open
table, behind the wrong glass, or pointing the wrong way. Nothing in it looks
wrong.

**What this solution would do.** It sees the kind of picture it was trained
on. Its chunk should look like the teacher's push: go behind the crowded
glass, on the line away from its neighbour, come down to the lowest height,
feel forward, and push.

**Where this solution is only as good as its teacher.** Which glass of the
pair to move is the ranker's choice, and here it is nearly arbitrary. The
policy copies what the ranker usually did. It makes the choice more steadily,
not better.

**Where the look-again loop does the work in both.** The pushed glass does not
land where it was aimed. The arm looks again. The fine-tuned policy has seen
many short landings in training, so its next chunk fits that case. Solution 5
has seen none. Neither learns during the run.

**And the case neither can answer.** The shared check finds the narrow-footed
glass's limit below 107 mm. It refuses that glass before either model is
asked. The table is marked *correct but incomplete*.

**But the refused glass stays in the picture.** Neither model can be told to
avoid it. So a chunk whose path runs into it is not carried out. The geometry
can only check the path after the model answers. So each such chunk costs one
of the table's pushes. Both solutions pay this in the same code. Each folder's
`asking.json` counts how often it happened.

So fine-tuning changes the chunk, not the rest. The refusal, the topple limit,
the destinations and the loop stay where they were.

## What it needs

It needs **LeRobot**, which is Apache-2.0, and the SmolVLA weights, which the
library downloads. Do not commit that large file. Read the terms on the
weights, not only the library. A fine-tuned file inherits them. It needs
**PyTorch** for training and for the forward pass.

It needs **the two examiner parts it waited on**, and both exist.
`bench/top_view.py` is a camera 750 mm above the middle of the glass zone,
looking straight down. It returns a 384 by 384 picture of the whole zone. It
is separate from the camera the films use. `Bench.follow()` carries out a
chunk. It takes the waypoints a fixed period apart and reports the same record
as a push. So the scorecard cannot tell which way an action came in. Every
LeRobot policy expects pictures and actions at control rate, so these two parts
were the real price of going off the shelf.

It needs **solution 2 built**, because solution 2 is the teacher. It needs
**simulator time** to record the pushes, and a filter for failed ones. It
needs the **held-out tables**, which the examiner already keeps apart.

**It does not need a rented accelerator. The earlier version of this document
was wrong about that.** Training runs on this Apple Silicon Mac through Metal.
It held **1.02 GiB**, measured while it ran. Only the correction's four
million numbers carry gradients and optimiser state, as
[low-rank adaptation](#low-rank-adaptation--a-small-correction-instead-of-a-large-change)
explains. Memory was never the obstacle.

**Renting would buy time, not memory.** LeRobot's own SmolVLA fine-tune is
twenty thousand steps at a batch of sixty-four. This one ran a thousand at a
batch of four, a small fraction of that compute. **Every number this solution
reports carries that caveat.** A step took about three seconds, on a laptop
that was also training other solutions. Hours of a small rented accelerator
cost of order tens of dollars. A weekend costs of order a hundred. A month
costs of order five hundred. None of it was spent.

[The plan](../solutions-plan.md) allows rented compute in problem 3. **This
solution did not need it.** The second way would: π0 has about 3.3 billion
parameters and a full fine-tune needs more than 70 GB. **The trained model
also runs here**, because SmolVLA uses a few gigabytes at inference.

Once trained, it needs **the correction kept in step with the cell**. Change
the camera, the view from the top, the glass proportions or the teacher, and
the file is out of date. No code test would notice.

## Where it is strong and where it breaks

**It is fitted on the inputs it will be shown.** That is its strongest point.
The domain gap is closed by construction.

**Its demonstrations cost nothing.** The teacher is a program, so nobody has
to teleoperate the task.

**It needs no reward function.** A reward would turn "never topple a glass"
into a price the policy could pay. Learning from correct pushes keeps it a
rule, enforced by the teacher and again by the shared check.

**Its training is affordable, and its run-time cost is its partner's.** The
correction fits in a laptop's memory and folds into the weights.

**It is one half of the cleanest comparison in this folder.** That is a
strength of the arrangement, not of the model.

Against that, four kinds of weakness.

**From the borrowed model.** It is about 450 million parameters, and many
serve a language channel this task does not use. It commits to a chunk. It
cannot explain itself. The correction is low-rank, so it may leave some of
fine-tuning's value unclaimed.

**From its teacher.** Its ceiling is solution 2. It was fitted only on the
teacher's successes. It has seen no refusals, so it proposes pushes on glasses
that must not be pushed.

**From training on one examiner's tables.** It becomes good here and worse
elsewhere. It absorbs this examiner's friction as a constant, which would not
survive a real table. A small training set would teach it the tables. It is
random, so one run is not a measurement.

**What it does not do at all.** It does not refuse, choose destinations, own
the loop, or stop a push going wrong. The shared machinery does all of those.

## The general ideas behind this

Every part of this solution is standard practice. Each idea below says where
it is the right tool and where it is not.

### Transfer learning and fine-tuning

Take a model fitted on a large general task, keep its weights, and continue
training on new data. It works because early layers learn general things, such
as edges, textures, smoothness and approach. Later layers learn the specific
task. Yosinski and colleagues
([arXiv:1411.1792](https://arxiv.org/abs/1411.1792)) showed that transfer gets
worse with depth.

It is right when data for the real task is scarce. It is wrong when data is
free **and** the new task looks nothing like the old one. Then the borrowed
weights bring knowledge of a different world and force a size someone else
chose. This solution sits between the two. [Solution
3](03-imitation-from-demonstrations.md) takes the other side. For more, see
[transfer learning](https://en.wikipedia.org/wiki/Transfer_learning).

### Low-rank adaptation

Add a correction forced through a narrow squeeze, instead of changing every
weight. The method is **LoRA**, by Hu and colleagues
([arXiv:2106.09685](https://arxiv.org/abs/2106.09685)). It is the standard way
to adapt a large model on modest hardware.

It is right when the model is too large to fine-tune fully and the new task is
near the old one. It is limiting when the new task is far away. It buys nothing
when the model is small enough to fine-tune fully for the same money. Here the
model is small and the task is far. That is why the result is a lower bound.

### Behaviour cloning, and its ceiling

[Solution 3](03-imitation-from-demonstrations.md#behaviour-cloning) explains
behaviour cloning, its ceiling and compounding error. Here the expert is a
correct program, which is the case where cloning fits. **DAgger** (Ross,
Gordon and Bagnell, 2011) is the repair, and it is cheap because the expert can
label any state.

### Domain adaptation

Methods that close a **domain gap** are called **domain adaptation**.
Fine-tuning on data from the new domain is the simplest and strongest when
such data exists, as here.

When no such data exists, harder methods are needed. One is **domain
randomisation**: vary the training data so widely that the new domain falls
inside it. It is the usual way to move a policy from a simulator to a real
robot. This solution would need it before reaching a real table, because it
learned one examiner's friction as a number.

### Catastrophic forgetting

A network trained on a new task tends to lose the old one, because the same
weights move. McCloskey and Cohen first described it. The modern fix protects
the weights that mattered most to the old task (Kirkpatrick and colleagues,
[arXiv:1612.00796](https://arxiv.org/abs/1612.00796)).

It matters when a model must stay good at several things. Here the model is
wanted for one examiner only, so its cost is close to zero. Low-rank adaptation
also softens it for free.

### Overfitting and the held-out split

A model can fit accidents in its examples. The defence is to fit on one part of
the data and measure on another. Then any such accident shows as a gap between
the two scores.

It is always right. Its usual problem is scarce data. Here tables are made from
numbers, so more cost only simulator time. For more, see
[overfitting](https://en.wikipedia.org/wiki/Overfitting).

### Action chunking

[Solution 3](03-imitation-from-demonstrations.md#action-chunking-and-why-it-matters)
explains action chunking. It suits smooth contact motions like a push. It
fails where a fast reaction inside the chunk is needed. Here nothing fills that
gap, because the early abort is only a design. The examiner accepts chunks so
that a chunked policy is measured as it is.

## Where it sits among the other five

[The six solutions](overview.md) form a ladder, ordered by how much is fitted
in this cell. This one is at the top, because all of its fitting happens on a
borrowed model.

Against [solution 5](05-smolvla-as-it-downloads.md), only the training
differs. Whatever separates the two scores is what fine-tuning bought. Two
qualifications hold: the correction is low-rank, so the answer is a lower
bound, and the convention must be fair to solution 5. **If this document is
read for one reason, it should be that one.**

**The measurement answers it in an unexpected way.** Training worked, and the
score got worse. The fine-tuned chunks are much closer to the teacher's. The
jaw comes down to the table, where solution 5's never did. But about three
fifths of its pushes are blocked coming down, and 40 glasses a run go over.
Solution 5 stays out of the *wrong* column by never reaching a glass. It
hovers, refuses nearly everything, and ends 9 of fifty tables wrong, against
36 here. So training bought enough skill to act, but not enough to act safely.
**A policy that does nothing scores better than a policy that does the wrong
thing.** The method's verdict is still open. It waits on more training, since
the compute here was about one part in three hundred of the recipe. It also
waits on DAgger, because "the jaw came down on a glass" is a state the teacher
never visits.

Against [solution 3](03-imitation-from-demonstrations.md), the comparison is
borrowing against building. Both learn from the same demonstrations. Solution 3
fits ACT from random numbers, owns every number, and pays nothing for
language. This solution borrows 450 million numbers and adjusts a few. The pair
asks whether general robot knowledge from 487 datasets beats a small model
fitted to this cell.

Against [solution 2](02-geometry-ranked.md), it is the student against the
teacher. Solution 2 explains its refusals and needs no accelerator or borrowed
weights. It is also the ceiling on the pushes this solution copies. A large win
for this solution would be a question about the teacher's ranker.

Against [solution 1](01-one-fixed-nudge.md), it is the most expensive against
the cheapest. Solution 1 computes one push by fixed arithmetic and costs
nothing. If this solution does not beat it by more than its spread, the
450 million parameters and the training bought nothing.

Against [solution 4](04-a-world-model.md), it is reacting against planning.
Solution 4 searches over pushes at run time and can be given a new constraint.
This solution holds its answer in its weights and must be retrained to change.

On the ladder, this solution is the way where all fitting happens on borrowed
weights. Its partner one way below fits nothing. The distance between those
two is the most valuable number this folder can produce.

← [A foundation model as it downloads](05-smolvla-as-it-downloads.md) ·
[The six solutions](overview.md) →
