# Step 3 — what kind of glass is it

The arm now has a profile. Before it can choose a grip it has to decide which
rule applies, and that means deciding what kind of glass this is.

Code: `classify()` in `glasses/detect.py`.

## The realisation that removes a whole component

A "kind" in this project is a **shape**: a tube, a cone, a bowl on a stem. And
the profile from step 2 is a *description of the shape*. So the kind can be
read off the profile with a few arithmetic tests, and this project needs no
trained classifier, no labelled dataset and no model to keep up to date.

That is worth pausing on, because the reflex when a robot has to recognise
something is to train a classifier. Here it would be both more work and less
reliable than three comparisons.

## The three tests, in an order that matters

```python
waist = profile.waist_at()
if waist is not None:
    fraction = waist / profile.total_height
    return "short_stemmed_glass" if fraction < 0.17 else "stemmed_glass"

lean = median slope over the lower half
return "tapered_glass" if lean > 6 degrees else "straight_glass"
```

**Is there a waist?** A waist is a local narrowing with wider glass above and
below it. That is what a stem is, and nothing else on a drinking glass looks
like one.

The order is not incidental. A stemmed glass *also* has a sloping bowl, so
asking about slope first would call every wine glass tapered and hand it the
wrong rule.

**If there is a waist, how far up is it?** This is the one place the classifier
has to separate two things the silhouette barely distinguishes, and the
threshold came from looking at the populations rather than from a principle. A
wine glass's waist sits at 20–28% of its height. An Irish coffee glass's sits
at about 13%. `SHORT_STEM_FRACTION` is 0.17, which leaves room on both sides.

They are separated at all because they want different things: a different
search band, a different opening range, and a very different force cap — a
wine glass stem is thin-walled and an Irish coffee glass is thick.

**If there is no waist, does the wall lean?** `TAPER_THRESHOLD_DEG` is 6,
measured over the lower half of the glass, because that is where a grip would
go. Below six degrees, the wall is upright enough for flat pads to press on
without sliding; above it, they would.

Note what that threshold is a statement about. It is not a fact about
glassware, it is a fact about **the gripper**. Fit softer pads and it moves.

## What the classifier actually looks like

![Classification from the measured profile](../images/classify-from-profile.png)

Every glass in that picture is one the project generated at random
proportions. The marker shape says which kind it was *made* as; the colour says
what `classify()` *called* it. The two dotted lines are the two thresholds.

Three things are visible in it.

**The stemmed and short-stemmed populations separate cleanly** — the 0.17 line
has empty space on both sides, which is what a threshold should look like.

**Straight and tapered glasses overlap at the boundary.** Some glasses drawn as
tapered were called straight. That is not an error, and it took a wrong test to
work out why.

## The test that was asking the wrong question

There was a test called `test_every_drawn_glass_is_classified_as_its_own_kind`.
It demanded that a glass be labelled with the kind it was generated as, and it
failed.

The test was wrong, not the code. A glass drawn as a tapered glass with a very
shallow taper is, physically, a glass with nearly upright walls — and the
straight-glass rule holds it perfectly well. Insisting on the generated label
would have meant contorting the classifier to preserve a distinction that does
not matter to the gripper.

The test now asks the question that does matter:

> does every glass get a kind whose rule can actually hold it?

That is both easier to pass and much harder to cheat, because it can only be
satisfied by the arm ending up able to pick the glass up.

## Returning nothing is a real answer

`classify()` can return `None`, and `task.py` turns that into `UnknownShape`
and leaves the glass standing with a line in the report.

This matters more than it looks. The alternative — snapping every shape to the
nearest known kind — means an unfamiliar object gets handed a rule derived from
something it is not, and the arm closes its fingers somewhere that was never
checked. A project that refuses to say "I do not know what that is" is a
project that will eventually break something.

→ [Step 4 — where to hold it](step4-where-to-hold-it.md)
