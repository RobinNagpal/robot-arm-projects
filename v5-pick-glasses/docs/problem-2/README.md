# Problem 2 — many glasses of one kind

Several glasses of the same kind stand on the table. The arm has to work out
which pixels belong to which glass, and where each one stands.

It stops there. It does not measure a profile, and it does not pick anything
up.

- [**The problem**](problem.md) — what is on the table, what is asked for, the
  two difficulties, and what "done" means.
- [**Solution overview**](solution-overview.md) — **nine solutions in full**:
  three programmed, three hybrid, three learned, and every one of them
  buildable inside the simulator. It starts with the vocabulary,
  because three of the words this subject uses mean different things to
  different people, and then with two ideas the rest depends on — where a
  learned component can sit in a pipeline, and what it means for a system to
  choose its own next measurement rather than taking a fixed number of
  pictures. Each solution is written the same way: what it is, why anyone does
  it like that, how it would work here, its feedback loop if it has one, a
  worked example with real numbers, what it needs, what it is good and bad at,
  how it fails, and when it would be the right choice.
- [**The ones that need more than a simulator**](learned-with-hardware.md) —
  four good answers that were moved out, each with the condition it fails: a
  promptable foundation model, a fine-tuned instance segmenter, amodal masks
  with learned association, and an active-vision policy. None needs a different
  algorithm to become usable. They need a graphics card, or a real camera.

## The short version

Two things are hard here, and they are not the same thing.

**Glasses merge in the picture even when they are apart on the table.** Two
glasses a hand's width apart land on top of each other in a photograph if the
camera happens to be in line with both. The flood fill that works perfectly for
one glass returns one blob for two. The answer is to stop grouping in the
picture and group on the table instead, where the two are plainly apart.

**The camera can no longer stand wherever it likes.** Problem 1 measures a
glass from 380 mm away, looking level, from whichever of nine directions the
arm can reach — and with a bare table, several always work. With five glasses,
each direction has to clear the line of sight, the arm's path, and the edge of
its reach at once, and a glass can end up with no usable viewpoint at all.

That second one is what makes this a different problem rather than a harder
version of problem 1. And a glass with no viewpoint is not a failure: it is the
handover to [problem 3](../problem-3/), which moves it.

## Where it sits

← [Problem 1 — one glass, start to finish](../problem-1/)
→ [Problem 3 — glasses standing too close](../problem-3/)

[The five problems](../README.md) has the map.
