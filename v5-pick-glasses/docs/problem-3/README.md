# Problem 3 — glasses standing too close

Problem 2 has said which pixels are which glass. Some of those glasses are
standing too close together for the gripper to get round one without fouling
its neighbour. The arm has to move them apart by **dragging them across the
table**, not by lifting them.

This folder holds the problem; [`solutions/`](solutions/) holds the answers.

- [**The problem**](problem.md) — why dragging rather than lifting, the three
  distances that matter, how low a push has to be and why that is a property of
  the glass, and what "done" means.
- [**Solution overview**](solutions/solution-overview.md) — **eleven solutions in full**:
  four programmed, four hybrid, three learned, and every one of them buildable
  inside the simulator. It opens with the vocabulary and the
  mechanics of a push, because a push is less simple than it looks. Then it
  covers two ideas the rest depends on: where a learned part can sit in a
  pipeline, and what it means for a machine to choose its own next
  measurement. Every solution is written to the same plan. What it is. Why
  anyone does it that way. How it would work here. Its feedback loop, if it has
  one. A worked example with real numbers. What it needs. What it is good and
  bad at. How it fails. And when it would be the right choice.
- [**The eleven solutions in full**](solutions/) — one document each, with its
  own diagrams and its own measurements. Four programmed:
  [1 do not drag at all](solutions/01-do-not-drag-at-all.md),
  [2 one fixed nudge](solutions/02-one-fixed-nudge.md),
  [3 plan, feel, look again](solutions/03-plan-feel-look-again.md),
  [4 predict the slide](solutions/04-predict-the-slide.md). Four hybrid:
  [5 a learned residual](solutions/05-a-learned-residual-on-the-push-model.md),
  [6 geometry generates, a model ranks](solutions/06-geometry-generates-a-model-ranks.md),
  [7 a learned change-verifier](solutions/07-a-learned-change-verifier.md),
  [8 a learned early-abort](solutions/08-a-learned-early-abort.md). Three learned:
  [9 identify the contact parameters](solutions/09-identify-the-contact-parameters.md),
  [10 learn a forward model](solutions/10-learn-a-forward-model-then-plan.md),
  [11 search a push strategy](solutions/11-search-a-push-strategy.md).
- [**The ones that need more than a simulator**](solutions/learned-with-hardware.md) —
  two good answers that were moved out. One is model-free reinforcement
  learning, which wanted about eleven days of continuous simulation when that
  was worked out for Gazebo; the cell has since been rebuilt in MuJoCo, where
  the measured figure is about 29 core-hours for one reward function. The other
  is imitation from a scripted expert, which wants a large model trained on a
  machine with a graphics card.

## The short version

**Lifting is not available, and the reason is circular.** To lift a glass the
fingers have to close somewhere chosen; to choose it the arm needs the profile;
to measure the profile it needs a side-on photograph; and a photograph is what
the crowding has taken away. A push breaks the circle because it needs only a
contact and a direction — a position and a base width, both of which problem 2
already produced.

**The gap that matters is not between the glasses.** It is between one glass
and everything the gripper has to put somewhere. Two glasses 105 mm apart are
not touching and neither can be picked up, because the open jaw needs about
70 mm of clear room in every direction from a glass's middle.

**Where to push is decided by the glass, not by preference.** A pushed object
slides while the contact is below `a / μ` — half its base width over the
friction with the table — and tips above it. A 60 mm base at μ = 0.3 leaves
100 mm to work in. A 45 mm base at μ = 0.5 leaves 45 mm, which is lower than the
gripper can reach, so that glass is refused rather than pushed.

**And the height to check against is not the one you would guess.** The middle
of the jaw rides as low as the gripper goes, 50 mm, but the jaw is 30 mm tall,
so its top edge is at 65 mm — and a glass that is wider higher up meets that
top edge first. Every tapered glass is wider higher up. Checking the rule at
50 mm rather than 65 reports about three quarters of this kind as safe to push
when the true figure is about a quarter, and every one of those mistakes is in
the direction that topples a glass. That error is larger than the one made by
guessing the friction, which is the more famous unknown.
[Solution 9](solutions/09-identify-the-contact-parameters.md) has the
arithmetic and the comparison.

**And the push is not predicted, it is watched.** Friction under a glass is not
uniform and μ is not measured anywhere in this cell, so the arm pushes once,
looks again, and compares. Cheap guess, checked by a measurement, measurement
decides — the same structure as the squeeze in problem 1.

## Where it sits

← [Problem 2 — many glasses of one kind](../problem-2)
→ [Problem 4 — several kinds at once](../problem-4)

[The five problems](../README.md) has the map.
