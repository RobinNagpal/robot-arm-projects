# Problem 5 — kinds whose proportions are not known

The same as problem 4, except that no two glasses of a kind are alike and
nothing about their proportions is written down anywhere. The arm still has to
pick each one up and invert it.

- [**The problem**](problem.md) — the four things that must never be written
  down, the six steps and where the pressure lands, and what is already known
  to fail.

## The short version

**Nothing about the pipeline is new. Everything about what may be recorded is.**
Problem 4 could get away with a number that happens to be true of the glasses in
its ranges. Problem 5 cannot get away with any number about a glass at all —
only sentences about shape, and numbers about the gripper.

**The pressure lands on step 3 and on step 4's checks.** The two thresholds that
name a kind were set by looking at two populations of generated glasses. Widen
the populations and they overlap. And an unusual glass is far more likely to
produce a grip that is arithmetically correct and a bad idea, which is what the
five rejections exist to catch.

**The rules already generalise. The gripper does not.** This is the part worth
knowing before starting. The test was 200 random glasses of each kind, at their
exact shapes, with no camera error at all. Straight glasses got a usable grip 85
times out of 200. Short-stemmed ones got none — because a glass under about 120 mm
has no height at all between the lowest the gripper body can go and the highest
a grip can be and still be turned over. The numbers are in
[`known-gaps.md`](../known-gaps.md).

So the work here does not start on the rules. It starts on the cell.

## Where it sits

← [Problem 4 — several kinds at once](../problem-4)

[The five problems](../README.md) has the map.
