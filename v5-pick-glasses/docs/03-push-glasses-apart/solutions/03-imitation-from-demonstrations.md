# Solution 3 — imitation from demonstrations

> **What it uses** — [LeRobot](https://github.com/huggingface/lerobot), which
> holds reference implementations of this whole family of policies, with
> PyTorch underneath. No rented accelerator: this one fitted on the machine
> the project is written on, an Apple M4 with no NVIDIA card. The model
> is **ACT**, an action chunking transformer: it predicts a short run of future
> actions in one go rather than one action at a time. A second rung uses
> **Diffusion Policy**, also in LeRobot, which reaches the same kind of answer
> by starting from noise and denoising towards an action chunk. Nothing is
> downloaded except the library: both models are fitted here, from random
> numbers, on demonstrations produced inside this project.
> **What it does** — the arm is shown what a good push looks like, many times
> over, and a network is trained to copy it. The demonstrations come from
> [solution 2](02-geometry-ranked.md), which generates legal candidate pushes
> and ranks them, so they cost nothing but arm time on the examiner's tables. The trained
> policy then maps what the camera sees straight to a short run of jaw
> waypoints, with no geometry, no friction model and no candidate list
> anywhere inside it. Nobody writes down how to push a glass; the examples
> carry that, and the fitting extracts it.
> **How the output is produced** — a view of the table from the top goes in.
> The policy returns an **action chunk**: a short run of consecutive jaw
> waypoints, predicted together in one pass. The examiner carries those waypoints
> out directly, because there is nothing to expand — a chunk is already a jaw
> trajectory. The arm then looks again, and the fresh picture is the next
> input. One push is one chunk, and the loop runs until every glass has room,
> or the glasses that are left have been refused, or the push budget is spent.
> **How it differs from the other five** — [solution
> 1](01-one-fixed-nudge.md) fits nothing and pushes a fixed fraction of the
> room a glass is short of, which is the floor this has to clear. [Solution
> 2](02-geometry-ranked.md) writes the geometry by hand and fits only a ranker
> over the candidates that geometry produces, and it is this solution's
> teacher, which makes the pair a reading of how close a student gets to the
> program it copied. [Solution 4](04-a-world-model.md) learns how the world
> changes and searches over actions at run time, so it can find a push nobody
> ever demonstrated, and pays for the search on every push. [Solution
> 5](05-smolvla-as-it-downloads.md) runs a large borrowed policy exactly as it
> downloads, with no fitting here at all. [Solution
> 6](06-smolvla-fine-tuned.md) continues that borrowed policy's training on
> this cell's own data, which is this solution's method applied to somebody
> else's weights instead of to random ones.
> **What it costs** — the demonstrations are free in money and cheap in time,
> because the teacher is a program and the tables are simulated, so the whole
> dataset is arm time on the examiner's tables rather than human hours at a teleoperation
> rig. Training runs in hours — on this machine's own graphics processor, as
> it turned out, so the rental this document first budgeted for was not
> needed. The licence position is as simple as it gets here:
> LeRobot is Apache-2.0, which is the permissive kind of licence [the
> implementation notes](../../../implementation-notes.md) record for
> everything else this project depends on, and because no borrowed weights
> are used, the weights file this solution produces inherits no terms from
> anybody. The real price is paid elsewhere, in two parts named plainly below:
> the policy cannot be much better than its teacher, and it asks two things of
> the examiner that a push-parameter solution never needs: the table seen from
> straight above, and a path given as waypoints rather than as a push.

> **The cell is described once, in [the cell](../../the-cell.md)** — the
> layout, the two places the camera works from, from the top and from the
> side, all four sensors, and the words this project uses them with. What
> follows is only what is specific to this solution.

## Introduction

This document explains how to answer problem 3 by showing the arm examples of
good pushes and training a model to copy them. The method has a name,
**behaviour cloning**, and it is the plainest kind of learning there is: no
reward, no exploration, no physics, only a large table of situations and the
action somebody took in each one. The model that does the copying is ACT, an
action chunking transformer, taken from LeRobot, and a second rung replaces it
with Diffusion Policy, which arrives at the same kind of answer by a different
route.

**This is built, and it is worth being exact about which parts.** [The test
examiner](../the-examiner.md) is built, the programmed geometry that picks a landing
spot for one glass at a time is built, and so is the ranker that turns that
geometry into [solution 2](02-geometry-ranked.md), which is this solution's
teacher. The two things the examiner was missing are built as well: the
straight-down rendered view this policy reads, as `bench/top_view.py`, and the
path that carries out a chunk of waypoints, as `Bench.follow`. ACT has been
fitted here, from random numbers, on demonstrations recorded off solution 2's
own pushes, and run over the held-out tables. The code is in
`03-push-glasses-apart/03-imitation-from-demonstrations/` and the numbers it
scored are in that folder's `README.md`, not here: this document is the
design, and a measurement quoted in two places drifts.

Three things below are still prescriptions rather than code, and each says so
where it appears: the DAgger round, the force monitor that would watch a chunk
while it runs, and deliberately over-representing the crowded corner cases in
the demonstration set.

The reason this solution is worth writing out in full is that it is the
cheapest way of asking a question the other five cannot ask. Solution 2 is a
program that chooses pushes well. If a network trained only to copy that
program comes close to it, then the mapping from a picture of a crowded table
to a good push is learnable, and the remaining error belongs to the teacher
rather than to the idea. If the student falls a long way short, that is
evidence about the policy class itself, and it is evidence gathered before any
of the expensive solutions is attempted.

By the end of this document you will understand what behaviour cloning is, why
it is unusually attractive in this cell and where it is fragile; where the
demonstrations come from and why they cost almost nothing; what an action chunk
is and why committing to a short run of actions beats re-deciding at every
instant; what a denoising policy adds when more than one push would have been
good; what compounding error is, why it is the characteristic failure of
copying, and what in this problem's own loop blunts it; and the three honest
costs this solution carries, none of which can be engineered away.

## The code at the heart of it

This solution lives or dies on one join. A demonstration is the path the jaw
really followed, written down waypoint by waypoint by the examiner; a policy's
answer is an **action chunk**, a block of numbers of fixed shape. The code that
turns the first into something the model can be fitted on, and turns the model's
answer back into waypoints the examiner will carry out, is this solution's own
contribution, and beside it sits the single call that reaches into the borrowed
library.

The conversion is in
[`03-push-glasses-apart/03-imitation-from-demonstrations/chunks.py`](../../../03-push-glasses-apart/03-imitation-from-demonstrations/chunks.py),
which holds no model and no geometry of pushing. `push_segment` keeps the part
of a recorded path at push height, from where the jaw started travelling across
the table to the furthest point it reached, and drops the descent, the back-off
and the lift, because the examiner does all three itself. `to_action` then writes
what is left as the five columns the policy is fitted on. The way back is the
same file's `to_waypoints`, which turns the cosine-and-sine pair into an angle
again and pulls every waypoint inside what the jaw can reach:

```python
def push_segment(waypoints: tuple[Waypoint, ...]) -> tuple[Waypoint, ...]:
    """The feeling-and-pushing part of a recorded path, with the back-off and lift off.
    ...
    """
    low = [i for i, point in enumerate(waypoints) if point.z <= PUSH_HEIGHT + AT_PUSH_HEIGHT]
    ...
    start, end = low[0], low[-1]
    origin = waypoints[start]
    gone = [math.dist((p.x, p.y), (origin.x, origin.y)) for p in waypoints[start : end + 1]]
    furthest = start + int(np.argmax(gone))
    return tuple(waypoints[start : furthest + 1]) if furthest > start else ()

def to_action(waypoints: tuple[Waypoint, ...]) -> np.ndarray:
    """A run of waypoints as the (n, 5) numbers a policy is fitted on."""
    return np.array(
        [[p.x, p.y, p.z, math.cos(p.heading), math.sin(p.heading)] for p in waypoints],
        dtype=np.float32,
    )
```

The borrowed model is reached in one place, in
[`03-push-glasses-apart/03-imitation-from-demonstrations/policy.py`](../../../03-push-glasses-apart/03-imitation-from-demonstrations/policy.py):
one call that builds LeRobot's ACT, and one that asks it for a chunk.

```python
    if kind == "act":
        from lerobot.policies.act.configuration_act import ACTConfig
        from lerobot.policies.act.modeling_act import ACTPolicy

        return ACTPolicy(
            ACTConfig(
                input_features=inputs,
                output_features=outputs,
                chunk_size=chunk,
                n_action_steps=chunk,
                pretrained_backbone_weights=None,
                normalization_mapping=_UNTOUCHED,
                push_to_hub=False,
            )
        )
...
    def chunk(self, picture: np.ndarray) -> np.ndarray:
        """One action chunk from one picture: (chunk, 5) in the table's own units."""
        self.net.eval()
        with torch.no_grad():
            answer = self.net.predict_action_chunk(self.batch(picture))
        return self.scale.back(answer[0].float().cpu().numpy())
```

Three of those settings are the whole of what this folder insists on against
LeRobot's own defaults: `pretrained_backbone_weights=None`, which switches off
the ImageNet weights ACT would otherwise download for its vision backbone and
is what makes "fitted from random numbers" true; `normalization_mapping`, which
hands the scaling back to this folder's own code so that the numbers reaching
the model are only ones written here; and `n_action_steps` set to the chunk's
full length, because one push is one chunk and nothing re-plans part way
through. The rest of the model is LeRobot's, untouched.

Reading the two blocks together says where the measured shortfall has to sit,
and it does sit there. The first two columns of the chunk come out roughly
right — the policy puts the fingertips down in about the neighbourhood the
teacher used — while the heading carried in the last two comes out about thirty
degrees away from the teacher's, which is enough that on a crowded table the
jaw meets a neighbour while it is still coming down, and the push ends before
any glass is touched.

## The problem this solves

[The problem](../problem.md) asks for a jaw trajectory, and then another, until
every glass has about 70 mm of clear room in every direction or the glasses
that are left have been refused with a reason. So the thing to be produced is a
function: from the arrangement of a crowded table, to a motion of the jaw.

That function is hard to write down, and [pushing without
toppling](../pushing-without-toppling.md) says exactly why. The relation
between a push and the slide it produces runs through the friction coefficient
between the glass and the table, **nothing in this cell measures friction**,
and the examiner never tells any solution what it is. On top of that, the contact
between a flat jaw and a curved glass is a small patch rather than a point, and
a pushed glass turns as well as travels. Planar pushing is a well studied
problem and the honest summary is that predicting an outcome precisely needs
numbers nobody here has.

Solution 2 answers that difficulty by not predicting much. It enumerates pushes
that are legal by construction, scores each one, and takes the best. That works,
and it has a price that is easy to overlook: somebody has to write the
enumeration, choose which features the ranker sees, and keep both in step with
the cell. Every one of those choices is a place where a person's model of
pushing enters the method, and a person's model of pushing is the thing that is
known to be incomplete.

**This solution attacks the same difficulty from the other end.** Nobody can
write the function from a crowded table to a good push. But an examiner can tell
afterwards whether a push was good, because [the examiner](../the-examiner.md)
marks the outcome and not the action. So good pushes can be collected even
though they cannot be derived, and a network can be fitted to the collection.
The function is not written; it is measured into existence.

Two further things follow from doing it this way, and they are what make this
solution different in kind from its teacher rather than merely cheaper.

**The policy learns the motion, not only the choice.** Solution 2 emits a
parameterised push — which glass, where to put the jaw down, which way to
point, how far to feel, how far to push — and [the test
examiner](../the-examiner.md) owns the macro that expands those numbers into a
descent, a feel, a slide, a back-off and a lift. Every parameterised push is
expanded the same way. A policy that emits waypoints is not limited to motions
that macro can express. It can slow where a neighbour is close, lean the slide
away from a glass it is passing, or stop short of the distance it set out to
cover. Whether any of that helps is exactly the sort of thing this folder
exists to measure, but the freedom is real and only the trajectory solutions
have it.

**The policy reads the picture.** Solution 2 works from the numeric readings
`look()` returns. A policy of this family takes an image, and the examiner hands
one over for that reason. An image holds things the readings do not: the shape
of the gap between two glasses, how a third glass sits behind them, where the
edge of the glass zone is relative to all of it. None of that is in a list of
positions and widths, and none of it has to be named in advance for a network
to use it.

## The main idea

The idea is one sentence long: **run solution 2 over the training tables, keep
the pushes that worked, and fit a network that maps the picture of the table to
the next short run of jaw waypoints.**

Three things follow from that sentence, and the rest of this document is those
three things.

**The teacher is a program.** The demonstrations are not recorded from a person
driving the arm. They are produced by another one of the six, which generates
candidate pushes and ranks them, running on the same examiner, on tables drawn
from numbers below the dividing line that separates training from testing. That
single fact changes almost everything about the economics of this method, and
the next section is about it.

**The answer is a chunk, not an action.** The policy does not return one target
and wait to be asked again. It returns a short run of consecutive waypoints,
predicted together. This is not a convenience. It is the mechanism that keeps
the motion committed, and the section on action chunking explains why a push in
particular needs that.

**The loop is unchanged.** [Pushing without
toppling](../pushing-without-toppling.md) describes the loop every solution
here runs: plan, feel, look again. This solution replaces the planning step and
nothing else. The arm still feels its way to contact rather than driving to a
computed point, still looks again afterwards, and still refuses a glass it
cannot push safely. That the loop stays is what makes copying survivable at
all, for a reason the section on compounding error gives.

## Behaviour cloning — learning a policy by copying

Because behaviour cloning is the whole of this solution, it is worth setting
out carefully and in plain words before anything is built on it.

A **policy** is a function from what the arm can see to what the arm should do.
**Behaviour cloning** is fitting that function from examples of somebody else
doing the job. Each example is a pair: what was seen at some moment, and what
the demonstrator did at that moment. The first half of the pair is the input,
the second half is the label, and fitting proceeds exactly as it would for any
other supervised problem — show an example, compare what the network produced
against what the demonstrator did, and nudge every weight a little in the
direction that would have closed the gap.

The programming comparison is a close one. Behaviour cloning is fitting a
lookup table that was given to you, and then being asked to answer queries that
are not in it. The table holds situations and the right answer for each. The
network is a compressed, smooth stand-in for the table, and the whole hope of
the method is that smoothness between the entries is a good guess at what
belongs there.

Three things make this attractive here, and all three are things the method does
not have to do.

**There is no reward to design.** Reinforcement learning needs a number that
says how good an outcome was, and writing such a number is its own difficulty,
because a learner optimises what the number says rather than what the number was
meant to say. A number that rewards moving glasses apart quickly rewards
shoving. A number that punishes toppling heavily teaches the arm to stop
touching anything. Behaviour cloning never needs one. The label is the action,
and the only thing being measured during training is how far the network's
action was from the demonstrator's.

**There is no exploration.** A learner that discovers by trying has to try bad
things, and in this problem one class of bad thing cannot be undone: **nothing
in this project stands a toppled glass back up.** A method that learns by
knocking glasses over until it stops is learning at a cost the arrangement
cannot absorb. Behaviour cloning never tries anything during training. It only
reads.

**There is no physics to model.** Friction does not appear anywhere in this
method. Not as a constant, not as a guess, not as a quantity to be estimated.
The demonstrations were produced in a world with friction in it, so the
consequences of friction are in the data, and the network learns whatever of
them it can use without ever representing the number. Compare that with
[solution 4](04-a-world-model.md), whose whole business is learning how the
world changes and planning through it. This solution does not predict what a
push will do. It only predicts what the teacher would have done.

Against those three, one fragility, and it is the only one that matters because
everything else about this method follows from it.

**A cloned policy only knows situations the demonstrator visited.** The fitted
function was determined by the examples, and the examples cover a region of its
input. Inside that region, smoothness between examples is a reasonable guess.
Outside it, the network still returns an answer — a network always returns an
answer — and that answer is an extrapolation with nothing behind it. Worse,
**nothing in the output says which case you are in.** The policy emits a chunk
of waypoints either way, with the same confidence, because it has no way of
expressing doubt. A method whose mistakes announce themselves can be guarded;
this one's do not.

## Where the demonstrations come from

Behaviour cloning needs examples, and in most of robotics that is the sentence
that kills it. Here it is almost free, and it is worth being clear about why,
because the judgement of whether this method is worth its price depends on it.

**The teacher is [solution 2](02-geometry-ranked.md).** That solution generates
candidate pushes from geometry — pushes that are legal by construction, aimed
at destinations [the target layout](../the-target-layout.md) computed — and
ranks them with a fitted model, taking the best. Run it on a table and it
produces a push. Run it on many tables and it produces many pushes. Each one is
carried out by the examiner, which expands the parameterised push into the
waypoints the jaw actually followed, and marks what happened to the table
afterwards. So **every push solution 2 makes is a finished demonstration
already**: a picture of the table before it, the waypoints that were followed,
and the examiner's own verdict on whether it worked.

![One real training table seen from the top with the push the teacher chose on it, the path the jaw really followed written down waypoint by waypoint at half a millimetre apart while feeling and a millimetre apart while pushing, and the counts for the whole set: 22,846 pushes on 5,200 tables of which 12,656 were kept, where almost everything dropped is the teacher's own 5 mm test push rather than a failure.](../../../images/03-push-glasses-apart/03-where-the-demonstrations-come-from.png)

Five consequences follow, and they are the reason [the
plan](../solutions-plan.md) says that supplying demonstrations is what earns
solution 2 its place beyond being a baseline.

**The cost is arm time on a simulated examiner, and nothing else.** There is no
teleoperation rig, no operator, no scheduling of a person's hours, and no
agreement to be reached about what a good push looks like. The examiner is
MuJoCo, which is fast for exactly this reason, and [the test
examiner](../the-examiner.md) records that a learned approach needs thousands of
pushes while Gazebo would run each one at the speed of real time.

**The demonstrations are reproducible.** Every table comes from a single
number, so the same number always gives the same table, and the dataset can be
regenerated rather than archived. This is not a small thing. A demonstration
set recorded from a person is a one-off artefact that can never be made again;
this one is a function of a list of numbers.

**Training and testing cannot be confused.** The examiner's table numbers are
split, with numbers above a fixed dividing line reserved for testing.
Demonstrations are drawn only from below it, so no policy here is ever marked
on a table it learned from.

**The teacher can be asked again, at any state.** A person who demonstrated a
hundred pushes last week cannot be asked what they would have done on a table
that came up today. A program can, every time, for nothing. This is the single
most useful property of a programmed teacher, and the section on compounding
error is where it is spent.

**And the teacher is itself one of the six.** So the comparison between
solution 2 and this solution is not two methods against each other but a
student against the program it copied, measured on the same tables with the
same scorecard. That is a rare and clean reading, and [the
plan](../solutions-plan.md) builds it in deliberately.

One honest qualification belongs with all of that. **This is a privilege of
working in a simulator with a programmed teacher.** On a real arm with a human
demonstrator, collecting demonstrations is the dominant cost of the whole
method, and usually the thing that decides whether it is affordable. Any
judgement made here about whether imitation is worth its price should carry
that qualification with it.

## Choosing which demonstrations to keep, and the bias it buys

Free demonstrations are not the same as a good demonstration set, and the
choice of which pushes to keep is the place where this solution's second honest
cost enters.

Start with why any filtering happens at all. **A cloned policy copies
everything in its data.** It has no notion of a good action and a bad one; it
has only a label to reproduce. If the set holds a push that toppled a glass,
that push is a label like any other, and the fitting moves the weights towards
producing it. Solution 2 is not perfect — no solution here is — so some of its
pushes topple a glass, push one out of the glass zone, or jam. Keeping those
teaches the student to make them. So the set is filtered by the examiner's own
verdict, and only the pushes that worked are kept.

That is clearly right, and it has a consequence that is clearly uncomfortable.

**Filtering by outcome does not only change which actions are recommended. It
changes which situations are covered.** Suppose there is a kind of table
solution 2 handles badly — glasses crowded in a corner of the glass zone, say,
where the legal destinations are few and the teacher's candidates are poor.
Most of the teacher's pushes on such tables fail, so most of them are dropped,
so the training set holds few examples of that kind of table. The student is
therefore fitted most densely on the situations where the teacher was already
strong, and thinly or not at all on the situations where help was most needed.
**The filtering removes the examples exactly where the examples would have been
most valuable.**

Said in the language of the previous section: conditioning the dataset on
success biases the input distribution as well as the labels, and it biases it
towards the teacher's own competence. So this solution's picture of problem 3
is solution 2's picture of problem 3, with solution 2's blind spots deepened
rather than merely copied.

Three things can be done about it. Two are now code and the third is still a
prescription.

**Keep the teacher's refusals, as refusals.** A glass solution 2 declined to
push is not a failure and should not be dropped as one; [pushing without
toppling](../pushing-without-toppling.md) is explicit that a refusal is a
result. A dataset that silently omits those tables teaches the student nothing
about them, and silence in a dataset is not a label. **Done**: the refusals
and their reasons are counted beside the demonstrations.

**Record what the filtering removed, broken down by table.** The thinning is
invisible unless it is counted. A table of kept and dropped pushes, grouped by
the kind of table and by the way the dropped ones failed, says where the
student's coverage is thin before the student is ever run. **Done**: the
collection writes exactly that table, and the first thing it says is that on
these tables the teacher is clean enough that the thinning is small — far
smaller than this section assumed when it was written.

**Weight the hard tables up, and gather more of them.** Because tables are
drawn from numbers and cost only time, a thin region can be filled by drawing
more tables of that kind rather than by accepting the thinness. That is the
cheapest defence available here and it is unavailable on real hardware.
**Not done**: the demonstration set is drawn from consecutive table numbers,
so it holds whatever mixture the examiner produces.

None of the three removes the problem. The ceiling stays where the next
sections put it.

## Action chunking, and why it matters

The policy's output is the second thing that defines this solution, and the
word for it is the one in ACT's own name.

**Action chunking** means predicting a short run of future actions in one go,
rather than one action at a time. Ask the network once and it returns a
sequence: this waypoint, then this one, then this one, several of them,
produced together in a single pass. The arm then carries out that whole
sequence before anything is asked again.

![A parameterised push drawn from the side as the examiner's macro expands it — down at 10 mm a waypoint, feeling at 0.5 mm, pushing at 1 mm, backing off and lifting — against the chunk the policy emits, a fixed block of 120 waypoints by five columns predicted in one pass, with the teacher's own pushes running from 25 to 246 waypoints and every one of them resampled to that fixed 120.](../../../images/03-push-glasses-apart/03-a-chunk-is-not-a-push.png)

The programming comparison is exact and it is worth stating plainly, because
the difference sounds smaller than it is. One way to write a controller is a
function called on every tick that returns the single next thing to do; the
plan exists only as whatever that function happens to decide each time. The
other way is a function called once that returns a few steps of a plan, which
are then carried out. The second **commits**. It cannot change its mind partway
through, and that is both what it costs and what it buys.

Here is the reason committing helps, and it is specific to pushing rather than
general.

**A push is one continuous motion, and it only works if it is sustained.** A
glass does not move because the jaw touched it; it moves because the jaw kept
travelling in one direction, in contact, for some distance. A policy that
re-decides at every instant has no record of why it was going that way, so each
decision is made afresh from a picture that has barely changed. Two failures
follow, and both are commonly seen in policies that predict one action at a
time. The first is **dithering**: tiny disagreements between consecutive
decisions turn into a motion that wanders instead of travelling, and a wandering
jaw in contact with a glass is doing something nobody designed. The second is
worse and quieter. At the moment of choosing, the arm has usually seen a
demonstration that pushed left and a demonstration that pushed right from a
situation that looked much the same, and a network asked for the single best
next step minimises its error by producing something between the two. **The
average of two commitments is not a commitment.** Chunking does not remove that
difficulty but it moves it to where it does least damage: the averaging now
happens once per push, over whole pushes, rather than at every instant over
every step.

Two more things follow from chunking, one good and one a genuine cost.

**Errors do not compound inside a chunk.** The waypoints of a chunk were
produced together, so they are consistent with each other by construction.
Nothing inside the chunk is a decision made on top of an earlier mistake. A
step-by-step policy has one decision per tick, and every one of them is made
from a state its own previous decisions produced, which is the mechanism the
section after next is about.

Consistent is not the same as direct, and the measurement makes the difference
plain. The fitted policy's chunks wander two to four times as far as the glass
they move ends up travelling, where the teacher's path and its displacement are
the same length. So chunking stops one mistake from feeding the next, and it
does not stop the policy from being unsure: a chunk can be internally
consistent and still take a long, wavering route to a short move. What
chunking removes is compounding, not indecision.

**A chunk is open-loop while it runs.** Nothing is being read during it. The
arm is carrying out a motion it decided on from a picture that is now out of
date, and if something unexpected happens three waypoints in, the remaining
waypoints do not know. So the chunk's length is a real trade and not a
formality: a long chunk is committed and blind, a short chunk is responsive and
prone to dither. And it is a trade in speed as well as in length, because
waypoints are consumed at a fixed rate: how far apart they are is how fast the
jaw goes. The examiner caps that at the fastest the cell ever moves the jaw, so a
chunk whose waypoints are further apart than the arm can cover in one control
period is taken slower rather than at a speed the arm does not have. A policy
copying this teacher never meets the cap — the teacher's own waypoints are
about a millimetre apart, and the cap is at ten — but a policy that learned to
emit coarser chunks would be slowed by it.

What makes the trade bearable is set by `Bench.follow`, and it is worth being
exact, because it is less than the loop gives a parameterised push. Coming
down to the chunk's first waypoint is the examiner's
own move and it stops if the jaw touches anything on the way, so a chunk that
starts over an obstacle comes back as blocked rather than being driven
through. But **once the jaw is travelling across the table the examiner does not
feel for the glass.** A chunk is carried out as it was given, which is the
whole point of accepting one, and the only thing that stops it is the jam
threshold. So the slow approach to contact is not the cell's behaviour here;
it is part of the chunk, copied from the teacher's own feel. That is the one
place where this solution leans on the demonstrations for safety rather than
on the examiner.

Finally, chunking is the reason [the examiner](../the-examiner.md) accepts
waypoints at all, and that argument is worth repeating here because it is about
this solution specifically. The examiner could have required every solution to
emit the same three or four push parameters, which sounds like the fairest
possible rule. It would be the unfair one, because squeezing a chunking policy
down to a handful of parameters removes the mechanism that makes it work, and
what you would then measure is a damaged version of the method rather than the
method that exists.

## The second rung — Diffusion Policy

The plan carries a second rung for this solution, and it is not a spare in case
the first one fails. It is there to test one specific weakness of the first,
which the previous section has just named.

**Diffusion Policy reaches the same kind of answer by starting from noise and
denoising towards an action chunk.** In plain words: instead of computing the
chunk, the model begins with a chunk of pure random numbers — a run of
waypoints that is nothing but static — and then removes a little of what it
judges to be noise, and does that again, and again, until what is left is a
plausible run of waypoints. The model was trained to answer one question: given
a noisy chunk, which part of it is noise? Asking that question repeatedly
carves an answer out of the static.

A comparison from mathematics helps with why that is even possible. Think of
every possible chunk of waypoints as a point in a space, and of the good chunks
— the ones a demonstration might contain — as lying on a thin region inside it.
Pure noise is a point far off that region. The denoising step is a nudge
towards it. Repeated, the nudges arrive at the region, and where exactly they
arrive depends on where the noise started, which is why asking twice can give
two different good answers.

That last property is the whole argument, and it is worth stating carefully
because it is the clearest reason to carry both rungs.

**When several different pushes would all be good, a model trained to predict
one answer tends to average them.** This is not a flaw in any particular
network; it is what fitting towards a single answer does. If the training data
holds, for situations that look alike, one demonstration that pushed the left
glass left and one that pushed the right glass right, then the single prediction
that is least wrong on average is somewhere between the two — and between
"push left" and "push right" is "barely move". The average of several good
pushes is commonly not a push at all. A denoising model does not have this
problem, because it is not trying to name one answer. It represents a
distribution over chunks and draws from it, so it can keep both options and
pick one.

**And this problem has several good answers nearly everywhere.** That is not a
hypothetical. [The target layout](../the-target-layout.md) says it twice over:
minimising travel subject to clearance has more than one local optimum, because
moving the left glass left and moving the right glass right are both perfectly
good answers to the same crowded pair; and success is defined on the clearance
rather than on the layout, so **there is more than one way to uncrowd a table
and the alternatives are not wrong.** A method that must name a single answer
is therefore being asked, at almost every step, to choose between options it has
no reason to choose between — and its way of coping is to produce their
average.

So the two rungs together measure something real rather than merely trying two
models. ACT predicts a chunk directly, and if the averaging problem bites, it
will show up as pushes that move glasses too little or in the wrong direction
on exactly the symmetric arrangements where two answers were available.
Diffusion Policy can represent the choice. The gap between the two is a
measurement of how much the averaging cost, on this table, with this data.

**The rung is written and it runs; it has not been fitted here.** It is in
`policy.py` beside ACT, taking the same demonstrations, the same scaling and
the same picture, so that only the model differs. What stopped it was the
compute bill rather than the code: Diffusion Policy is about 75 million
parameters against ACT's 52 million, a training step costs it roughly twice as
much, and one chunk at run time is sixteen denoising passes rather than one
forward pass. Fitting it with several seeds on this machine is a night's work
on top of ACT's, and a rung reported from one seed is not a result. So there
is no `results-diffusion.json`, and the gap this section argues for has not
been measured.

It is worth saying plainly that **ACT's measured behaviour makes this the most
valuable thing left undone in this solution.** What ACT produces on a table it
has not seen is a chunk about 55 mm away from the teacher's and about 30
degrees off in heading — close to what averaging over the teacher's
alternatives would give, and far enough off that the jaw meets a neighbour on
the way down. Whether a model that draws its chunk instead of naming one
escapes that is now a question with a measurement behind it rather than an
argument.

![The teacher's chunk drawn beside the policy's on the same scale: the teacher's is a straight 87 mm of path for 87 mm of displacement, every single one of them, while the policy's wanders 262 mm of path to get 28 mm away, and across the held-back demonstrations the policy's chunks walk two to four times as far as they get; beside it, the waypoints that had to be pulled inside the jaw's limits, which were every one of them the height column and at most 1.7 mm below push height.](../../../images/03-push-glasses-apart/03-inside-one-chunk.png)

Two costs come with the second rung and both belong on the scorecard.

**It costs more per push.** One chunk needs several denoising passes rather
than one forward pass, so the run-time cost is some multiple of ACT's. [The
examiner](../the-examiner.md) carries a compute column for precisely this kind
of difference, because a solution that wins while taking much longer has not
obviously won.

**It is one more thing that varies by seed.** A policy that draws its answer is
stochastic by construction, so asked the same question twice it may act
differently. The examiner's requirement applies with full force: several training
seeds, several evaluation runs, and the spread reported, because a method that
wins by less than its own spread has not been shown to win.

## Compounding error

Behaviour cloning has one characteristic failure, and it follows directly from
the fragility named earlier: a cloned policy only knows situations the
demonstrator visited.

Here is the mechanism, in order. The policy acts slightly differently from the
teacher — a little short, a little off the demonstrated heading, because no
fitted function reproduces its labels exactly. That small difference puts the
arm in a state the teacher would not have reached. In that state the policy is
a little further outside the region its examples covered, so its next action is
a little worse, which puts the arm in a state further out still. **The error is
not added once; it is fed back into its own input.** This is **compounding
error**, and it is why a policy that looks excellent on held-out single
decisions can still fail over a whole run.

The comparison from programming is the difference between a rounding error in a
calculation and a rounding error inside a loop that reads its own last result.
The first stays the size it was. The second grows with the number of
iterations.

**What mitigates it here is the loop, and the mitigation is substantial.**
[Pushing without toppling](../pushing-without-toppling.md) describes every
solution in this problem as acting, measuring what really happened, and then
deciding again from what it measured. The arm is not following a script of
pushes; it repeats one step — look at the table, choose one push, make it, look
again — until the work is done. For a cloned policy that arrangement is worth
more than it is for anybody else, because **the state the policy is asked about
is always a measured table and never a predicted one.** Drift inside a chunk is
cut off at the end of the chunk. The policy is re-anchored on a fresh reading
before it is asked anything again, so the feedback path that makes error
compound is broken once per push.

It is blunted, not removed, and two ways it still bites are worth naming.

**Inside a chunk, nothing is read.** The chunk is carried out as decided, so
whatever drift accumulates over its waypoints accumulates unobserved. This is
the cost of chunking from the previous section, seen from the other side, and it
is bounded by the chunk being short.

**Across pushes, the arrangement itself drifts.** This is the real one. Looking
again tells the policy where the glasses are; it does not make those positions
ones the teacher ever produced. A policy whose first push went further than the
teacher's would have leaves a table the teacher never generated, and the second
push is then chosen on a table outside the demonstration set. Repeated over a
run, the policy walks its own table into territory its data does not cover.
Measuring positions accurately does not help with that at all, because the
problem is not that the state is unknown but that the state is unfamiliar.

**The standard repair for this is called DAgger, and it is unusually cheap
here.** The idea is to collect demonstrations where the policy actually goes
rather than only where the teacher went: run the policy, and at every state it
visits, ask the teacher what it would have done there, and add that answer to
the training set as a label. Retrain, and repeat. The set then covers the
policy's own drift, which is exactly the region plain cloning leaves empty.

The reason this is affordable here is the property named two sections ago.
**The teacher is a program, so it can be asked about any state, at any time,
for nothing.** A human demonstrator cannot answer "what would you have done on
this table that my policy produced last Tuesday"; solution 2 can answer it
every time it is asked. So the one serious weakness of behaviour cloning has, in
this particular arrangement, a cheap and well understood repair available — and
it is worth recording that this is a consequence of the teacher being code,
not a property of imitation learning in general.

## The pushes are what this contributes

One point about the output has to be clear, because it decides what a
comparison with this solution is a comparison of.

**This solution emits waypoints directly, and nothing expands them.** [The test
examiner](../the-examiner.md) owns a macro that turns a parameterised push into a
descent, a feel, a slide, a back-off and a lift, and the solutions that think
in parameterised pushes go through it. A chunk is already a jaw trajectory, so
there is nothing for the macro to do. The examiner carries the waypoints out as
given, through `Bench.follow`, which is built.

**Two small things travel beside the waypoints, and they are not the
policy's.** The examiner's chunk carries the glass it is meant to move and the
place the solution expects that glass to arrive, because the scorecard counts
pushes per glass and measures how far each glass ended from its aim. A policy
whose output is a run of waypoints produces neither. Both are therefore read
back off the chunk after the fact: the glass is the one the jaw ends up
against, and the aim is that last fingertip moved forward by half the glass's
measured width, which is solution 1's own convention. Nothing about that
reaches the policy or changes the motion. It is bookkeeping for the
scorecard, and it is named here because it is the one place where this
solution's output is not literally the whole answer.

**The score is the outcome, not the action.** The examiner does not ask whether the
chunk was the chunk it would have chosen, or whether the waypoints were smooth.
It looks only at the table afterwards: which glasses have room, which are
standing, where each one ended up, and how many pushes it took. That is what
makes a three-number push and a chunk of a hundred-odd waypoints comparable at
all, and it is the only reason this solution and its teacher can be set side by
side.

![Two fits compared: the first drove the training loss to 0.04, six times lower than the fit this solution shipped, and was memorising — 11 mm from the teacher on tables it had seen against 62 mm on tables it had not — while four times the demonstrations removed the memorising and left the error on unseen tables exactly where it was; and of the three shipped seeds the one that fitted closest to the teacher both racked the most glasses and toppled the most.](../../../images/03-push-glasses-apart/03-the-loss-was-not-the-score.png)

**Everything else in the pipeline is shared, so a difference in the score
belongs to the policy.** The tables are the examiner's. The measurements are the
examiner's, carrying problem 2's measured error. The destinations come from [the
target layout](../the-target-layout.md), computed once per arrangement and so
every solution that aims at a destination aims at the same places, rather than
at an easier arrangement than another. The topple limit and the refusal rule
come from [pushing without toppling](../pushing-without-toppling.md). What this
solution contributes is one mapping — from a picture of the table to a short
run of waypoints — and nothing else.

There is a pleasing detail in how the shared parts reach this solution, and it
is worth noticing because it explains what the policy is really learning. The
target layout never appears inside the network. It reached the demonstrations,
because the teacher aimed at it, and the demonstrations are all the policy ever
saw. In the same way, the examiner's macro never appears inside the network, but
the waypoints it produced are the labels the network was fitted to, so **the
student's action space is the teacher's macro, written down as motion.** The
policy begins by being able to express only what the macro expressed, and
whatever it learns beyond that comes from generalising between those examples
rather than from being given a wider vocabulary.

## How the concepts fit together

The pieces now join into one pipeline. It has an offline half that happens once
and an online half that happens on every push, and the halves are worth keeping
apart because almost all the cost is in the first and almost all the risk is in
the second.

**Offline, and once.** Tables are drawn from numbers below the dividing line.
Solution 2 is run over them. For every push it chooses, three things are
recorded: the view of the table from the top at that moment, the waypoints the
examiner's macro produced, and the examiner's verdict on what happened to the table
afterwards. Pushes that failed are dropped and the dropping is counted, so the
thinning is visible. Refusals are kept as refusals. What remains is a dataset of
pairs — a picture, and a chunk of waypoints — which is exactly the shape
behaviour cloning needs. One detail of the shape is worth naming, because the
document above does not settle it: a recorded path is a few hundred waypoints
long and a chunk is a fixed, shorter run, so every demonstration is trimmed to
the part at push height and resampled to the chunk's length. The trimming is
free, because the examiner does the descent and the lift itself. The resampling
is not free: waypoints are consumed at a fixed rate, so squeezing a long push
into a fixed chunk runs it faster than it was demonstrated. The chunk's length
is therefore set near the median length of the teacher's own pushes, and a
push longer than that is replayed quicker than it was made.

ACT is then fitted on the dataset from random numbers, for hours. The second
rung fits Diffusion Policy on the same dataset, changing the model and nothing
else. Both are fitted several times with different seeds, because one training
run is not a measurement.

**Online, on every push.** The arm looks at the table and racks every glass
that already has room. The shared topple limit is then evaluated on every
glass still standing there, before the policy is asked anything, and a glass
that fails it is refused with its reason and taken out of play. Only then does
the straight-down view go into the policy, which returns one action chunk; the
chunk is charged to one of the glasses the limit left in play, so a refused
glass can never be pushed. The examiner carries the chunk out: the closed jaw is
placed clear above the first waypoint, comes down to it, follows the waypoints
one control period apart, and lifts clear, reporting what it felt in the same
words a parameterised push reports. The arm looks again. The loop repeats
until every glass has room, or the glasses that are left have all been
refused, or the push budget is spent.

Three things are worth holding on to from all of that.

**Nothing in the method represents pushing.** There is no friction coefficient,
no slide prediction, no candidate list and no geometry inside the policy. The
consequences of friction are in the data, and what the network holds is a
mapping, not an understanding. This is the most economical of the six in terms
of what somebody had to know in order to build it.

**The loop is what makes copying survivable.** A cloned policy run open-loop
over a whole run would compound its own error. Run one chunk at a time against
a freshly measured table, it is re-anchored on every push. The method and the
loop are a pair; neither would be sensible here without the other.

**The ceiling is the teacher.** Every label this policy ever saw came from
solution 2, and nothing in behaviour cloning evaluates an outcome. So the
student has no mechanism by which to discover a better choice of glass, or a
better destination, than the one it was shown. The next sections are about what
that does and does not rule out.

## When a glass cannot be pushed safely

Every solution document in this folder answers this question. This one's answer
is that **the refusal does not and cannot live inside the policy**, and the
reasoning is worth following because it is a good illustration of what a cloned
policy is unable to express.

The limit itself is shared and is set out in full in [pushing without
toppling](../pushing-without-toppling.md). A pushed glass slides while the
contact height is below half its foot width divided by the friction
coefficient, and tips above it. The height that counts is the **top edge of the
jaw**, which stands at 65 mm, rather than the 50 mm the jaw's middle rides at,
because a glass that is wider higher up meets the top edge first. Those are the
gripper's own numbers. The foot width comes from `look()`. The friction does
not come from anywhere, because nothing in this cell measures it. For a glass
whose foot is narrow enough that the limit falls below the jaw's top edge at any
plausible friction, there is no contact height the arm can offer, and the only
correct answer is to refuse.

**A policy of this kind has no way to say that.** Its output is a chunk of
waypoints. There is no channel in it for "I cannot move this glass, and the
reason is that it tips before it slides". The examiner requires a refusal to carry
a reason — a glass abandoned in silence is marked **wrong**, while a glass
refused with a reason is **correct but incomplete**, which is a good outcome —
so the thing the examiner wants is a kind of answer this policy cannot produce.

It is tempting to hope the policy learns to refuse by itself, and it is worth
being exact about why it does not. The teacher refuses those glasses, so the
dataset contains no push on them. But **the absence of an example is not a
label.** The network was never shown a situation of that kind paired with an
instruction to do nothing; it was shown nothing at all. Asked about such a
table, it will return a chunk of waypoints, because returning a chunk of
waypoints is the only thing it does, and that chunk will be an extrapolation
with nothing behind it. The one case where the arm must not act is therefore the
case where the policy is least anchored and least able to warn.

So the limit sits **in front of** the policy, as shared arithmetic, exactly as
it does for the other five. The foot width is measured, the limit is evaluated
at the jaw's top edge, and a glass that fails never reaches the policy at all.
If every glass left on a table fails, the run ends *correct but incomplete*,
with each remaining glass reported with its reason. The policy is not consulted
and cannot be blamed, which is the right arrangement for a decision whose wrong
answer cannot be recovered.

Two further points are specific to this solution.

**The gate makes the comparison cleaner, not dirtier.** Because the same
arithmetic refuses the same glasses for all six, no solution can score well by
refusing more or badly by refusing less. What is left to compare is the pushes
on the glasses everybody agreed were pushable.

**The early abort matters more here than elsewhere.** [Pushing without
toppling](../pushing-without-toppling.md) describes a monitor that reads the
jaw's force signal during a push and stops the arm the moment the contact stops
behaving like a slide, and notes that it is the only thing in this problem that
can prevent a topple rather than report one. A chunking policy is open-loop
while its chunk runs, so during that window such a monitor would be the only
thing observing at all. **It is still a prescription rather than built code,
and this solution is the one with the strongest reason to want it.** What the
examiner does have during a chunk is the jam threshold, which stops a chunk whose
jaw has wedged. That catches a blocked path; it does not recognise a glass
beginning to tip, which is the failure the monitor was for.

## A worked example

Follow one table through, because the places where this solution differs from
its teacher are easier to recognise on a concrete arrangement than in the
abstract.

**The table.** Five straight glasses stand in the glass zone, drawn at
proportions from across that kind's range, so they are not all the same size.
Two of them stand deliberately close — closer than the gripper can work with,
with a little daylight still between them — and one of that pair is also fairly
near the edge of the glass zone. The other three have room. The examiner accepted
the table because at least one glass on it has no room, so there is work to do.

**What happened offline.** Long before this table was drawn, solution 2 was run
over many tables below the dividing line. On each, it generated legal candidate
pushes, ranked them, pushed, and the examiner recorded the picture, the waypoints
and the verdict. The failures were dropped and counted. What was left was fitted
into ACT, several times with different seeds. None of that involves this table,
which comes from above the dividing line.

**The first push.** The arm takes the view from the top and the policy returns
one chunk: a descent behind the outer glass of the crowded pair, a slow feel
forward, a committed slide outward along a heading away from its neighbour, a
back-off, and a lift to travel height. Notice what the chunk is free to do that
a parameterised push is not. It can lean the slide as it travels, so the glass
leaves its neighbour at a slightly different angle from the one it started on,
and it can slow as it approaches the end rather than stopping at speed. Whether
either of those is worth anything is a thing to measure rather than to assert.
The freedom is real, it belongs to the trajectory solutions only, and this is
the kind of place it would show up.

**What the push actually does.** The glass goes further than the teacher's aim
would have put it, because the friction under this glass's foot is not what any
of the demonstrations happened to sit at, and no part of this method models
friction. Nothing is lost by that: the arm looks again, and the fresh reading
says where the glass really is.

**And here is compounding error, in one concrete form.** The table the policy
now faces has a glass closer to the edge of the glass zone than the teacher
would ever have left one, because the teacher aimed at a destination the layout
computed and this push overshot it. If the demonstration set happened to hold
tables with a glass in roughly that position, the policy is on familiar ground
and the second push is as good as the first. If it did not — and the filtering
makes that more likely, because overshoots near the zone edge are exactly the
pushes that failed and were dropped — then the policy is being asked about a
table outside its data. It will answer. The answer will arrive as a chunk of
waypoints like any other, with nothing to distinguish it from a confident one.
This is the failure to watch for in this solution, and the DAgger repair is
aimed precisely at it: ask solution 2 what it would have done on this table,
and the gap closes.

**Where the averaging problem would show.** Change the table slightly so that
the crowded pair sits symmetrically, with as much free table to the left of the
left glass as to the right of the right glass. Pushing the left glass left and
pushing the right glass right are equally good, and [the target
layout](../the-target-layout.md) says plainly that both are legal answers. The
demonstration set will hold both kinds of example, taken from arrangements that
look much alike. ACT must name one chunk, and the chunk that is least wrong on
average over those examples is something between them: a short, hesitant motion
that separates nothing. The examiner would score that as a push spent with the
table unchanged, and a solution that repeats it would burn its push budget
without failing in any way the counts call wrong. **This is the case the
Diffusion Policy rung exists to test**, because a model that draws its chunk
can commit to one side.

**And the refusal.** Take a different table, of stemmed glasses this time, one
of them drawn with a foot narrow enough that half its width divided by any
plausible friction falls below the jaw's top edge. The shared arithmetic
evaluates that from the measured foot width before the policy is consulted, and
refuses the glass with its reason. The policy never sees it. The other glasses
on the table are pushed as usual, and the run ends *correct but incomplete*,
which is the right result. The important part of this example is the negative
one: nothing the policy could have learned would have improved it, and nothing
the policy might have produced was allowed to make it worse.

**One correction to all of the above, now that it has been run.** Everything in
this example is what the design says the method would do, and it was written
before any of it existed. The refusal behaves exactly as described. The first
push does not. What the fitted policy actually returns on a table it has not
seen is a chunk that starts in roughly the right neighbourhood but points about
thirty degrees away from where the teacher pointed, and the jaw is a quarter of
a metre long behind its fingertips, so on a crowded table it meets a neighbour
while it is still coming down. Almost every push ends there, before any glass
is touched. Nothing in the example about leaning the slide or slowing near the
end was reached, because the motion never got that far. The folder's
`README.md` has the counts.

![The same held-out table with the teacher's push and the policy's chunk side by side: the teacher brings the fingertips down 10 mm clear of the glass's rim and the 270 mm body of the jaw clears every other glass, while the policy brings them down 30 mm inside the rim of the glass it means to push, so the examiner stops the descent and reports the chunk blocked with nothing moved; over the whole run 569 of 643 pushes end that way and 472 of them go to a glass that has already been pushed.](../../../images/03-push-glasses-apart/03-blocked-on-the-way-down.png)

## What it needs

It needs **[LeRobot](https://github.com/huggingface/lerobot)**, which holds ACT
and Diffusion Policy as reference implementations, with **PyTorch** underneath.
LeRobot is Apache-2.0, and because this solution downloads no weights, the
weights file it produces is fitted entirely on data generated inside this
project and inherits no terms from anybody. That is as simple as a licence
position gets in this folder: [solution 5](05-smolvla-as-it-downloads.md) and
[solution 6](06-smolvla-fine-tuned.md) both carry borrowed weights, and this
one carries none.

It needs **[solution 2](02-geometry-ranked.md) working**, because that solution
is the teacher. This is a real dependency and not a preference: without a
program that chooses pushes well, there are no demonstrations, and with a
teacher that chooses badly the student has nothing worth copying. [The
plan](../solutions-plan.md) builds the two in that order for this reason.

It needed **two things the examiner did not have**, and that was the third of the
honest costs. [The plan](../solutions-plan.md) recorded both in its audit of
`bench.py`. The first was a **rendered view of the table from the top**: the
examiner returned numeric readings, and it did render the world, but from the
arm's side rather than straight down, and only for the films used to check a
run by eye. The second was a **path that accepts a chunk of waypoints**:
`push()` takes a parameterised push and *is* the macro that expands it, so
there was no way in for a trajectory. Both are now built — `bench/top_view.py`
and `Bench.follow` — and both were the real price of going off the shelf,
because every LeRobot policy expects pictures and a control-rate action space.
Solutions 1 and 2 need neither, which is one more reason to build them first.

It needs **demonstrations**, which cost arm time on the examiner's tables's tables and nothing else,
drawn only from table numbers below the dividing line. The prescription here
is to over-represent the crowded corner cases deliberately, so that the edge
of what the policy will face sits somewhere in the middle of what it was
trained on. **That part is not done**: the demonstration set is drawn from
consecutive table numbers, which is whatever mixture the examiner's own table
generator produces, and the crowded corners are therefore as rare in the
training set as they are on the examiner's tables.

It needs **compute**, and this is the cheapest entry in the folder. **Training
runs in hours.** The reason it is so modest is worth stating, because it is
easy to assume that anything with a transformer in it is expensive. The dataset
is small — thousands of pushes, each a picture and a short chunk — the network
is small by the standards of the foundation models in [solution
5](05-smolvla-as-it-downloads.md) and [solution
6](06-smolvla-fine-tuned.md), and nothing has to be learned about vision in
general, only about this one cell's pictures of this one task.

**In the end nothing was rented.** This document first budgeted tens of
dollars for a small accelerator, and that is still the right figure for
anybody who wants one. But a network of a few tens of millions of parameters
on a few thousand small pictures fits on the graphics processor an Apple M4
already has, in about an hour per training seed, so the whole of this solution —
demonstrations, several training seeds and the held-out run — was made on the
machine the project is written on. For comparison, renting an accelerator for
a weekend is of order a hundred dollars, and a small one for a month of order
five hundred, so even a generous schedule of retraining stays well inside a
weekend's rental if a laptop is not available.

At run time it needs very little: **one forward pass per chunk** for ACT, and
several passes per chunk for the denoising rung, against a push that takes the
arm seconds to carry out. The compute column on the scorecard is where that
difference between the two rungs becomes visible.

And once fitted, it needs **a weights file kept in step with the examiner**.
Change how the view from the top is rendered, or the macro whose waypoints
became the labels, or the error the readings carry, and the file is quietly out
of date in a way no test of the code would notice.

## Where it is strong and where it breaks

**Nothing has to be written about pushing.** No friction model, no candidate
generator, no features chosen by hand, no geometry. The method's entire content
is a dataset and a fitting procedure, and the dataset was produced by a program
that already exists. Of the six, this is the one that demands the least prior
understanding of the task from whoever builds it.

**The output is native.** This solution emits a chunk because a chunk is what
it is built to emit, so nothing is squeezed or expanded on the way out, and the
examiner's decision to accept waypoints costs it nothing.

**Labels are free and plentiful.** The usual reason not to attempt imitation
learning — that somebody has to demonstrate the task by hand, many times — does
not apply, because the teacher is code and the tables are simulated.

**It is cheap to train and cheap to run.** Hours on a laptop's own graphics
processor, and one forward pass per push.

**It is a measurement.** Student against teacher, on the same tables with the
same scorecard, with every shared part held still. Even if this solution were
not the one carried forward, that reading would have earned its place.

Against that, five weaknesses, and the first three cannot be engineered away.

**The ceiling is the teacher's quality.** Every label came from solution 2, and
nothing in behaviour cloning ever evaluates an outcome, so **this solution
cannot beat solution 2 by much on the pushes it imitates.** It is worth being
precise about the two narrow ways it might exceed its teacher, because they are
real but small: it can smooth away some of the teacher's inconsistency, since a
fitted function averages over many examples and so is steadier than any one of
them; and it can express motions the examiner's macro cannot, since its output is
waypoints rather than push parameters. What it cannot do is discover that a
different glass should have been moved, or a different destination chosen,
because no mechanism in it compares one outcome against another. [Solution
4](04-a-world-model.md) has such a mechanism, which is the sharpest difference
between the two.

**Filtering the demonstrations biases it towards what the teacher does well.**
Keeping only the pushes that succeeded is necessary, because a cloned policy
copies failures as readily as successes, and it thins the dataset exactly in
the situations where the teacher struggled. So the student is fitted most
densely where help was least needed.

**It needed examiner work the first two solutions did not.** A straight-down
rendered view and a waypoint path, both recorded in the plan as missing and
both now built. That cost is paid, but two smaller ones are paid on every
push rather than once. The examiner's chunk wants a glass and an aim that the
policy does not produce, so both are read back off the waypoints outside it.
And nothing stops a network emitting a coordinate the jaw cannot reach, so
every chunk is pulled inside the jaw's limits before it is followed, and how
often that happens has to be counted and reported rather than hidden. When it
was counted, the character of it was milder than this warning suggests: every
waypoint that had to be pulled in was pulled in **height** alone, by less than
two millimetres, and not one chunk ever asked for a place off the table. So the
limit that bites is the one the jaw has below the table top, not the reach
across it.

**It is open-loop inside a chunk, and it cannot refuse.** During a chunk
nothing is read, and the monitor that would watch the force is not built, so
the only thing stopping a chunk is the jam threshold. And the policy's only
output is waypoints, so a refusal has to come from the shared gate in front of
it rather than from the policy itself.

**And it cannot explain itself, or say when it is lost.** When solution 2 is
wrong you can print the candidates and the scores and see which step went
astray. When this policy is wrong you can look at the picture and guess. It has
no confidence output, and the situation in which it is least reliable — a table
unlike anything in its data — is indistinguishable in its output from the
situation in which it is most reliable. Combined with it being stochastic and
with training varying by seed, that is why the examiner insists that one run is not
a measurement and that a result quoted without a spread is not a result.

## The general ideas behind this

Nothing in this solution was invented for glassware. Every part of it is a
standard piece of modern practice, and each is worth knowing on its own,
including where it is normally the wrong tool.

### Behaviour cloning

Fit a policy by supervised learning on pairs of what the demonstrator saw and
what the demonstrator did. It is the oldest and simplest form of imitation
learning, going back to driving a vehicle from camera images with a small
network trained on a person's steering, and it remains the first thing to try
whenever demonstrations exist.

It is normally the right choice when demonstrations are plentiful and the task
is reactive — when what to do next really is a function of what is in front of
you. It is normally the wrong choice when demonstrations are scarce, when the
task needs a long-horizon plan that no single observation implies, or when the
demonstrator cannot be consulted again, because then the compounding error
below has no cheap repair. For more, see [imitation
learning](https://en.wikipedia.org/wiki/Imitation_learning).

### Compounding error, and dataset aggregation

A cloned policy's own small mistakes move it to states its demonstrations never
covered, where it acts worse, which moves it further out. The standard analysis
of this and the standard repair are both in **DAgger** — dataset aggregation —
by Ross and colleagues ([arXiv:1011.0686](https://arxiv.org/abs/1011.0686)):
run the policy, label the states it actually visits with what the expert would
have done there, add them to the training set, and retrain.

It is the right method whenever the expert can be queried at a state of your
choosing, which is the case here because the expert is a program. It is wrong,
or rather unavailable, when the expert is a person, because asking a person to
label thousands of states the policy wandered into is slower and more
unpleasant than asking them to demonstrate the task properly in the first
place. That asymmetry is the main reason a programmed teacher is worth so much
more than a human one for this particular method.

### Action chunking

Predict a short sequence of future actions in one pass and execute it, rather
than predicting one action per control step. ACT introduced this for fine
manipulation learned from inexpensive hardware (Zhao and colleagues,
[arXiv:2304.13705](https://arxiv.org/abs/2304.13705)) and it has become a
standard component of imitation policies, including the vision-language-action
models [solution 5](05-smolvla-as-it-downloads.md) and [solution
6](06-smolvla-fine-tuned.md) use.

It is right for continuous, committed motions — a push, a wipe, a pour — where
re-deciding every instant produces dithering and averages away the commitment
the motion needs. It is wrong when the environment can change faster than a
chunk takes to run, because a chunk is blind while it executes: a policy
chunking through a moving obstacle is a policy driving with its eyes closed.
This cell is quasi-static and nothing moves except what the arm moves, which is
why chunking is safe here and would not be in a scene with people in it.

### Denoising diffusion, and Diffusion Policy

Learn to remove noise from a corrupted sample, then generate by starting from
pure noise and removing a little at a time. The modern form of this is the
denoising diffusion probabilistic model (Ho and colleagues,
[arXiv:2006.11239](https://arxiv.org/abs/2006.11239)), and **[Diffusion
Policy](https://diffusion-policy.cs.columbia.edu/)** applies it to action
chunks for robot control (Chi and colleagues,
[arXiv:2303.04137](https://arxiv.org/abs/2303.04137)).

It is right when the right answer is not unique — when several actions would
all be good and a model forced to name one would return their average, which is
often no answer at all. It is wrong when the answer genuinely is unique and
speed matters, because the several denoising passes buy nothing and cost real
time per decision. The honest reading in this problem is that uncrowding a
table has many good answers, which argues for it, and that a push happens at
the speed of an arm rather than of a processor, which means the extra passes are
affordable.

### Mode averaging under a single-answer loss

The failure the previous idea repairs deserves its own name, because it is
general and it catches people out. Fitting a model to produce one output while
minimising its average error over examples that disagree makes the model produce
something between those examples. Where the examples are two sensible choices,
the something between them is frequently a third thing that is not sensible at
all.

It is worth knowing because the symptom is misleading. The model's training
error looks reasonable and its behaviour looks timid, and the natural diagnosis
— that it needs more data or more training — is the wrong one, since more
examples of both choices make the averaging worse rather than better. The
repairs are to represent a distribution rather than a point, as the denoising
model does, or to remove the ambiguity from the data by making the choice part
of the input.

### Distilling a planner or a program into a policy

Use a slow but good procedure as the teacher for a fast network, so that the
network ends up doing at run time what the procedure did offline. This is a
common and unglamorous pattern, and it is exactly what the relationship between
solution 2 and this solution is.

It is right when the teacher is correct but too slow to run where it is needed,
or when the teacher needs information at training time that is unavailable at
run time. It is wrong when the student is expected to be better than the
teacher, because distillation has no mechanism for improvement — it is copying,
and copying has a ceiling. In this folder the honest statement is that
distillation is being used for its measurement value rather than for speed,
since solution 2 is not slow; what the pair establishes is whether the mapping
is learnable at all.

## Where it sits among the other five

[The six solutions](overview.md) form a ladder, ordered by how much of each one
was fitted in this cell, and this solution is the first rung on which
everything was.

Against [solution 1](01-one-fixed-nudge.md), the comparison is the basic one
the whole folder is built around: does any learning beat a fixed nudge? Solution
1 fits nothing, pushes the same distance in the same way every time, and looks
again. It is arithmetic and it costs essentially nothing to run. If this
solution cannot clear more tables than that, no part of the machinery above has
earned its place.

Against [solution 2](02-geometry-ranked.md), the comparison is student against
teacher, and it is the most informative pairing this solution has. Every label
this policy saw came from that solution, so it cannot discover a better choice
of glass or destination than the one it was shown, and it should not be expected
to beat its teacher by much on the pushes it imitates. What the gap measures is
therefore not which method is better but whether the mapping from a picture to
a good push is learnable: a student that nearly matches its teacher says the
policy class is adequate and the remaining error belongs to the teacher's
geometry, and a student that falls well short says the opposite. The two places
this solution can legitimately exceed its teacher are narrow and worth watching
for in the numbers — a steadier push, from averaging over many examples, and a
motion the examiner's macro could not have expressed.

Against [solution 4](04-a-world-model.md), the comparison is the sharpest
question in the folder after the foundation-model pair: plan with a model, or
learn the push directly? That solution learns how the world changes and
searches over candidate actions at run time, simulating each one forward before
committing, so **it can find a push nobody ever demonstrated** — which is
exactly the thing this solution cannot do. It pays for that on every push, in
run-time cost that [the examiner](../the-examiner.md) puts at hundreds or
thousands of times the arithmetic a fixed nudge costs, and it pays again in
needing a model of the world accurate enough to plan against,
which is a harder thing to learn than a mapping. So the pair trades a ceiling
against a cost: this solution is cheap and capped by its teacher, that one is
expensive and capped by what its own encoding can express rather than by
anybody else's work.

Against [solution 5](05-smolvla-as-it-downloads.md), the comparison is fitting
here against borrowing wholesale. That solution runs SmolVLA exactly as it
downloads, with about 450 million parameters and a pretraining set of 487
community datasets of real teleoperation behind it, and fits nothing in this
cell. So it brings a vast amount of experience of robot manipulation in general
and none of this cell in particular, while this solution brings the opposite: a
small network that has seen nothing but this examiner, this jaw and these four
kinds of glass. Which of those two is the better trade is precisely what the
folder is for.

Against [solution 6](06-smolvla-fine-tuned.md), the comparison is where the
fitting happens. That solution takes SmolVLA's borrowed weights and continues
their training on this cell's own data with low-rank adaptation, which is this
solution's method — imitation from demonstrations collected here — applied to
somebody else's starting point instead of to random numbers. Reading the two
together separates what the demonstrations are worth from what the pretraining
is worth. And solutions 5 and 6 are the sharpest pair in the folder in their own
right: same model, same weights, and the only difference between them is that
one has had its training continued here.

Read as a ladder, the six measure what each increment of fitting buys. This one
is the rung where all the fitting is done here, from nothing, on examples a
program produced for free — the cheapest honest attempt at learning this task
that the folder contains, and the one whose limits are easiest to state in
advance.

← [Geometry generates, a model ranks](02-geometry-ranked.md) · [A world model,
then plan with it](04-a-world-model.md) →
