# Problem 3 — glasses standing too close

Problem 2 has said which pixels are which glass. Some of those glasses are
standing too close together for the gripper to get round one without fouling
its neighbour. The arm has to move them apart by **dragging them across the
table**, not by lifting them.

- [**The problem**](problem.md) — why dragging rather than lifting, the three
  distances that matter, how low a push has to be and why that is a property of
  the glass, and what "done" means.
- [**Solution overview**](solution-overview.md) — **eleven solutions in full**:
  four programmed, four hybrid, three learned, and every one of them buildable
  inside the simulator. It starts with the vocabulary
  and the contact mechanics, because a push is less simple than it looks, and
  then with two ideas the rest depends on — where a learned component can sit
  in a pipeline, and what it means for a system to choose its own next
  measurement. Each solution is written the same way: what it is, why anyone
  does it like that, how it would work here, its feedback loop if it has one, a
  worked example with real numbers, what it needs, what it is good and bad at,
  how it fails, and when it would be the right choice.
- [**The ones that need more than a simulator**](learned-with-hardware.md) —
  two good answers that were moved out: model-free reinforcement learning,
  which wants about eleven days of continuous simulation, and imitation from a
  scripted expert, which wants a transformer or a diffusion policy trained on a
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

**And the push is not predicted, it is watched.** Friction under a glass is not
uniform and μ is not measured anywhere in this cell, so the arm pushes once,
looks again, and compares. Cheap guess, checked by a measurement, measurement
decides — the same structure as the squeeze in problem 1.

## Where it sits

← [Problem 2 — many glasses of one kind](../problem-2/)
→ [Problem 4 — several kinds at once](../problem-4/)

[The five problems](../README.md) has the map.
