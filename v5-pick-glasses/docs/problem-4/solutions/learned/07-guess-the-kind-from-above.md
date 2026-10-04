# Solution 7 — guess the kind from above

*Hybrid, with the model as a ranker. From the survey alone, before any side
view, guess each glass's kind from how tall and how wide it looks from above.
Use the guess only to plan — which glass to push, which to measure first,
which slots to keep — and never to choose a grip. Rejected: every use either
already has the number it needs, or cannot afford the guess's mistakes.*

> **The cell is described once, in [the cell](../../../the-cell.md).** [The
> problem](../../problem.md) says what is asked for, and the [solution
> overview](../solution-overview.md) says where the numbers come from. What
> follows is only what is specific to this solution.

## Introduction

In problem 4 the kind arrives late. It comes from the side view, and the side
view comes after the survey, after the racking of the glasses with room, and —
for a crowded glass — possibly after a push. Several decisions before that
point would be easier with the kind in hand.

So the obvious idea is to guess it early. The survey sees every glass from
above. Its depth readings give how high the rim stands, and its outline gives
the widest part. Problem 3's bench reports both with every glass it sees. A
wine glass is tall for its width; a tumbler is not. Can that be enough?

This document measures how good the guess is, and then asks, use by use,
whether it helps. It does not.

## The guess

A nearest-neighbour vote: for a glass seen from above, find the five generated
glasses most like it in height and width, and take the kind most of them are.
Nearest neighbour is the fairest test of what the two numbers can say, because
it assumes nothing about where the lines between kinds fall.

Tested on 800 generated glasses, 200 of each kind, each one against the other
799, with the exact height and width — better than the survey will measure
them:

| Made as | guessed straight | tapered | stemmed | short-stemmed |
| --- | --- | --- | --- | --- |
| straight | **177** | 3 | 2 | 18 |
| tapered | 9 | **86** | 71 | 34 |
| stemmed | 12 | 27 | **161** | 0 |
| short-stemmed | 31 | 8 | 0 | **161** |

Right on 585 of 800, 73%. Straight, stemmed and short-stemmed are mostly
right. Tapered is right less than half the time, because the tapered range is
the widest of the four on purpose and overlaps all three others in height and
width.

## Where the guess would be used, and what it does there

### To bound the foot, before a push

This is the use that motivated it. [Solution
5](../programmed/05-measure-before-you-push.md) shows that the foot decides whether a glass
may be pushed, and that a glass nobody has measured has to be assumed to have
the narrowest foot any kind has. A kind guessed from above would give a foot
range per glass instead.

Look at which mistakes the guess makes. Tapered glasses have the narrowest
feet of the four, 0.38 to 0.58 of their widest part. The other kinds' feet are
0.70 to 0.98. **Every time a tapered glass is guessed as something else, its
foot is overestimated.** That happened to 114 of the 200 tapered glasses. A
foot overestimated is a push allowed that should not be, which is the direction
that topples a glass.

A ranker's mistakes are supposed to cost an attempt, not a glass. Here the
mistake feeds the one safety check the push has. So the guess cannot be used
for the foot, which was its main use.

### To plan the rack

[Solution 4](../programmed/04-plan-the-rack-for-the-whole-table.md) needs to know, for each
glass still standing, whether it will need an empty neighbour. That depends on
the glass's width and height, not its kind. The survey already gives both. The
kind would be a worse way to get a number that is directly measured.

### To choose which glass to measure first

[Solution 5](../programmed/05-measure-before-you-push.md) measures every crowded glass with a
clean side view, before any push. The order among them does not change what is
learned; every one of them is measured. The kind would decide nothing.

### To choose which glass to push

It would bias the push towards glasses guessed to have wide feet. That is the
foot use again, with the same mistakes.

## The verdict

Rejected. Where the guess is safe to use, the arm already has something better
— the width and height for the rack, the view check for the order. Where the
arm has nothing better — the foot of an unmeasured glass — the guess fails in
the dangerous direction for more than half of one kind.

It is kept in this list because it is the first thing anyone suggests, and the
reason it does not work is specific and worth knowing: **the kind with the
narrowest foot is also the kind whose shape from above overlaps the others
most.**

## What it would need

A table of generated glasses to vote against, or a small classifier trained on
them. The survey's height, which problem 3's bench reports and the real survey
would have to be shown to measure. Nothing else. The cost was never the
objection.

## Where it is strong and where it breaks

**Strong.** It is cheap, it needs no arm move, and it is right about most
straight, stemmed and short-stemmed glasses.

**Breaks.** On tapered glasses, the kind whose mistakes matter most. 114 of 200
guessed wrong, every one of them towards a wider foot.

## Where the idea comes from

**A prior from a cheap sensor.** Using a quick, rough measurement to set up
expectations for a slower, better one is standard, and often right. It works
when the rough measurement's mistakes are harmless to what it is used for.

**Why a ranker is not automatically safe.** [The problem 3
overview](../../../03-push-glasses-apart/solutions/solution-overview.md#three-families-and-what-hybrid-means)
says a ranker's mistakes cost one wasted attempt. That is true when the ranked
candidates have all passed a safety check that does not depend on the ranker.
Here the guess would be an input to the safety check itself, and that makes it
something closer to a decider.

## Where it sits among the other solutions

It is the alternative to [solution 5](../programmed/05-measure-before-you-push.md), which
gets the kind before a push by measuring it rather than guessing. Solution 5 is
used; this one is not.

← [Solution 6 — a learned second opinion on the name](06-a-learned-second-opinion-on-the-name.md) · [Solution 8 — the learned pipelines, retrained](08-the-learned-pipelines-retrained.md) →
