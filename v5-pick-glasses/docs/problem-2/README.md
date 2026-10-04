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
- [**Solution overview**](solutions/solution-overview.md) — the way into the ten
  solutions. It covers what they share: what each does about a glass nobody saw,
  the vocabulary, where a learned part can sit in a pipeline, and what it means
  for a machine to choose its own next measurement instead of taking a fixed
  number of pictures. Then a one-line table of the ten, what was built, and
  where that can fail.
- **The ten solutions in full**, one document each, split by whether they
  contain a trained model. The three in [`solutions/programmed/`](solutions/programmed/)
  are rules somebody wrote down. The seven in [`solutions/learned/`](solutions/learned/)
  all have numbers fitted to examples somewhere inside them, whether the fitted
  part decides the answer or only puts candidates in order. Those seven divide
  again by where their numbers come from. Some are fitted from nothing on this
  cell's own pictures, so everything they know comes from the table in front of
  them. The others begin from a large model already fitted elsewhere on ordinary
  photographs, and what that trades is knowledge of a world this cell is not:
  the cell can only render a grey picture shaded from depth, and such a model
  has to accept that in place of a photograph. Each document is written from the
  beginning, with diagrams, and each ends with **the general methods behind
  it** — the named, published techniques it is built from, with an honest note
  on where each one is normally the right tool and where it is not.

  | | Solution | Family | Built |
  |---|---|---|---|
  | 1 | [Split the blob in the picture](solutions/programmed/01-split-the-blob-in-the-picture.md) | programmed | |
  | 2 | [Cluster on the table](solutions/programmed/02-cluster-on-the-table.md) | programmed | the finding step of [`problem-2-programmed`](../../problem-2-programmed/README.md) |
  | 3 | [Move the camera](solutions/programmed/03-move-the-camera.md) | programmed | its veto tests, in both pipelines |
  | 4 | [Choosing the next look](solutions/learned/04-choosing-the-next-look.md) | hybrid | the Ranker in [`problem-2-learned`](../../problem-2-learned/README.md) |
  | 5 | [A model that already knows what a glass is](solutions/learned/05-a-model-that-already-knows-a-glass.md) | learned | |
  | 6 | [A network trained from scratch](solutions/learned/06-a-network-trained-from-scratch.md) | learned | the finding step of [`problem-2-learned`](../../problem-2-learned/README.md), the pipeline taken forward |
  | 7 | [Self-supervised from the arm's own movement](solutions/learned/07-self-supervised-from-the-arms-own-movement.md) | learned | |
  | 8 | [Segment anything, then keep the glasses](solutions/learned/08-segment-anything-then-keep-the-glasses.md) | learned | [`problem-2-pretrained`](../../problem-2-pretrained/README.md) |
  | 9 | [A fine-tuned instance segmenter](solutions/learned/09-a-fine-tuned-instance-segmenter.md) | learned | [`problem-2-pretrained`](../../problem-2-pretrained/README.md) |
  | 10 | [Amodal masks for the hidden part](solutions/learned/10-amodal-masks-for-the-hidden-part.md) | learned | [`problem-2-pretrained`](../../problem-2-pretrained/README.md) |

Two of these were written as two documents each and then joined, because in both
cases the second was not a different method but the same method with one part
changed. Solution 4 was two ways of ordering the same candidates, and solution 6
was two output heads on one network.

- [**The one that needs more than a
  simulator**](solutions/learned/learned-with-hardware.md) — a good answer that
  sits outside the ten, with the condition it fails: an active-vision policy,
  which learns for itself where to point the camera next rather than being told
  how to rank the choices. Nothing about it needs a different algorithm, and
  nothing it needs is missing from the cell. What it needs is throughput,
  because learning a policy means resetting the table and starting again over
  and over, and the usual way out of that is a simulator running many worlds at
  once on a graphics card. [Solution
  4](solutions/learned/04-choosing-the-next-look.md) is the same idea with the
  learning done by supervision instead, asking only whether a viewpoint will be
  worth taking, and that one fits the machine as it is.

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
costs arithmetic and nothing else. [Solution
3](solutions/programmed/03-move-the-camera.md) has the working.

**And a second finding, from the other end.** Because the outline of a found
glass is thrown outwards by an amount that can be computed exactly, the region
of table it could have been hiding can be computed too. So the question that
looks unanswerable — *is a glass missing?* — becomes one that is answerable:
*where could a glass have been hiding, and is that region big enough to hold the
smallest glass of the kind?* That turns silence into a finite list of places to
go and look at, and it is the second half of [solution
2](solutions/programmed/02-cluster-on-the-table.md).

## Where it sits

← [Problem 1 — one glass, start to finish](../problem-1) → [Problem 3 — glasses
standing too close](../problem-3)

[The five problems](../README.md) has the map.
