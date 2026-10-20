# Solutions 1 and 2 — the geometry reference

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

## Its settings are fixed

Every push uses one safe set of settings: the hand low, a middle stroke speed and some
extra padding round each box. Because the settings never change, it treats a stemmed glass
exactly like a straight one. If MoveIt refuses a push, it is not asked for again.

## How it does

It gains 2 glasses and breaks 4, and it uses all 15 arm minutes on only 22 tables (see the
[results](../README.md#results)). It spends about 40 arm seconds on each table, where the
world model spends about 6, because it makes every push the geometry finds instead of
judging which ones are worth making. It also cannot tell which glasses tip. Both are what
the learned solutions are meant to improve.
