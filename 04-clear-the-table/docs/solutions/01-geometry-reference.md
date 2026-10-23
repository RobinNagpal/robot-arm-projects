# Solution 1 — the geometry reference

Nothing in this solution is learned. It exists so that every learned solution has a number
to be compared with. This page explains how it chooses a push and why its settings never
change.

## How it chooses a push

It uses problem 3's geometry. For every glass that is short of room, it tries every
direction and distance, and it keeps the pushes where the hand fits between the glasses on
the way and the glass ends with room. Of those, it takes the shortest.

The chosen push is lengthened by two centimetres when the geometry still allows it. This is
because a very short push, planned in advance with no feeling of contact, often ends just
as the hand touches the glass, and so moves it by almost nothing.

## What it leaves alone

Problem 3's planner is used as it is, but the arm's cell differs from problem 3's in two ways
that the planner cannot know about, so the solution tells it about both.

The first is that a glass with room stays on the table. In problem 3 such a glass is lifted
off as soon as it has room, so problem 3's planner never sees one. Here it would look like the
easiest glass of all to free, because the shortest push of all gives it room, and that push
gains nothing and can tip the glass. So the solution leaves out every glass that already
stands where a freeing push would put it. Such a glass is still an obstacle, and every other
push keeps clear of it.

The second is the height of the hand. Problem 3's tipping rule says whether a push slides a
glass or tips it, and the answer depends on how high the hand's top edge meets the glass,
because a push higher up turns the glass over more easily. The arm's hand rides 10 mm higher
than problem 3's, so the rule is asked at the arm's own top edge. A glass with a narrow foot
that problem 3's hand could slide can tip under the arm's hand, and then it is not pushed.

## Its settings are fixed

Every push uses one safe set of settings: the hand low, a middle stroke speed and some
extra padding round each box. Because the settings never change, it treats a stemmed glass
exactly like a straight one. If MoveIt refuses a push, that glass is not asked for again on
the same table. The glass is remembered by where it stands, not by its number, because the box
model can list the glasses in a different order on the next look.

## How it does

It gains 5 glasses and breaks 3, and it uses all 15 arm minutes on only 22 tables (see the
[results](../README.md#results)). It spends about 40 arm seconds on each table, where the
world model spends about 6, because it makes every push the geometry finds instead of
judging which ones are worth making. It also cannot tell which glasses tip. Both are what
the learned solutions are meant to improve.

## Where the code is

Its code is in [`01-geometry-reference/`](../../01-geometry-reference/README.md). It is one file, because the choosing is problem 3's planner and the rest is the turn-by-turn loop that every solution shares, in `shared/`.
