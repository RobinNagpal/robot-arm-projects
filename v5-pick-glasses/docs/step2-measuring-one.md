# Step 2 — measuring one

The arm carries the wrist camera to a point beside the glass, 300 mm away and
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
about 277 pixels. At the 300 mm standoff:

    300 / 277 = 1.08 mm per pixel

and the frame is 240 × 1.08 ≈ 260 mm tall, which is why aiming it at 120 mm
above the table fits anything from a 60 mm tumbler to a 240 mm flute.

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

About a millimetre. One pixel is 1.08 mm at this standoff, and smoothing along
the height does nothing to improve resolution *across* it.

That figure is not a footnote; it sets a number further down. When the fingers
close on the glass in step 5, the width at first contact is compared against
the width the camera predicted, and the tolerance on that comparison is 4 mm.
Four rather than one, because one would fail on a good grasp about as often as
on a bad one. A tolerance tighter than the measurement is a tolerance that
reports noise as failure.

→ [Step 3 — what kind of glass is it](step3-what-kind-of-glass.md)
