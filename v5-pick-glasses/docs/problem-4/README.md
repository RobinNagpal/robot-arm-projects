# Problem 4 — several kinds at once

A few kinds of glass stand on the table together. The arm has to measure each
one, name its kind, pick it up, invert it and rack it, until the table is
clear.

This folder holds the problem; [`solutions/`](solutions/) holds the answers.

- [**The problem**](problem.md) — what is new, the six steps and what changes
  at each, and what "done" means.
- [**Solution overview**](solutions/solution-overview.md) — the way into the
  nine. Which pieces of problems 1, 2 and 3 are reused and where each sits in a
  run, five findings measured before the nine were written, a table of all
  nine, and the combination recommended.
- [**`problem-4-learned`**](../../problem-4-learned/README.md) — solution 8
  built and scored: five small models find, measure, name, grip and push, and
  rules keep the camera places, the slots and the squeeze.
- **The nine solutions in full**, one document each, split as problem 2's
  are. Five programmed, in [`programmed/`](solutions/programmed/):
  [1 join them as they are](solutions/programmed/01-join-them-as-they-are.md),
  [2 a name that shows its evidence](solutions/programmed/02-a-name-that-shows-its-evidence.md),
  [3 let the fingers check the name](solutions/programmed/03-let-the-fingers-check-the-name.md),
  [4 plan the rack for the whole table](solutions/programmed/04-plan-the-rack-for-the-whole-table.md),
  [5 measure before you push](solutions/programmed/05-measure-before-you-push.md). Two
  hybrid and two learned, in [`learned/`](solutions/learned/):
  [6 a learned second opinion on the name](solutions/learned/06-a-learned-second-opinion-on-the-name.md),
  [7 guess the kind from above](solutions/learned/07-guess-the-kind-from-above.md),
  [8 the learned pipelines, retrained](solutions/learned/08-the-learned-pipelines-retrained.md),
  [9 plan the whole table with the push model](solutions/learned/09-plan-the-whole-table-with-the-push-model.md).

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

Nothing here needs a new technique. Writing the solutions up found that it
needs four existing decisions made better, not two:

- **The name has to show its evidence, not only its margin.** Most wrong names
  already end in a refusal, because the wrong rule finds no grip. The ones
  that do not are a reflection taken for a stem, which a margin cannot see,
  and a stemmed glass named short-stemmed, which is gripped in the right place
  and squeezed at 20 N instead of 6. [Solutions
  2](solutions/programmed/02-a-name-that-shows-its-evidence.md) and
  [3](solutions/programmed/03-let-the-fingers-check-the-name.md).
- **The slot has to be chosen for the whole table.** The rack is small enough
  that the best choice can be computed exactly. [Solution
  4](solutions/programmed/04-plan-the-rack-for-the-whole-table.md).
- **A crowded glass has to be measured before it is pushed**, wherever it can
  be seen. Its foot decides whether it may be pushed, and its foot comes from
  its kind. [Solution 5](solutions/programmed/05-measure-before-you-push.md).
- **The push model has to be told each glass's kind**, or that it has none yet.
  [Solution 9](solutions/learned/09-plan-the-whole-table-with-the-push-model.md).

The weaker footprint check matters less than it sounds: neither of problem 2's
built pipelines uses one.

## Where it sits

← [Problem 3 — glasses standing too close](../problem-3)
→ [Problem 5 — kinds whose proportions are unknown](../problem-5)

[The five problems](../README.md) has the map.
