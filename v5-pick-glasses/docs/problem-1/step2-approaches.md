# Step 2 — other ways to measure a glass

[`step2-measuring-one.md`](step2-measuring-one.md) explains how the arm
measures a glass today: one picture from the side, turned into a width at
every height. This document puts that method next to the others that could do
the same job.

It covers ways of getting a shape out of pictures. Other *sensors* that can
also measure a glass — a fixed camera at table level, touch with the fingers, a
lidar, sensors in the fingertips — are in
[`step1-approaches.md`](step1-approaches.md), because most of them find the
glass as well.

Step 2 gets a complete description of the shape out of one photograph, and
it can only do that because a glass is a solid of revolution. Every other way
of measuring an object is a way of *not* needing that assumption, and pays for
it in time, in hardware, or in both.

Most of these have a longer treatment in robotics-basics, and each one below
links to it. The two documents that cover the most ground here are
[methods you write yourself](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md), for everything
measured rather than inferred, and
[models that measure](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/05_models-that-measure.md), for the learned end.

| Approach | What it does | What it runs on | Suitability here |
| --- | --- | --- | --- |
| **One side-on silhouette** | one picture, one scale factor, a width at every height | [OpenCV](https://github.com/opencv/opencv) and NumPy, in `glasses/perception.py` | good, and in use |
| **Silhouettes from several sides** | carves the shape out of several outlines | OpenCV plus [Open3D](https://www.open3d.org/) | the honest answer for objects that are not round |
| **Photogrammetry** | reconstructs the surface from many overlapping photos | [COLMAP](https://colmap.github.io/), [Open3D](https://www.open3d.org/) | minutes per glass, and glass is its worst case |
| **Radiance fields and splatting** | learns a 3-D scene from photos and renders new views of it | [NeRF for transparent objects](https://sites.google.com/view/dex-nerf), [3D Gaussian splatting](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/) | the best results on glass, at the worst cost per object |
| **Structured light or a laser line** | projects a known pattern and watches how it bends | industrial scanners, [Open3D](https://www.open3d.org/) for the cloud | accurate, and defeated by a transparent surface |
| **Fit a parametric shape** | assumes a family of shapes and fits the best member | [scikit-learn](https://scikit-learn.org/) or SciPy least squares | a neat alternative to the rules in step 3 |
| **Match against known models** | line the glass up against a library of CAD models | [Open3D](https://www.open3d.org/) ICP, [trimesh](https://trimesh.org/) | needs the library this project refuses to have |

**One silhouette, which is what is used here.** Longer treatment:
[silhouettes of a solid of revolution](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/03_programmed-methods.md#27-silhouettes-of-a-solid-of-revolution),
which calls it a special case that is unreasonably powerful when it applies,
and lists the five jobs it cannot do — the first being anything not round.
[`step2-measuring-one.md`](step2-measuring-one.md) explains why one picture is
enough. Against the others below, it is fast, it needs no model of any
particular glass, and the only number it needs from outside is a distance the
arm already knows. What it cannot see is anything that breaks the symmetry: a
glass with a chip or a badge on one side is measured as though it were plain.

*Needs, and from [step 1](step1-approaches.md):* one side-on picture, plus the
distance to the glass. Today that is the wrist camera carried round to the side
(approach 0), or a fixed camera at table level with no arm move (approach 2).
The distance comes from where step 1 found the glass.

**Silhouettes from several sides** is the same idea taken further: photograph
the object from several angles and keep only the space that every outline
agrees is solid. It handles objects that are not solids of revolution, which
is exactly what this project's assumption gives up, and it needs no special
hardware. The cost is a circuit of the table per object and a worse answer
than it sounds — a silhouette carve cannot see a dent in the side of a cup,
because no outline shows it. It would be the right move the day this project
had to pick up a jug.

*Needs, and from [step 1](step1-approaches.md):* side-on pictures from several
known angles. Either the wrist camera stopping at several points round the
glass, or two or more fixed side cameras (approach 2).

**Photogrammetry and the radiance-field methods** —
[reconstruction, when you do not have a model](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/05_models-that-measure.md#4-reconstruction-when-you-do-not) —
produce a genuine surface
rather than an outline. The newer ones handle transparency and bright
reflections far better than anything classical, so they are the state of the art
for exactly this object.

They are also seconds to minutes of computation per glass, they want many
overlapping views, and what they give back is a dense model of which this task
would use about six numbers. For a bin-picking cell
facing unknown objects that trade is often worth it; for a task whose shape
rules need a profile and nothing else, it is not.

*Needs, and from [step 1](step1-approaches.md):* dozens of overlapping colour
pictures from all round the glass, with the camera's position for each. Only the
wrist camera circling the glass can give that. No fixed camera in step 1 can.

**Structured light and laser scanning** —
[how the four sensing principles fail](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/02_sensors.md#11-how-the-four-sensing-principles-fail)
is what each one does and does not survive — are how industry actually measures
shapes to a fraction of a millimetre. They fail on this object for the same
reason the depth camera does: the pattern goes through the glass instead of
landing on it. Making them work means coating the glass in scanning spray,
which is fine in a metrology lab and absurd in a kitchen.

*Needs, and from [step 1](step1-approaches.md):* a new sensor — a projector or
laser line plus a camera, swept up the glass. The nearest thing in step 1 is the
lidar (approach 4), which fails on real glass for the same reason.

**Fitting a parametric shape** is the most interesting alternative on the
list, because it competes with step 3 rather than with this step. Instead of
measuring a profile and then asking which kind of glass it resembles, you assume
a family at the start: a bowl on a stem on a foot, with a handful of free
numbers. Then you fit whichever member of that family best matches the outline.

What comes out is the kind and the dimensions in one go, with an error bar
attached, which is more than the current arrangement gives.

The catch is that it only works for families somebody has written down. A glass
of a shape nobody anticipated fits badly and reports a confident wrong answer.
The rules in step 3 return `None` and leave it standing instead. That
difference — a bad fit against an honest refusal — is why it was not chosen.

*Needs, and from [step 1](step1-approaches.md):* no new picture at all. It runs
on the outline one of the silhouette methods above already gives. So the same
side picture as today (approach 0), or one from a fixed side camera
(approach 2).

**Matching against a library of CAD models** —
[pose estimation, when you have a model](https://github.com/RobinNagpal/robotics-basics/blob/main/docs/06_object-perception/05_models-that-measure.md#3-pose-estimation-when-you-have-a-model) —
is common in warehouses, where
there are a few thousand known products and a new one arrives with a model
attached. It is very accurate when the model exists and useless when it does
not, and this project's opening premise is that the sizes are not known in
advance, so the library cannot exist.

*Needs, and from [step 1](step1-approaches.md):* a 3D point cloud of the glass,
which the depth camera from above gives (approaches 0 and 1). Plus a library of
glass models, which this project's rule forbids.

← [Step 2 — measuring one](step2-measuring-one.md)
