# Problem 3 — how it would be solved

[`problem.md`](problem.md) says what is being asked. This says how it would be
answered, what else was considered, and why.

Three decisions, and they are separate:

1. **Which glass to move, and where to.**
2. **How to push it** — where to touch it, how low, how fast.
3. **How to know it worked.**

---

## Decision 1 — which glass to move, and where to

### The approaches

| Approach | What it does | Programmed or learned | Verdict |
| --- | --- | --- | --- |
| **Push the pair apart along the line joining them** | one fixed nudge, both ways | programmed | the baseline, and it is often enough |
| **Plan the destination against the free table** | treat the other glasses, the rack and the reach as obstacles, pick a clear spot | programmed | **chosen** |
| **Push towards the emptiest direction** | move down the gradient of a crowding score | programmed | a good tie-breaker, not a plan |
| **Plan the whole rearrangement** | solve for the order and the targets together | programmed, search | more than this needs |
| **A learned pushing policy** | learn to singulate a pile by trial and reward | learned | the answer for a pile, not for five round objects |

### Plan the destination against the free table

The table is a flat rectangle. The glasses are circles on it with known
middles and known widths. The rack is a box. The arm's reach is a ring. That is
a small enough world to reason about exactly, and doing so gives a better
answer than a fixed nudge for almost no extra work.

For a glass that needs moving, the destination has to satisfy four things at
once, and every one of them is a comparison of numbers the arm already has:

1. at least 70 mm clear of every other glass's middle, plus their widths;
2. inside the part of the table the glasses may stand on;
3. inside the arm's comfortable reach;
4. clear of the rack.

Score what survives by how far the glass has to travel — the shortest safe push
is the best one, because every millimetre of push is a millimetre of chance to
topple something.

**Bound the search before scoring**, not after. This is the same reordering the
gripping docs call the commonest structural mistake in a grasp pipeline, in
[bounding the search by the gripper's own body](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/03_choosing-a-grip.md#7-bounding-the-search-by-the-grippers-own-body).
Generating pushes, scoring them by how much they separate, and then discovering
the planner will not execute them is how a cell becomes slow and unreliable
without anything erroring.

### Which one of a crowded pair

Move the one that is **easier to push and less likely to topple** — which is
to say the one with the widest base relative to its height, because that is the
one `h < a / μ` is most forgiving about. If neither can be pushed safely, both
are refused and reported.

If they are equally safe, move the one whose destination is the shorter push.

### What was turned down

**A learned pushing policy** is a real research area and it is aimed at a
harder version of this. Work on singulating cluttered piles learns where to push
when the objects are a jumble of unknown shapes and there is no geometry to
reason about. Here there are five round objects of one known kind on a flat
table with their positions already measured. The geometry is not the hard part;
there is nothing for a policy to discover that arithmetic does not already give.
It also costs what every learned component costs — a training loop, a file of
weights, and an answer that cannot say why. It belongs on the list for the day
the table holds a jumble rather than five glasses.

**Planning the whole rearrangement at once** — deciding the order and every
destination together — is the thorough answer and it is more than the problem
needs, because after each push the arm is going to look again anyway. One push
at a time, replanned each time, gets the same result with none of the
machinery.

---

## Decision 2 — how to push

### The approaches

| Approach | What it does | Programmed or learned | Verdict |
| --- | --- | --- | --- |
| **Closed gripper as a finger, moved in a straight line** | drive the closed jaw through the glass's middle | programmed | **chosen** |
| **Guarded approach, then push** | move in until the contact fires, then push a measured distance | programmed | **chosen** |
| **Predict the slide with pushing mechanics** | use the motion cone to work out where it ends up | programmed | good theory, needs μ |
| **Learn a forward model** | predict the outcome from data | learned | same objection, plus training |
| **A dedicated tool** | a paddle or a hook on the tool changer | hardware | the clean answer, and a change to the cell |

### Push with the closed gripper, low, after feeling for the glass

**Close the fingers first.** A closed jaw is a single stiff object with a known
shape. An open jaw is two thin fingers that can catch on a rim.

**Come in at the lowest height the gripper can reach**, and check that height
against `a / μ` for this glass using its measured base width. If the limit is
below what the gripper can reach, refuse the glass. Do not push it gently and
hope — a push that tips a glass tips it whatever the speed.

**Feel for the glass rather than driving to it.** Move in slowly until the
contact sensor or the wrist force says the glass is there, and record where that
happened. This is
[the guarded move](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#21-what-you-can-actually-do-with-it),
and it is worth using here for a second reason: the place contact happens is a
measurement of where the glass's *surface* is, which is a better number than the
one the camera gave, exactly as the width at first contact is in step 5 of
problem 1.

**Push through the middle.** A push whose line passes through the glass's
footprint centre slides it roughly straight. A push off to one side spins it.
The middle is known from problem 2.

**Push slowly, and only as far as the plan said.** Then stop, and look.

### What was turned down

**Predicting the slide.** There is real theory here — a pushed object's motion
is decided by where the push line falls relative to the friction cone at the
contact, and the classical treatment predicts rotation as well as translation.
It is turned down for the reason the whole project turns down driving to a
calculated value: it needs `μ`, and `μ` is not measured anywhere in this cell.
A prediction from a guessed coefficient is a confident number with nothing
behind it. Looking again after the push costs one picture and needs no
coefficient at all.

**A learned forward model** has the same problem with an extra training loop in
front of it.

**A dedicated pushing tool** — a paddle, a low hook — would be better than a
closed gripper at this and worse at everything else, and swapping tools needs a
tool changer.
[Tool changers, and custom tooling](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/02_grippers-and-hardware.md#7-tool-changers-and-custom-tooling)
is what that would involve. It is a change to the cell rather than to the code,
and it belongs in the same conversation as raising the arm.

---

## Decision 3 — how to know it worked

**Look again.** Not "verify the model"; look.

One push, then a fresh pair of overhead pictures, then problem 2's separation
run over them again. Compare what is there now against what the push aimed for.
Three outcomes:

- **it moved about as far as intended** — carry on to the next crowded pair;
- **it moved much less** — the glass is heavier or the friction higher than
  assumed; push again, from the newly measured position;
- **it is not where any glass should be, or there is now one blob where there
  were two** — something has toppled or been knocked. Stop and report.

Toppling is the outcome that must never be pushed through, and the cheapest
detector for it is the one already built: a glass that has fallen over is no
longer a circle of the right size on the table, and problem 2's circle fit says
so immediately.

This is the same shape as everything else in the project. A cheap guess,
checked by a measurement, with the measurement deciding. The gripping docs put
it as [the squeeze sequence](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/07_gripping/05_holding-on.md#1-the-squeeze-sequence);
here it is a push sequence and the structure is identical.

---

## The solution, as pseudocode

```text
loop:
    glasses = problem 2's separation, run fresh    ours: problem-2 solution
    crowded = pairs closer than 140 mm             new: 70 mm of room each

    if nothing is crowded:
        done

    pick the pair whose glasses are closest        new
    choose which of the two to move                new: the wider base wins
        limit = a / mu, from its measured base     new
        if limit < the lowest the gripper reaches:
            refuse this glass, and say why

    destination = a clear spot for it              new
        at least 70 mm from every other glass
        inside the glass zone and the reach
        clear of the rack
        the shortest push that satisfies all
      if there is no such spot:
          refuse, and say why

    close the fingers                              ros2_control
    move to the push height, behind the glass      MoveIt 2
    feel forward until contact                     ours: descend_until_contact,
                                                     turned sideways
    push in a straight line to the destination     MoveIt 2: Cartesian path
    retreat

    look again, and compare                        new
        moved about as far as aimed -> carry on
        moved much less -> push again
        a glass is missing, or one blob where
          there were two -> stop and report
```

## Where this solution can fail

**μ is guessed, so the push height limit is guessed.** The arithmetic is sound
and one of its two inputs is not measured. Pushing as low as the gripper can
reach is the mitigation, and it is not a proof.

**A glass can be pushed into a place that is clear now and crowded later.** The
destination is chosen against the arrangement as it stands. Moving a second
glass afterwards can undo it. Replanning after every push keeps this from
compounding, at the cost of more pushes.

**The arm can run out of table.** Five glasses each needing 140 mm of separation
in a zone 320 by 360 mm is close to what fits. With six it may not be solvable
at all, and the honest output is to say which glasses could not be separated
rather than to shuffle indefinitely.

**Pushing changes the viewpoints as well as the spacing.** A glass moved to
make room for the gripper can block the line of sight to another one. The loop
above catches this because it re-runs the whole separation each time, but it
means the number of pushes is not bounded by the number of crowded pairs.

**Nothing here measures the glass's mass before touching it.** A push force is
applied to an object of unknown weight. In the simulator that is harmless. On a
real table a heavy glass resists and a light one skates, and the difference is
the same factor of three that step 5 of problem 1 has to weigh for.
