# Results

What the trained policy scores, how it got there over three training runs,
and what is left.

## The result in one line

**The best ACT policy puts the block on the target in 37 of 50 episodes it
never saw (74%), 8.1 mm from the target's middle on median.** The scripted
expert it learned from scores 49 of 50 on the same episodes, 0.4 mm off.

That is the checkpoint at 15,000 training steps of the third run, playing 10
steps of each predicted chunk before asking again:

```
make evaluate      # uses outputs/act/checkpoints/015000/pretrained_model
```

Only run 3 is still on disk: each `make train` deletes the previous run of
the same name.

## How it is scored

- 50 episodes from seeds 1,000,000 up. Recording uses seeds from 0, so every
  block shape, start position, turn and target here is new to the policy.
- The policy gets 16 seconds. The expert's longest episodes take about 12.
- **Success:** when time runs out, the block's centre of mass is within 15 mm
  of the target's middle, the block lies flat on the table, and the gripper
  is open.
- The expert runs the same 50 seeds, as the score to beat.

## Where the 13 failures go

| Outcome | Episodes |
| --- | --- |
| on target | 37 |
| carried and put down flat, but 19 to 33 mm off | 6 |
| never lifted: the gripper closed short of the block | 6 |
| put down tipped | 1 |

Both main failure kinds are about precision at the moment the gripper acts,
not about the order of the task. The policy never skipped a step, dropped a
block in the air or wandered off.

## The three training runs

Every run used 200 recorded demonstrations and ACT with the same settings
(chunk of 20 steps, 10 played, learning rate 1e-4, batch 64, 20,000 steps,
about 37 minutes on an M5 MacBook). What changed was what the policy was
given and what the demonstrations showed. Scores are on 20 to 50 unseen
episodes; the 50-episode ones are marked.

| Run | What changed | 5k | 10k | 15k | 20k |
| --- | --- | --- | --- | --- | --- |
| 1 | absolute positions in, absolute joint angles out | 0% | | | |
| 2 | gaps from the fingertips to the goals in, joint moves out | 15% | 47% | | 28% (50) |
| 3 | expert waits for the arm to arrive; half the demonstrations pushed off course | 20% | 10% | **74% (50)** | 56% (50) |

Run 1 was stopped early, and run 2's 15k checkpoint was not scored.

**Run 1** did the whole task in the right order from the first checkpoint,
but its fingers came down 2 to 3 cm beside the block. Asked to turn "block at
x, y" into absolute joint angles, it had to learn the arm's inverse
kinematics to a millimetre. See
[approach.md](approach.md#why-relative-not-absolute).

**Run 2** grasped and carried the block, and failed on timing: it closed the
gripper 1.6 to 3 cm short in a fifth of episodes, and let go 1.5 to 3 cm off
target in most of the rest. The expert followed a timetable, so the policy
learned to act when it was time to, not when it had arrived.

**Run 3** changed the demonstrations so arrival and timing come apart (see
[approach.md](approach.md#why-the-expert-waits-for-the-arm-and-why-half-the-recordings-push-it)).
It was slow to start, 10% at 10k, and then the best by far at 15k.

## Things the runs showed

- **Checkpoints differ a lot, and the last is not the best.** Both finished
  runs peaked before 20,000 steps and then fell back (run 2 to 28%, run 3
  from 74% to 56%). The training loss keeps falling throughout, so it says
  nothing about which checkpoint drives the arm best; only running it does.
  Evaluate every checkpoint and keep the best.
- **How much of each chunk to play matters, and not the same way every
  time.** Asking the model again every 5 steps instead of 10 lifted run 2's
  10k checkpoint from 47% to 60%, but dropped run 3's 15k checkpoint from 70%
  to 47%. Asking every step fails outright (3%): the arm never commits to a
  motion, which is exactly what chunking is for.
- **ACT's temporal ensembling does not suit these actions.** Averaging the
  overlapping chunks, as the ACT paper does, dropped run 2's 10k checkpoint
  from 47% to 20%. The actions are moves from where the joints were when each
  chunk was predicted, and averaging moves from different starting points
  mixes them up. `evaluate.py` leaves it out.
- **The expert is not the limit.** It lands at 0.4 mm and succeeds 98% of the
  time. The gap is all in the learning.

## What would improve it

None of these has been tried. Each needs a new training run.

1. **More demonstrations.** 200 is on the small side for ACT, and every
   failure is a precision failure near the block, where more examples help
   most. Recording 500 takes under two minutes.
2. **Keep the best checkpoint automatically.** Save every 2,500 steps and
   score each on 20 episodes, instead of picking from four.
3. **The wrist camera as an input.** The last centimetre before the grasp is
   where the policy misses, and it is where a camera on the gripper sees
   the block best.
4. **Diffusion Policy on the same data**, to compare with ACT.
