# Step 2 — measuring one

The arm carries the wrist camera to a point beside the glass, 380 mm away and
120 mm above the table, and takes **one** picture. Out of it comes a width for
every height up the glass, in millimetres.

Code: `glasses/perception.py`, and `_view_from()` in `task.py`.

## Why one picture is enough

A drinking glass is a **solid of revolution**: it is a shape spun about a
vertical axis. Spin anything about an axis and the outline you see from the
side is the same from every side, and that outline is the full description of
the shape. The width on screen at some height *is* the diameter of the glass at
that height.

So there is nothing a second viewpoint could add. A circuit of the table — the
obvious thing to do with an object you cannot see through — would return the
same silhouette four times.

The one exception is a handle, because a mug with a handle is not a solid of
revolution. That is the only reason `expects_handle` exists in `spec.py`, and
the only case that takes a second picture, a quarter turn round.

## Pixels to millimetres

A camera measures angles, not lengths. A pixel covers `1/fx` radians; how many
millimetres that is depends entirely on how far away the thing is.

Here the camera is 320×240 with a 60° horizontal field of view, so `fx` is
about 277 pixels. At the standoff this works out at:

    380 / 277 = 1.37 mm per pixel

and the frame is 240 × 1.37 ≈ 330 mm tall, which is what lets the camera aim
at 120 mm above the table and still catch both the foot a glass stands on and
the rim of the tallest glass the cell handles.

The standoff itself is not written down. It is worked out per cell from the
lens, the height the camera aims at and that tallest glass, because what has
to fit in the frame is as much a question about the lens as about the glass,
and a number written down here would be right for one camera only. It comes to
380 mm with this one. It used to be a flat 300, and the last section on this
page is about what that cost.

The standoff is the whole conversion, so the arm has to *know* it rather than
measure it. It does, and for a reason that has nothing to do with the glass:
the glass stands on the table, the table's position has been known since
startup, and the arm put the camera there itself. **At no point does the arm
need a depth reading of the glass** — which, as step 1 established, it could
not get anyway.

## Reading the silhouette

Three details in `row_widths()` and `smooth()` do more work than they look.

**The width is edge to edge, not a pixel count.** A transparent object
segments with holes in the middle: the model sees the table through it and
labels those pixels as background. Counting glass pixels in a row therefore
undercounts badly, and gets worse the more transparent the glass is. The
distance from the leftmost glass pixel to the rightmost does not care about
holes in the middle.

**The profile is smoothed with a five-row median.** A segmentation edge wanders
by a pixel or two, and an unsmoothed profile has a waist in every wobble — which
matters here, because "find the waist" is a rule the project actually uses.

**The raggedness check runs on the raw widths, not the smoothed ones.** This
was a bug for a while and is worth spelling out. Smoothing makes any mask look
clean, so a quality check applied afterwards never fires. The question
"was this mask worth trusting?" has to be asked of what came out of the mask;
the smoothed version is what gets measured. The threshold is 2% of the glass's
own width, averaged over neighbouring rows.

If the mask fails that check, or holds almost no glass, `profile_from_mask()`
raises `NotMeasurable` and the glass is left standing. It is not guessed at.

## What comes out

For the wine glass in the pictures below — 153.6 mm tall, drawn at random
proportions the arm knows nothing about:

| Measured | Value |
| --- | --- |
| Total height | 153.6 mm |
| Widest point | 64.1 mm, at the rim |
| Waist | 30.8 mm up |
| Width at the waist | 9.2 mm |

![A profile and the grip read off it](../images/profile-to-grip.png)

The left panel is the glass. The right panel is the same information as the
project actually holds it: two arrays, a height and a width, one pair per row
of the picture. Everything after this point is arithmetic on those two arrays,
which is why none of it needs a robot to test.

## How good is the measurement, really

About a millimetre and a half. One pixel is 1.37 mm at the standoff this
works out at, and smoothing along the height does nothing to improve
resolution *across* it.

That figure is not a footnote; it sets a number further down. When the fingers
close on the glass in step 5, the width at first contact is compared against
the width the camera predicted, and the tolerance on that comparison is 4 mm.
Four rather than one, because one would fail on a good grasp about as often as
on a bad one. A tolerance tighter than the measurement is a tolerance that
reports noise as failure.

## Five things that were wrong with this picture

Once the survey started working, this step was asked real questions for the
first time, and most of its answers came back wrong. They were five separate
faults that happened to look like one, and untangling them is most of what it
took to measure a glass at all.

**The picture came out rolled.** The function that points the camera pins the
last free angle — the roll about the direction it is looking — using a hint
chosen for poses that look downwards, and every pose here looks along the
table instead. For those it handed back a different roll for each side of the
glass the arm happened to stand on, so the same glass measured differently
depending on where the arm was. Since the profile is read one row at a time
with a row meaning a height, a picture that comes out turned measures the
glass across instead of up. The roll is now pinned against the room's own
upright, the same from every side.

**The camera stood too close.** It looks level from `MEASURE_VIEW_HEIGHT`
above the table, so at the old 300 mm the foot of the glass sat 21.8 degrees
below the middle of the picture against a half frame of 23.4 — inside the
picture, but in the last few pixels of it, and seen almost edge on. A wine
glass with its foot cut off the bottom is a bowl narrowing into a stem with
nothing below it, and that shape has no waist in it, and a glass with no waist
is not a stemmed glass to any rule that looks for one. How far back to stand
is now worked out per cell from the lens, the height the camera aims at and
the tallest glass the cell handles, which comes to 380 mm here — and that is
why the resolution above is 1.37 mm rather than 1.08.

**It measured everything else in the frame too.** A glass with a neighbour
standing behind it measured as one glass the width of the table, because
`row_widths()` measures every hole in the mask at once. It now measures the
one in the middle, which is the one the camera was aimed at, and the arm
prefers a line of sight with nothing behind it — judged as an angle at the
camera rather than as a distance on the table, because an angle is what
decides whether two glasses touch in a picture.

**The test for a ragged outline assumed a bigger glass.** `MAX_RAGGEDNESS` is
a fraction of the glass's own width, which quietly assumes a glass a
hundred-odd pixels across; standing further back made them forty, and the
one-pixel wander that any mask edge has is already two and a half per cent of
forty. Clean pictures of narrow glasses were being refused. Whichever of the
fraction and two pixels is the more forgiving now wins, which leaves the test
doing its real job — catching a reflection or a neighbour — without catching
ordinary noise.

**Nothing checked that the answer was possible.** A profile taller than the
tallest glass the cell handles is two glasses standing one behind the other,
and a foot further from where the arm aimed than a glass is wide belongs to a
different glass. Either of those now sends the arm round to look from another
side, which is what the retry was always for and what the note under
`raggedness()` had been recommending all along.

→ [Step 3 — what kind of glass is it](step3-what-kind-of-glass.md)
