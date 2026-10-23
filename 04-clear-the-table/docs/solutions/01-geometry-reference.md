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

It reaches all 50 tables in under 7 arm minutes, gains 11 glasses and breaks 18 (see the
[results](../README.md#results)). Its gain is the largest of any solution, because it pushes
only crowded glasses and makes every safe push the geometry finds. Its breakage is also among
the largest, with a glass going over on about one table in three.

The breakage comes from the tipping rule. At the arm's top edge, the rule calls about four
crowded glasses in five on these tables uncertain: whether such a glass slides or tips
depends on the friction between it and the table, and nothing in the cell measures that.
Problem 3 settles the question with a test push of 5 mm, and it counts the glass as sliding
when the glass moved 1.5 mm. On the arm that test cannot work, because the box model places a
glass with a typical error of 1.2 mm, and 90 % of its errors are within 5 mm. So a slide
and a lean look the same. The geometry therefore pushes every uncertain glass, and knowing
which of them tip is what the learned solutions are meant to add.

Before it left out the glasses that already have room, and before the tipping rule was asked
at the arm's top edge, it gained 5 and broke 3, and it used all 15 arm minutes on only 22
tables. Most of its pushes then went to glasses that already had room, which are safe
to push and gain nothing.

## Where the code is

Its code is in [`01-geometry-reference/`](../../01-geometry-reference/README.md). It is one file, because the choosing is problem 3's planner and the rest is the turn-by-turn loop that every solution shares, in `shared/`.
