# Step 4 — other ways to choose where to hold it

[`step4-where-to-hold-it.md`](step4-where-to-hold-it.md) explains how the arm
chooses a grip today: one rule per kind of glass, applied to the measured
profile. This document puts that method next to the others that could do the
same job, and says which of them to try next.

There are only two ways to answer "where do I hold this?": work it out from a
measurement, or learn it from examples. Everything below is one of those two,
or a way of correcting the answer once it exists. Some of them overlap, and
two of them are only useful together.

| Approach | What it does | What it runs on | Suitability here |
| --- | --- | --- | --- |
| **Rules on the profile** | one sentence per kind, applied to the measured outline | NumPy, in `glasses/rules.py` | good, and in use |
| **Ranked search** | scores every possible grip instead of returning the first one | NumPy, [MoveIt 2](https://moveit.ai/) to ask what the arm can reach | best next step |
| **Feel for it** | when the fingers meet nothing, hunt for the stem by touch | the sensors already in the cell, through [ros2_control](https://control.ros.org/) | cheap, and nothing new to install |
| **Camera in the loop** | corrects the aim on the way down | [OpenCV](https://github.com/opencv/opencv), on the wrist camera | useful, but only fixes aiming error |
| **Score grasps on a spun mesh** | classical grasp planning on a mesh built from the profile | [trimesh](https://trimesh.org/), already a dependency | redundant — same answer, more arithmetic |
| **Copy an expert** | learns the movement by watching the rules do the job | [PyTorch](https://pytorch.org/), [LeRobot](https://github.com/huggingface/lerobot) or [ACT](https://tonyzhaozh.github.io/aloha/) | fits, once search and touch are done |
| **Reinforcement learning** | discovers a grasp by trial and reward | [Stable-Baselines3](https://stable-baselines3.readthedocs.io/), on [Isaac Lab](https://isaac-sim.github.io/IsaacLab/) or [MuJoCo](https://mujoco.org/) | poor fit |
| **Off-the-shelf grasp network** | point cloud in, ranked grasps out | [Contact-GraspNet](https://github.com/NVlabs/contact_graspnet), [GraspNet-1Billion](https://graspnet.net/), [AnyGrasp](https://graspnet.net/anygrasp.html) | possible now, and still answers the wrong question |
| **Depth completion** | invents the depth a see-through glass did not return | [ClearGrasp](https://sites.google.com/view/cleargrasp), [TransCG](https://github.com/Galaxies99/TransCG), [DREDS](https://github.com/PKU-EPIC/DREDS) | not needed while the glasses are opaque |

## What each one actually does

### Rules on the profile

Write down a sentence about glassware, and apply it to whatever the camera
measured. This is what the project does now, and
[`step4-where-to-hold-it.md`](step4-where-to-hold-it.md) walks through it step
by step.

**Needs:** NumPy, and nothing else. No training, no dataset, no internet.

**Good:** you can read the rule, and you can read the reason when it refuses.
A glass of a size nobody has seen needs no change at all.

**Bad:** it produces one answer. If that answer is 3 mm out, there is no
second plan.

### Ranked search

The same rules, but they stop picking a single winner. They hand back a list,
best first.

The rule scores every height in the allowed band, from every direction the arm
could come in, and every wrist rotation. Each option gets marked on how upright
the wall is there, how much of the pad would touch, whether the arm can reach
that pose, and whether the wrist can still turn the glass over afterwards. The
arm tries the best one. If that fails it tries the next.

**Needs:** NumPy for the scoring, and [MoveIt 2](https://moveit.ai/) — already in the project — to
answer "can the arm reach this?"

**Why it matters:** most failures today are not "this glass cannot be held".
They are "this glass cannot be held *the first way tried*".

### Feel for it

The fingers are sensors too. If they close and find nothing, look around with
them.

The fingers close slowly. Each fingertip has a contact sensor, so the arm knows
the moment it touches something and what the gap was at that moment. If they
close all the way and touch nothing, the stem is not where it was expected. So
the arm opens, moves 3 mm up, and closes again. Still nothing? Then 3 mm down.
A stem usually turns up in two or three tries.

**Needs:** nothing new. The contact sensors and the wrist force sensor are
already in the cell.

The project already says the last millimetres should be felt rather than
driven. At the grasp, it does not yet follow through.

### Camera in the loop

Do not trust one measurement taken from a distance. Keep checking on the way
in.

The rule says hold this glass 31 mm up. To put the hand there, the arm also has
to know where the glass stands on the table, and that number can be a few
millimetres wrong. So the camera keeps looking at the glass while the hand
comes down, and the arm keeps nudging sideways to keep the glass between the
two fingers. The closer it gets, the smaller the error.

**Needs:** [OpenCV](https://github.com/opencv/opencv), on the camera already on the wrist.

**Limit:** in the last few centimetres the gripper covers the glass and the
camera sees nothing. That is where feeling takes over.

### Score grasps on a spun mesh

Build a 3D model of the glass, and search its surface for good finger spots.

A glass is round, like a pot made on a potter's wheel, so the measured outline
can be spun around into a full 3D model. trimesh does this in one line — it is
how the glasses in the simulator are built. Then comes the usual grasp search:
take every pair of surface spots that face each other, and score whether the
fingers would hold or slide.

**Needs:** [trimesh](https://trimesh.org/), already a dependency.

**Why it is skipped:** the 3D model was built *from* the outline, so it holds
nothing the outline did not. All that searching arrives at the same height the
one-line rule gives, slower.

This is the family the older grasp planners belong to, and it is worth naming
them because they are what a robotics textbook would reach for first.
[GraspIt!](https://graspit-simulator.github.io/) scores grasps on a known mesh
by simulating the contacts, [GPD](https://github.com/atenpas/gpd) samples
candidate grasps straight out of a point cloud and ranks them with a small
classifier, and [Dex-Net](https://berkeleyautomation.github.io/dex-net/) built
the bridge to the learned methods by generating millions of scored grasps in
simulation and training on them. All three are strong on an object whose shape
you have and whose shape is awkward. None of them earns its place here. A solid of
revolution has no awkwardness left to find once the profile is known, so the
interesting question has already been answered by the time you would call
them.

### Copy an expert

Let something do the job many times, record it, and train a model to imitate
it.

1. Run the rules a few hundred times. Each run, record two things at every
   instant: what the camera saw, and where the joints were.
2. That is the dataset. Nothing is labelled by hand.
3. Train a policy — ACT, or a diffusion policy — whose job is: given this
   picture and this arm position, what is the next stretch of movement?
4. At run time the camera still measures the glass and the rules still decide
   where to hold it. The policy only drives the hand in over the last stretch,
   instead of MoveIt planning a path.

**Needs:** [PyTorch](https://pytorch.org/), with [LeRobot](https://github.com/huggingface/lerobot) or the original [ACT](https://tonyzhaozh.github.io/aloha/) code, a GPU, and the
collection runs.

**Proof:** [`v5-learn-pick-place`](../../v5-learn-pick-place) does exactly this
with blocks and reaches 74% on blocks it never saw.

**The catch:** the model has only ever seen these glasses, so their proportions
end up inside its weights — which breaks this project's one rule, quietly,
where nobody can read it. And when it fails it cannot say why.

### Reinforcement learning

No teacher. The arm tries, gets scored, and finds its own way.

The arm grabs. Glass ends up on the rack, points; glass dropped, no points.
Repeat a few hundred thousand times and the policy slowly gets good.

**Needs:** [Stable-Baselines3](https://stable-baselines3.readthedocs.io/) for the learning, and [Isaac Lab](https://isaac-sim.github.io/IsaacLab/) or
MuJoCo for the simulator — a run here takes about five minutes in Gazebo, which
would take a lifetime.

**Why it fits badly** is the three reasons set out further down.

### Off-the-shelf grasp network

Someone has already trained a large model on millions of grasps. Give it a 3D
scan, and it gives grasps back.

The workflow is: depth picture, then point cloud, then the network, then throw
away the grasps the arm cannot reach, then do the best one left. A point cloud
is a cloud of dots in space, one per bit of surface the camera saw.

**Needs:** [Contact-GraspNet](https://github.com/NVlabs/contact_graspnet), [GraspNet-1Billion](https://graspnet.net/) or [AnyGrasp](https://graspnet.net/anygrasp.html), on PyTorch. No data
collection: the weights are a download.

**Why it is skipped:** this one used to be impossible here and now is not,
which is worth saying plainly. The glasses are opaque by assumption, so the
depth camera sees them and there is a point cloud to feed the network after
all. What is left against it is not the input but the output. These models know
shapes in general, not glassware. Nothing in them knows that the stem is the
part of a wine glass to hold. They would return a ranked list of places
a two-finger gripper could close on a curved object, and the project already
has that answer, from a rule that can say why. On real see-through glassware
they would be impossible again, for the reason in the next section.

### Depth completion

Use a model to invent the depth the glass did not return. How it works is
explained under approach 10 in [`step1-approaches.md`](step1-approaches.md).
What matters here is what it unlocks: with the gap filled there is a point
cloud, and with a point cloud a grasp network becomes possible.

None of that is needed while the glasses are opaque. This row is here for the
day the assumption is dropped.

**Where it sits:** it decides nothing by itself. It is only ever the first half
of a chain — repair the picture, then a grasp network. That is two trained
models and two things that can go wrong, in front of a network that still does
not know a stem from a bowl. The rules get there in one step.

## The three that need a trained model

Three of the rows above train a model, and it is easy to think they are the
same idea. They are not. What matters is which part of the job the model takes
over, and who has to train it.

| | What the model learns | What it is given | What it hands back | Who trains it |
| --- | --- | --- | --- | --- |
| **Copy an expert** | the movement | the camera picture, and where the joints are | the next stretch of movement | you, from a few hundred of your own runs |
| **Grasp network** | what a good grasp looks like on any object | a 3D point cloud of the scene | a ranked list of gripper poses | someone else; you download it |
| **Depth completion** | what the missing depth should have been | the colour picture and the broken depth | a full depth picture | someone else; you download it |

The split that matters is what each model takes over. Copying an expert
replaces the *moving* — the rules still decide where to hold the glass. A grasp
network replaces the *deciding* — it never measures a glass or names a kind.
Depth completion replaces neither; it repairs the picture so that a grasp
network has something to work on.

## Which of them to do next

The rules are not producing wrong numbers. A glass that really is 189 mm tall
and 64 mm across measures 180 × 63, is called a stemmed glass, and the stem is
found. What goes wrong is narrower than that: the rules produce **one** answer,
and when that answer is three millimetres out the arm has nowhere to go. The
fingers close on a 5 mm stem, meet nothing, and the glass is left standing.

So the real weakness is not that the grip point is calculated. It is that it is
calculated *once*. Ranked search, touch and a closed loop on the camera all
attack exactly that, none of them is learning, and all three are cheap. They
come first.

### Learning it, after that

Copying an expert is proven next door.
[`v5-learn-pick-place`](../../v5-learn-pick-place) reaches 74% on blocks it
never saw. Note what that project did *not* learn: the block is still found
with plain geometry from a depth camera, and only the movement is learned. That
split would carry over here — the profile and the kind stay measured, the last
part of the reach becomes a policy, and MoveIt stops being in the way.

Reinforcement learning is the wrong member of that family for this job, for
three reasons in order of how much they matter:

1. *The reward is the hard part.* "Do not chip the rim, do not crush it, and
   leave it standing if you are unsure" is a set of constraints, not a score.
   This project treats a refused glass as a success, and there is no natural
   way to reward an arm for declining.
2. *It would not touch most of the failures.* A glass that is measured wrongly
   is refused by the rules before anything moves. No policy sees that.
3. *The sample cost.* Contact-rich grasping wants a number of episodes with
   five or more zeroes on it. A run here takes about five minutes in Gazebo,
   so this would mean rebuilding the cell in a fast simulator first — most of
   a project before the first episode.

Copying an expert avoids all three, and there *is* an expert to copy: the rules
in step 4, on the glasses they already handle.

### What learning would cost

Two things, and neither is the training time.

The project's one rule is that no glass's size appears anywhere in it. A policy
trained on this family of glasses has their proportions in its weights. Nothing
would be written down, and the rule would still be broken — just somewhere
nobody can read it.

And a rule can say why it refused. "The rule wants the fingers 246 mm apart,
outside the 20 to 95 mm a straight glass should ever need" is a sentence that
sends you to the bug. A policy that does not grasp a glass has no reason to
offer, and a project whose refusals are results needs its refusals to be
legible.

The honest summary: search and touch first, because they are cheap and they fix
what is broken. Learn the movement after that, if the reach is still the weak
part. Learning where to hold a glass is the last thing to give away, not the
first.

← [Step 4 — where to hold it](step4-where-to-hold-it.md)
