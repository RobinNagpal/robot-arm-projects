# Solution 5 — a foundation model as it downloads

> **What it uses** — [LeRobot](https://github.com/huggingface/lerobot), a
> library of robot policies, with PyTorch underneath it. From LeRobot it takes
> one borrowed model, **SmolVLA**, exactly as it downloads. SmolVLA has about
> 450 million parameters. It uses a few gigabytes while it answers, and it runs
> on a laptop. Not one number in it is fitted in this cell.
> **What it does** — it shows the model the rendered view of the table from the
> top. It gives the model one plain English instruction and the arm's joint
> readings. Then it carries out the jaw waypoints the model returns. It looks
> at the table again and asks again, until every glass has room or the push
> budget is spent.
> **How the output is produced** — the picture, the instruction and the joint
> readings go in. A run of actions comes out. Those actions are read as jaw
> waypoints, and the examiner carries them out directly, without its push
> macro.
> **How it differs from the other five** — it is the only solution whose
> numbers all come from somewhere else. [Solution 6](06-smolvla-fine-tuned.md)
> is the same model with its training continued on this cell's pushes.
> [Where it sits among the other five](#where-it-sits-among-the-other-five)
> compares all six.
> **What it costs** — no demonstrations, no labels and no training run. It
> needs the library, the downloaded weights and a laptop. The one real cost is
> time per push, because every answer is a pass through a large network.

> **The cell is described once, in [the cell](../../../01-rack-one-glass/docs/the-cell.md)** — the
> layout, the two camera positions, the four sensors, and the words this
> project uses for them. This page covers only what is specific to this
> solution.

## Introduction

This page answers [problem 3](../problem.md) with a downloaded robot model. Nothing is
collected, trained or fitted in this cell. The model sees the table from the
top, gets told in words what to do, and returns actions. Those actions are
carried out.

**This solution is built and has run.** The code is in
`03-push-glasses-apart/05-smolvla-as-it-downloads/`. It runs on the same
held-out tables as the other solutions. Its folder's README holds the
measured numbers. Most of this page was written before the run. Where it says
what would probably happen, that is a prediction, not a measurement. The
captions under the pictures give what was measured. The biggest surprise was
how much depends on the join between the model's actions and this jaw.

There are two reasons to build this solution. First, it is the cheapest thing
in this folder to try: there is nothing to collect and nothing to train.
Second, it was expected to do badly. Its value is not its score. It is the
starting point for [solution 6](06-smolvla-fine-tuned.md), which is the same
model trained further here.

This page covers what kind of model this is, where its skill comes from, and
what is borrowed. It then covers the three places where borrowing hurts: the
units of the actions, the instruction, and the force reading. Last, it covers
the domain gap, which is the main risk.

## A film of one table

Here is this solution on one table, recorded from the simulator at one and a
half times real speed.

[Watch the film (74 s)](../../videos/05-smolvla-as-it-downloads.mp4)

It is table 10025, the same table every solution is filmed on. [Solution 1's
film section](01-one-fixed-nudge.md#a-film-of-one-table) says how that table
was chosen and what the drawn pick and the hand's shell show.

In this film the jaw sweeps across the table sixteen times. It never reaches a
glass, because the model's chunks come back about 200 mm above the table. One
of the six glasses is racked, only because it already had room. This is the
longest and emptiest of the six films. That is the result, not a fault in the
recording.

The model draws its answer, so the film shows one draw. The scored runs on
this table racked one glass each and spent thirteen pushes on average. The
film spent sixteen, so it is a slightly busier draw than the middle one.
`results-tables.json` holds every row.

## The code that does the work

Nothing here is fitted. The only code this project wrote is the join between
the model's output and this cell's jaw. That join turned out to be the whole
solution. The released checkpoint saves its normalisation statistics under
keys the normaliser never looks up. So the normaliser and the un-normaliser
both pass numbers through unchanged. The actions arrive as z-scores, with no
units at all. A scale therefore had to be **chosen**, not converted. The lines
that choose it are the lines to read.

The library does its work in one call, in
[`03-push-glasses-apart/05-smolvla-as-it-downloads/policy.py`](../../05-smolvla-as-it-downloads/policy.py).
`predict_action_chunk` is LeRobot's. `self.pre` and `self.post` are the
processors the checkpoint ships, which do nothing here. `to_jaw` is this
project's.

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
[`03-push-glasses-apart/05-smolvla-as-it-downloads/joining.py`](../../05-smolvla-as-it-downloads/joining.py).
The whole choice is one constant and the four lines that use it.

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

Two things follow. First, the frame of the straight-down picture is the only
thing here that has a size in millimetres and is seen by the model. So
`ACTION_SPAN = 2.0` makes two standard deviations of the output span that
frame exactly. The model can then put the jaw anywhere it can see, and nowhere
it cannot. Second, the examiner uses one waypoint every fixed period. So the
gap between waypoints *is* the speed of the jaw. The same constant sets both
the reach and the speed, and the two cannot be chosen separately.

![Three things go into the borrowed model and only one of them varies: the rendered view from the top changes with every table, while the instruction is the same sentence every time and the jaw's own pose is the same six numbers at all 2,260 asks, because the examiner parks the jaw outside the picture's frame and the reading clips it to the edge of the range; what comes back is fifty waypoints of six numbers whose shipped normalisation statistics are saved under keys the normaliser never looks up, so both the normaliser and the un-normaliser do nothing and the numbers arrive as z-scores with no units in them, which is why four of the six slots have to be read as the jaw's x, y, height and heading by hand and the other two dropped.](../../images/05-the-join-at-both-ends.png)

## The problem this solves

[The problem](../problem.md) asks for jaw trajectories until every glass has
about 76 mm of clear room and nothing has fallen over. [Pushing without
toppling](../pushing-without-toppling.md) explains why this is hard: a push
does not go where it was aimed.

The other solutions each build something for this table: a rule, geometry and
a ranker, a policy, or a model of the table. This solution builds nothing.
Many people have recorded robots pushing and moving things on tables, and
somebody has fitted one model on a large pool of those recordings. So this
solution borrows a method for tables in general. It asks whether the general
method is good enough for this table. That answer is worth having before
anybody spends a week recording demonstrations.

## The main idea

The idea has three steps.

**First, run the downloaded model on the view from the top.** [The
examiner](../the-examiner.md) renders this view: a fixed camera 750 mm above the
middle of the glass zone, looking straight down. It is 384 by 384 pixels of
red-green-blue, and the frame is the same on every table.

**Second, give it the instruction and the joint readings.** The instruction is
one line of plain English, the same every time. It says the glasses are too
close together and should be pushed apart. The joint readings say where the
arm's joints are now.

**Third, carry out what comes back.** The model returns actions. Read as jaw
waypoints, they go straight to the examiner. The jaw follows them, the table
changes, and the model is asked again.

So this solution has no fitted numbers, no hand-written geometry and no
search. It has a download, an instruction and a loop. **Hold on to that**:
nearly every strength and weakness below follows from it.

## A model that sees, is told, and acts

Three things go into this kind of model together:

- **what the camera sees**, as an ordinary picture;
- **an instruction in ordinary words**, such as "push the glasses apart";
- **the robot's joint readings**, so the model knows the arm's current shape.

One thing comes out: **robot actions**. One answer is a short run of targets
for the robot, not a single pose.

A model with these three inputs and this one output is called a
**vision-language-action model**. The name lists the three parts in order. It
is not a perception part that reports what it sees. It is not a controller
that gets a goal in numbers. It takes the raw picture and the sentence, and it
returns movement. Nothing a person wrote sits in between.

This is a different shape from the other learned solutions. In solution 4, a
learned model predicts the table and a separate search chooses. In solution
2, hand-written geometry proposes and a learned ranker chooses. Here one
network does the whole job. That is why one downloaded file can be a complete
answer. It is also why no small piece of it can be fixed when it is wrong.

## Flow matching, and why one run is not enough

SmolVLA has two halves. The first is a vision-language model, which reads the
picture and the words. The second is a smaller **action expert**, which turns
what the first half read into a chunk of 50 actions. An action chunk is a short
run of actions predicted together; [solution
3](03-imitation-from-demonstrations.md#action-chunking-and-why-it-matters)
explains it.

The action expert does not calculate its chunk. It **draws** one, by a method
called **flow matching**. In training, the model sees a real chunk mixed with
random noise. It learns which direction leads from the noisy chunk back
towards the real one. When it answers, it starts from pure noise. It then
takes 10 steps along those directions, and what is left is a chunk. This is
close to the denoising idea that [solution 3's Diffusion
Policy](03-imitation-from-demonstrations.md#the-second-way--diffusion-policy)
explains. The difference is that flow matching learns the direction to move,
not the noise to remove.

One result matters for scoring. **The same table, asked twice, gets two
different answers**, because each answer starts from fresh noise. So one run
is not a measurement. [The
examiner](../the-examiner.md#two-things-this-scorecard-needs-that-problem-2s-did-not)
asks for several runs and a spread for this reason. This solution is scored
over three runs. It trains nothing, so it has no training seed. The noise is
the only thing that changes between runs, and `run.py` seeds it with the run
number. So its spread should be narrower than solution 6's, which also varies
by training seed.

## Where such a model gets its competence

A model that knows nothing of this cell is only worth trying if it knows
something general. That general knowledge comes from **pretraining**: fitting
on very many recorded demonstrations, across many robots and many tasks. In
each recording, a person drove a robot arm through a task. The picture, the
instruction and the joint readings were all recorded together. SmolVLA's pool
is **487 community datasets of real teleoperation**: real robots in real
rooms, driven by real people.

From a pool like that, the model does not learn one task. It learns the
general shape of manipulation. An arm slows as it reaches an object. A gripper
closes when it is on the object. Movement near a surface stays near it. A push
is a contact and then travel in one direction.

**So the model brings a general sense of manipulation, and nothing about this
cell.** It does not know the glass zone, the rack, or that the arm reaches
between 300 and 780 mm from its base. It does not know that a push too high
tips a glass. Those facts are in [the cell](../../../01-rack-one-glass/docs/the-cell.md) and [the
problem](../problem.md), and this model has never seen them.

## What is borrowed, and what is not

**Nothing at all is fitted here.** The weights are used unchanged. There is
no training, no fine-tuning, no small correction and no tuned threshold.

So the model has never seen this cell. It has never seen these four kinds of
glass. It has never seen this jaw: two fingers held closed and level, 30 mm
tall, riding as low as the gripper reaches. It has never seen a table rendered
the way this examiner renders one.

What **is** borrowed is everything else: the architecture, the weights, and
the way pictures, words and actions are read and written. Somebody else fixed
all of these, for other robots. The next three sections show where that
choice hurts.

## The actions come out in somebody else's units

The first problem is at the output. It must be solved before anything can run.

A model fitted on other robots returns actions in those robots' layout and
units. This arm is a UR5e with a two-finger gripper, and the recordings were
made on other arms. So **turning the model's numbers into jaw waypoints is a
reading that somebody has to choose.** The model does not know this arm's
joints, its reach, or what height zero means.

A bad reading would make the model look worse than it is. The score would then
measure the reading, not the model. So the reading is **chosen once and used
by both solution 5 and solution 6**, which keeps the pair clean. It is in
`05-smolvla-as-it-downloads/joining.py`, and the folder's README says what was
decided and why. It was a larger decision than expected. The checkpoint fixes
less about its own action space than this page first assumed.

[The examiner](../the-examiner.md#the-shared-output-and-why-it-is-a-jaw-trajectory)
accepts a run of waypoints directly, without the push macro. That path exists
so that a policy which outputs movement does not have to be squeezed into
three push numbers. This solution uses that path.

![The only object in this solution with both a size in millimetres and a place in the picture is the frame of the straight-down view, 727 mm across on the table top, so two standard deviations of the model's action space are made to span it exactly and anything beyond that clips back onto its edge; because the examiner consumes one waypoint every 50 ms, the same constant also fixes the speed, and the median gap in the model's own chunks works out at 292 mm/s against the 20 mm/s the examiner's own push macro moves at and the 200 mm/s the arm tops out at.](../../images/05-two-sigmas-span-the-frame.png)

## The instruction is nearly dead weight here

The second problem is at the input. It is the one most easily misread.

The language half of the model exists so that **different instructions select
different tasks**. One set of weights can pick a thing up, put it down, or open
a drawer, and the sentence says which. That is a real skill, and it took a lot
of data to learn.

**Problem 3 has one instruction.** It is the same sentence for every table and
every push. An input that never changes carries no information. So here the
language half does no work.

Two things follow. First, **the model is used here as an expensive policy that
maps a picture to movement**. Solution 3 fits that kind of policy from
demonstrations, with a far smaller network. So the extra size here buys only
the pretraining.

Second, **a poor score here says little about vision-language-action models in
general.** It would show that one such model does badly with a fixed
instruction, on pictures unlike its training pictures, with nothing fitted.
The model's main selling point, following different instructions, is never
tested. A single-task cell cannot test it.

## The force reading has nowhere to go

The third problem is a mismatch between what the examiner offers and what the
model can accept.

[The examiner](../the-examiner.md) says the force reading is the most valuable
thing it reports. Nothing in the cell measures friction. The force it took to
start a glass moving, and how far the glass went, are the only evidence of
friction anywhere.

**This model has three inputs, and force is not one of them.** What the jaw
felt during a push has nowhere to go in. That includes being blocked, jamming,
the peak force, and how far the glass moved. So the one channel that observes
friction is closed to this solution.

The solution is not blind. The arm looks again after every push, so the next
picture shows where the glasses ended up. What is lost is what happened
*during* the push. That is what tells a glass that slid from a glass that
leaned and settled back. And this solution learns nothing from any push. It
only sees the new arrangement and answers again.

Solution 6 cannot add a force input either. Its training can only absorb this
examiner's friction into the weights as a constant. [Solution
6](06-smolvla-fine-tuned.md) calls that a weakness away from this examiner,
not a fix.

## The domain gap, which is the heart of this document

Everything above assumes the model works at all on this examiner's pictures.
That is the assumption most likely to fail.

A **domain gap** is the difference between the data a model was fitted on and
the data it is used on. Problem 2 meets the same gap with a borrowed picture
model. [Its solution
3](../../../02-segment-glasses/docs/solutions/03-yolo-zero-shot.md#the-domain-gap-which-is-the-main-risk)
explains the idea and why real glasses look so different from rendered ones.
Here are the two sides of the gap for this model.

**It was fitted on real teleoperation.** That means real cameras, with noise,
blur and real colour. It means real light, with shadows where an object meets
the surface, and highlights that follow a curved surface. It means real
scenes, which are cluttered and full of texture.

**This examiner shows a rendered view, from the top, of pale blue glasses on a
tan table.** The glasses are stacks of cylinders, shaded as solid objects. The
table is a flat rectangle, and nothing else is in the frame. Every glass is
the same colour. There is no clutter, almost no texture, and no transparency.
In a photograph, transparency is the strongest clue that an object is a glass.

So the model sees pictures unlike the ones it learned from, with much of its
usual evidence missing.

**Models usually fail across such a gap without producing nonsense.** They
produce **confident, plausible, wrong actions**: a movement that looks like a
push, aimed somewhere reasonable, at a sensible speed, but not the push this
table needs. That is worse than nonsense, because **nothing downstream looks
wrong.** The waypoints are well formed, the arm does not fault, and the
examiner records a push. The only sign is in the arrangement afterwards.

The direction of those mistakes matters. A push aimed at the wrong place can be
recovered, because the arm looks again and replans. A push that topples a
glass cannot, because nothing in problem 3 stands a glass back up. That is why
[the topple check](#when-a-glass-cannot-be-pushed-safely) is taken out of the
model's hands.

The measured failure was blunter than this prediction. The picture below shows
it.

![Measured, the failure across the gap is blunter than confident wrong pushes: the lowest point of a chunk has a median of 217 mm above the table over 1,855 answers, which is twice the 107 mm at which a push really lands and clear over the top of all but the tallest glass the kind is drawn at, so 506 of one run's 620 pushes never touched anything at all, nothing was ever blocked coming down because nothing ever came down, and 79 of the 114 pushes that did reach a glass jammed.](../../images/05-the-chunks-come-back-high.png)

## The honest expectation

So this solution was expected to do badly. It is better to say so here than to
let the scorecard surprise a reader.

The prediction, made before the run, had three parts. The model should produce
well-formed movement, because that does not depend on reading the scene. It
should sometimes produce a sensible push, because a crowd of upright objects on
a table is a familiar shape. And it should often choose the wrong glass,
direction or distance, because that needs the picture read correctly.

Against [the target layout](../the-target-layout.md)'s yardstick, that means
glasses that land far from the aim, and a total travel many times the
displacement floor. Such a method succeeds by looking again, not by
predicting.

**A poor score is this solution's job.** It is the baseline for solution 6. If
this solution scored well, training would have little room to show anything.

![Put the racking beside the crowding and nothing at all is left over: 48 of the 251 glasses already had their room at the start and exactly 48 were racked, where any solution that freed a glass would have racked more than 48, because racking one loosens its neighbours; one table of the fifty was finished in each of the three runs, 520 of 620 pushes were repeats, and the 36 to 42 glasses a run refused for tipping show that the shared rule holds back about a sixth of them before the model is asked, so what is left to explain the shortfall is the pushes.](../../images/05-nothing-is-left-over.png)

## The price of the model, and why this model

This model is cheap to run, and that is part of why it is tried first.

**It has about 450 million parameters.** It uses a few gigabytes of memory
while it answers, and it runs on a laptop. There is no accelerator to rent.
Nothing is collected or trained. So this is **the cheapest learned solution in
this folder to try**: the whole setup is a download.

What it does cost is time per push. Every answer is a pass through a large
network. That is a different cost from solution 1's arithmetic and from
solution 4's search. The examiner reports time per push for this reason.

**Why not a larger model?** Larger robot models exist, and a bigger one might
close more of the domain gap. The alternative considered was π0, with about
3.3 billion parameters, about seven times the size. The problem is training
it, which [solution 6](06-smolvla-fine-tuned.md) must do. π0's low-rank
fine-tune needs more than 22 GB of accelerator memory, and a full fine-tune
more than 70 GB. A pair is only worth building if both halves can be built.
**SmolVLA is chosen because its fine-tuning is affordable.** π0.5 appears only
as a second way inside solution 6.

## The pushes are what this contributes

[The examiner](../the-examiner.md) fixes what every solution reads and what
it returns, and it scores the table afterwards, not the push. So any
difference in this solution's score belongs to its trajectories.

Two points are specific to this solution. It reads mostly the rendered
picture, because that is what the model takes. And it returns a run of
waypoints directly, not three numbers for the push macro.

Its runs differ only in the noise the model draws from. [Flow
matching](#flow-matching-and-why-one-run-is-not-enough) explains why.

## How the concepts fit together

The model was fitted on a large pool of real teleoperation. Here it is used
unchanged. It sees a rendered view from the top, one fixed sentence and the
joint readings. It returns actions, which a chosen reading turns into jaw
waypoints. The examiner carries them out, and the model is asked again.

The model brings a general sense of manipulation and nothing about this cell.
It has no input for force. A large domain gap lies between its training
pictures and these.

All of this follows from one decision: **fit nothing here**. That makes the
solution free to try. It also removes every way to fix the problems above.
[Solution 6](06-smolvla-fine-tuned.md) uses exactly one of those ways.

## When a glass cannot be pushed safely

[Pushing without toppling](../pushing-without-toppling.md) sets out the topple
limit and the refusal once. It is arithmetic, applied before any model is
asked, in five of the six solutions. Only this solution's own part follows.

**The refusal must be arithmetic here.** The limit depends on a foot width the
camera measures, on this jaw's height, and on a friction nothing in the cell
measures. A model fitted on other robots knows none of these. It cannot learn
them from a picture of plain shapes. Asking it to respect the limit would be
asking it to guess. A toppled glass is the one mistake this problem cannot
recover from.

There is a second half. A refused glass is still in the picture, so the model
can still aim at it. And a model that writes waypoints freely can write a
contact that is too high. **So each trajectory is checked, not trusted.** A
trajectory that would reach a refused glass is thrown away. The heights in the
rest are kept inside the range the jaw rides at. Both checks are in this
solution's own folder, not in the examiner.

## A worked example

Here is one crowded table, step by step.

Five tapered glasses stand in the glass zone. Two stand very close together,
as [the examiner](../the-examiner.md) places them on purpose. A third is
crowded by accident. Two are clear. One of the close pair has a narrow foot,
so its topple limit is the tightest on the table.

**The shared check runs first.** It finds that the narrow-footed glass would
tip before it slides, and refuses it with its reason. Four glasses remain for
the model. The picture still shows all five, so a push aimed at the refused
glass is thrown away. The crowding around that glass can no longer be solved,
and that is a correct outcome.

**Then the model is asked.** It gets the picture, the fixed sentence and the
joint readings. The prediction was a well-formed push: smooth, at a sensible
speed, down and then across. Whether it is the right push is the doubt. It
may pick the wrong glass, because every glass is the same colour and there
are no shadows to show which pair is tight. It may push a glass out of one
crowd into another. Or it may push too far or too little, because it does not
know this table's clearances.

**Then the arm looks again.** The model is asked again from the new
arrangement. A wrong push is not fatal, only wasteful: it costs one push from
the budget. Repeated often, that leaves a clear mark on the scorecard: many
pushes, a lot of travel, and few tables finished.

What the run would *not* contain matters too. There is no crash, no fault, and
no number marked as doubtful. Every push looks like a push. So this result
must be read against solution 6's, not on its own.

## What it needs

Less than anything else in this folder.

**Software.** [LeRobot](https://github.com/huggingface/lerobot) (Apache-2.0)
and PyTorch (BSD-3-Clause). Both are permissive licences, so neither changes
this project's terms. [The implementation
notes](../../../01-rack-one-glass/implementation-notes.md) explain why a copyleft licence would.
The weights carry their own terms, which this project does not record. Check
them before shipping anything. A licence on weights is not the same as a
licence on the library that loads them. A fine-tuned file, as [solution
6](06-smolvla-fine-tuned.md) makes, inherits the weights' terms. This solution
makes no new file.

**The weights.** Downloaded and used unchanged: about 450 million parameters.

**Hardware.** A laptop. This page once said solution 6 would need a rented
accelerator. That was wrong: [solution 6](06-smolvla-fine-tuned.md)'s
low-rank fine-tune of this model used **1.02 GiB** on this machine's own
Metal. The 22 GB and 70 GB figures above belong to π0. Renting would only make
sense to run the evaluations faster. For scale, renting an accelerator for a
weekend costs about a hundred dollars, and a small one for a month about five
hundred.

**Data.** None.

**What the examiner had to add.** The rendered view from the top, and the path
that accepts waypoints without the push macro. [The
examiner](../the-examiner.md) now has both. Solutions 3 and 6 use them too.

## Where it is strong and where it breaks

Its strengths all come from fitting nothing. There is nothing to collect,
train or keep in step with the cell. It needs no accelerator. It shows what a
borrowed robot model is worth before anyone spends a week recording pushes. No
solution can be cheaper to set up. And it is the clean half of the 5 and 6
pair, which holds even if it scores badly.

Its weaknesses are the four problems above: [the units of the
actions](#the-actions-come-out-in-somebody-elses-units), [the idle
instruction](#the-instruction-is-nearly-dead-weight-here), [the missing force
input](#the-force-reading-has-nowhere-to-go) and [the domain
gap](#the-domain-gap-which-is-the-heart-of-this-document). And it cannot do
anything that needs fitting. It cannot learn from a bad push, be corrected on
the glass it handles worst, or have a threshold tuned. The one fix for all of
that is more training on this cell's pushes. That is solution 6.

So this is among the first things to run, and unlikely to be the one kept.
Its value is the comparison it makes possible.

## The general ideas behind this

Five named ideas sit under this solution.

### Robot foundation models — one model pretrained for manipulation in general

A **foundation model** is fitted once on a very large, broad pool of data, and
then used for tasks nobody planned. [Problem 2's solution
5](../../../02-segment-glasses/docs/solutions/05-sam2-with-a-keeper.md#what-a-foundation-model-is)
explains the idea. The robot version pools demonstrations from many different
robots. This is called **cross-embodiment** pretraining.
[LeRobot](https://github.com/huggingface/lerobot) carries several, among them
π0, π0.5, GR00T N1.7 and SmolVLA.

It is usually right when your task looks like the pool and your own data is
scarce. It is usually wrong when your input does not look like the pool's, or
when the task needs an input the model lacks. Both are true here. It is also
wrong when a few lines of geometry would do, as [solution
2](02-geometry-ranked.md) shows.

### Zero-shot transfer — using a model on a task it was never fitted for

A model is used **zero-shot** when it gets no examples of the new task. [Problem
2's solution
3](../../../02-segment-glasses/docs/solutions/03-yolo-zero-shot.md#zero-shot-transfer--using-a-model-on-a-task-it-was-never-fitted-for)
explains when that works. The usual fix, when the input looks different, is to
continue training on your own data. That is [solution
6](06-smolvla-fine-tuned.md).

### Language conditioning — the sentence that selects the task

An instruction in words lets one set of weights serve many tasks. That is the
"language" in the model's name. It helps when there are many tasks that a
sentence can tell apart. With one task, as here, it does nothing. So this cell
says nothing about language conditioning in general.

### Action chunking — predicting a run of movement rather than one step

These policies return a short run of actions at once. [Solution
3](03-imitation-from-demonstrations.md#action-chunking-and-why-it-matters)
explains it. Here it matters because the examiner therefore accepts a run of
waypoints directly. A chunk cannot react inside itself. [The early
abort](../pushing-without-toppling.md) covers that gap for every solution.

### The domain gap, and the honest reading of a failure across one

The domain gap is the most common reason a borrowed model disappoints. Its
usual sign is confident wrong output, not nonsense.

Decide which side of the gap you will move before you measure. Moving the
model is fine-tuning, which is solution 6. Moving the data means making the
rendered pictures look real, which no solution here attempts. Do not conclude
that a method is poor when you have only measured the gap. Solutions 5 and 6
are written as a pair to prevent that mistake.

## Where it sits among the other five

The useful way to see all six is **where their numbers came from**. [Solution
1](01-one-fixed-nudge.md) has no fitted numbers; it is arithmetic and the
floor. [Solution 2](02-geometry-ranked.md) writes the candidates by hand and
fits only the ranker. [Solution 3](03-imitation-from-demonstrations.md) fits a
whole policy on demonstrations recorded here. [Solution
4](04-a-world-model.md) fits a model of the table here and searches through it
at run time. This solution is the only one whose numbers all came from
**somewhere else**. [Solution 6](06-smolvla-fine-tuned.md) is the same numbers
with this cell's pushes added. [The overview](overview.md) maps all six.

The 5 and 6 pair is the sharpest comparison in the folder. **Solution 6 is
this same model, library and weights, trained further on this cell's own
pushes, on the same examiner.** The input, the output, the scoring, the
reading of the actions and the topple check are all held still. Only the
training differs. So the gap between their scores measures what the training
bought, and nothing else. One limit applies, and solution 6 explains it: its
training uses a low-rank correction, not every weight. So the gap is a lower
bound on what fine-tuning could buy.

That is why this solution is worth building even though it was expected to do
badly. A poor score here gives solution 6 room to show what training buys. It
is the measurement working.

← [A world model, then plan with it](04-a-world-model.md) · [The same model,
fine-tuned here](06-smolvla-fine-tuned.md) →
