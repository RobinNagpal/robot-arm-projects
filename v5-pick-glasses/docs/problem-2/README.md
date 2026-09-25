# Problem 2 — many glasses of one kind

Several glasses of the same kind stand on the table. The arm has to work out
which pixels belong to which glass, and where each one stands.

It stops there. It does not measure a profile, and it does not pick anything
up.

This folder holds the problem; [`solutions/`](solutions/) holds the answers.

- [**The problem**](problem.md) — what is on the table, what is asked for, the
  two difficulties, and what "done" means.
- [**Solution overview**](solutions/solution-overview.md) — **nine solutions in full**:
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
- **The nine solutions in full**, one document each in
  [`solutions/`](solutions/), written from the beginning and with six to eight
  diagrams apiece. The overview has a paragraph on each and the comparison;
  these have the explanation.

  | | Solution | Family |
  |---|---|---|
  | 1 | [Split the blob in the picture](solutions/01-split-the-blob-in-the-picture.md) | programmed |
  | 2 | [Cluster on the table](solutions/02-cluster-on-the-table.md) | programmed — **chosen** |
  | 3 | [Move the camera](solutions/03-move-the-camera.md) | programmed — **chosen** |
  | 4 | [Learned doubt steers the next picture](solutions/04-learned-doubt-steers-the-next-picture.md) | hybrid |
  | 5 | [A learned verifier over the clusters](solutions/05-a-learned-verifier-over-the-clusters.md) | hybrid |
  | 6 | [Learn which viewpoints pay off](solutions/06-learn-which-viewpoints-pay-off.md) | hybrid |
  | 7 | [A segmenter trained from scratch](solutions/07-a-segmenter-trained-from-scratch.md) | learned |
  | 8 | [Per-pixel votes for the centre](solutions/08-per-pixel-votes-for-the-centre.md) | learned |
  | 9 | [Self-supervised from the arm's own movement](solutions/09-self-supervised-from-the-arms-own-movement.md) | learned |

- [**The ones that need more than a simulator**](solutions/learned-with-hardware.md) —
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
handover to [problem 3](../problem-3), which moves it.

**One finding from writing these up is worth reading on its own.** Over 600
drawn arrangements, 45 per cent of glasses have no usable viewpoint on the
cell's current nine-direction grid — but only 14 per cent if the grid is
refined from 40 degrees to 5. The clear arcs in a typical scene run 34, 16,
110, 7 and 10 degrees wide, and only one of those is wider than a 40-degree
step. So most "no viewpoint" reports are the *grid* running out, not the
geometry, and refining it costs arithmetic and nothing else.
[Solution 3](solutions/03-move-the-camera.md) has the working.

And a second, from the other end: within problem 2's guarantee that glasses
stand 150 mm apart, **two of them cannot merge into one cluster on the table**
— the closest two footprints can come is 45 mm, against a 25 mm grouping
distance. The ambiguity here is never a merge. It is a glass seen from too
narrow an angle, whose circle fit looks perfectly healthy and whose position is
quietly wrong. [The solution overview](solutions/solution-overview.md#when-can-a-cluster-actually-be-wrong)
has the numbers.

## Where it sits

← [Problem 1 — one glass, start to finish](../problem-1)
→ [Problem 3 — glasses standing too close](../problem-3)

[The five problems](../README.md) has the map.
