# Problem 2 — many glasses of one kind

Several glasses of the same kind stand on the table. The arm has to work out
which pixels belong to which glass, where each one stands, and roughly how wide
each one is.

It stops there. It does not measure a shape, and it does not pick anything up.

This folder holds the problem; [`solutions/`](solutions/) holds the answers. The
cell they all share — the layout, the two places the camera works from, the
sensors and the vocabulary — is described once in [the cell](../the-cell.md).

- [**The problem**](problem.md) — what is on the table, what is asked for, the
  three difficulties, and what "done" means.
- [**Solution overview**](solutions/solution-overview.md) — the way into the
  nine solutions. It opens with the vocabulary, because three of the words this
  subject uses mean different things to different people. Then it covers two
  ideas the rest depends on: where a learned part can sit in a pipeline, and
  what it means for a machine to choose its own next measurement instead of
  taking a fixed number of pictures. After that it gives a short paragraph on
  each of the nine and ends with the recommendation, which is a combination of
  methods rather than a single choice.
- **The nine solutions in full**, one document each in
  [`solutions/`](solutions/). Each is written from the beginning, with diagrams,
  and each ends with **the general methods behind it** — the named, published
  techniques it is built from, with an honest note on where each one is normally
  the right tool and where it is not.

  | | Solution | Family |
  |---|---|---|
  | 1 | [Split the blob in the picture](solutions/01-split-the-blob-in-the-picture.md) | programmed |
  | 2 | [Cluster on the table](solutions/02-cluster-on-the-table.md) | programmed — **chosen** |
  | 3 | [Move the camera](solutions/03-move-the-camera.md) | programmed — **chosen** |
  | 4 | [Learned doubt steers the next picture](solutions/04-learned-doubt-steers-the-next-picture.md) | hybrid |
  | 5 | [Is anything hiding there?](solutions/05-is-anything-hiding-there.md) | hybrid |
  | 6 | [Learn which viewpoints pay off](solutions/06-learn-which-viewpoints-pay-off.md) | hybrid |
  | 7 | [A segmenter trained from scratch](solutions/07-a-segmenter-trained-from-scratch.md) | learned |
  | 8 | [Per-pixel votes for the centre](solutions/08-per-pixel-votes-for-the-centre.md) | learned |
  | 9 | [Self-supervised from the arm's own movement](solutions/09-self-supervised-from-the-arms-own-movement.md) | learned |

- [**The ones that need more than a simulator**](solutions/learned-with-hardware.md) —
  four good answers that were moved out, each with the condition it fails: a
  promptable foundation model, a fine-tuned instance segmenter, amodal masks
  with learned association, and an active-vision policy. None of them needs a
  different algorithm to become usable. They need a graphics card, or a real
  camera.

## The short version

Three things are hard here, and they are not the same thing. They are listed
below in order of how dangerous they are rather than how obvious they are.

**A glass can be missing from a picture altogether.** The glasses are all
tapered and the range of sizes inside that kind is wide, so a tall glass and a
short one can differ several times over in height. Seen from the top, a glass's
outline is thrown outwards away from the point directly below the camera, and
the taller the glass the further out it goes. A tall glass's outline can
therefore sweep over a short one and cover it completely. Nothing in the picture
says that this happened, because every check in this project is a check on
something that was found, and a glass that produced no pixels produces nothing
to check.

**Glasses merge in the picture even when they are apart on the table.** Two
glasses a hand's width apart land on top of each other in a photograph when the
camera happens to be in line with both, and the flood fill that works perfectly
for one glass returns a single patch for two. The answer is to stop grouping in
the picture and to group on the table instead, where the two are plainly apart.
This failure is at least loud, because the patch is wider than any glass of the
kind can be.

**The camera can no longer stand wherever it likes.** Problem 1 measures a glass
by standing back from it, looking level, from whichever direction the arm can
reach, and with a bare table several directions always work. With five glasses,
each direction has to clear the line of sight, the arm's path and the edge of
its reach all at once, and a glass can end up with no usable viewpoint at all.
That is not a failure but the handover to [problem 3](../problem-3), which moves
it.

**One finding from writing these up is worth reading on its own.** Most of the
"no usable viewpoint" reports come from the *grid* of directions running out,
not from the geometry. The clear arcs around a typical glass are mostly narrower
than the step between two directions the arm currently tries, so refining that
step turns a large share of those reports back into ordinary viewpoints, and it
costs arithmetic and nothing else. [Solution 3](solutions/03-move-the-camera.md)
has the working.

**And a second finding, from the other end.** Because the outline of a found
glass is thrown outwards by an amount that can be computed exactly, the region
of table it could have been hiding can be computed too. So the question that
looks unanswerable — *is a glass missing?* — becomes one that is answerable:
*where could a glass have been hiding, and is that region big enough to hold the
smallest glass of the kind?* That turns silence into a finite list of places to
go and look at, and it is the second half of
[solution 2](solutions/02-cluster-on-the-table.md).

## Where it sits

← [Problem 1 — one glass, start to finish](../problem-1)
→ [Problem 3 — glasses standing too close](../problem-3)

[The five problems](../README.md) has the map.
