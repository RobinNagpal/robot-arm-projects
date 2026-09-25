# The cell — the layout, the sensors, and the words

Every solution in this project works in the same room, with the same arm, the
same camera and the same table. Rather than restate those numbers in each
document, they are here once.

**Every dimension on this page is read from the project's own constants** by
[`make_cell_images.py`](../images/generators/make_cell_images.py), which imports
`arm/dimensions.py`, `table/layout.py`, `rack/layout.py` and
`glasses/shapes.py` and draws what it finds. If a number moves in the code, the
pictures move with it the next time the script runs. Nothing here is typed in
by hand.

## The layout, from above

![The cell from above](../images/cell-from-above.png)

The arm is bolted to the table at the origin. Everything it does happens in two
rectangles on that table:

- **the glass zone**, 320 by 360 mm, where glasses may stand;
- **the rack**, 60 by 40 mm, where they end up, upside down on pegs.

Both sit inside the ring the arm reaches comfortably — closer than 300 mm and it
is folded over itself, further than 780 mm and it is reaching straight out with
nothing left for the wrist. That ring is a working preference, not a hard joint
limit.

## The layout, from the side

![The cell from the side](../images/cell-from-the-side.png)

The table top is 750 mm above the floor and the arm stands on it, so **every
height in this project is measured from the table**, not the ground. A glass's
height, the camera's height, the rack's pegs: all from the table top.

The camera is only ever put in two poses, and almost every misunderstanding in
these documents comes from mixing them up.

| | the survey pose | the side-on pose |
|---|---|---|
| where | 450 mm above the table | 120 mm above the table |
| looking | straight down | level |
| how far from the glass | directly overhead | about 380 mm |
| one pixel covers | 1.62 mm | 1.37 mm |
| the frame covers | 519 by 390 mm of table | 439 by 329 mm |
| what it is for | finding everything, roughly | measuring one glass, precisely |

The 380 mm is **not a constant**. `MEASURE_STANDOFF` fixes only a floor of
300 mm — nearer than that and a glass fills the frame before it is all in it.
The distance actually used is worked out per run from the lens and the tallest
glass the cell handles, and comes to about 380 mm. `MEASURE_VIEW_HEIGHT` is a
fixed 120 mm, deliberately: the overhead view cannot tell how tall a glass is,
which is what the side view is for, so aiming at a fixed height is the only
option available.

## The glasses

![The four kinds](../images/the-four-kinds.png)

Four kinds, each drawn at random inside its own range of proportions. **No
glass's size is written down anywhere in this project** — not in a constant,
not in a test fixture, not in a mesh. The arm measures every glass during the
run. What the code holds is the *range the spawner draws from*, which is a
different thing and is what makes the tests meaningful.

| kind | height | across the top |
|---|---|---|
| straight glass | 65–170 mm | 45–90 mm |
| tapered glass | 120–200 mm | 75–105 mm |
| stemmed glass | 165–230 mm | 60–100 mm |
| short stemmed glass | 110–165 mm | 60–85 mm |
| **all four** | **65–230 mm** | **45–105 mm** |

## The sensors

![The sensors](../images/the-sensors.png)

Four, and that is the whole list. Everything else the cell believes is
arithmetic on these.

| sensor | where | rate | what it returns |
|---|---|---|---|
| **RGB-D camera** | on the wrist, 85 mm off the flange | 15 Hz | colour and aligned depth, 320 × 240, 1.047 rad across, usable from 0.05 to 3.0 m |
| **wrist force-torque** | between the flange and the gripper | 100 Hz | three forces and three torques |
| **pad contact** × 2 | one in each fingertip pad | 60 Hz | whether that pad is touching something |

There is a fourth thing that is not a sensor but is easy to mistake for one: an
**ArUco marker**, 70 mm square, printed on the rack. It is how the camera works
out where the rack is, rather than trusting that it was placed exactly.

The camera being *on the wrist* rather than above the table is the single fact
that shapes most of these solutions. It means the arm chooses its own
viewpoints. It means moving the camera costs seconds of arm time. And it means
the camera's pose is known exactly, from the joint encoders — which is what makes
[solution 9](problem-2/solutions/09-self-supervised-from-the-arms-own-movement.md)
possible at all.

## The words

Terms used throughout, several of which mean different things elsewhere.

**The survey.** The opening move of a run: the arm flies the camera over the
glass zone, looking straight down from 450 mm, and takes pictures from several
**stations** until every part of the zone has been seen. It answers *what is on
the table and roughly where*, not *how big is this glass*.

**A station.** One place the camera is parked during the survey. Each station
takes **two** pictures 120 mm apart — the **baseline** — so that the apparent
shift between them gives depth. Stations overlap by 35 per cent of a frame, so
a glass cut off at the edge of one picture is well inside another.

**Standoff.** How far the camera is from the thing it is looking at. Used almost
always of the side-on pose.

**The nadir.** The point on the table directly under the camera. Only meaningful
in the survey pose. Things directly under the camera are seen honestly; things
off to the side are seen at an angle, which matters more than it sounds.

**Splay.** The consequence of that angle. A glass is tall, so the ray from an
overhead camera through its rim carries on past its base and lands further out.
The silhouette leans away from the nadir, and a glass's outline therefore does
*not* sit where the glass does. Problem 1 measured what this costs: a glass
157 mm from the camera was reported at 244 mm.

**Mask, patch, blob.** A **mask** marks every pixel as glass or not glass. A
**patch** or **blob** is one group of touching marked pixels — what connected
components returns. One patch is not the same as one glass, which is the whole
of problem 2's first difficulty.

**Silhouette.** The outline of one glass in one picture. Not a circle in either
pose: from above it is a teardrop leaning away from the nadir, from the side it
is the glass's profile.

**Cluster.** A group of 3-D points that belong together, formed by distance in
the room rather than by adjacency in the picture.

**Footprint — and the one word that does double duty.** Read this one slowly.
Two different quantities get called by the same name:

- the **contact patch**, where the glass actually touches the table, which is
  30–88 mm across over the four kinds;
- the **flattened disc**, what you get when every point of a glass is dropped
  straight down onto the table, which is the glass's *widest* part and is
  45–105 mm across.

Most of these documents mean the second, because that is what
[clustering on the table](problem-2/solutions/02-cluster-on-the-table.md) groups
and what a circle is fitted to, and it is also what limits how close two glasses
can stand. [Solution 1](problem-2/solutions/01-split-the-blob-in-the-picture.md)
is the exception: its contact runs read the first. Where a number matters, the
documents say which they mean.

## Every constant, and where it lives

Numbers live with their subject and nowhere else, so this table is a directory
rather than a second copy.

| what | value | where it is defined |
|---|---|---|
| table top above the floor | 750 mm | `table/layout.py` `TABLE_TOP_Z` |
| table | 1600 × 1400 × 50 mm | `table/layout.py` `TABLE_SIZE` |
| arm's base | (0, 0) on the table top | `table/layout.py` `ROBOT_BASE` |
| comfortable reach | 300–780 mm | `arm/dimensions.py` `COMFORTABLE_REACH` |
| glass zone | 320 × 360 mm | `rack/layout.py` `GLASS_ZONE` |
| rack area | 60 × 40 mm | `rack/layout.py` `RACK_AREA` |
| rack top / peg | 770 mm / 55 mm tall | `rack/layout.py` `RACK_TOP_Z`, `PEG_HEIGHT` |
| ArUco marker | 70 mm | `rack/layout.py` `MARKER_SIZE` |
| survey height | 450 mm above the table | `arm/dimensions.py` `SURVEY_HEIGHT` |
| survey baseline | 120 mm | `arm/dimensions.py` `SURVEY_BASELINE` |
| survey overlap | 35 per cent | `arm/dimensions.py` `SURVEY_OVERLAP` |
| side-on standoff, floor | 300 mm | `arm/dimensions.py` `MEASURE_STANDOFF` |
| side-on view height | 120 mm above the table | `arm/dimensions.py` `MEASURE_VIEW_HEIGHT` |
| camera offset from the flange | 85 mm out, 15 mm up | `arm/dimensions.py` `CAMERA_OFFSET` |
| gripper opening | up to 95 mm | `arm/dimensions.py` `GRIPPER_MAX_OPENING` |
| lowest the fingers reach | 50 mm above the table | `arm/dimensions.py` `LOWEST_GRIP` |
| pad | 14 × 40 mm | `arm/dimensions.py` `PAD_HEIGHT`, `PAD_LENGTH` |
| camera | 320 × 240, 1.047 rad, 15 Hz | `arm/camera/wrist_camera.urdf.xacro` |
| the kinds and their ranges | see above | `glasses/shapes.py` `KIND_RANGES` |

Two useful numbers are **derived**, not stored, and are recomputed every run:

- the **focal length in pixels**, `fx = (320 / 2) / tan(1.047 / 2) ≈ 277.1`,
  which turns every angle into pixels;
- the **side-on standoff**, about 380 mm, from the lens and the tallest glass.

## Where to go next

- [The five problems](README.md) — the map.
- [Problem 1](problem-1/) — one glass, start to finish.
- [Problem 2](problem-2/) — many glasses of one kind.
