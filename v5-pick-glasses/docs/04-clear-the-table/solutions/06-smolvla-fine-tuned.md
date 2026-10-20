# Solution 6 — SmolVLA, fine-tuned

SmolVLA is the largest model here. It is a vision-language-action model: it reads pictures
and a sentence, and it writes an action. It was made to move a small arm's joints. Here it
is fitted a little so that it answers with a push instead. This page explains what it reads
and writes, what is fitted, and why so little fitting does not get it far.

## What it reads and writes

It reads the two wrist pictures from the start of each turn and one fixed sentence: *push
the crowded glasses apart so each has room, without tipping any*. It does not read the
boxes. So it must work out from the pictures alone where the glasses are and which ones to
push.

It writes twelve numbers: whether to stop, the point on the table it means to push (two
numbers), the direction (two numbers), the distance, and the six settings. The cell pushes
the glass whose box is nearest that point.

## What is fitted

The model's own 450 million numbers are never changed. Instead, a small low-rank correction
is added beside each attention layer, and only the correction is trained: 3.8 million
numbers, under 1 % of the model. This is LoRA, the usual way to teach a large model a new
task cheaply. The correction starts at zero, so before training the model is exactly the one
that was downloaded.

It is fitted on the same 883 examples that [imitation](03-imitation.md) copies, but with
pictures in place of boxes, for 600 training steps.

The model was built for an action of six numbers, and it silently cut its answer and its
training loss down to six. This had to be set to twelve, or the six settings would never be
trained, and nothing would warn about it.

## How it does

It loses 3 pickable glasses and breaks 22 (see the [results](../README.md#results)). With
the [safety check](safety-check.md) it breaks none, but it still gains nothing. Fitted on
fewer examples, it scored −1, which is within the same range. It has the same weakness as
imitation, since it copies only successes, and two more of its own. It must find the
glasses in the pictures, and as [the speed
table](../what-the-pushes-show.md#how-each-solution-sets-its-speed) shows, it gives every
kind of glass nearly the same settings. It also has very little to learn from: about 880
examples and 600 steps, for a model that was originally trained on millions of frames.
