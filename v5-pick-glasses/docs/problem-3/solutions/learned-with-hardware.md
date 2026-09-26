# Problem 3 — learned approaches that need more than a simulator

These were in [`solution-overview.md`](solution-overview.md) and were moved
here, because none of them can be built and trained inside this project's
simulation alone.

## The test each one failed

A solution belongs in the main overview if **everything it needs can be
produced by Gazebo on the machine this project runs on**: an Apple Silicon Mac
with no NVIDIA graphics card, no robot on a bench, and no real-world data. In
practice that is four conditions:

1. **No artefact from outside.** Any model it uses has to be trainable from
   what the simulator renders. A downloaded file of weights fitted to
   photographs of the real world is not reproducible here, however good it is.
2. **No sensor the simulator does not have.** Gazebo gives this cell a depth
   camera, pad contact sensors and a wrist force-torque sensor. Anything else
   is a purchase order.
3. **No graphics card it has not got.** Anything needing compiled CUDA kernels
   is out. Apple's MPS backend runs, with some operations falling back to the
   processor.
4. **Hours, not days.** A method that takes a week of continuous simulation to
   train cannot be iterated on, and a method you cannot iterate on will not be
   debugged.

Everything below fails at least one of those. Nothing below is wrong. Each is a
reasonable answer to this problem, and several are what a well-resourced team
would reach for first. They are here so that the choice stays visible, and so
that the reason for not taking them is the honest one — the machine and the
data, not a view about learned methods.

None of them needs a different *algorithm* to become usable. They need a
different *setup*: a graphics card, or a camera on a real table, or both.

---

## Learn to push

> **Fails condition 4, but by much less than this document first said.** The
> figure below — eleven days for one reward function — was worked out for
> Gazebo, and the cell has since been rebuilt in MuJoCo. Measured there, one
> reward function is about **29 core-hours**, not eleven days. What still holds
> is that a reward function needs several attempts, which multiplies that by
> five or so, and that GPU-batched simulators are what make this comfortable
> elsewhere and none of them runs here. *An evolutionary search over a handful
> of strategy parameters gets some of the same benefit in under three
> core-hours, and it is in
> [solution 11](11-search-a-push-strategy.md).*

*Learned, as the decider. Let the arm discover which pushes separate objects,
by trying them in simulation and being rewarded when it works.*

### What it is

Three methods get called "learning to push".

**Reinforcement learning** is trial and reward. The arm is shown the table,
picks a push, and a single number — the **reward** — says how good it was. What
is trained is a **policy**: a function, usually a small neural network, from
what is seen to what to do. One attempt, fresh table to finish, is an
**episode**. Training runs episodes over and over, nudging the weights towards
whatever scored higher. There is no teacher; the only signal is the score.

**Imitation learning**, or behaviour cloning, has a teacher. Something does the
job many times — a person with a joystick, or another program — and each instant
is recorded as a pair: what was seen, what was done. Training is then ordinary
supervised learning. No reward, no exploration, and the ceiling is the teacher.

**Learning a forward model** learns what *happens* rather than what to do. Give
it the arrangement and a proposed push; it predicts the arrangement afterwards.
Deciding comes after, by trying candidate pushes against the model and keeping
the best. It is a learned stand-in for physics you do not have.

### Why anyone does it this way

Pushing is contact, contact is friction, and friction is the number nobody
measures. The classical alternative needs the friction under the object and how
its weight is spread over its base, and the second of those is statically
indeterminate — no unique answer exists even in principle. Learning samples
outcomes instead of deriving them.

The research line aimed at this exact task is called **singulation**: pushing
objects apart until one stands alone enough to be gripped. It goes back well
over a decade, first as hand-written push heuristics, later as learned push
proposals, and it is nearly always motivated by a pile where the segmenter
cannot say how many objects there are.

The best known work joining pushing and grasping is Zeng and colleagues'
*Learning Synergies between Pushing and Grasping with Self-supervised Deep
Reinforcement Learning* (2018), shortened to **VPG**. Both behaviours are
learned from one overhead picture: each pixel gets a score for "push here" and
one for "grasp here", and only grasp success is rewarded. Useful pushes appeared
anyway — it learned to shove a tight cluster apart so a grasp became possible,
without being told pushing had a purpose. I am confident of that paper, not of
its trial counts, so I quote none, and I name no singulation papers because I am
not confident of particular titles.

### How it would work here

**Observation:** the overhead picture, or — since problem 2 has measured it —
ten numbers: five glass centres plus each base width.

**Action:** a straight push, with a start point, a direction, a length and a
height.

**Reward:** a point when a pair crosses 140 mm apart, a large fine for a topple,
a small fine per push.

The reward is the hard part, not the training. A reward is a **score**, and what
this problem has are **constraints**. "Never topple a glass" is not a quantity;
written as a fine it becomes a price, and a price is a trade the policy may
make. The project also counts a refusal as a success, and nothing rewards an arm
for declining. And a shaped reward gets gamed: pay for increases in the minimum
pairwise distance, and shoving one glass to the far corner scores best every
time.

Nor can a policy be *told* not to topple a glass. It is a function from
observation to action; there is no field in it for a rule, so the reward is the
only channel. A run-time check can veto an unsafe push — but that check is the
geometry this project already has, and it, not the policy, is doing the safety
work.

### A worked example

Set the topple fine at ten points and a separation at one. Ten separations now
buy one broken glass, so a policy that topples one glass in twenty runs still
scores well and gets selected for. Raise the fine to a thousand: doing nothing
scores zero, which beats any push carrying risk, and the policy learns to stand
still. Between them lies a number that behaves, found by training again, and it
still means "a topple is worth this many separations", never "do not".

### What it needs

Gazebo Harmonic runs headless and resets, so episodes are possible in principle.
The cost is throughput. One episode — reset, spawn five glasses, let them
settle, push slowly, look — will not come in under about twenty seconds, or 180
an hour. Contact-rich policies are trained on tens of thousands of attempts at
the very least, so 50,000 episodes is about **eleven days of continuous
running**, or three days across four parallel instances. That is one reward
function, and the reward needs several attempts.

The usual escape is a GPU-batched simulator running thousands of worlds at
once. **This machine is an Apple Silicon Mac with no NVIDIA GPU.** That rules
those out specifically. Isaac Sim and Isaac Lab are CUDA-only, with no macOS
build at all, and MuJoCo's batched version, MJX, wants JAX on an NVIDIA GPU or
a TPU. Plain MuJoCo runs natively, so rebuilding the cell there is possible,
but it buys single-world speed, not thousands of worlds. PyTorch's MPS backend
trains a small policy network happily; the network was never the bottleneck.

**That rebuild has since happened, and single-world speed turned out to be
enough to change the answer.** Problem 3's bench, `problem-3-sim/bench.py`, is
MuJoCo, and it has been timed rather than estimated: one push costs about a
seventh of a second of wall clock against nearly eight seconds of simulated arm
motion, so the physics runs fifty to a hundred times faster than real time. A
full fifteen-push episode is about two seconds. Fifty thousand of them is
therefore **roughly 29 hours on one core, or seven across four** — not eleven
days. The paragraph above is kept because its reasoning is the reasoning to
use; only its engine was wrong. [Solution
11](11-search-a-push-strategy.md) has the measured budget, and the
same arithmetic is what makes an evolutionary search over a few parameters an
afternoon's work rather than a week's.

Licences need the same look the grasp models get in
[the licence picture](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/04_models-that-grasp.md#5-the-licence-picture):
research pushing code ships without a licence file just as often, which grants
nothing.

### What it is good at

It never needs μ. It learns what pushes tend to produce, whatever the friction
happens to be.

It handles clutter with no geometry in it. When objects are a jumble of unknown
shapes, overlapping, and the segmenter cannot say how many there are, "which
push opens something up" has no closed form. That is the case singulation exists
for, and it is real.

It finds behaviours nobody would write down — pinning an object against a wall,
or moving one object with another.

### What it is bad at

The sample cost and the reward design, above.

Explaining itself. The rules refuse with "this glass tips before it slides,
because its base is 45 mm and the gripper cannot get below that". A policy that
does not push has nothing to say, and this project needs its refusals legible.

And the decisive one. This table holds five discs, one known kind, on a flat
surface, with centres and base widths already measured. The state is ten
numbers, and choosing which glass to move and where is a circle-packing check
against a rectangle — exact, instant, readable. A policy would spend a month of
wall-clock time rediscovering, approximately, what that check gives exactly.
Singulation policies earn their keep on a jumble of unknown shapes. This is not
a jumble, and the shapes are known.

### How it fails

**The sim-to-real gap, worse for pushing than for most tasks.** Most sim-to-real
trouble is appearance or timing. Pushing turns on friction, which in a simulator
is a configured constant in a contact solver, not a measurement, so a policy
trained in Gazebo learns that solver. And μ does not merely shift the outcome.
The line between sliding and tipping is `h < a / μ`, so μ moves the boundary
between a safe push and a broken glass: a height safe at μ = 0.3 topples the
same glass at μ = 0.5. Training across a range of μ is the standard answer; it
multiplies the episode count and yields a timid policy.

**A silent topple.** The method learns from failures it has experienced. Every
topple in simulation is free; every topple on a real table is unrecoverable,
because nothing in this project can stand a glass back up.

**A sixth glass.** The policy is trained on arrangements it saw. Change the
count, the zone or the kind, and there is no guarantee and no error message.

### When it would be the right choice

It is the right answer to the harder version of this problem, and that version
is real. Put a tote of mixed unknown objects on the table — different shapes,
some lying down, some on top of each other, the segmenter unsure how many there
are — and arithmetic has nothing to compute against. Then pushing to singulate
is a genuine answer and VPG's result is the relevant one. It is also right where
failures are cheap and plentiful: wooden blocks on a robot that runs all night,
or a lab with NVIDIA hardware where the episode budget is hours, not weeks.

Keep it on the list for the day the table stops holding five glasses of one
known kind.

---

---

## Copy a scripted expert

> **Fails condition 4, and borderline on 1.** Eleven unattended hours to
> generate demonstrations is affordable; training an action-chunking
> transformer or a diffusion policy on top of them, on a processor with
> partial graphics support, is not something you do between experiments. The
> policy classes worth using also assume a graphics card as a matter of
> course.

*Learned, as the decider. The demonstrations do not need a human: the geometric
planner is itself an expert, and it can generate thousands of correct pushes in
simulation overnight.*

### What it is

**Imitation learning** trains a model to copy something that already does the
job. Its simplest form, **behaviour cloning**, is ordinary supervised learning:
at every instant of a demonstration record the **observation** — everything the
arm can sense — and the **action**, what it did next. A network learns to
predict the second from the first. No reward, no exploration: solution 5 learns
from a number grading a push, this from an example of a good one.

**The demonstrations need not come from a person.** Solution 3 is an expert,
and every headless run of it in Gazebo is a correct demonstration — one every
twenty seconds, nobody holding a controller. So imitation here is not a way of
avoiding a planner, but a way of **compressing a planner that already works
into one fast reactive function**.

The classic failure runs like this. The policy is slightly wrong, so it drifts
into situations the demonstrations never covered. There it is more wrong, so it
drifts further — **compounding error**, with a worst case growing as the
*square* of the episode length. The mitigation is **DAgger**, dataset
aggregation (Ross, Gordon and Bagnell, 2011): run the half-trained learner, let
it wander, ask the *expert* what it would have done at each state it reached,
and retrain on those labels. The dataset then covers where the learner goes,
not where the expert goes.

### Why anyone does it this way

DAgger normally costs a human to label the states a robot got itself into. Here
the expert is a hundred lines of Python: freeze the world, survey it, ask the
planner, and get a label in a second, unattended, overnight. The famous
weakness of imitation is nearly free to fix here, because **there is already a
correct program to ask.**

### How it would work here

**The expert** is solution 3 running headless, discarding any demonstration
that toppled a glass. **The observation at each control step:** the wrist RGB-D
frame at 320x240, six joint angles, six wrist force and torque readings, two
pad contacts, and the destination in the gripper's frame. The **action** is a
small delta on the wrist pose.

**Action-chunking transformers (ACT)** —
[github.com/tonyzhaozh/act](https://github.com/tonyzhaozh/act), MIT licence,
Zhao and colleagues, 2023. It predicts not one action but a **chunk** of the
next *k* actions in one pass. One step at a time makes a policy dither, and at
10 Hz dither is a knock. A chunk commits to a short smooth movement, which is
what a push is, and that cuts the number of decisions per episode — and
compounding error compounds per decision.

**Diffusion policies** —
[github.com/real-stanford/diffusion_policy](https://github.com/real-stanford/diffusion_policy),
MIT licence, Chi and colleagues, 2023. A diffusion model starts from noise and
removes a little at a time; a diffusion policy does that to an action chunk,
conditioned on the observation, in about ten passes of a small network. The
gain is **multimodality** — a crowded glass can correctly go left or right, and
a network emitting one number averages the two and pushes into the neighbour.

**Frameworks.** [LeRobot](https://github.com/huggingface/lerobot), Apache-2.0,
carries both, on [PyTorch](https://pytorch.org/), BSD-3-Clause. No NVIDIA GPU
here, but PyTorch's **MPS** backend trains on Apple Silicon and these networks
are small. Set `PYTORCH_ENABLE_MPS_FALLBACK=1`; some operators still drop to
the CPU, and how well LeRobot's loop is tested on MPS is uncertain. Unlike
solution 5, though, **the bottleneck is Gazebo episodes, not gradient steps**.

### The feedback loop

What decides this solution is **what the policy sees**, and a policy given the
wrist image alone is **open-loop within a push**. At the 50 mm push height the
closed jaw fills the frame, and the glass wall against it is a near-textureless
curve 40 mm from the lens, inside the depth camera's minimum range. Vision goes
blind as contact starts.

So add the wrist force and the pads. **The loop, at 10 Hz:** every 100 ms read
the frame, the joints, the wrist reading and the two pads; get back a chunk of
20 actions, two seconds' worth; execute the first 10 and re-predict. Ten hertz
comes from the physics — the push runs at 10 mm/s, so one step is one
millimetre — and inference must fit in that 100 ms on MPS.

A 250 g glass at μ = 0.3 needs 0.74 N to keep sliding, and across 150-400 g and
μ from 0.3 to 0.5 an ordinary push stays under 2 N horizontal. Meet a second
glass, the rack, or a glass that sticks, and the reading leaves that range
within one step — which demonstrations containing aborted pushes teach the
policy to stop on.

### A worked example

Solution 3's glass B: 75 mm across, 250 g, pushed 48 mm — 48 control steps at
10 Hz, three chunks. At step 12 the pads fire, contact.

At step 31 the horizontal force goes 0.9 N to 4.2 N in two steps: B has caught
a third glass the survey placed 6 mm wrong. **The picture-only policy has 1.7 s
of chunk left and executes it, at 10 mm/s, into a glass.** The policy with
force in its observation sees it at once; its worst case is the rest of the
ten-step commitment, one centimetre.

### What it needs

Solution 3 built, because it is the expert, and a harness: Gazebo Harmonic
([gazebosim.org](https://gazebosim.org/), Apache-2.0) resetting headless,
spawning five glasses across the zone's 45-105 mm and 150-400 g ranges,
recorded at 10 Hz through [ros2_control](https://control.ros.org/).

**Data volumes.** Published ACT results learn real tasks from tens of
demonstrations each; exact counts are uncertain, so treat fifty as an order of
magnitude. A push is simpler: a few hundred may do, a few thousand is
comfortable. At twenty seconds each, two thousand is eleven unattended hours,
or under three across four Gazebo instances — eleven hours a person on a
joystick would stay awake for.

**The asymmetry is narrowness, not volume.** A scripted expert only shows
states it visits: approaches that worked, contacts where the survey said. The
states that matter are the ones it never reaches — a glass that sticks, a jaw
that meets a neighbour first. Those must be manufactured, by perturbing the
spawn or injecting survey error, and labelled by DAgger.

### What it is good at

**No reward function**, so solution 5's argument about pricing a toppled glass
disappears: "never topple" stays a constraint the expert enforces.

**Reactive at 10 Hz on sensors the planner reads once**, where solution 3 reads
the wrist force as a trigger and then stops.

### What it is bad at

**Its ceiling is the expert**; what it learns about contact is the simulator's
friction constant; and it puts glass proportions inside weights, breaking the
repo's one rule quietly.

**It cannot explain a refusal.** Solution 3 says "its base is 45 mm and the
gripper cannot get below 50 mm". A policy that stops has nothing to say, and
this project treats refusals as results.

### How it fails

**Drift**, showing as a push that starts well and curves. DAgger answers it
cheaply here.

**A chunk executed through a surprise**, the picture-only case: a fault in the
observation vector, not the training.

**Silent narrowing.** A sixth glass, or one near the rack: the expert refuses,
the policy pushes.

### When it would be the right choice

Not yet. **If a planner good enough to be the expert already exists, the
policy's only advantage is speed — and speed is not the bottleneck.** Solution
3's destination search is four comparisons on ten numbers: microseconds. A push
costs arm motion, fifteen to twenty seconds. Trading microseconds for
microseconds buys nothing, and costs a training loop, a weights file and an
unreadable refusal. Three things change that.

**The reactive half becomes the bottleneck**, when runs fail during contact
rather than planning. What is needed then is a response within 100 ms on force
and touch, and the rules alternative is a thicket of thresholds.

**The surveys become the bottleneck.** Solution 3's worst complaint is that
every push costs a survey. A policy working from the wrist image needs one only
to pick a destination, so several pushes run under one — seconds of arm motion
saved, and the first economic case.

**The expert stops existing.** Problems 4 and 5 bring several kinds, then kinds
nobody measured. A tray of jumbled glassware has no destination search, because
there are no clean footprints. A planner that cannot be written cannot be
compressed, and the choice moves to solution 5's ground.

---

← [The solutions that do fit](solution-overview.md)
