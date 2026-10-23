# Solution 3 — imitation

Imitation learns by copying. It is shown examples of good pushes, and it is trained to
answer the same way on a new table. This page explains what it reads and writes, where its
examples come from, and why copying alone makes it break glasses. By the end you will also
know how a better teacher is being added.

## What it reads and writes

It reads the boxes, one row of numbers for each glass: where it stands, its radius, height
and foot radius, and how far it is from having room. It writes one answer: which glass to
push, or "finished", and for that glass the direction, the distance and the six settings.

## How it works

The network is small, about 81,000 numbers. A table has no natural order, so the network
treats the glasses as a set: a small transformer lets every glass look at every other one,
and the order of the rows makes no difference to the answer. Three small heads read the
result. One scores each glass, one scores "finished", and one writes the push for each glass.

Training is ordinary supervised learning, like fitting a function to examples. One loss
says which glass was chosen, or that the table was finished. A second loss says how the
push should be written, and it is used only at the chosen glass.

## Where the examples come from

The simulator is the teacher. From all [12,609 pushes](../what-the-pushes-show.md), a push
is kept as an example only if MoveIt planned it, no glass tipped, and it gave a glass room
or clearly loosened the table. Tables where every glass already had room are kept with the
answer "finished". This gives 883 examples, of which 288 say "finished".

## Why it breaks glasses

Every example is a push that worked, and almost all of them are pushes on straight glasses.
So the network learns *where* to push, but it never sees a glass that should be left alone.
It pushes stemmed and tapered glasses as readily as straight ones, and it breaks 19 glasses
on the held-out tables.

The [safety check](safety-check.md) fixes the breakage: with it, imitation breaks no glass
and gains 2, where it gains 1 without it. That small rise is within the noise of one run.
The check cannot raise the gain much, because it can only reject imitation's pushes, and
imitation rarely proposes a push that frees a glass.

## A better teacher: copying the ceiling

The ceiling search, which tries 30 pushes in the physics before every move, gains 24 glasses
where imitation gains 1. It cannot run on a real arm, but it can teach. It is run on
training tables, and every turn is saved as a lesson: the table, and the push the search
made. When no push the search tried was worth making, the lesson is "finished", even though
the table is still crowded. These are the examples imitation never had: tables to leave
alone. Training a fast network to copy a slow, strong method like this is called
**distillation**.

On 240 training tables the search gave 367 lessons: 127 pushes, and 181 crowded tables
marked "finished", most of them with stemmed glasses. Imitation was trained on its old 883
examples plus these lessons, with each lesson shown three times. On the held-out tables it
then broke 8 glasses instead of 19, because it had learned when to stop. Its gain, however,
stayed at 1, and with the safety check it scored +1 with nothing broken, which is no better
than the safety check alone. A few hundred lessons teach it when to stop, but too few good
pushes to copy.

A second run on 480 more training tables tripled the lessons to 1,103, and this did not
help. Two thirds of the lessons say "finished", so imitation learned to stop on almost every
table and gained nothing. Showing the pushes three times as often as the "finished" lessons
gave +3 with 7 broken, or +0 with nothing broken once the check was on. Leaving the
"finished" lessons out entirely did well on the tuning tables, but on the held-out tables it
broke 29 glasses, and with the check it lost 3. So no version that breaks nothing does
better than the plain imitation with the safety check. A few hundred example pushes are not enough for
imitation to learn which push frees a glass. That needs either many more lessons, or a model
that also learns from the pushes that failed, which is what the world model does.

## Where the code is

Its code and weights are in [`03-imitation/`](../../03-imitation/README.md), together with the program that runs the ceiling on training tables to write the extra lessons.
