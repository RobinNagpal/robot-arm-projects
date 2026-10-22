# The dataset

What is recorded, what one entry looks like, and what a whole episode of
entries shows. How it is made is in [workflow.md](workflow.md); why it is
made that way is in [approach.md](approach.md).

## In one paragraph

`make record` writes 200 episodes, 42,248 entries, to `data/pick-place/`
(5.8 MB). An **episode** is one complete pick and place of one block by the
scripted expert, about 10.6 seconds long. An **entry** is one moment of an
episode: 20 entries per second. Each entry holds what the arm could sense at
that moment and what the expert did next. The dataset is the arm's movement,
not pictures: there are no images in it.

## One entry

Three vectors of numbers, plus bookkeeping. Here is a real one: episode 0,
entry 57, at 2.85 s, the moment the expert starts to close the gripper on
the block.

**`observation.state`**: what the arm's own sensors say, 7 numbers.

| | shoulder pan | shoulder lift | elbow | wrist 1 | wrist 2 | wrist 3 | gripper |
| --- | --- | --- | --- | --- | --- | --- | --- |
| value | −3.1418 | −1.3618 | 2.2615 | −2.4703 | −1.5708 | −0.7143 | 0.0033 |
| unit | rad | rad | rad | rad | rad | rad | 0 open … 1 closed |

**`observation.environment_state`**: where the goals are, measured from the
fingertips, 8 numbers.

| | to grasp x | to grasp y | to grasp z | to place x | to place y | to place z | wrist turn left | thickness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| value | −0.0000 | 0.0000 | −0.0009 | 0.0837 | −0.3420 | 0.0021 | 0.0000 | 0.0335 |
| unit | m | m | m | m | m | m | rad | m |

Reading it: the fingertips are 0.9 mm above the grasp point and exactly over
it, so the arm has arrived. The place point is 8.4 cm further out and 34.2 cm
to the right. The wrist is already turned to line the fingers up. The block
is 3.35 cm thick.

**`action`**: what the expert did next, 7 numbers.

| | move pan | move lift | move elbow | move wrist 1 | move wrist 2 | move wrist 3 | gripper |
| --- | --- | --- | --- | --- | --- | --- | --- |
| value | 0.0000 | 0.0021 | 0.0010 | −0.0034 | 0.0000 | 0.0000 | **1** |
| unit | rad | rad | rad | rad | rad | rad | 0 open, 1 closed |

Reading it: the joints barely move (a fraction of a degree) and
the gripper is told to close. This is the entry that teaches "the gap is
zero, so close".

**Bookkeeping**, added by LeRobot: `timestamp` (seconds into the episode),
`frame_index` (entry number in the episode), `episode_index`, `index`
(entry number in the whole dataset) and `task_index` (always 0: there is one
task, "pick up the block and place it on the red target").

### Why these numbers and not others

- **The goals are gaps from the fingertips, not positions on the table.**
  The fingertip position is worked out from the joint angles, the way a real
  UR reports its tool position. So the policy sees "3 cm to the left of
  where I need to be", which looks the same wherever the block is.
- **The action is how far to move each joint, not where it should end up.**
  The arm is sent "where the joints are now, plus this move". Small numbers
  are easier to learn precisely.
- **Wrist 2 always reads −1.5708 and never moves.** That joint keeps the
  gripper pointing straight down, which it always is here.

## One episode, entry by entry

Episode 0, 196 entries, 9.75 seconds. The expert moves on to the next phase
only once the arm has really arrived, so the times differ from episode to
episode.

| Time | Entry | Phase | What the numbers show |
| --- | --- | --- | --- |
| 0.00 s | 0 | **start**, arm at home, gripper open | grasp point 15 cm ahead, 13 cm left, 34 cm below; wrist has 49° to turn |
| 1.00 s | 20 | **moving above the block**, turning the wrist | grasp gap down to 6 cm across and 19 cm down; turn nearly done |
| 2.25 s | 45 | **coming down** onto the block | grasp gap 2 cm, all of it height |
| 2.85 s | 57 | **close**: arrived within 1.5 mm | grasp gap 0.9 mm; action gripper becomes 1 |
| 2.85–3.65 s | 57–73 | **hold still** while the fingers close | gripper reading rises to 0.37 as the fingers meet the block |
| 4.50 s | 90 | **lifting** | grasp gap now 11 cm of height: the block is going up with the gripper |
| 6.00 s | 120 | **carrying** across to above the place point | place gap 4 cm across, 12 cm down |
| 7.60 s | 152 | **open**: arrived at the place point, within 1.5 mm | place gap 0.9 mm; action gripper becomes 0 |
| 7.60–8.40 s | 152–168 | **hold still** while the fingers open | gripper reading falls back to 0 |
| 9.75 s | 195 | **back up** 11.5 cm above the place point, held for half a second; the episode ends | |

The episode ends above the place point. The arm does not go back to its
home position: that would be another 1.5 s per episode of learning a motion
that is always the same.

## Clean and pushed episodes

About half the episodes (chosen by the seed) are **pushed**: while the arm
travels, a slowly drifting offset of about 0.02 rad per joint, 1 to 2 cm at
the fingertips, is added to what the arm is actually sent. The recorded
action is still the expert's correct move, measured from where the pushed
arm really is. So in pushed episodes, the actions show how to get back on
course. The final approach, the grasp and the release are never pushed.

Nothing in an entry says whether its episode was pushed. The policy is meant
to learn the same thing from both: from where the arm is now, what to do
next.

## What varies between episodes

| What | Range |
| --- | --- |
| block outline | 3 to 6 sides, irregular, convex, 7 to 12 cm across at the widest |
| block thickness | 2.5 to 4 cm |
| block density | 400 to 900 kg/m³, light wood to hard plastic |
| block start | x 0.40–0.58 m, y 0.10–0.30 m from the arm's base, turned any way |
| target | x 0.40–0.58 m, y −0.30 to −0.10 m |
| pushed or clean | about half each |

Episodes come from seeds 0, 1, 2, … in order. A seed decides everything
about its episode, so `random_episode(7)` is always the same block and
target. The expert misses in about 1 episode in 70 (seeds 22, 39 and 195 in
this dataset), and those are left out, which is why 203 seeds give 200
episodes.

## On disk

```
data/pick-place/
  meta/info.json                        the features above, fps, counts
  meta/stats.json                       mean, spread, min and max of every number; training uses these
  meta/tasks.parquet                    the one task sentence
  meta/episodes/chunk-000/file-000.parquet   where each episode starts and ends
  data/chunk-000/file-000.parquet       every entry, one row each
```

To look at it yourself:

```
pixi run python -c "
import pandas as pd
df = pd.read_parquet('data/pick-place/data/chunk-000/file-000.parquet')
print(df[df.episode_index == 0].iloc[57])
"
```
