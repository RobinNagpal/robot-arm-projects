# Problem 4 — several kinds at once

A few kinds of glass stand on the table together. The arm has to measure each
one, name its kind, pick it up, invert it and rack it, until the table is
clear.

- [**The problem**](problem.md) — what is new, the six steps and what changes
  at each, and what "done" means.

## The short version

This is problems 1, 2 and 3 joined up, plus one thing none of them has: **the
rule changes per glass.**

**Naming becomes load-bearing.** In problem 1 a wrong name is cheap, because a
rule applied to the wrong kind usually fails its own checks and the glass is
refused. With several kinds a name can be wrong *and plausible*. Call a
tumbler with a notch in its outline stemmed, and the rule for a stemmed glass
will return a grip at a stem that does not exist. Nothing downstream re-checks
the name, because nothing downstream can.

**The rack has to be shared out.** Six slots, several glasses, different
widths. A wide glass needs its neighbour left empty. Taking the wrong slot early
can leave a later glass with nowhere to go, which problem 1 never has to face.

**And problem 2's strongest tool is taken away.** Its footprint check works
because every glass is one known kind with one known diameter range. Across four
kinds that range is the union of four, which is wide enough to be much weaker.

Nothing here needs a new technique. It needs two existing decisions made
better: a classifier that says how close the call was, and a slot choice that
plans for the glasses still on the table.

## Where it sits

← [Problem 3 — glasses standing too close](../problem-3)
→ [Problem 5 — kinds whose proportions are unknown](../problem-5)

[The five problems](../README.md) has the map.
