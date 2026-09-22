# The workflow, start to finish

How the project goes from a block on a table to a trained model that moves
the arm: finding the block, recording the demonstrations, training, and
running the trained model. The maths is kept to the level of what each step
computes, not how.

[dataset.md](dataset.md) shows the recorded data in detail, and
[approach.md](approach.md) gives the reasons behind each choice.
[results.md](results.md) has the scores.

## The whole thing in one picture

```
 1. FIND THE BLOCK          2. RECORD                 3. TRAIN                  4. RUN
 (geometry, no model)       (scripted expert)         (ACT)                     (trained model)

 depth camera               expert picks and          the model learns:         every 0.05 s:
   │                        places 200 blocks,        "in this situation,       read the joints,
   ▼                        each one recorded         the expert moved          work out the gaps,
 block outline,             20 times a second         the joints like this"     ask the model,
 centre of mass,              │                         │                       move the joints
 thickness                    ▼                         ▼                         │
   │                        dataset:                  a model file:             ▼
   ▼                        42,248 entries of         outputs/act/checkpoints/  block on the target
 grasp point,               (arm state, gaps          015000/pretrained_model
 place point                 to goals, move)
```

`make record` does steps 1 and 2 for every episode. `make train` does step 3.
`make evaluate` does steps 1 and 4 on episodes the model has never seen.

## 1. Find the block

At the start of every episode the overhead camera takes one depth picture:
for every pixel, how far away the surface is. From it, with no model:

1. **Pixels to points.** Each pixel is turned back into a point in the room.
   The camera's lens gives the direction the pixel looks in, the depth gives
   how far along that direction, and the camera's known position puts the
   point in the room. (For a pixel `u` pixels right of the middle, the point
   is `u × depth ÷ focal length` to the right; the same for up.)
2. **Points to the block.** The table is at height 0. Every point more than
   5 mm above it is the block. The highest of those are its top face.
3. **Top face to outline.** Around the top face's points goes the tightest
   convex outline, which is then straightened into the block's real corners.
4. **Outline to centre of mass.** The block is one solid material, so its
   centre of mass is the middle of the outline's area (its centroid, a
   standard formula over the corners). The thickness is the top face's
   height.

Error against the simulator's true values: 0.15 mm on average for the centre
of mass, 0.1 mm for the thickness. Code: [`locate.py`](../pick_place/locate.py).

### Then choose the grasp and the two goal points

The gripper has two parallel fingers that open to 8.5 cm, and the blocks are
irregular. The grasp is chosen by trying each side of the outline as the one
a finger lies flat against, and keeping the grasps where the block is 3 to
6.5 cm across between the fingers. Of those, the one closest to the centre
of mass wins, so the block does not twist in the fingers. Code:
[`shapes.py`](../pick_place/shapes.py).

That gives the two points the rest of the episode is about:

- **the grasp point:** where the point between the fingertips has to be to
  close on the block, 2.5 cm below its top face, and which way to turn the
  wrist;
- **the place point:** where the point between the fingertips has to be
  to let go, so the block's centre of mass lands on the target. The block is
  held a fixed distance from its centre of mass, so this is the target
  shifted by that same distance.

## 2. Record the demonstrations

A scripted expert does the task and every step is written down.

**What the expert does.** It moves the fingertips through phases, one after
another:

```
home → above the block → down to the grasp point → CLOSE → up
     → across to above the place point → down → OPEN → up (end)
```

In each phase it slides a target point for the fingertips smoothly towards
the phase's goal, and turns that point into six joint angles with inverse
kinematics: the calculation of which joint angles put the fingertips at a
given point. It closes or opens the gripper only once the fingertips have
really arrived, within 1.5 mm. A typical episode takes about 10 seconds.
The arm does not return home at the end; it stops 11.5 cm above the place
point.

**What is written down, 20 times a second:**

| | What | Numbers |
| --- | --- | --- |
| **state** | the six joint angles and how closed the gripper is | 7 |
| **environment state** | the gap from the fingertips to the grasp point, and to the place point; how far the wrist still has to turn; the block's thickness | 8 |
| **action** | how far the expert moved each joint from where it was, and whether the gripper is closed | 7 |

**What is kept.** Only episodes where the block really ended on the target:
the expert misses about 1 in 70, and those are skipped. Half the episodes
push the arm slightly off course while it travels, so some demonstrations
show how to get back. 200 episodes take about 40 seconds.

[dataset.md](dataset.md) walks through a real entry and a real episode.
Code: [`expert.py`](../pick_place/expert.py), [`record.py`](../pick_place/record.py).

## 3. Train the model

**The model:** ACT, Action Chunking with Transformers (Zhao et al., 2023),
from Hugging Face's LeRobot library. About 40 million numbers to learn.

**What it learns:** given the state and the environment state at one moment,
the expert's next **20 actions**, one second of movement. That is the
"chunk" in the name.

**How, at a high level:**

1. **Scale everything to the same size.** Joint angles, gaps in metres and
   the gripper are on very different scales. Each of the 22 numbers is
   shifted and scaled so that across the dataset it has average 0 and spread
   1. The averages and spreads are saved with the model and undone on its
   output.
2. **A training step.** Pick 64 random entries from the dataset. For each,
   the model predicts the next 20 actions, and these are compared with the
   20 actions the expert really took. The error is the average absolute
   difference (the "L1 loss"). The model's numbers are nudged a little to
   make that error smaller.
3. **Repeat 20,000 times.** That is about 30 passes over the whole dataset,
   and about 37 minutes on an M5 MacBook. A copy of the model is saved every
   5,000 steps: a **checkpoint**.

**One detail: the "style" summary.** ACT is trained as a variational
autoencoder (a CVAE). During training a second small network looks at the
true 20 actions and sums up their style in 32 numbers, which the main model
also gets. A penalty (the "KL" term, weighted 10) keeps that summary small
and vague, so the main model cannot lean on it too much. When the model is
used, the summary is simply set to zero. This matters when people give
demonstrations, because they do the same thing different ways; our expert is
consistent, so the style carries little.

**What the numbers during training mean:** `loss` is the L1 error plus 10 ×
the KL penalty. It falls from about 1.7 to about 0.1. It says how well the
model copies the dataset, **not** how well it moves the arm: in both
finished runs a middle checkpoint drove the arm better than the last, while
the loss was still falling. Only running a checkpoint on the arm tells you
which is best.

**Why ACT is a good fit here:**

- **Chunks stop small errors adding up.** A model that predicts one step at a
  time is a little wrong every step, and each error takes it somewhere the
  demonstrations never went. A chunk commits to a smooth second of movement.
  Asking the model every step instead of in chunks dropped success to 3%.
- **It learns from few demonstrations.** ACT was designed for 50 to 200
  demonstrations per task. We have 200.
- **It is small and quick.** With no pictures going in, it trains in half an
  hour on a laptop and answers in a few milliseconds.
- **It is standard and ready-made.** LeRobot has it, with training, saving
  and loading, and the same dataset format works for Diffusion Policy, the
  obvious model to compare it with.

Command: `make train`. Code: LeRobot's `lerobot-train`, called from the
[Makefile](../Makefile).

## 4. Run the trained model

When the model drives the arm, the expert is gone. The camera looks once,
the geometry finds the two goal points, and from then on the model decides
every movement. This is the loop, 20 times a second:

```
 ┌──► read the six joint angles and the gripper from the arm
 │         │
 │         ▼
 │    work out where the fingertips are, from the joint angles and the arm's
 │    known lengths; subtract that from the grasp point and the place point
 │         │
 │         ▼
 │    scale the 15 numbers the way training did
 │         │
 │         ▼
 │    no chunk waiting? ask the model for the next 20 actions,
 │    and keep the first 10
 │         │
 │         ▼
 │    take the next action from the kept ones and unscale it:
 │    six joint moves and a gripper command
 │         │
 │         ▼
 │    send the arm "joints now + move", and the gripper open or closed
 │         │
 └─────────┘   0.05 s later
```

So the model is asked every half second, and in between the arm carries out
its plan. Code: `run_policy` in [`evaluate.py`](../pick_place/evaluate.py).

**In Gazebo** the loop is exactly this one too, with Gazebo in place of
MuJoCo: see [gazebo.md](gazebo.md).

**On a real UR5e** the loop would be the same. What changes is around it:
the joint angles and tool position come from the UR controller (over its
RTDE interface), the "joints now + move" command goes back the same way,
and the camera has to be calibrated so its position over the table is
known to a millimetre. None of that is built yet; everything here runs in
MuJoCo.

## 5. Score it

`make evaluate` plays 50 episodes the model has never seen: seeds from
1,000,000 up, where the dataset used seeds from 0. For each it runs the
loop above for 16 seconds, then checks:

- is the block's centre of mass within **15 mm** of the target's middle,
- is it lying flat on the table,
- is the gripper open?

All three means success. The scripted expert plays the same 50 seeds too, as
the score to compare with. It also films the first 3 episodes into
`figures/evaluate/NAME/`.

## The three versions

Training was done three times. Each run showed a problem, and fixing it
changed the dataset, so the next run started from scratch. Full detail in
[results.md](results.md).

| Run | What the model saw and did | Best result | What went wrong |
| --- | --- | --- | --- |
| 1 | the grasp and place points as positions on the table; absolute joint angles out | 0% | fingers came down 2 to 3 cm beside the block |
| 2 | gaps from the fingertips to the goals; joint moves out | 47 to 60% at 10,000 steps | closed and opened the gripper when it was time to, not when it had arrived |
| 3 | as run 2, and the expert waits for the arm to arrive; half the episodes pushed off course | **74% at 15,000 steps** | |

**Run 3 at 15,000 steps is the best, and it is the only run still on disk.**
Each `make train` deletes the previous run with the same name, so runs 1
and 2 exist only as the numbers above. `make evaluate` uses the run 3,
15,000-step checkpoint by default:

```
make evaluate                 # 50 unseen episodes, a few minutes, films 3 of them
```

Other checkpoints of run 3:

```
make evaluate POLICY=outputs/act/checkpoints/020000/pretrained_model NAME=act-20000
```

Training again with `make train` would overwrite run 3. To keep it, give the
new run another name: `make train NAME=act-v4`.
