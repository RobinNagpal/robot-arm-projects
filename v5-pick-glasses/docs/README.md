# Walkthrough

Six documents, one per stage of a run, in the order the arm does them.

They exist because the interesting part of this project is invisible in the
code. `find_grip()` is thirty lines, and reading them tells you which functions
were called — not why the stem of a wine glass is the only place on it worth
holding, or how the fingers end up 9 mm apart when nobody wrote 9 mm anywhere.
These documents take one stage at a time and put the project's own numbers
through it.

Every picture in `../images/` is drawn by [`make_images.py`](make_images.py),
which imports the project's modules and plots what they return. Nothing is
illustrative. If a rule changes, the pictures change with it.

- [**Step 1 — finding the glasses**](step1-finding-the-glasses.md). Why a depth
  camera returns nothing where a glass is, why that is the signal rather than
  the problem, and how a pixel becomes a place on the table without a depth
  reading.
- [**Step 2 — measuring one**](step2-measuring-one.md). One picture from the
  side, and why one is enough. Pixels to millimetres using a distance the arm
  knows for a reason that has nothing to do with the glass.
- [**Step 3 — what kind of glass is it**](step3-what-kind-of-glass.md). Reading
  the kind off the measured profile with three tests, and why this is both
  cheaper and more honest than classifying from above.
- [**Step 4 — where to hold it**](step4-where-to-hold-it.md). Three rules, the
  features they read, the four ways an answer gets rejected, and why the
  opening is never a number from a file.
- [**Step 5 — how hard to squeeze**](step5-how-hard-to-squeeze.md). Why the
  weight of a glass cannot be seen, what the estimate is good for, and the
  ten-millimetre lift that settles it.
- [**Step 6 — turning it over and standing it down**](step6-turning-it-over.md).
  Rotating about the grip rather than the wrist, the wrist limit that has to be
  checked before the fingers close, the tilt budget, and feeling for the rack.

For the reasoning behind these choices, read
[`../implementation-notes.md`](../implementation-notes.md). For which file and
function each stage lives in, read [`../pseudocode.md`](../pseudocode.md).
