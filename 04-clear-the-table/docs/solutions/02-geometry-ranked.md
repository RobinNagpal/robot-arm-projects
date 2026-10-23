# Solution 2 — geometry ranked

Solution 2 is the [geometry reference](01-geometry-reference.md) with one thing changed: the
way it chooses between the pushes the geometry allows. Solution 1 always takes the shortest
safe push that gives a glass room. This solution scores every safe push with problem 3's fitted
trees and takes the one with the best score. This page explains how it chooses, why the trees
are problem 3's own, and what the change does on the arm.

## How it chooses a push

It starts from exactly the list solution 1 chooses from: every push, for every glass short of
room, in which the hand fits between the glasses on the way. Problem 3's fitted trees then give
each push a score, which is their estimate of how much room the push will gain, worked out from
eight measurements such as how far the push goes and how much room there is where the glass
will end. The push with the best score is made. Like solution 1, it lengthens a push that frees
a glass by two centimetres when the geometry allows it, it uses the same fixed settings for
every push, and it does not ask again for a glass MoveIt refused. It also leaves out the same
glasses as solution 1, the ones that already have room, and it asks problem 3's tipping rule
at the arm's top edge, as solution 1 does. One of the trees' eight measurements is how close a
push comes to tipping the glass, and that measurement is taken at the arm's top edge too.

So the two solutions differ in one decision only. Comparing them measures what the ordering is
worth when the arm makes the pushes.

## Why the trees are problem 3's own

The trees are loaded from problem 3's fitted file and are not fitted again here. If they were
fitted again, a difference between problem 3's solution 2 and this one could come from the new
fit rather than from the problem. Because they are problem 3's, they were fitted in problem 3's
cell, where the hand feels for the glass before it pushes, and on the room a push gains.

## How it does

It reaches all 50 tables in under 8 arm minutes, gains 9 glasses and breaks 16 (see the
[results](../README.md#results)). Solution 1, choosing from the same pushes with the same
settings, gains 11 and breaks 18. The difference is within the noise of one run, so the
ordering learned in problem 3 neither helps nor harms on the arm.

That is not surprising, because the trees cannot fix what makes solution 1 break glasses. Both
solutions push glasses whose tipping is uncertain, and the trees were fitted in problem 3's
cell, where an uncertain glass was always tested with a short push before it was pushed for
real. So the trees never had to learn which uncertain glasses tip. To help here, they would
have to learn from pushes the arm made, including the ones that tipped a glass, which is what
the [world model](04-world-model.md) does.

## Where the code is

Its code is in [`02-geometry-ranked/`](../../02-geometry-ranked/README.md). It is one file,
because the list of pushes and the trees are problem 3's, and the rest is solution 1's.
