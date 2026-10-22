# The approach, and why each part is what it is

What the project does, split into its parts, with the reason for each choice
and the alternatives that were turned down.

## The split: geometry finds the block, a model moves the arm

```
overhead depth camera ──► geometry ──► grasp point, place point, grasp direction, thickness
                                            (once, at the start)          │
                                                                          ▼
arm joint angles + gripper ──► where the fingertips are ──► gap to each goal point
          │                                                               │
          └───────────────────────────────┬───────────────────────────────┘
                                          ▼
                                   ACT ──► how far to move each joint, and the gripper
          ▲                                                               │
          └────────────────── the arm moves, 20 times a second ◄──────────┘
```

Finding the block is not what is being learned. A depth camera looking
straight down at a flat table sees a block as the pixels that stand above
the table, and turning those into a position is arithmetic (see
[Finding the block](#finding-the-block-no-model)). A model would add
training data and error for no gain.

The movement is what is learned: from the arm's joint angles and how far the
fingertips are from where they have to go, how to move each joint next,
through reaching, grasping, lifting, carrying and setting down.

## The model: ACT

**ACT, Action Chunking with Transformers**, from Zhao et al., 2023,
[*Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware*](https://arxiv.org/abs/2304.13705)
(the ALOHA project). The implementation is Hugging Face's
[LeRobot](https://github.com/huggingface/lerobot), pinned at 0.6.1.

What it does: it takes the current observation and predicts the next
**chunk** of actions at once, here 20 steps (one second), of which the first
10 are carried out before it looks again. Predicting a chunk is what makes
it work from a small number of demonstrations: a policy that predicts one
step at a time drifts a little each step, and the drift takes it to states
no demonstration ever visited. A chunk commits to a whole smooth piece of
motion.

It is trained as a conditional VAE: during training a small encoder also
sees the true action chunk and compresses it to a 32-number "style". This
matters for human demonstrations, where the same situation is handled
different ways. The expert here is deterministic, so the style carries
little, and at test time it is set to zero.

What goes in and out:

| | Size | What |
| --- | --- | --- |
| `observation.state` | 7 | the six arm joint angles, radians, and how closed the gripper is, 0 to 1 |
| `observation.environment_state` | 8 | the vector from the fingertips to the grasp point (3), and to the place point (3); how far the wrist still has to turn to line up with the grasp; the block's thickness |
| `action` | 7 | how far to move each of the six joints from where it is now, radians, and the gripper: 0 open, 1 closed |

### Why relative, not absolute

The first version gave the policy absolute positions (grasp at x, y; place
at x, y) and asked for absolute joint angles. After 5,000 training steps it
did the whole task in the right order, reaching, closing, carrying and
letting go over the target, and missed every one of 20 test episodes,
because its fingers came down 2 to 3 cm beside the block and closed on air.
Its joint angles were within 0.03 to 0.06 rad of the expert's. That sounds
close, but 0.03 rad at the shoulder is 1.7 cm at the fingertips.

The problem was the job it had been given: from a position on the table,
produce exact joint angles, which is the arm's inverse kinematics, learned
to a millimetre from 200 examples. Two changes fix it:

- **Goals relative to the fingertips.** The fingertip position comes from the
  joint angles through the arm's known geometry, as a real UR reports its tool
  position. The policy is given the gap from there to each goal, so near the
  block it only has to learn "move to shrink this gap", which looks the same
  wherever the block is.
- **Moves relative to the joints.** An action is how far to move each joint
  this step, not where it should be. These are small numbers (about 0.07 rad
  spread, against about 0.5 for the absolute angles), and the network's
  error is a fraction of that spread, so the same relative error is about
  ten times smaller at the arm.

No pictures go in. ACT normally takes camera images through a ResNet; with
the block already located, the numbers above say everything the images
would, and training takes minutes, not hours. The ResNet is not built at
all when there are no image inputs.

**Alternatives:**

| Model | Why not first |
| --- | --- |
| Diffusion Policy (Chi et al., 2023), also in LeRobot | The natural second model: same data, same evaluation, different way of producing actions. Slower to train and to run. |
| Behaviour cloning with a plain MLP, one step at a time | The baseline ACT improves on. It drifts, as above. |
| Reinforcement learning | Needs a reward and millions of tries, and for a precise grasp it rarely finds the motion without demonstrations to start from. |

## The demonstrations: a scripted expert

The policy learns by copying. What it copies is a scripted expert
([`expert.py`](../pick_place/expert.py)). It works in phases: above the
grasp, down, close, up, across to above the place spot, down, open, up. In
each phase:

1. It moves a commanded point for the fingertips towards the phase's goal,
   at up to 25 cm/s, easing in as it gets close.
2. Every control step, damped least-squares inverse kinematics turns that
   point into six joint angles
   ([`kinematics.py`](../pick_place/kinematics.py)).
3. It moves on to the next phase only when the arm has **really arrived**:
   the measured fingertip position within 1.5 mm of the goal before the
   fingers close or open, within 1 cm where the arm only passes through.

Each recorded frame is: the arm's measured state, the gaps to the goals at
that moment, and the expert's commanded joint angles minus the measured
ones, so the move the policy has to learn to make. Only episodes where the
block ended on the target are saved: 200 good demonstrations take about 40
seconds to record, and the expert misses about 1 in 70.

### Why the expert waits for the arm, and why half the recordings push it

The first expert followed a fixed timetable: its whole path was planned at
the start, and the gripper closed at a set moment. It was just as accurate,
but the policy trained on it failed in two telling ways. Of 20 test
episodes, in 4 it closed the gripper 1.6 to 3 cm short of the block, and in
12 it opened it 1.5 to 3 cm from the place point. It had learned to close
and open when it was time to, not when it had arrived, because in every
demonstration the two always happened together.

And training longer made it worse: 47% success at 10,000 steps, 28% at
20,000. The better it copied the perfect paths, the less it knew what to do
once it was even slightly off one, since no demonstration ever was. This is
the standard failure of learning by copying, called covariate shift.

Two changes, one for each:

- **The expert waits for the arm.** The gripper only closes or opens once the
  measured fingertip position is within 1.5 mm of the goal, so what the
  demonstrations show is "close when the gap is zero".
- **Half the demonstrations push the arm off course** (after DART, Laskey et
  al., 2017, [*Noise Injection for Robust Imitation Learning*](https://arxiv.org/abs/1703.09327)).
  While the arm travels, a slowly drifting offset of about 0.02 rad per joint,
  1 to 2 cm at the fingertips, is added to what the arm is actually sent.
  The recorded action is still the move from where the pushed arm really is
  to the expert's clean command, so these demonstrations show how to get back
  on course. The final approach, the grasp and the release are never pushed,
  so the policy learns those from clean, exact examples.

**The expert uses nothing the policy is not shown.** It plans to the same
two goal points and grasp direction that the policy's inputs measure the
gap to, from the arm's own joint angles, never from the simulator's record
of where the block is. So everything the expert does is something
the policy can in principle learn from its inputs.

## Finding the block: no model

The same method as v1 ([`locate.py`](../pick_place/locate.py)):

1. The overhead camera renders a depth picture: for every pixel, how far
   away the surface is.
2. Each pixel goes back through the lens model into a point in the room:
   `x = (u − cx) · depth / f`, and the same for y, then the camera's pose.
3. Points more than 5 mm above the table, in and around the pick zone, are
   the block. The ones at its full height are its top face.
4. The convex hull of the top face, simplified to its real corners, is the
   block's outline. Its centroid is the centre of mass, because the block is
   one solid material.

Checked against the simulator on 15 episodes: 0.15 mm average error in the
centre of mass, 0.4 mm worst, and the thickness to 0.1 mm. A real depth
camera is far noisier than a simulated one; that is a later problem.

## The grasp: plain geometry too

Two parallel fingers have to hold an irregular block
([`shapes.py`](../pick_place/shapes.py), `best_grasp`). One finger lies flat
on a side of the block and the other closes straight towards it. Every side
is tried as the flat one, and a side qualifies if:

- the block is between 3.0 and 6.5 cm across in that direction, so the
  open fingers (8.5 cm) clear it;
- the far finger pad, 2.2 cm wide, reaches the far corner or side.

Of those, the grasp chosen is the one that holds the block closest to its
centre of mass, so gravity twists it least. Every generated block shape has
at least one grasp; shapes with none are redrawn.

## The simulator: MuJoCo

The model does not care which simulator made its data. MuJoCo was chosen
for the recording and testing loop:

- **Speed.** An 8-second episode, with the camera render, takes about 0.1 s
  to simulate. 200 demonstrations in 40 s; 50 test episodes in a few
  minutes.
- **Our code steps it.** Read the state, compute the action, step 50 ms,
  repeat. Nothing runs on its own clock, so every recorded frame lines up
  exactly with its action. In Gazebo with ROS the simulator and the code
  run separately and talk over topics, and the timing between them varies.
- **Ready models.** The UR5e and the Robotiq 2F-85 are from
  [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie),
  pinned to one commit, attached together with `MjSpec.attach`.
- **Runs on a Mac.** The `mujoco` wheel from PyPI renders offscreen on Apple
  Silicon with no extra setup. Only the interactive viewer window needs
  `mjpython` instead of `python` on macOS; nothing here uses it.

### Two changes to the stock models

- **Gravity compensation on the arm.** A real UR controller cancels the
  arm's weight itself. Menagerie's position actuators do not, and the arm
  sagged 5–10 mm below every commanded position, enough to put the fingers
  beside the block. With it, the expert lands the block 0.4 mm from the
  target on median, from 7 mm without.
- **A pause before closing and before opening.** The arm's position
  controllers trail a moving command by up to 4 cm, and take about 0.15 s to
  halve what is left. The expert stands still for 0.6 s before the fingers
  close or open; with 0.3 s they closed 4 mm too high.
- **The lowest grasp height is 15 mm.** Lower than that, the open fingertips
  land on the table and the arm stops short.

## Randomised per episode

Every episode draws, from its seed:

| What | Range |
| --- | --- |
| block outline | 3 to 6 sides, irregular, convex, 7 to 12 cm across at the widest |
| block thickness | 2.5 to 4 cm |
| block density | 400 to 900 kg/m³ |
| block start | x 0.40–0.58 m, y 0.10–0.30 m, any turn |
| target | x 0.40–0.58 m, y −0.30 to −0.10 m |

All of these are in [`settings.py`](../pick_place/settings.py) and
[`shapes.py`](../pick_place/shapes.py). Training uses seeds from 0 up;
evaluation uses seeds from 1,000,000, so every test block and target is new.
