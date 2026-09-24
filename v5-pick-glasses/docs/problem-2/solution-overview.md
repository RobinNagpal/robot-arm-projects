# Problem 2 — how it would be solved

[`problem.md`](problem.md) says what is being asked. This says how it would be
answered, what else was considered, and why the thing chosen was chosen.

Two decisions have to be made, and they are separate:

1. **How to separate the glasses** — turn one picture of five glasses into five
   sets of pixels.
2. **How to choose where the camera stands** — given that the ideal viewpoint
   may be blocked, unreachable, or both.

Most write-ups answer only the first. The second is the one that actually makes
this problem different from problem 1.

---

## Decision 1 — how to separate the glasses

### The approaches

| Approach | What it does | Programmed or learned | Verdict |
| --- | --- | --- | --- |
| **Flood fill on the above-table mask** | groups the pixels standing above the table | programmed, in use for problem 1 | the baseline, and it merges |
| **Split the blob in the image** | watershed or GrabCut on a blob that is too wide | programmed | treats the symptom |
| **Cluster on the table, not in the picture** | put every pixel in the room, then group by distance | programmed | **chosen** |
| **Fit a circle to each footprint** | one known kind means one known diameter range | programmed | **chosen**, as the check |
| **Agreement across several stations** | a glass is what appears in the same place from everywhere | programmed, partly in use | **chosen**, as the confirmation |
| **Template matching** | slide a picture of the one known kind over the scene | programmed | brittle, and beaten by the circle fit |
| **A trained instance model** | learns to outline each glass separately | learned | the answer on real glassware, not needed here |
| **Segment Anything, prompted** | turns a rough hint into a precise outline | learned | worth keeping as a fallback |
| **An open-vocabulary detector** | "find the wine glasses", with no training | learned | a name is not what this needs |

### Why clustering on the table rather than in the picture

This is the whole of it. Two glasses that overlap in a picture are at different
*distances* from the camera, and the depth picture knows that even though the
flood fill does not. Once every pixel is turned into a point in the room —
which problem 1 already does, to find the table top — glasses that touch in the
image are two clumps of points a couple of hundred millimetres apart.

That is the standard table-top recipe, and robotics-basics sets it out as
[point clouds: remove the plane, then cluster](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#16-point-clouds-remove-the-plane-then-cluster).
Here the plane does not have to be found by RANSAC, because the table is bolted
to the same frame as the arm and its height was measured at startup. So the
recipe reduces to: keep the points above the table, and group them.

It has a known limit and it is the honest one: **objects that genuinely touch
cluster into one.** That limit is what problem 3 exists to remove.

### Why fit a circle to the footprint

Because problem 2 gives away something problem 4 will not: **every glass is the
same known kind.** So the diameter of a footprint is not unknown. It is inside
a range the kind's own specification already holds.

That turns the merged-blob check from a guess into arithmetic. Take each
cluster's points at the table, fit a circle, and ask whether it is inside the
range. A footprint 260 mm across when the kind is 60 to 90 mm is not one glass,
and fitting two circles instead of one says where the two of them are.

This is the same shape of argument as
[rules from a measured profile](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/03_choosing-a-grip.md#6-rules-from-a-measured-profile)
makes for gripping: a sentence about the object beats a model, when there is a
sentence to write. Here the sentence is *a glass of this kind is between 60 and
90 mm across*.

### Why agreement across stations

A single station can be unlucky. Two glasses in line with the camera merge; a
glass behind another is half hidden. Move the camera 200 mm and both change.

Problem 1 already takes two pictures at each station, a known distance apart,
to work out how high each glass stands — the technique is
[two photos from one moving camera](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#23-two-photos-from-one-moving-camera),
and `merge_sightings()` already joins what several stations saw. Problem 2 asks
more of the same machinery: a glass should be **found in the same place from
more than one station**, and a blob that appears from one station only is
reported as doubtful rather than as a glass.

One thing gets harder and is worth naming. With one glass, pairing the two
pictures of a station is trivial. With five, deciding which blob in the left
picture is which blob in the right is a matching problem, and a wrong pairing
produces a confident position for a glass that is not there. The existing code
already rejects the worst of these by checking that the implied height is
possible. With more glasses that check does more work, and it should be
reported rather than silent.

### What was turned down, and why

**Splitting the blob in the image** — watershed, GrabCut — is the classical
answer to a clump, and robotics-basics covers it under
[watershed and GrabCut](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#15-watershed-and-grabcut).
It is turned down because it works on the wrong thing. The blob is wide because
of where the camera was, not because of anything about the glasses, and a method
that reasons in the picture cannot know that. Clustering on the table makes the
question disappear rather than answering it.

**A trained instance-segmentation model** is what a real cell would use, and it
is the right answer the day the glasses are real glass, because then there is no
depth to cluster. Here it is more machinery than the problem needs: it wants a
labelled set, a file of weights kept in step with the glassware, and a graphics
card, and in exchange it does a job that a distance comparison already does
exactly. The families are in
[mask models](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/04_models-that-find.md#12-mask-models),
and the data for it would be drawn in the simulator rather than photographed —
[making the training data in a simulator](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/04_models-that-find.md#31-making-the-training-data-in-a-simulator)
is how, and this project already generates the glasses to do it with.

**Segment Anything** is kept in mind rather than turned down. It needs no
training, it takes a point or a box as a prompt, and the geometric detector can
supply exactly that. If a cluster fails the circle fit and fitting two circles
does not help either, prompting
[a promptable segmenter](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/04_models-that-find.md#13-promptable-segmenters-the-segment-anything-family)
at the middle of the blob is a cheap second opinion. It would be a **candidate
generator with the geometry deciding**, never the decider.

**An open-vocabulary detector** answers a question this problem is not asking.
It gives a name. Problem 2 already knows the name and needs a boundary.

---

## Decision 2 — where the camera stands

### The approaches

| Approach | What it does | Programmed or learned | Verdict |
| --- | --- | --- | --- |
| **Try directions in order, take the first that plans** | nine directions round the glass, ask the planner | programmed, in use for problem 1 | works with one glass, degrades badly with five |
| **Bound the search, then score what is left** | reject occluded and unreachable poses *before* asking the planner | programmed | **chosen** |
| **Next best view** | choose the viewpoint that removes the most uncertainty | either | the right idea, more than is needed |
| **Move the glass** | if no viewpoint works, change the scene | programmed | **chosen**, as the fallback — and it is problem 3 |
| **A second, fixed camera** | put a camera on the wall, where nothing blocks it | hardware | the honest answer, and a change to the cell |

### Bound the search, then score

Problem 1 asks the planner about each candidate pose in turn and takes the
first that works. With five glasses that behaves in a specific and confusing
way: the planner rejects pose after pose, the run gets slower by a large
factor, and eventually a poor viewpoint is accepted because it was the only one
left. Nothing errors.

That is the same structural mistake the gripping area names as the commonest in
a grasp pipeline —
[bounding the search by the gripper's own body](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/03_choosing-a-grip.md#7-bounding-the-search-by-the-grippers-own-body) —
and the fix is the same. Put the constraints in the search rather than on the
answer. Before asking the planner anything:

1. Drop any direction where another glass's footprint lies inside the wedge the
   camera would see. This is a ray test against circles, and it is arithmetic.
2. Drop any direction whose standoff point is outside the arm's comfortable
   reach.
3. Drop any direction where the straight path in would cross another glass.
4. Score what survives: prefer the least reach, then the widest clear angle.
5. Only now ask the planner, best first.

The cost is nothing and the failure mode changes from *slow and occasionally
bad* to **returns fewer viewpoints, and says which glass has none**.

### And when a glass has no viewpoint at all

That is not an error. It is the answer, and it is the handover to problem 3:
this glass cannot be measured from where it stands, so something has to move.

Saying so explicitly is the point. A pipeline that quietly accepts a bad
viewpoint produces a confidently wrong profile, and everything after it believes
that profile.

---

## The solution, as pseudocode

```text
for each survey station:                          ours: task.py, as today
    take the two pictures                         as today
    points = every pixel, placed in the room      ours: detect.py
    standing = points above the table top         ours: standing_on_the_table()

    clusters = group standing points by distance  new: cluster on the table,
      from each other, on the table plane              not in the picture

    for each cluster:
        circle = fit a circle to its footprint    new
        if the circle is inside the kind's
          diameter range:                         ours: glasses/spec.py
            one glass, here
        else if two circles fit it:
            two glasses, there and there
        else:
            doubtful; prompt a segmenter, or
              report it and move on

sightings = merge across stations                 ours: merge_sightings()
    a blob seen from one station only is
      doubtful, not a glass

for each glass found:                             new
    viewpoints = directions round it              ours: _standoffs(), extended
        drop the ones another glass is behind
        drop the ones out of reach
        drop the ones the arm cannot get to
    if none survive:
        this glass needs moving -> problem 3
```

## Where this solution can fail

**Glasses that genuinely touch still cluster into one.** Distance separates
them only when there is distance. This is the limit that problem 3 removes, and
the circle fit is what notices it: a footprint too wide for one glass and not
resolvable into two.

**The circle fit assumes the kind.** That is what makes it strong here and it is
exactly what problem 4 takes away. With several kinds on the table the diameter
range is the union of four ranges, which is wide enough to be much weaker.

**A glass seen from one station only is reported as doubtful, and may be real.**
That is the safe direction to be wrong in, and it will sometimes mean a real
glass left out of a run.

**Pairing across the two pictures of a station gets harder with every glass
added.** A wrong pairing gives a confident position for a glass that is not
there. The height check catches the impossible ones and not the plausible ones.

**None of it works on real glassware.** Everything above starts with "put every
pixel in the room", which needs a depth reading, which real glass does not give.
There the trained instance model is not an alternative, it is the answer.
