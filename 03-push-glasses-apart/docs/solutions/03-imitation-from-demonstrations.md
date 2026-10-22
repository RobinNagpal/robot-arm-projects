# Solution 3 — imitation from demonstrations

> **What it uses** — [LeRobot](https://github.com/huggingface/lerobot), with
> PyTorch underneath. The model is **ACT**, an action chunking transformer. It
> predicts a short run of future actions in one go. A second way uses
> **Diffusion Policy**, also from LeRobot. Both models are fitted here from
> random numbers. Nothing is downloaded except the library. Everything ran on
> an Apple M4 with no NVIDIA card.
> **What it does** — the arm is shown many good pushes, and a network learns to
> copy them. The good pushes come from [solution 2](02-geometry-ranked.md), so
> they cost only arm time on the examiner's tables. The policy has no geometry,
> no friction model and no candidate list inside it.
> **How the output is produced** — a view of the table from straight above goes
> in. An **action chunk** comes out: a short run of jaw waypoints, predicted
> together in one pass. The examiner carries the waypoints out as given. Then
> the arm looks again. One push is one chunk. The loop runs until every glass
> has room, the rest are refused, or the push budget is spent.
> **How it differs from the other five** — it copies solution 2, so the pair
> shows how close a student gets to its teacher. [Where it sits among the
> other five](#where-it-sits-among-the-other-five) compares it with each one.
> **What it costs** — the demonstrations are free, training takes hours on a
> laptop, and no borrowed weights are used. The real price has three parts. The
> policy is capped by its teacher. Filtering the demonstrations biases them.
> And the examiner had to gain a top view and a waypoint path. [What it
> needs](#what-it-needs) has the details.

> **The cell is described once, in [the cell](../../../01-rack-one-glass/docs/the-cell.md)**: the layout,
> the two camera places, the four sensors, and the words this project uses.
> What follows is only what belongs to this solution.

## Introduction

This document answers problem 3 by showing the arm good pushes and training a
model to copy them. The method is called **behaviour cloning**. It uses no
reward, no exploration and no physics. It uses only a table of situations and
the action taken in each one.

**This is built.** [The examiner](../the-examiner.md) is built, and so is
[solution 2](02-geometry-ranked.md), which is the teacher. The examiner's
straight-down view is built as `bench/top_view.py`. The path that carries out a
chunk of waypoints is built as `Bench.follow`. ACT has been fitted here from
random numbers, on demonstrations recorded from solution 2's pushes. It has
been run over the held-out tables. The code is in
`03-push-glasses-apart/03-imitation-from-demonstrations/`. Its full scores are
in that folder's `README.md`.

Three things are still designs, not code. They are the DAgger round, a force
monitor that watches a chunk while it runs, and extra weight for crowded corner
cases in the demonstrations. Each says so where it appears.

This solution matters because it asks a question the others cannot. Solution 2
is a program that chooses pushes well. If a network that copies it comes close,
then a good push can be learned from a picture. Any remaining error then
belongs to the teacher. If the network falls far short, that is evidence about
this kind of policy. We learn it before trying the expensive solutions.

This document covers behaviour cloning, where the demonstrations come from,
action chunks, what a denoising policy adds, compounding error, and the costs
this solution carries.

## A film of one table

Here is this solution on one table, filmed in the simulator at one and a half
times real speed.

[Watch the film (23 s)](../../videos/03-imitation-from-demonstrations.mp4)

It is table 10025 of the held-out fifty. Every solution is filmed on this
table. [Solution 1's film section](01-one-fixed-nudge.md#a-film-of-one-table)
explains how the table was chosen, and what the drawn hand and drawn pick show.
Five of its six glasses start with no room. Over all fifty tables, 203 of the
251 glasses start that way.

In the film the policy makes fourteen pushes and racks one glass. That glass
already had room. Most pushes end while the jaw is still coming down. The chunk
puts the jaw over a neighbour instead of behind the target. So the arm touches
something, lifts, and asks for another chunk from the same picture.

Three seeds of the policy were fitted, and the film shows seed 0. On this
table the three seeds racked 1, 1 and 3 glasses in 14, 14 and 11 pushes.
`results-tables.json` holds all three rows. How each solution does over all
fifty tables is in [the comparison](../../results/README.md).

## The code at the heart of it

This solution depends on one join. A demonstration is the path the jaw really
followed, recorded waypoint by waypoint by the examiner. The policy's answer is
an **action chunk**, a block of numbers of fixed shape. This solution's own code
turns the first into the second for fitting. It also turns the answer back into
waypoints for the examiner.

The conversion is in
[`03-push-glasses-apart/03-imitation-from-demonstrations/chunks.py`](../../03-imitation-from-demonstrations/chunks.py).
It holds no model and no geometry of pushing. `push_segment` keeps the part of a
recorded path at push height. That part starts where the jaw began to travel
across the table, and ends at the furthest point it reached. The descent, the
back-off and the lift are dropped, because the examiner does those itself.
`to_action` writes what is left as the five columns the policy is fitted on.
The way back is `to_waypoints` in the same file. It turns the cosine and sine
pair back into an angle, and pulls every waypoint inside the jaw's reach.

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
[`03-push-glasses-apart/03-imitation-from-demonstrations/policy.py`](../../03-imitation-from-demonstrations/policy.py).
One call builds LeRobot's ACT, and one asks it for a chunk.

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

Three settings differ from LeRobot's defaults. The rest of the model is
LeRobot's, untouched.

- `pretrained_backbone_weights=None` switches off the ImageNet weights ACT
  would download for its vision backbone. This makes "fitted from random
  numbers" true.
- `normalization_mapping` hands the scaling to this folder's own code. So every
  number the model sees is written here.
- `n_action_steps` is the chunk's full length. One push is one chunk, and
  nothing re-plans halfway.

The two blocks also show where the measured shortfall sits. The first two
columns come out roughly right. The fingertips go down near where the teacher
put them. The heading, in the last two columns, is 22 to 27 degrees away from
the teacher's. On a crowded table, that is enough for the jaw to meet a
neighbour on the way down. The push then ends before any glass is touched.

## The problem this solves

[The problem](../problem.md) asks for jaw motions until every glass has about
76 mm of clear room, or the rest are refused with a reason. So the answer is a
function from a crowded table to a jaw motion. That function is hard to write.
The main reason is that nothing in this cell measures friction, as [pushing
without toppling](../pushing-without-toppling.md#the-number-nobody-has)
explains.

Solution 2 copes by listing legal pushes and ranking them. But a person had to
write that list and choose the ranker's inputs. Each choice brings in a
person's model of pushing, and that model is incomplete.

**This solution comes at the same difficulty from the other end.** Nobody can
write the function down. But [the
examiner](../the-examiner.md#the-score-is-the-outcome-not-the-action) can tell
afterwards whether a push was good. So good pushes can be collected, and a
network can be fitted to them.

Two more things make it different in kind from its teacher.

**The policy learns the motion, not only the choice.** Solution 2 emits a
parameterised push, and the examiner's macro expands every one the same way. A
policy that emits waypoints is not limited to that macro. It can slow near a
neighbour, lean the slide away from a glass, or stop short. Whether that helps
is for measurement to decide.

**The policy reads the picture.** Solution 2 works from the numbers `look()`
returns. This policy takes an image. An image shows the shape of the gap
between two glasses, what stands behind them, and where the zone edge is. None
of that has to be named in advance for a network to use it.

## The main idea

The idea fits in three steps. **Run solution 2 over the training tables. Keep
the pushes that worked. Fit a network that maps a picture of the table to the
next short run of jaw waypoints.**

Three points follow, and the rest of this document covers them.

- **The teacher is a program**, not a person. [Where the demonstrations come
  from](#where-the-demonstrations-come-from) explains why that matters.
- **The answer is a chunk, not one action.** [Action chunking, and why it
  matters](#action-chunking-and-why-it-matters) explains why a push needs that.
- **The loop does not change.** Every solution here plans, feels, and looks
  again, as [the loop](../pushing-without-toppling.md#the-loop-plan-feel-look-again)
  describes. This solution replaces only the planning step. [Compounding
  error](#compounding-error) explains why the loop keeps copying safe.

## Behaviour cloning — learning a policy by copying

Behaviour cloning is the whole of this solution, so it is set out here in plain
words.

A **policy** is a function from what the arm sees to what the arm should do.
**Behaviour cloning** fits that function from examples of someone else doing
the job. Each example is a pair: what was seen, and what the demonstrator did.
The first is the input, and the second is the label. Fitting works like any
supervised learning. The network makes a guess, and the guess is compared with
the label. Then every weight moves a little to close the gap.

In programming terms, it is like being given a lookup table, then being asked
about entries that are not in it. The network is a smooth stand-in for the
table. The hope is that a smooth guess between entries is a good guess.

Three things make the method attractive here. Each is something it does not
need.

**No reward to design.** Reinforcement learning needs a number that scores each
outcome. A learner chases what the number says, not what it was meant to say.
A reward for moving glasses apart fast rewards shoving. A big penalty for
toppling teaches the arm to touch nothing. Behaviour cloning needs no such
number. Training only measures how far the network's action was from the
demonstrator's.

**No exploration.** A learner that learns by trying must try bad things. Here
one bad thing cannot be undone: **nothing in this project stands a toppled
glass back up.** Behaviour cloning tries nothing during training. It only
reads.

**No physics to model.** Friction appears nowhere in this method. The
demonstrations happened in a world with friction, so its effects are in the
data. The network learns what it can use from them. [Solution
4](04-a-world-model.md), by contrast, learns how the world changes and plans
through it. This solution predicts only what the teacher would have done.

Against these three there is one weakness, and everything else follows from it.

**A cloned policy only knows situations the demonstrator visited.** Inside the
region its examples cover, a smooth guess is fair. Outside it, the network still
returns an answer, but nothing backs that answer. Worse, **nothing in the
output says which case you are in.** The policy returns a chunk either way, with
the same confidence. A method whose mistakes show can be guarded. This one's
mistakes do not show.

## Where the demonstrations come from

In most of robotics, collecting demonstrations is what makes behaviour cloning
too costly. Here they are almost free.

**The teacher is [solution 2](02-geometry-ranked.md).** It generates legal
pushes aimed at the destinations [the target layout](../the-target-layout.md)
computes. It ranks them and takes the best. The examiner expands each push into
the waypoints the jaw really followed, and marks what happened to the table. So
**every push solution 2 makes is already a finished demonstration**: a picture
before it, the waypoints followed, and the examiner's verdict.

![One real training table seen from the top with the push the teacher chose on it, the path the jaw really followed written down waypoint by waypoint at half a millimetre apart while feeling and a millimetre apart while pushing, and the counts for the whole set: 17,816 pushes on 5,200 tables of which 6,659 were kept, where almost everything dropped is the teacher's own 5 mm test push rather than a failure.](../../images/03-where-the-demonstrations-come-from.png)

Five things follow. They are why [the plan](../solutions-plan.md) values
solution 2 for more than being a baseline.

**The only cost is arm time on a simulated examiner.** There is no
teleoperation rig and no operator. The examiner runs on MuJoCo, which is fast.
[The examiner](../the-examiner.md) notes that a learned approach needs
thousands of pushes. Gazebo would run each one at real-time speed.

**The demonstrations can be made again.** Each table comes from a single
number, and the same number always gives the same table. So the dataset can be
regenerated instead of archived.

**Training and testing cannot mix.** [Table
numbers](../the-examiner.md#what-the-examiner-draws) above a fixed dividing line
are for testing only. Demonstrations come only from below it. This document
calls that range of training tables the **demonstration band**. So no policy is
marked on a table it learned from.

**The teacher can be asked again, about any table.** A person who demonstrated
last week cannot say what they would do on today's table. A program can, every
time, for free. [Compounding error](#compounding-error) is where this pays off.

**The teacher is itself one of the solutions.** So the comparison is a student
against the program it copied, on the same tables with the same scorecard.
[The plan](../solutions-plan.md) builds this in on purpose.

One caveat goes with all of this. **This is a privilege of a simulator with a
programmed teacher.** On a real arm with a human demonstrator, collecting
demonstrations is usually the biggest cost of the method. Any judgement here
about the price of imitation should carry that caveat.

## Choosing which demonstrations to keep, and the bias it buys

Free demonstrations do not make a good demonstration set. Choosing which pushes
to keep brings in this solution's second cost.

**A cloned policy copies everything in its data.** It has no idea of a good or
bad action, only labels. Some of solution 2's pushes topple a glass, push one
out of the zone, or jam. Keeping them would teach the student to do the same.
So only the pushes the examiner marked as working are kept.

That is right, but it has an uncomfortable side. **Filtering by outcome also
changes which situations are covered.** Say solution 2 handles one kind of
table badly, such as glasses crowded in a corner. Most of its pushes there fail
and are dropped. So the student sees few tables of that kind. It is fitted most
densely where the teacher was already strong. **The filter removes examples
exactly where they would help most.** [Solution 2's own
section](02-geometry-ranked.md#it-is-the-teacher) makes the same point from the
teacher's side.

There are three defences. Two are now code, and one is still a design.

**Keep the teacher's refusals as refusals.** A glass solution 2 declined to
push is a result, not a failure, as [pushing without
toppling](../pushing-without-toppling.md) says. A dataset that silently drops
those tables teaches nothing about them. **Done**: the refusals and their
reasons are counted beside the demonstrations.

**Count what the filter removed.** The thinning is invisible unless it is
counted. **Done**: the collection writes a table of kept and dropped pushes, by
reason and by kind of glass. In total the thinning is small. By kind of glass
it is very uneven, as [the folder's
README](../../03-imitation-from-demonstrations/README.md#where-the-demonstrations-come-from)
shows.

**Weight the hard tables up, and draw more of them.** Tables cost only time, so
a thin region can be filled by drawing more tables of that kind. **Not done**:
the demonstrations come from consecutive table numbers. So they hold whatever
mix the examiner produces.

None of the three removes the problem. The teacher still sets the ceiling, as
[where it is strong and where it breaks](#where-it-is-strong-and-where-it-breaks)
says.

## Action chunking, and why it matters

The policy's output is the second thing that defines this solution. Its name is
in ACT's own name.

**Action chunking** means predicting a short run of future actions in one go,
not one action at a time. The network is asked once and returns several
waypoints together. The arm carries out the whole run before it asks again.

![A parameterised push drawn from the side as the examiner's macro expands it — down at 10 mm a waypoint, feeling at 0.5 mm, pushing at 1 mm, backing off and lifting — against the chunk the policy emits, a fixed block of 120 waypoints by five columns predicted in one pass, with the teacher's own pushes running from 25 to 246 waypoints and every one of them resampled to that fixed 120.](../../images/03-a-chunk-is-not-a-push.png)

In programming terms, there are two ways to write a controller. One function is
called every tick and returns the next single step. The other is called once
and returns several steps, which are then carried out. The second one
**commits**. It cannot change its mind partway. That is both its cost and its
value.

Committing helps for a reason specific to pushing. **A push works only if the
motion is sustained.** A glass moves because the jaw keeps travelling one way,
in contact, for some distance. A policy that decides afresh each instant
forgets why it was going that way. Two failures follow.

The first is **dithering**. Small differences between steps make the jaw
wander instead of travel. The second is quieter. The data often holds a push to
the left and a push to the right from tables that look alike. A network asked
for one best next step lowers its error by answering between the two. **The
average of two commitments is not a commitment.** Chunking does not remove
this. It moves the averaging to once per push, over whole pushes, instead of at
every step.

Two more things follow from chunking. One is good and one is a cost.

**Errors do not compound inside a chunk.** The waypoints of a chunk are made
together, so they agree with each other. No waypoint is a decision built on an
earlier mistake. A step-by-step policy makes every decision from a state its own
past decisions produced. [Compounding error](#compounding-error) is about that.

Consistent does not mean direct, and the measurement shows it. The fitted
policy's chunks wander two to four times as far as the glass they move travels.
The teacher's path is the same length as its displacement. So chunking stops
compounding, but it does not stop indecision.

**A chunk is blind while it runs.** Nothing is read during it. If something
unexpected happens three waypoints in, the rest of the chunk does not know. So
chunk length is a real trade. A long chunk is committed but blind. A short chunk
responds, but tends to dither.

It is a trade in speed too. Waypoints are used at a fixed rate, so their spacing
sets the jaw's speed. The examiner caps that at the fastest the cell ever moves
the jaw. A chunk spaced wider than one control period allows is run slower.
This policy never meets the cap. The teacher's waypoints are about a millimetre
apart, and the cap is at ten. A policy that emitted coarser chunks would be
slowed.

`Bench.follow` makes the trade bearable, but it protects less than a
parameterised push gets. The descent to the first waypoint is the examiner's
own move. It stops if the jaw touches anything, so a chunk that starts over an
obstacle is reported blocked. But **once the jaw travels across the table, the
examiner does not feel for the glass.** The chunk runs as given, and only the
jam threshold stops it. So the slow approach to contact is part of the chunk,
copied from the teacher. This is the one place where this solution relies on its
demonstrations for safety, not on the examiner.

Chunking is also why the examiner accepts waypoints at all. Squeezing a chunking
policy into a few push parameters would remove what makes it work. [The
examiner](../the-examiner.md#the-shared-output-and-why-it-is-a-jaw-trajectory)
explains this once for every solution.

## The second way — Diffusion Policy

The second way is not a spare. It tests one weakness of the first: the
averaging that the previous section named.

**Diffusion Policy starts from noise and removes it, step by step, until an
action chunk is left.** The model begins with a chunk of pure random numbers.
It removes a little of what it judges to be noise, and repeats. What remains is
a plausible run of waypoints. The model was trained on one question: given a
noisy chunk, which part of it is noise?

A picture from mathematics helps. Think of every possible chunk as a point in a
space. The good chunks lie in a thin region of that space. Pure noise is a
point far from that region. Each denoising step moves the point a little
towards the region. Where it arrives depends on where the noise started. So
asking twice can give two different good answers.

That last property is the whole argument.

**When several pushes would all be good, a model that predicts one answer tends
to average them.** Any network fitted to a single answer does this. Suppose the
data holds, for similar tables, one push of the left glass left and one push of
the right glass right. The least wrong single answer lies between them. Between
"push left" and "push right" is "barely move". A denoising model does not name
one answer. It holds a distribution over chunks and draws from it. So it can
keep both options and pick one.

**This problem has several good answers almost everywhere.** [The target
layout](../the-target-layout.md#two-cautions) says so. Moving the left glass
left and the right glass right are both good answers for one crowded pair.
Success depends on clearance, not on one fixed layout. So a single-answer model
must often choose between options it has no reason to prefer. It copes by
averaging them.

So the two ways together measure something real. If averaging hurts ACT, it
shows as pushes that move glasses too little, or the wrong way, on symmetric
tables. Diffusion Policy can represent the choice. The gap between the two
measures what averaging cost.

**This way is written and runs, but it has not been fitted here.** It is in
`policy.py` beside ACT. It uses the same demonstrations, the same scaling and
the same picture, so only the model differs. The compute bill stopped it, not
the code. Diffusion Policy has about 75 million parameters against ACT's 52
million. A training step costs it roughly twice as much. One chunk at run time
takes sixteen denoising passes instead of one forward pass. Several seeds of it
would be a night's work on top of ACT's, and one seed is not a result. So there
is no `results-diffusion.json`. The gap this section argues for has not been
measured.

**ACT's measured behaviour makes this the most valuable thing left undone.** On
tables it has not seen, ACT's chunk is 48 to 52 mm from the teacher's. Its
heading is 22 to 27 degrees off. That is close to what averaging the teacher's
choices would give. Whether a model that draws its chunk avoids this is now a
question with a measurement behind it.

![The teacher's chunk drawn beside the policy's on the same scale: the teacher's is a straight 79 mm of path for 79 mm of displacement, every single one of them, while the policy's wanders 97 mm of path to get 67 mm away, and across the held-back demonstrations the policy's chunks walk one and a half to twice as far as they get; beside it, the waypoints that had to be pulled inside the jaw's limits, which were every one of them the height column and at most 2.3 mm below push height.](../../images/03-inside-one-chunk.png)

Two costs come with this way, and both belong on the scorecard.

**It costs more per push.** Each chunk needs several denoising passes, not one.
[The examiner](../the-examiner.md) has a compute column for this kind of
difference. A solution that wins while taking much longer has not clearly won.

**Its answers vary more.** A model that draws its answer may act differently
when asked the same thing twice. So it needs several training seeds, several
runs, and the spread reported, as [the
examiner](../the-examiner.md#two-things-this-scorecard-needs-that-problem-2s-did-not)
requires.

## Compounding error

Behaviour cloning has one typical failure. It follows from the weakness named
earlier: a cloned policy only knows situations the demonstrator visited.

The mechanism goes in four steps.

1. The policy acts a little differently from the teacher, a little short or a
   little off the heading. No fitted function matches its labels exactly.
2. That puts the arm in a state the teacher would not have reached.
3. In that state the policy is a little outside its examples, so its next
   action is a little worse.
4. That puts the arm further out still.

**The error is fed back into its own input.** This is **compounding error**. It
is why a policy that does well on single held-out decisions can still fail over
a whole run. In programming terms, compare a rounding error in one calculation
with one inside a loop that reads its own last result. The first stays the same
size. The second grows with each pass.

**The loop blunts it a great deal.** Every solution here looks at the table,
chooses one push, makes it, and looks again, as [the
loop](../pushing-without-toppling.md#the-loop-plan-feel-look-again) describes.
So **the policy is always asked about a measured table, never a predicted
one.** Drift inside a chunk is cut off at the end of the chunk. The feedback
path is broken once per push.

It still bites in two ways.

**Inside a chunk, nothing is read.** Drift over its waypoints goes unseen. The
chunk being short limits the damage.

**Across pushes, the table itself drifts.** This is the real one. Looking again
tells the policy where the glasses are. It does not make that layout one the
teacher ever produced. Say the first push went further than the teacher's
would. The second push is then chosen on a table outside the demonstrations.
Over a run, the policy walks its own table into places its data does not cover.
Measuring positions well does not help. The state is not unknown; it is
unfamiliar.

**The standard repair is called DAgger, and it is cheap here.** DAgger collects
demonstrations where the policy goes, not only where the teacher went. Run the
policy. At each state it visits, ask the teacher what it would do, and add that
answer as a label. Then retrain and repeat. The set then covers the policy's own
drift, which plain cloning leaves empty.

It is cheap because **the teacher is a program, so it can be asked about any
table, at any time, for free.** A person cannot say what they would have done on
a table the policy made last Tuesday. Solution 2 can. This comes from the
teacher being code, not from imitation learning in general. DAgger is not built
yet.

## The pushes are what this contributes

This section says what a comparison with this solution is a comparison of.

**This solution emits waypoints, and nothing expands them.** Solutions that
think in parameterised pushes go through the examiner's macro, as [solution
2](02-geometry-ranked.md#the-pushes-are-what-this-contributes) describes. A
chunk is already a jaw path. So the examiner runs it as given, through
`Bench.follow`.

**Two small things travel with the waypoints, and they are not the policy's.**
The examiner's chunk carries the glass it means to move and where that glass
should arrive. The scorecard needs both. It counts pushes per glass and
measures how far each glass ended from its aim. The policy produces neither, so
both are read off the chunk afterwards. The glass is the one the jaw ends up
against. The aim is the last fingertip point, moved forward by half the glass's
measured width. That is solution 1's convention. None of this reaches the
policy or changes the motion. It is bookkeeping, and it is the one place where
the policy's output is not the whole answer.

**The score is the outcome, not the action.** The examiner looks only at the
table afterwards. That is what lets a three-number push and a chunk of a
hundred-odd waypoints be compared, as [the
examiner](../the-examiner.md#the-score-is-the-outcome-not-the-action) explains.

![Two fits compared: an early one drove the training loss to 0.04, more than twice as low as the fit this solution shipped, and was memorising — 11 mm from the teacher on tables it had seen against 62 mm on tables it had not — while four times the tables removed the memorising and took only about a fifth off the unseen error; and of the three shipped seeds the one that fitted closest to the teacher racked the fewest glasses of the three.](../../images/03-the-loss-was-not-the-score.png)

**Everything else is shared, so a difference in score belongs to the policy.**
The tables are the examiner's. So are the measurements, which carry problem 2's
measured error. The destinations come from [the target
layout](../the-target-layout.md), the same for every solution. The topple limit
and the refusal rule come from [pushing without
toppling](../pushing-without-toppling.md). This solution adds one mapping: from
a picture of the table to a short run of waypoints.

The shared parts reach the policy only through the demonstrations. The target
layout is not inside the network. But the teacher aimed at it, so it is in the
labels. The examiner's macro is not inside the network either. But the macro's
waypoints are the labels. So **the student's action space is the teacher's
macro, written down as motion.** The policy starts able to express only what the
macro expressed. Anything beyond that comes from generalising between examples.

## How the concepts fit together

The pipeline has two halves. The offline half happens once, and the online
half runs on every push. Almost all the cost is offline, and almost all the risk
is online.

**Offline, once.** Tables are drawn from the demonstration band, and solution 2
runs on them. Each push records three things: the top view at that moment, the
waypoints the macro produced, and the examiner's verdict. Failed pushes are
dropped and counted. Refusals are kept as refusals. What remains is pairs of a
picture and a chunk.

One detail of shape matters. A recorded path is a few hundred waypoints long,
and a chunk is a fixed, shorter run. So each demonstration is trimmed to the
part at push height, then resampled to the chunk's length. The trimming is
free, because the examiner does the descent and the lift. The resampling is
not. Waypoints run at a fixed rate, so a long push squeezed into a short chunk
runs faster than it was shown. So the chunk length is set near the median
length of the teacher's pushes. A longer push is replayed faster than it was
made.

ACT is then fitted on the dataset from random numbers, for hours. It is fitted
several times with different seeds, because one training run is not a
measurement. The second way would fit Diffusion Policy on the same data,
changing only the model.

**Online, on every push.**

1. The arm looks at the table and racks every glass that already has room.
2. The shared topple limit is checked on every glass left. A glass that fails
   is refused with its reason and taken out of play.
3. The straight-down view goes into the policy, which returns one chunk.
4. The chunk is charged to a glass still in play, so a refused glass is never
   pushed.
5. The examiner places the closed jaw above the first waypoint and lowers it.
   It follows the waypoints one control period apart, then lifts clear. It
   reports what it felt in the same words as for a parameterised push.
6. The arm looks again.

The loop repeats until every glass has room, the rest are refused, or the push
budget is spent.

**Nothing in the method represents pushing.** The policy holds no friction
value, no slide prediction, no candidate list and no geometry. Of the six
solutions, this one needed the least knowledge of pushing to build. Its ceiling
is its teacher, as [where it is strong and where it
breaks](#where-it-is-strong-and-where-it-breaks) explains.

## When a glass cannot be pushed safely

Some glasses tip before they slide at every height the jaw can offer. The
height that counts is the jaw's top edge at 107 mm, not the 75 mm its middle
rides at. The only correct answer is to refuse such a glass with a reason. The
run is then *correct but incomplete*, not wrong. [Pushing without
toppling](../pushing-without-toppling.md#some-glasses-cannot-be-pushed-at-all)
sets this out once. In five of the six solutions it is arithmetic, run before
any model is asked. What follows is only what belongs to this solution.

**A policy of this kind has no way to refuse.** Its output is a chunk of
waypoints. It has no channel for "I cannot move this glass, because it tips
before it slides". The examiner wants a refusal with a reason, and this policy
cannot produce one.

It does not learn to refuse by itself either. The teacher refuses those
glasses, so the data holds no push on them. But **the absence of an example is
not a label.** The network was never shown such a table paired with "do
nothing". It was shown nothing. Asked about one, it returns a chunk, because
that is all it can do. So the case where the arm must not act is where the
policy is least anchored.

**An early abort matters more here than anywhere else.** A chunk runs blind. A
monitor reading the jaw's force during a push would be the only thing watching.
[Pushing without
toppling](../pushing-without-toppling.md#an-early-abort-acting-during-the-push)
describes it. It is a design, not built code. This solution has the strongest
reason to want it.

## A worked example

This follows one table as the design said it would go. A correction at the end
says what the fitted policy really did.

**The table.** Five straight glasses of different sizes stand in the zone. Two
of them stand closer than the gripper can work with, with a little gap still
between them. One of that pair is near the zone edge. The other three have
room.

**Offline.** Long before, solution 2 ran on many tables in the demonstration
band. ACT was fitted on the kept pushes, with several seeds. This table comes
from above the dividing line, so none of that involved it.

**The first push, as designed.** The policy returns one chunk. The jaw comes
down behind the outer glass of the pair and feels forward slowly. It slides the
glass outward, away from its neighbour, then backs off and lifts. The chunk could lean the slide or slow near
the end. A parameterised push cannot do either. Whether that is worth anything
is for measurement to decide.

**What the push does.** The glass goes further than the teacher would have
aimed. Its friction differs from the demonstrations, and nothing here models
friction. Nothing is lost by that. The arm looks again and sees where the glass
really is.

**Compounding error, in one concrete form.** The policy now faces a glass
closer to the zone edge than the teacher would have left it. If the data held
tables like that, the second push is fine. If not, the policy is outside its
data. The filter makes that more likely, because overshoots near the edge are
pushes that failed and were dropped. The policy will still answer, with nothing
to mark the answer as unsure. DAgger aims at exactly this case. Ask solution 2
about this table, and the gap closes.

**Where averaging would show.** Now make the crowded pair symmetric, with equal
free space on both sides. Pushing the left glass left and the right glass right
are equally good. The data will hold both, from tables that look alike. ACT
must name one chunk, and the least wrong one is between them. That is a short,
hesitant motion that separates nothing. The examiner scores it as a wasted
push. Repeated, it uses up the budget without anything the counts call wrong.
**This is the case the Diffusion Policy way exists to test**, because a model
that draws its chunk can commit to one side.

**And the refusal.** On a different table, one stemmed glass has a foot so
narrow that it tips before it slides. The shared arithmetic refuses it from the
measured foot width, before the policy is asked. The policy never sees it. The
other glasses are pushed as usual, and the run ends *correct but incomplete*.
That is the right result. Nothing the policy learned could improve it, and
nothing it produced could make it worse.

**The correction, now that it has run.** The refusal works as described. The
first push does not. On unseen tables, the policy's chunk starts in roughly the
right place but points 22 to 27 degrees away from the teacher's heading. The
hand reaches a quarter of a metre behind its fingertips. So on a crowded table
it meets a neighbour on the way down, and the push ends before any glass is
touched. The leaning and slowing were never reached. The folder's `README.md`
has the counts.

![The same held-out table with the teacher's push and the policy's chunk side by side: the teacher brings the fingertips down 10 mm clear of the glass's rim and the 266 mm body of the hand clears every other glass, while the policy brings them down 3 mm inside the rim of the glass it means to push, so the examiner stops the descent and reports the chunk blocked with nothing moved; over the whole run 331 of 438 pushes end that way and 308 of them go to a glass that has already been pushed.](../../images/03-blocked-on-the-way-down.png)

## What it needs

It needs **[LeRobot](https://github.com/huggingface/lerobot)**, which holds ACT
and Diffusion Policy, with **PyTorch** underneath. LeRobot is Apache-2.0. That
is the permissive kind of licence [the implementation
notes](../../../01-rack-one-glass/implementation-notes.md) record for the rest of the project. No
weights are downloaded. So the weights this solution produces carry no one
else's terms. [Solution 5](05-smolvla-as-it-downloads.md) and [solution
6](06-smolvla-fine-tuned.md) both carry borrowed weights.

It needs **[solution 2](02-geometry-ranked.md) working**, because it is the
teacher. Without it there are no demonstrations. With a poor teacher, the
student has nothing worth copying. [The plan](../solutions-plan.md) builds the
two in that order.

It needed **two things the examiner did not have**. [The
plan](../solutions-plan.md#the-examiner-had-to-grow-before-cars-3-to-6-could-run)
recorded both when it audited `bench.py`. The first was a **rendered view from
straight above**. The examiner rendered only from the arm's side, for films.
The second was a **path that accepts a chunk of waypoints**. `push()` takes a
parameterised push and *is* the macro that expands it. Both are now built, as
`bench/top_view.py` and `Bench.follow`. Every LeRobot policy expects pictures
and a control-rate action space. So these were the real price of using one off
the shelf. Solutions 1 and 2 need neither.

It needs **demonstrations**, which cost only arm time on the examiner's tables.
They are drawn from the demonstration band. The design says to over-represent
crowded corner cases, so the hardest tables sit inside the training data.
**That part is not done.** The demonstrations come from consecutive table
numbers. So crowded corners are as rare in training as on the examiner's
tables.

It needs **compute, and less than any other solution here.** Training takes
hours. The dataset is small: thousands of pushes, each a picture and a short
chunk. The network is small next to the foundation models in solutions 5 and 6.
It only has to learn this one cell's pictures of this one task.

**In the end nothing was rented.** This document first budgeted tens of dollars
for a small accelerator. That is still the right figure for anyone who wants
one. But a few tens of millions of parameters, on a few thousand small
pictures, fit on an Apple M4's own graphics processor. Each training seed took
about an hour. So the demonstrations, the seeds and the held-out run were all
made on the project's own machine. For comparison, renting an accelerator costs
about a hundred dollars a weekend. A small one costs about five hundred a
month.

At run time it needs **very little**: one forward pass per chunk for ACT, and
several for the denoising way. A push takes the arm seconds, so this barely
matters. The compute column on the scorecard shows the difference.

Once fitted, it needs **a weights file kept in step with the examiner**. Change
how the top view is rendered, the macro whose waypoints became the labels, or
the error in the readings. The file is then out of date, and no test of the
code would notice.

## Where it is strong and where it breaks

It has five strengths.

**Nothing about pushing has to be written.** It needs no friction model, no
candidate generator, no hand-chosen features and no geometry. The method is a
dataset and a fitting procedure, and a program made the dataset.

**The output is native.** It emits a chunk because it is built to. So the
examiner's choice to accept waypoints costs it nothing.

**Labels are free and plentiful**, because the teacher is code and the tables
are simulated.

**It is cheap to train and to run**: hours on a laptop, and one forward pass
per push.

**It is a measurement**: student against teacher, on the same tables and the
same scorecard, with everything else held still.

It has five weaknesses, and the first three cannot be engineered away.

**The ceiling is the teacher.** Every label came from solution 2, and nothing
in behaviour cloning judges an outcome. So **this solution cannot beat solution
2 by much on the pushes it copies.** It might beat it in two small ways. A
fitted function averages many examples, so it can be steadier than its teacher.
And it can express motions the macro cannot. But it cannot discover that a
different glass or destination was better. [Solution 4](04-a-world-model.md)
can, and that is the sharpest difference between the two.

**Filtering biases it towards what the teacher does well**, as [choosing which
demonstrations to
keep](#choosing-which-demonstrations-to-keep-and-the-bias-it-buys) explains.

**It needed examiner work the first two solutions did not.** The top view and
the waypoint path are built. Two smaller costs are paid on every push. The
glass and the aim are read back off the waypoints, outside the policy. And a
network can emit a coordinate the jaw cannot reach. So every chunk is pulled
inside the jaw's limits, and the count is reported. In practice, every pulled
waypoint was pulled in **height** only, by at most 2.3 millimetres. None of the
six hundred chunks measured asked for a place off the table. So the limit that
bites is how low the jaw can go, not how far it can reach.

**It is blind inside a chunk, and it cannot refuse.** The force monitor is not
built, so only the jam threshold stops a chunk. Refusals come from the shared
gate in front of the policy, not from the policy.

**It cannot explain itself, or say when it is lost.** When solution 2 is wrong,
you can print its candidates and scores. When this policy is wrong, you can only
look at the picture and guess. It has no confidence output. A table unlike its
data looks the same in its output as a familiar one. With training that varies
by seed, this is why [the
examiner](../the-examiner.md#two-things-this-scorecard-needs-that-problem-2s-did-not)
insists that one run is not a measurement.

## The commonest refusal reason is not the reason it fails

The reason given most often for a glass left on the table is **"push budget
spent"**. That reads as if the solution was stopped early and would do better
with more tries. It would not, and the real reason points at a different
repair.

The budget is shared: four pushes per glass and sixteen per table. [The
examiner](../the-examiner.md#what-the-examiner-measures) holds it, so that push
counts mean the same thing for every solution. Raising it is easy to test. Each
of the three seeds was run again over the same fifty held-out tables at four
budgets, with nothing else changed. The table gives glasses racked, out of 251,
for each seed at each budget.

| budget, per glass and per table | seed 0 | seed 1 | seed 2 |
|---|---|---|---|
| 4 and 16, the shared budget | 64 | 51 | 63 |
| 8 and 32 | 65 | 52 | 64 |
| 16 and 64 | 65 | 52 | 64 |
| 32 and 128 | 66 | 52 | 64 |

**Eight times the budget buys one or two glasses.** Meanwhile the pushes made
rise from about 440 to about 3,000. So the budget is where the run stops, not
why it stops.

It stops because of the blocked descents. Three pushes in four end before they
begin, because the jaw meets a glass on the way down. A push that moves nothing
still costs a push. More budget only buys more of the same. So "budget spent"
is the last of a line of wasted attempts. The repair is to stop wasting pushes,
not to allow more of them.

Two notes help when reading the other solutions beside this one. First, the
budget is not a limit that binds everyone. Solutions 1 and 2 never spend it in
fifty tables. [Solution 4](04-a-world-model.md) spends it for ten glasses of
251. It shows up here because this solution wastes pushes. Second, the budget
stayed at four and sixteen after this test. These are the held-out tables. A
budget chosen because it scored better on them would taint every later result.

## Most of what the policy has to learn is the coordinate system

The blocked descents come from the policy putting the jaw down about 50 mm from
where the teacher did. That looks like a limit of the model. Measurement says
it is mostly a limit of **how the target is written down**. That is cheaper to
change.

A chunk's waypoints are now written as positions on the table. So the numbers
depend on where the table's origin is. The same push can be written as an
offset from the glass it pushes. That offset can be turned once more, so one
number runs along the push and the other across it. The motion is the same in
all three. Only the description changes.

**A description with less spread is easier to learn.** Fitting a line through
points in a narrow band is easier than through widely scattered points. So the
three descriptions were measured on 477 demonstrations from 400 tables. The
table gives the spread as a radius, which is the typical distance from the
middle. Its two columns are where the chunk starts and where it ends.

| how the target is written | where the chunk starts | where the chunk ends |
|---|---|---|
| as a position on the table | 135.8 mm | 127.8 mm |
| as an offset from the target glass | 46.2 mm | 39.2 mm |
| as that offset in the push's own frame | **7.5 mm** | **25.8 mm** |

The first column matters most. Where the chunk starts is where the jaw comes
down, and that is what the blocked descents are about. Written on the table, it
varies by 135.8 mm. Written in the push's own frame, it varies by **7.5 mm**.
The spread *across* the push direction is exactly zero.

That zero comes from how the teacher works. It always brings the jaw down on
the line through the target glass. It lands a near-constant 46 mm behind the
glass's measured middle. So in the right frame, the descent point is almost one
number. Most of the 135.8 mm the policy must learn is just where things are on
the table. The examiner already measures that and hands it over for free.

The second column is different. The end point keeps 25.8 mm of spread in the
push's frame. That spread is real. It is how far the teacher chose to push,
which changes from table to table. So the measurement splits the two cleanly.
Where to come down is nearly fixed, once the glass and heading are known. How
far to push is a real decision that must be learned.

**One caveat: this is not a free improvement.** To use the push's own frame,
the policy must output a glass and a heading, because those define the frame.
That is how [solution 1](01-one-fixed-nudge.md) and [solution
2](02-geometry-ranked.md) describe a push. So the change moves this solution
towards its teacher's vocabulary, and away from plainly copying a path. It may
be the right trade, and a large one. But it changes what this solution *is*. If
it is made, it should sit beside the present result as a variant, so both
readings survive.

Nothing has been fitted in the new frame yet, so it has no score. The numbers
come from `03-imitation-from-demonstrations/measure_frames.py`. That script
trains nothing and reads only the demonstration band.

## Telling the policy where the glasses are, and what it changed

The last section found that the policy spends most of its effort locating
things. So the next question is: what if it is simply told where the glasses
are? This is a safer repair than changing the frame. The policy's answer stays
the same, and only its input grows. The short version is that **it bought
consistency, not glasses**.

A network has a fixed number of inputs, but a table holds a varying number of
glasses. The way round this is the one [solution 4](04-a-world-model.md) uses.
There are six fixed slots, and each one describes one glass or stands empty.
Glasses fill the slots in a set order, so the same table always gives the same
row. Six is enough, because the examiner never puts more than six glasses on a
table. Each slot holds six numbers: two for position, the widest width, the
height, the foot width, and a flag for whether the slot is used. Without the
flag, an empty slot of zeros would look like a glass at the table's centre.

This is cheap. The row is 36 numbers. The model grows from 51,598,725 numbers
to 51,637,125, which is less than one part in a thousand. The readings are not
privileged. The examiner hands them to every solution at the start of a push.
So any change in score comes from the information, not from a bigger model or
an unfair advantage.

**How closely it copies the teacher** changed as the last section predicted.
The table gives the distance from the teacher's chunk for the three fits of
each kind. One column is tables the fits were trained on, and the other is
tables they never saw.

| | tables it was fitted on | tables it never saw |
|---|---|---|
| from the picture alone | 20.4 to 20.7 mm | 48.1 to 52.4 mm |
| with the readings | **17.2 to 19.3 mm** | 48.3 to 52.9 mm |

On seen tables, every fit with the readings is closer to the teacher than any
picture-only fit. On unseen tables, the two groups are the same. So the model
used the new information to fit its examples more exactly. It learned nothing
that carries over to a new table. It memorised better; it did not understand
better.

**What it did to the score** follows from that. Each column below is three fits
scored on the same 50 held-out tables, given as the average across fits.

| | from the picture alone | with the readings |
|---|---|---|
| glasses racked | 59.3 | 61.3 |
| the three fits separately | 64, 51, 63 | 61, 65, 58 |
| tables cleared completely | 2.0, between 1 and 3 | **3.0, every run** |
| glasses toppled | 10.7 | 10.3 |
| aim error, typical | 43.9 mm | 37.7 mm |
| arm travel a run | 2,245 mm | 1,824 mm |
| pushes blocked on the way down | 366.3 | 370.3 |

Two more glasses out of 251 is nothing. It is about four tenths of the
run-to-run variation, and this project does not report a number without its
spread. So **the readings did not raise the score.** They removed the bad fit
instead. Before, two fits racked 63 or 64 glasses and the third only 51. That
third fit cleared just one table. Now all three sit between 58 and 65, and each
clears exactly three tables. The spread on racked glasses halved, from 7.2 to
3.5.

That is a gain in how **dependable** the method is. One fit is now more
trustworthy, which matters when each fit costs an hour. It is not a gain in how
**good** the method is, because the average did not move.

The last row of the table says why. About 370 of 444 pushes are still lost to
a touch on the way down, and that number did not improve. The readings let the
policy aim about six millimetres better and travel a third less. So it did use
them, yet descents fail just as often. Aim was never the limit. **The limit is
the vertical approach itself.** The policy names a point, and the arm lowers
the jaw straight down onto it. Anything in the way ends the push. Better aim
cannot help while the approach is a straight drop. The obstacle is usually on
the way down, not at the target.

This variant sits beside the original, as the last section's caveat asks. The
picture-only score stays this solution's result, and this one is recorded next
to it.

## The general ideas behind this

Every part of this solution is a standard piece of modern practice. This
section gives each one in short, with a reference and with when it is the wrong
tool. The sections above hold the full explanations.

### Behaviour cloning

Fit a policy by supervised learning on pairs of what the demonstrator saw and
what it did. It is the oldest form of imitation learning. An early example
drove a vehicle from camera images, with a small network trained on a person's
steering. It is still the first thing to try when demonstrations exist.

It suits plentiful demonstrations and reactive tasks, where the next action
follows from what is in front of you. It is a poor choice when demonstrations
are scarce, when the task needs a long plan, or when the demonstrator cannot be
asked again. For more, see [imitation
learning](https://en.wikipedia.org/wiki/Imitation_learning).

### Compounding error, and dataset aggregation

[Compounding error](#compounding-error) explains the failure. The standard
analysis and the standard repair are both in **DAgger**, short for dataset
aggregation, by Ross and colleagues
([arXiv:1011.0686](https://arxiv.org/abs/1011.0686)).

DAgger works when the expert can be asked about any state you choose. That is
true here, because the expert is a program. It does not really work when the
expert is a person. Labelling thousands of states the policy wandered into is
slower and less pleasant than demonstrating the task well. That is the main
reason a programmed teacher is worth more than a human one for this method.

### Action chunking

Predict a short run of future actions in one pass and carry it out, instead of
one action per control step. ACT introduced this for fine manipulation on
low-cost hardware (Zhao and colleagues,
[arXiv:2304.13705](https://arxiv.org/abs/2304.13705)). It is now standard in
imitation policies. That includes the vision-language-action models [solution
5](05-smolvla-as-it-downloads.md) and [solution 6](06-smolvla-fine-tuned.md)
use.

It suits continuous, committed motions, such as a push, a wipe or a pour. It is
wrong when the scene can change faster than a chunk runs, because a chunk is
blind while it runs. In this cell nothing moves except what the arm moves. So
chunking is safe here. It would not be safe in a scene with people in it.

### Denoising diffusion, and Diffusion Policy

Learn to remove noise from a corrupted sample. Then generate by starting from
pure noise and removing a little at a time. The modern form is the denoising
diffusion probabilistic model (Ho and colleagues,
[arXiv:2006.11239](https://arxiv.org/abs/2006.11239)). **[Diffusion
Policy](https://diffusion-policy.cs.columbia.edu/)** applies it to action
chunks for robot control (Chi and colleagues,
[arXiv:2303.04137](https://arxiv.org/abs/2303.04137)).

It suits problems where several actions would all be good. It is wrong when the
answer is unique and speed matters, because the extra passes buy nothing. Here,
uncrowding a table has many good answers, which argues for it. And a push runs
at the speed of an arm, not of a processor, so the extra passes are affordable.

### Mode averaging under a single-answer loss

Fit a model to give one output while lowering its average error over examples
that disagree. It will give something between those examples. When the
examples are two sensible choices, the answer between them is often not
sensible at all. [The second way](#the-second-way--diffusion-policy) shows this
on a crowded pair.

The symptom misleads. Training error looks fine and the behaviour looks timid.
The natural guess is that it needs more data or more training, and that guess is
wrong. More examples of both choices make the averaging worse, not better.
There are two fixes. One is to represent a distribution instead of one point,
as the denoising model does. The other is to make the choice part of the input,
so the examples no longer disagree.

### Distilling a planner or a program into a policy

Use a slow but good procedure as the teacher for a fast network. The network
then does at run time what the procedure did offline. That is exactly how
solution 2 and this solution relate.

It suits a teacher that is correct but too slow where it is needed. It also
suits a teacher that needs information only available in training. It is wrong
when the student is meant to beat the teacher, because copying has a ceiling.
Here, solution 2 is not slow. Distillation is used to measure whether the
mapping can be learned at all.

## Where it sits among the other five

[The six solutions](overview.md) form a ladder, ordered by how much of each one
was fitted in this cell. This is the first one where everything was fitted
here. The scores of all solutions side by side are in [the
comparison](../../results/README.md).

**Against [solution 1](01-one-fixed-nudge.md)**, the question is whether any
learning beats a fixed nudge. Solution 1 fits nothing and costs almost nothing
to run. If this solution cannot clear more tables, none of its machinery has
earned its place.

**Against [solution 2](02-geometry-ranked.md)**, it is student against teacher,
and this is its most useful pairing. The gap shows whether a good push can be
learned from a picture. A student close to its teacher says this kind of policy
is good enough. A student far short says it is not. The two narrow ways it could
beat its teacher are a steadier push and a motion the macro cannot express.

**Against [solution 4](04-a-world-model.md)**, the question is whether to plan
with a model or learn the push directly. Solution 4 learns how the world
changes, and tries candidate pushes forward before it chooses. So **it can
find a push nobody demonstrated**, which this solution cannot. It pays on every
push. [The examiner](../the-examiner.md) puts its run-time cost at hundreds or
thousands of times a fixed nudge's. It also needs a world model good enough to
plan with. So this solution is cheap and capped by its teacher. Solution 4 is
costly and capped by what its own encoding can express.

**Against [solution 5](05-smolvla-as-it-downloads.md)**, it is fitting here
against borrowing whole. Solution 5 runs SmolVLA as it downloads: about 450
million parameters, pretrained on 487 community datasets of real
teleoperation, with nothing fitted here. It brings broad experience of
manipulation and none of this cell. This solution brings the opposite: a small
network that has seen only this cell.

**Against [solution 6](06-smolvla-fine-tuned.md)**, the question is where the
fitting starts. Solution 6 continues SmolVLA's training on this cell's data,
with low-rank adaptation. That is this solution's method, applied to borrowed
weights instead of random ones. Read together, the two separate what the
demonstrations are worth from what the pretraining is worth.

Read as a ladder, the six show what each step of fitting buys. This one does
all its fitting here, from nothing, on examples a program made for free. It is
the cheapest honest attempt at learning this task. Its limits are also the
easiest to state in advance.

← [Geometry generates, a model ranks](02-geometry-ranked.md) · [A world model,
then plan with it](04-a-world-model.md) →
