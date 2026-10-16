# Solution 7 — a newer and larger borrowed model, fitted on this bench

## Introduction

This solution asks one question. On a task as narrow as pushing glasses apart,
is a newer and larger borrowed model worth its cost?

Two solutions already use a borrowed model.
[Solution 5](05-smolvla-as-it-downloads.md) runs a 450-million-number model
exactly as it downloads. [Solution 6](06-smolvla-fine-tuned.md) fits that same
model on this bench's own pushes. Both racked around 50 glasses of 251, where
hand-written geometry racks 107. So the next question is whether the model was
too small or too old. This solution swaps in a larger and much newer model and
changes nothing else.

This page covers what Evo-1 is, which one thing this solution varies and why,
and the two sizes the borrowed checkpoint forces on this cell.

## The question this solution exists to answer

A measurement is about one thing only when everything else is held still.
Solutions 5 and 6 differ only in whether the model was fitted here. So the gap
between them measures fitting. Solutions 3 and 6 differ in model size.
[Solution 3's document](03-imitation-from-demonstrations.md) had to align their
demonstrations before that pair meant anything.

This solution makes a third pair with solution 6. Its one difference is the
borrowed model. Everything else is not just matched but shared:

- the demonstrations are solution 6's own folder, read as it is;
- the rule that turns the model's numbers into a jaw waypoint is solution 5's
  own function, imported, not copied;
- the loop that clears a table push by push is solution 5's own loop.

Sharing a file is stronger than copying a recipe. It removes even the
simulator's randomness from the difference between two results.

## What kind of model Evo-1 is

Evo-1 is a **vision-language-action model**: it reads a picture and a sentence
and answers with a run of actions.
[Solution 5](05-smolvla-as-it-downloads.md#a-model-that-sees-is-told-and-acts)
explains this kind of model. Solutions 5 and 6 use the same kind, which keeps
the comparison fair.

Two numbers describe it. It holds about **775 million** numbers, against
SmolVLA's 450 million, so it is about seventy per cent larger. It was published
in **November 2025**, about two years newer. Its vision-language half is
InternVL3-1B, a general picture-and-text model that knows nothing about robot
arms. Its action half turns what the first half understood into motion.

## Flow matching, and why every number needs a spread

Evo-1's action half draws its answer by **flow matching**. It starts from noise
and walks towards a plausible chunk of waypoints in a fixed number of steps.
SmolVLA works the same way, and
[solution 5](05-smolvla-as-it-downloads.md#flow-matching-and-why-one-run-is-not-enough)
explains it.

Two consequences matter here. First, **the training loss is not a distance.**
So the fitting also measures something a reader can picture: how far the
model's waypoints land from the teacher's, on tables it was not fitted on.
Second, **the same table asked twice gets two answers.** So the scorecard
reports a spread over both the noise within one fit and the difference between
fits with different seeds.
[The examiner](../the-examiner.md#two-things-this-scorecard-needs-that-problem-2s-did-not)
explains why a spread is needed.

## What is fitted, and what is left frozen

A 775-million-number model cannot be fitted whole on a 24-gigabyte laptop. So
part of it must stay still. Solution 6 uses
[a low-rank correction](06-smolvla-fine-tuned.md#low-rank-adaptation--a-small-correction-instead-of-a-large-change)
for this. Evo-1 does not need that, because **it has two training stages of its
own.** In the first stage the vision-language half is frozen and only the
action half moves. In the second stage everything moves.

This solution uses the first stage. So **122 million of the 775 million numbers
are fitted**. This is not a shortcut made up to fit the machine. It is the
model's own published first stage, so the model is used as intended. Each of
solutions 6 and 7 uses its own model's intended cheap path.

## What the machine forced, and what it did not

Evo-1's source mentions NVIDIA's CUDA in three places, and this machine has no
NVIDIA card. Trouble was expected. **There was none.** The model runs here with
no change to its code, only to its configuration. One mention is a default
argument. One is a guard that switches a CUDA-only precision trick off by
itself. One asks for a special attention kernel that is absent, so the model
falls back to ordinary attention. Three settings were enough. That was the main
unknown, so it is worth recording.

**Two other things were forced. These are real differences from solutions 5
and 6.**

The first is the picture. This cell renders its top view at 384 pixels square.
Evo-1 accepts only its checkpoint's own 448, because the number of image tokens
is fixed inside the checkpoint. So the view is scaled up first. Scaling up adds
no detail. It is a cost paid in tokens, not an advantage.

The second is the width of the answer. Evo-1 always gives 24 numbers per
waypoint, because it was built for many robots. This cell needs 6. The model's
own post-processing trims the rest. Nothing is lost, but a general model
carries that generality as dead weight on one specific cell.

## How the concepts fit together

The whole chain, in order:

1. The cell measures a table and renders a view of it.
2. The view is scaled up to the size the checkpoint demands.
3. The model reads the view and one fixed sentence.
4. Its frozen vision-language half turns both into a description.
5. Its fitted action half walks noise into a chunk of 50 waypoints under that
   description.
6. The extra 18 numbers per waypoint are trimmed away.
7. Solution 5's reading turns the remaining 6 into jaw positions.
8. Solution 5's loop lowers the jaw onto the first one and follows the rest.

Everything except the model and the scaling is shared with solution 6. So a
difference in score can be read as a difference in model.

## Results

**The fits were made. The scoring run was not.**

Three fits were made, one per seed. The distance between this model's answers
and the teacher's own waypoints was measured on tuning tables nothing was
fitted on. It went from 302 mm to 288 mm over a thousand steps. At the end the
three seeds differ by only a millimetre, so they agree.

The glass zone is 320 mm across. An answer 288 mm from the teacher's is not a
push at the wrong glass. It is a motion somewhere else on the table, which is
where this model started. **The fitting did not teach it the task.** Solution 6,
with the same demonstrations and the same budget, reached 85 mm.

The scoring run was stopped. It would have measured a policy that aims nowhere
near the glasses, at a cost of about two hours of this machine's graphics chip.
[Solution 5](05-smolvla-as-it-downloads.md) already measures what an unfitted
borrowed model does on this bench. The finding is in the fitting curve, and the
curve has three seeds behind it.

**This is not evidence that a newer or larger model is worse here.** Both fits
got the same number of steps, but that hid a thirty-fold difference in what
each had to learn. Solution 6 adjusts a few million numbers beside a model that
already produces robot motions. This solution fits a hundred and twenty-two
million numbers from random values. The first stage freezes the half that can
see and leaves the half that moves to be built from nothing. A model trained
too little looks just like a model that cannot do the task. The only way to
tell them apart is to keep training.

The next step is deliberately the cheap one.
[Issue #24](https://github.com/RobinNagpal/robot-arm-projects/issues/24) asks
whether this action head can memorise fifty demonstrations. A network with a
hundred and twenty-two million free numbers should find that easy. If it
cannot, the fault is in how the two halves are joined, and more training would
not help. If it can, the fault is only scale, and a longer fit on one seed is
worth the machine time.

One expectation is set now, so it cannot be changed later to match the result.
Newness is probably not what limits this task. Solution 5 shows that a borrowed
model used as it downloads racks 48 glasses, where geometry racks 107.
Solution 3's document places that solution's limit in the straight vertical
approach, which a bigger model would not fix. So the likely result is that
Evo-1 lands in the same band as solutions 5 and 6. The interesting number will
be its cost per push, not its score.
