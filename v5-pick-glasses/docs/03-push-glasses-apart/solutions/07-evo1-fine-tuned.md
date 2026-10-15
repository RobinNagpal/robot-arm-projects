# Solution 7 — a newer and larger borrowed model, fitted on this bench

## Introduction

This solution asks whether a newer and larger borrowed model is worth its cost
on a task as narrow as pushing glasses apart. Six solutions already exist here,
and two of them are about borrowed models:
[solution 5](05-smolvla-as-it-downloads.md) runs a 450-million-number model
exactly as it downloads, and [solution 6](06-smolvla-fine-tuned.md) fits that
same model on this bench's own pushes. Both racked around 50 glasses of 251
where hand-written geometry racks 107, so the obvious next question is whether
the model was simply too small or too old. This solution answers that by
swapping the model for a larger and much newer one and changing nothing else.

By the end you will understand what kind of model Evo-1 is, what "flow
matching" means and why it makes every number here need a spread, which single
thing this solution is allowed to vary and why that discipline matters, and the
two sizes the borrowed checkpoint forces on this cell whether anybody wanted
them or not.

## The question this solution exists to answer

A measurement is only about one thing when everything else is held still, and
this repository keeps arriving at that rule. Solutions 5 and 6 are a pair that
differ only in whether the model was fitted here, so the gap between them
measures fitting. Solutions 3 and 6 are a pair that differ in model size, and
the work described in [solution 3's document](03-imitation-from-demonstrations.md)
had to go back and align their demonstration bands before that pair meant
anything.

This solution is the third such pair, and its one difference is the borrowed
model itself. Everything that could otherwise vary is not merely matched but
shared: the demonstrations are solution 6's own folder read as it stands, the
rule for reading a model's numbers as a jaw waypoint is solution 5's own
function imported rather than copied, and the loop that clears a table push by
push is solution 5's own loop. Sharing a file is a stronger guarantee than
copying a recipe, because it removes even the simulator's randomness from the
difference between two results.

## What kind of model Evo-1 is

Evo-1 is a **vision-language-action model**, which is a model that reads a
picture and a sentence and answers with a run of actions. That is the same kind
of model as the one solutions 5 and 6 use, which is what makes the comparison
fair: a comparison with solution 3 instead would mix up size with whether the
model had ever been trained on anything before.

Two numbers describe it. It holds about **775 million** numbers, against
SmolVLA's 450 million, so it is roughly seventy per cent larger. It was
published in **November 2025**, which makes it about two years newer. Its
vision-language half is InternVL3-1B, a general picture-and-text model that
knows nothing about robot arms, and its action half is the part that turns what
that half understood into motion.

## Flow matching, and why every number needs a spread

The action half does not calculate an answer. It **draws** one, by a method
called flow matching, and the idea is worth understanding because it decides
how this solution has to be measured.

Think of it as the reverse of smudging a photograph. During training the model
is shown a real chunk with noise mixed into it, and it is asked which direction
leads back towards the real chunk. Do that enough times and the model learns a
direction field: for any noisy chunk, which way is less noisy. At answering
time it starts from pure noise and walks that field, a fixed number of steps,
until what is left is a plausible chunk.

Two consequences follow. The first is that **the loss cannot be read as a
distance.** What the training reports is an error in a direction, not an error
in millimetres, so the fitting also measures something a reader can picture:
how far the model's waypoints land from the teacher's own waypoints on tables
it was not fitted on. The second is that **the same table asked twice is
answered twice**, because the noise it starts from is fresh each time. So a
single run is never a result here, and the scorecard reports a spread over both
sources of variation: the noise within a fit, and the difference between fits
trained with different seeds.

## What is fitted, and what is left frozen

A 775-million-number model cannot be fitted whole on a 24-gigabyte laptop, so
something has to stay still. Solution 6 solves this with a low-rank
correction, which adds a small adjustable piece beside each weight table and
freezes the rest. Evo-1 does not need that trick, because **it names two
training stages of its own.** In the first stage the vision-language half is
frozen and only the action half moves. In the second everything moves.

This solution uses the first stage, so **122 million of the 775 million numbers
are fitted**. That is not a saving invented here to fit the machine, which
matters: it is the model's own published first stage, so using it is using the
model as intended rather than crippling it. It also means the two solutions are
fitted in comparable ways, each using its own model's intended cheap path.

## What the machine forced, and what it did not

The task that asked for this work expected trouble, because Evo-1's source
mentions NVIDIA's CUDA in three places and this machine has no NVIDIA card.
The honest answer is that **there was no trouble**: the model runs here with no
change to its code at all, only to its configuration. Of the three mentions,
one is a default argument, one is a guard that switches a CUDA-only precision
trick off by itself, and one asks for a specialised attention kernel that is
simply absent, so the model falls back to ordinary attention. Three settings
were enough, and that is a result worth recording because it was the main
unknown.

**Two other things were forced, and these are real differences from solutions 5
and 6 rather than nothing.**

The first is the picture. This cell renders its top view at 384 pixels square,
and Evo-1 refuses any size but its checkpoint's own 448, because the number of
image tokens the checkpoint expects is fixed inside it. So the view is scaled
up before it goes in. Scaling up invents no detail, so this is not an advantage
over the other two solutions; it is a cost, paid in tokens for a picture that
is no sharper.

The second is the answer's width. Evo-1 always answers 24 numbers for each
waypoint, because it was built to serve many different robots, and this cell
needs 6. The model's own post-processing trims the rest away. Nothing is lost,
but it is worth seeing that a general model carries that generality as dead
weight on a specific cell.

## How the concepts fit together

Putting it in one picture: the cell measures a table and renders a view of it,
the view is scaled up to the size the borrowed checkpoint demands, the model
reads that view together with one fixed sentence, its frozen vision-language
half turns both into a description, its fitted action half walks noise into a
chunk of 50 waypoints under that description, the extra 18 numbers a waypoint
are trimmed away, solution 5's reading turns the remaining 6 into jaw
positions, and solution 5's loop lowers the jaw onto the first of them and
follows the rest. Everything in that chain except the model and the scaling is
shared with solution 6, which is what lets the difference in score be read as a
difference in model.

## Results

**Being measured.** The three fits and the scoring run are in progress, and
this section will carry the scorecard beside solutions 5 and 6, with its
spread, as soon as they finish. Nothing is claimed until then.

One expectation is worth setting in advance, so that it cannot be adjusted
afterwards to match whatever arrives. Recency is probably not what limits this
task. Solution 5 shows that a borrowed model used as it downloads racks 48
glasses where geometry racks 107, and the three measurements reported in
solution 3's document locate that solution's limit in the straight vertical
approach rather than in anything a bigger model would fix. So the honest
prediction is that Evo-1 lands in the same band as solutions 5 and 6, and the
interesting number will be what it costs per push rather than what it scores.
