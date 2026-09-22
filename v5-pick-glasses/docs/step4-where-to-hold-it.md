# Step 4 — where to hold it

The arm knows the shape and it knows the kind. Now it has to pick a height to
grip at and a distance to open the fingers to.

Code: `glasses/rules.py`, `glasses/profile.py`, `glasses/spec.py`.

## What makes a grip point good

Three things, and every rule in the project is an attempt to satisfy all three
at once.

**The wall must be upright enough.** Flat pads on a sloping wall slide, and the
steeper the slope the more of the grip force turns into a push down the wall
instead of into it. `VERTICAL_TOLERANCE` is 6 degrees, and the number comes
from the pads: a 12 mm silicone pad conforms by about 1.2 mm across its height,
and `atan(1.2/12)` is 5.7 degrees.

It started at 2 degrees, which is what you pick if you are thinking about
geometry rather than about rubber. It refused every short mould-tapered tumbler
in the test family, because a wall that leans 3 degrees is not vertical and 2
degrees says so. Six is a fact about the hardware; two was an opinion.

**There must be enough of it.** A pad needs a band of wall at least as tall as
the pad to sit on. That is `min_band_height_m`, and it is 8–12 mm depending on
the kind.

**It must be low.** After the turn, the end that was at the bottom is at the
top. Hold a glass halfway up and, once it is upside down, the fingers are level
with the rack pegs. Every search band in `spec.py` stops at or below half the
glass's height, and `_check()` enforces it as well, because a rule that finds
something high up has found the wrong thing.

## Three rules

![One rule per kind](../images/grip-per-kind.png)

| Rule | Used by | What it looks for |
| --- | --- | --- |
| `lowest_vertical_section` | straight glass | the lowest band of wall within 6° of upright, at least a pad tall |
| `flattest_in_band` | tapered glass | the least-sloping band in the search window |
| `narrowest_below_widest` | stemmed, short-stemmed | the waist below the widest point |

`flattest_in_band` exists because a cone has no upright wall anywhere. Asking
for one returns nothing, so the tapered rule asks a different question: of all
the places a pad could sit, which is closest to upright? On a conical tumbler
that is near the base, where the wall has had least distance to spread.

`narrowest_below_widest` is the one that reads like a sentence about glassware,
and it is true of every stemmed glass ever made. The widest point of a wine
glass is its rim or the belly of its bowl; below that the glass necks down to
the stem before flaring out again into the foot. The narrowest point in
between is the stem, wherever it happens to be on this particular glass.

## Finding the waist was harder than it sounds

`waist_at()` originally returned the first index of the narrowest run of
widths. On a glass with a long parallel stem that is a plateau, many rows wide,
and the first row of that plateau is at the bottom — right where the stem
starts flaring into the foot. The arm would have gripped the flare, which is
sloping, wider, and exactly where a stem is weakest.

It now returns the **middle of the longest narrowest run**, which on a parallel
stem is the middle of the stem.

A second bug in the same area is worth recording because it only appeared once
in forty glasses. The generator drew the foot diameter independently of the
bowl diameter, so occasionally the foot came out wider than the bowl — which
makes the *base* the widest point of the glass, leaves `waist_at()` searching a
slice below the base, and crashes on an empty array. Real glasses do not have
feet wider than their bowls, and the generator now draws the foot as a fraction
of the bowl.

Neither of those would have been found with one test glass. Both were found by
running the rules over a family of forty.

## The opening is read off, never looked up

Once the rule has returned a height, the finger opening is the width the camera
measured **at that height**:

```python
opening = profile.width_at(height)
```

That single line is the whole reason this project can handle a glass nobody
measured. There is no lookup, no average stem diameter, no per-kind default.
The camera saw 9.2 mm at 30.8 mm up, so the fingers go to 9.2 mm.

Change the glass and both numbers change, with nothing to edit.

## Four ways an answer is rejected

A rule can return a number that is arithmetically correct and a bad idea — a
"waist" found in a mask artefact, a stem on a glass far too wide for the
gripper. `_check()` catches four cases, each one much cheaper here than with
the arm already moving:

1. **The opening is outside what this kind should ever need.** A stem 60 mm
   across is not a stem; the rule found something else.
2. **The opening is wider than the gripper opens at all** (95 mm).
3. **The band is shorter than the pads need.**
4. **The grip is more than halfway up the glass**, which after the turn puts
   the fingers among the rack pegs.

Each raises `NoGrip` with the reason written out, and that reason is what ends
up in the run report next to the glass that was left standing.

## Why this beats a table of measurements

![Eight wine glasses, and where the rule holds each one](../images/why-rules-not-sizes.png)

The left panel is eight wine glasses the project generated. They are all called
the same thing and no two are alike: heights from 131 to 230 mm, bowls of
different depths, stems of different lengths and thicknesses. The red mark on
each is where `narrowest_below_widest` decided to hold it.

The right panel is the same information as a table of measurements would have
to hold it — one dot per glass, and a spread of 25 mm in grip height for a
glass height that varies by 100 mm. The relationship is loose enough that no
single number works, which is exactly what makes a lookup table the wrong
shape for this problem.

One rule covers all of them. Adding a ninth glass to the left panel needs no
change at all, and *that* is the property the project is really built around.

## Every way of choosing a grip point

There are only two ways to answer "where do I hold this?": work it out from a
measurement, or learn it from examples. Everything below is one of those two,
or a way of correcting the answer once it exists. Some of them overlap, and
two of them are only useful together.

| Approach | What it does | What it runs on | Suitability here |
| --- | --- | --- | --- |
| **Rules on the profile** | one sentence per kind, applied to the measured outline | NumPy, in `glasses/rules.py` | good, and in use |
| **Ranked search** | scores every possible grip instead of returning the first one | NumPy for the scoring, MoveIt 2 to ask what the arm can reach | best next step |
| **Feel for it** | when the fingers meet nothing, hunt for the stem by touch | the pad contact and wrist force sensors already in the cell, through ros2_control | cheap, and nothing new to install |
| **Camera in the loop** | corrects the aim on the way down | OpenCV, on the wrist camera the arm already carries | useful, but only fixes aiming error |
| **Score grasps on a spun mesh** | classical grasp planning on a mesh built from the profile | trimesh, already used to build the glasses | redundant — same answer, more arithmetic |
| **Copy an expert** | learns the movement by watching the rules do the job | PyTorch, with LeRobot or the original ACT code | fits, once search and touch are done |
| **Reinforcement learning** | discovers a grasp by trial and reward | Stable-Baselines3 or RSL-RL, on Isaac Lab or MuJoCo | poor fit |
| **Off-the-shelf grasp network** | point cloud in, ranked grasps out | Contact-GraspNet, GraspNet-1Billion or AnyGrasp, on PyTorch | does not apply as things stand |
| **Depth completion** | invents the depth the glass did not return | ClearGrasp, TransCG or DREDS, on PyTorch | only worth it to feed the row above |

### What each one actually does

**Rules on the profile.** The arm measures the glass from the side, decides
from that measurement what kind it is, and runs that kind's one rule over the
outline. The rule returns a height; the finger opening is the width the camera
saw at that height. Four checks then reject anything the gripper cannot do, and
a rejected glass is left standing.

**Ranked search.** Same measurement, same rules, but the rule stops returning a
single winner. It scores every height in the search band, every direction the
arm could come in from and every wrist roll, on wall slope, how much pad would
touch, whether the arm can reach that pose, and whether the wrist can still
turn the glass over afterwards. The arm tries the best one and works down the
list. Most refusals today are "no way to hold it *the first way tried*".

**Feel for it.** Nothing changes until the fingers close. If they meet nothing,
or meet the wrong width, the arm does not give up: it opens, steps a few
millimetres up or down, and closes again, reading the pad contacts each time. A
stem is usually found in two or three tries. This is the fix for a measurement
that was 3 mm out, and the project already claims to work this way elsewhere —
the last millimetres are felt, not driven. At the grasp it does not follow
through.

**Camera in the loop.** The rule says hold this glass 31 mm up. To put the hand
there, the arm also has to know where the glass stands on the table, and that
number can be a few millimetres wrong. So the camera keeps looking at the glass
while the hand comes down, and the arm keeps nudging sideways to keep the glass
between the two fingers. In the last few centimetres the hand blocks the view,
so looking stops and feeling takes over.

**Score grasps on a spun mesh.** A glass is round, like a pot on a potter's
wheel, so the measured outline can be spun around into a 3D model — trimesh
already does this to build the glasses. Then comes the usual grasp search: look
over the whole surface for two spots, facing each other, where the fingers
would not slip. It works. It is also wasted work here, because the 3D model was
made from the outline and says nothing the outline did not, so the search ends
up where the rule ends up, slower.

**Copy an expert.** Run the rules a few hundred times and record the camera
images and the joint positions. Train a policy — ACT, or a diffusion policy —
to produce the next stretch of movement from what it sees. At run time the
policy drives the last part of the reach and the grasp, while the profile and
the kind stay measured as they are now. This is what
[`v5-learn-pick-place`](../../v5-learn-pick-place) does for blocks.

**Reinforcement learning.** No expert. The arm tries, gets a reward for a glass
that ends up on the rack, and slowly finds a policy. The workflow is a fast
simulator, a reward function, and a very large number of episodes. Both of the
hard parts are outside the training: writing a reward for "do not chip it, do
not crush it, and leave it alone if unsure", and getting enough episodes.

**Off-the-shelf grasp network.** A trained model takes the point cloud of a
scene and returns ranked gripper poses. The workflow is depth, then cloud, then
network, then throw away the grasps the arm cannot reach. It falls over at the
first step here: the depth picture has a hole where the glass is, so there is
no cloud of the glass to feed it.

**Depth completion.** A model trained on transparent objects looks at the
colour image and the broken depth and fills in what is missing. That gives back
a point cloud, which makes the grasp networks above usable. It is one more
trained model, one more dataset, and one more thing that can be wrong, in front
of a network that still does not know a stem from a bowl. The rules get there
in one step.

### The three that need a trained model

Three of the rows above train a model, and it is easy to think they are the
same idea. They are not. What matters is which part of the job the model takes
over, and who has to train it.

| | What the model learns | What it is given | What it hands back | Who trains it |
| --- | --- | --- | --- | --- |
| **Copy an expert** | the movement | the camera picture, and where the joints are | the next stretch of movement | you, from a few hundred of your own runs |
| **Grasp network** | what a good grasp looks like on any object | a 3D point cloud of the scene | a ranked list of gripper poses | someone else; you download it |
| **Depth completion** | what the missing depth should have been | the colour picture and the broken depth | a full depth picture | someone else; you download it |

**Copy an expert replaces the moving, not the deciding.** The rules still say
where to hold the glass. The policy only drives the hand there. It is the one
of the three you have to collect data for, and the data is your own cell doing
the job it already does.

**A grasp network replaces the deciding.** It never measures a glass and never
names a kind; it looks at the shape in front of it and offers poses. That also
means it does not know a stem from a bowl — it has no idea that this one part
of a wine glass is the part to hold.

**Depth completion decides nothing.** It repairs the picture, and that is all.
On its own it does not get the glass held. It is only useful as the first half
of a chain, with a grasp network behind it.

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
on this page, on the glasses they already handle.

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

→ [Step 5 — how hard to squeeze](step5-how-hard-to-squeeze.md)
