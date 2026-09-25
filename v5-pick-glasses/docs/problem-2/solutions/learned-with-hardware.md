# Problem 2 — learned approaches that need more than a simulator

These were in [`solution-overview.md`](solution-overview.md) and were moved
here, because none of them can be built and trained inside this project's
simulation alone.

## The test each one failed

A solution belongs in the main overview if **everything it needs can be
produced by Gazebo on the machine this project runs on**: an Apple Silicon Mac
with no NVIDIA graphics card, no robot on a bench, and no real-world data. In
practice that is four conditions:

1. **No artefact from outside.** Any model it uses has to be trainable from
   what the simulator renders. A downloaded file of weights fitted to
   photographs of the real world is not reproducible here, however good it is.
2. **No sensor the simulator does not have.** Gazebo gives this cell a depth
   camera, pad contact sensors and a wrist force-torque sensor. Anything else
   is a purchase order.
3. **No graphics card it has not got.** Anything needing compiled CUDA kernels
   is out. Apple's MPS backend runs, with some operations falling back to the
   processor.
4. **Hours, not days.** A method that takes a week of continuous simulation to
   train cannot be iterated on, and a method you cannot iterate on will not be
   debugged.

Everything below fails at least one of those. Nothing below is wrong. Each is a
reasonable answer to this problem, and several are what a well-resourced team
would reach for first. They are here so that the choice stays visible, and so
that the reason for not taking them is the honest one — the machine and the
data, not a view about learned methods.

None of them needs a different *algorithm* to become usable. They need a
different *setup*: a graphics card, or a camera on a real table, or both.

---

## Geometry proposes, a promptable model refines

> **Fails condition 1.** Its whole point is a promptable segmentation model,
> and every usable one is a file of weights fitted to millions of real
> photographs. That file cannot be produced from this simulator. It also has
> no sim-only substitute: a promptable model that has only ever seen Gazebo
> renders has no general notion of an object boundary to offer.

*Hybrid, with the model as a proposer. Send the model only the clusters the
geometry is unsure about, prompted with the point the geometry already
computed, then check its answer with the same arithmetic that flagged the
cluster.*

### What it is

A **hybrid**: geometry proposes, a learned model refines, geometry decides.
The model is never the last word.

Two words first. A **closed-set** model answers only with a name from the
fixed list it was trained on, and returns nothing for anything else — which a
robot reads as "nothing there". A **promptable** model takes a picture *and a
hint*, and returns the pixels at that hint. The hint is a **prompt**: a place,
not words — a point, a box, or a rough mask. Its answer is a boundary, never a
name, so there is no list to fall off.

The promptable models are the **Segment Anything** family. Licences read from
the projects:

| Model | Licence | Without CUDA? |
| --- | --- | --- |
| [SAM](https://github.com/facebookresearch/segment-anything) | Apache-2.0, code and weights | yes, slowly |
| [SAM 2](https://github.com/facebookresearch/sam2) | Apache-2.0, code and weights | yes; smallest size comfortably |
| [MobileSAM](https://github.com/ChaoningZhang/MobileSAM) | Apache-2.0 | yes |
| [FastSAM](https://github.com/CASIA-LMC-Lab/FastSAM) | **AGPL-3.0**, inherited from Ultralytics | yes, but the licence bites |
| [EfficientSAM](https://github.com/yformer/EfficientSAM) | uncertain; I have not read its licence file | yes |

FastSAM's README claims Apache-2.0 while its `LICENSE` file says AGPL-3.0; the
licence file counts. SAM 2 is the safe default.

**There is no NVIDIA GPU here** — this is an Apple Silicon Mac. None of these
need CUDA, but all were tuned for it, so running one means
[PyTorch](https://pytorch.org/) (BSD-3) on Metal, or a conversion with
[coremltools](https://github.com/apple/coremltools) (BSD-3).

### Why anyone does it this way

The two halves fail in opposite directions.

Geometry fails **loudly**. A merged pair comes back as a footprint 262 mm
across when the kind is 60 to 90, so the failure is a sentence with two
numbers in it. What geometry cannot do is draw a boundary through a clump,
because the projection threw that information away.

A model fails **quietly**. It draws a good boundary on an object it has never
seen, and an equally confident boundary round the wrong thing.

In this order, the loud failure catches the quiet one. That is the pattern
worth taking generally: **a learned component used as a proposer inside a
checkable envelope.** Its output is not trusted but tested, against a
measurement that exists independently of it. A wrong mask never becomes a
wrong glass; it becomes a diameter outside a range.

### How it would work here

**1. Geometry proposes, with a confidence.** The geometric detector already
gives, per cluster, a position on the table and a fitted footprint circle. Add
one label: a cluster whose circle is inside the kind's diameter range is
**settled**; one that is not, and that two circles do not explain either, is
**doubtful**. That word is the gate.

**2. The model refines — doubtful clusters only.** The prompt costs nothing,
because the geometry already computed it: the cluster's centre, projected back
into the picture, is a **point prompt**, its pixel bounding box is a **box
prompt**, and a clump believed to be two glasses gives two point prompts.

**3. Geometry decides.** Each mask goes back through stage 1's arithmetic:
pixels to points in the room, dropped onto the table, circle fitted. Accept
only if **both** diameters are in the kind's range and the centres far enough
apart to be two glasses. Otherwise both are discarded. The model proposed a
boundary; it did not get a vote.

**Why not every frame.** A mask cannot improve a number that is already right,
and it can make it wrong. One or two doubtful clusters per run is the right
load.

**What a call costs.** Encoder once per picture, decoder once per prompt, so
two prompts is one encode and two cheap passes. The encode is the bill. The
only measured Apple Silicon figures I have are Ultralytics' own: FastSAM-s
**58.0 ms**, MobileSAM **23,802 ms**, on a 2025 M4 Air, CPU — much of that gap
being the runtime, not the model. What SAM 2 would cost here is uncertain.

### The feedback loop

Suppose stage 3 rejects the masks. The tempting answers are a larger model, a
second prompt, or a looser threshold. All three are wrong for one reason:
**the picture does not contain the answer.** Two glasses in line with the
camera occlude each other, and no boundary drawn on those pixels recovers what
was never recorded.

The right next action is **another picture from somewhere else**. The
rejection carries what the viewpoint solutions want: which cluster is
doubtful, where it is, and how wide it wrongly appears. Solution 3 scores
directions round it for line of sight, arm path and reach, and the new picture
re-enters at stage 1. Cap it at two extra looks. If no viewpoint separates the
pair, they are unseparable where they stand — problem 3's business, moving
them apart rather than photographing them harder.

### A worked example

Five glasses of one known kind, footprint range 60 to 90 mm. The station sits
450 mm above the table, so one picture covers about 520 by 390 mm across 320
by 240 pixels, and one pixel is 1.6 mm.

*Stage 1.* Four clusters. Three fit circles of 77, 81 and 74 mm — settled, and
the model is never loaded for them. The fourth fits 262 mm; two circles give
131 and 129 mm, both out of range. Doubtful.

*Stage 2.* That cluster spans 262 / 1.6 ≈ **164 pixels** of the 320 across,
and its two likeliest centres project to pixels **80 apart**, 128 mm on the
table. Those are the prompts: one encode, two decoder passes.

*Stage 3.* Re-projected and fitted, the masks give **76 mm** and **73 mm**,
centres **158 mm** apart — both inside 60 to 90, and above the 150 mm the cell
guarantees between glasses. Accepted.

The other branch: the second mask fits at **118 mm**. Both are discarded, the
cluster stays doubtful, and it goes to solution 3 for a viewpoint
perpendicular to the line joining the pair.

### What it needs

PyTorch on Metal, or a Core ML conversion, and a version-pinned weights file
of tens to hundreds of megabytes. No labelled pictures and no training. A
projection from a table position back to image pixels, which exists; a rule
turning a cluster into a prompt; and stage 3, the circle fit called a second
time.

### What it is good at

Boundaries through a clump the geometry cannot cut — the one job geometry
genuinely cannot do. It enlarges nothing that is trusted, since every number
leaving it came from arithmetic checked against a range the project holds. It
costs nothing when nothing is wrong, and needs no data.

### What it is bad at

**It cannot start anything.** Nothing in it decides where to point.

**It cannot name what it outlined.** Point it at the rack or the arm's own
wrist and it outlines those just as willingly.

**Small pictures.** These models resize internally to around 1024 across, so
blowing 320 by 240 up returns a boundary smoother than the picture justifies.

**Transparent objects**, which the family handles worst.

### How it fails

**It outlines the wrong thing, confidently** — the table behind a rim, or a
highlight as its own object. Stage 3 catches that unless the wrong thing
happens to be glass-sized.

**It splits one glass.** Prompted at a bowl, it returns the bowl.

**Both masks pass and both are wrong.** The residual risk. Agreement across
stations is the remaining defence.

**It thrashes** without the cap, and a pinned weights file behind a gate that
rarely opens is never exercised by the tests.

### When it would be the right choice

When the cheap method has failed on a named cluster, and not before: a model
adds nothing to a cluster that passes the circle fit.

Three cases earn it. Here, for a doubtful cluster two circles cannot explain
and no viewpoint resolves. In problem 4, where the kind is unknown and the
allowed diameter becomes the union of several ranges, loosening the envelope.
And on real glassware, where there is no depth to cluster, so the geometric
route stops existing and takes the envelope with it.

Until then, the gate should stay shut.

---

---

## Train an instance model

> **Fails conditions 1 and 4.** The recipe is to fine-tune a model that
> already knows what objects look like, which means starting from a backbone
> trained on real photographs. And on this machine a fine-tune that takes an
> hour on a rented graphics card takes most of a day. *A version trained from
> random initialisation on renders alone does fit the budget, and it is in the
> main overview.*

*Learned, as the decider. Show a network a few thousand labelled pictures and
let it learn to outline each object separately.*

### What it is

A **neural network** is a program whose behaviour comes from numbers learned
from examples rather than from rules somebody wrote. The numbers are called
**weights**, and they live in a file. Three things such a network can do with a
picture of five glasses are easy to confuse.

- **Detection** returns a rectangle round each glass. Rectangles of overlapping
  glasses overlap too.
- **Semantic segmentation** labels every pixel with a class. Every glass pixel
  comes back labelled "glass". Nothing says *which* glass, so two overlapping
  glasses come back as one region — the merge this problem exists to prevent.
- **Instance segmentation** labels every pixel with a class *and* with the
  object it belongs to. Five glasses give five **masks**, a mask being a
  picture where every pixel is yes or no.

Problem 2 asks which pixels belong to which glass. That is instance
segmentation, exactly.

### Why anyone does it this way

Every other method here reasons about geometry, and all of it depends on the
glasses being opaque, so that the depth camera returns a real distance for
every glass pixel.

A real depth camera gets almost none back from real glass: nothing to cluster,
no points above the table, no circle to fit. What is left is the colour
picture, where a glass shows itself through refraction, highlights and the way
the background bends behind it. Nobody has written a rule that captures those.
A model learns them from examples.

### How it would work here

The pictures are 320 x 240, small by the standards of these models, which
usually expect 640 pixels or more. Training and inference are therefore cheap,
and the mask boundary stays coarse however good the model is.

The families worth considering, with licences read from the projects:

- **Mask R-CNN.** In `torchvision` it is BSD-3 throughout, the clean option.
  **Detectron2** has better recipes but its **weights are CC BY-SA 3.0** under
  Apache-2.0 code, and it is CUDA-shaped with no release since 2021.
- **YOLO-seg, from Ultralytics.** The easiest path by a distance, and
  **AGPL-3.0**: you must publish the source of anything you combine it with,
  including software you only run as a service and never distribute, and the
  weights carry the same terms however you got them. A commercial licence
  exists, priced by negotiation. For anything that might ship, that is a
  decision rather than a detail, and the same inheritance catches FastSAM.
- **Something smaller.** `segmentation_models_pytorch` (MIT) is semantic only,
  so it needs a separating step bolted on. Hugging Face `transformers`
  (Apache-2.0) fine-tunes Mask2Former and OneFormer, both MIT. At this size a
  Mask R-CNN on a small ResNet backbone is already small.

**Making the data.** The simulator knows every glass's outline, so it renders
labelled pictures for nothing, and the labels are perfect. Gazebo is Apache-2.0
and already running; Kubric (Apache-2.0) and BlenderProc (GPL-3.0 — the data is
yours, the tool is copyleft) render better.

**Domain randomisation** is what makes rendered data transfer. Rather than try
to make the render look real, vary everything you are *not* teaching —
lighting, textures, background, camera pose, exposure, noise, glass colour,
how many glasses and where — so widely that reality looks like one more
variation. The model then cannot latch onto anything that differs between
simulation and reality, because none of it was ever constant.

**Does it break the project's rule?** The model outputs a mask, in pixels, and
a mask holds no millimetres. Size still comes from the depth reading and the
camera geometry, measured during the run. So no: nothing is written down, and
the arm still measures every glass itself. It does put a *size-shaped prior* in
a file nobody can inspect, having been trained on one range of proportions.
That is knowledge about glass sizes held inside the project, and the report
should say so.

### A worked example

Five glasses stand on the table. Two are 300 mm apart but line up with the
camera, so their outlines touch in the picture.

Today `standing_on_the_table()` in `glasses/detect.py` returns one boolean mask
of everything above the table top, and `find_glasses()` groups it into blobs.
The lined-up pair become one blob 260 mm wide, and everything downstream
believes it is one large glass.

A trained model returns five masks, and the lined-up pair are two of them
sharing a boundary. Each mask runs through the existing code unchanged: points
in the room, circle fitted at the table, position and rough width reported.

### What it needs

**Pictures.** You fine-tune rather than train from scratch: take a model that
already knows what objects look like and teach it this one class. A few hundred
labelled pictures is enough to see it work, a few thousand to be steady, and
the simulator renders them overnight. How many are enough here has not been
measured, and I will not guess.

**A machine to train on.** This is the awkward part. The cell runs on an Apple
Silicon Mac and **there is no NVIDIA GPU**. PyTorch trains on Apple's **MPS**
backend, the Mac's own graphics processor, but some operations fall back to the
CPU, and a fine-tune of an hour on a rented NVIDIA card can take most of a day
here. It is possible; it is not something you do between two experiments.
Anything needing compiled CUDA kernels is out entirely: Detectron2's, mmcv's,
the deformable-convolution variants, TensorRT, Isaac ROS.

**Somewhere to run it.** `torchvision` Mask R-CNN runs on MPS, and Ultralytics
with `device="mps"`. At 320 x 240 that should sit inside the time an arm move
takes, but I have not measured it and will not quote a figure. One comparison
shows why guessing is unwise: MobileSAM, designed to be small, takes about 24
seconds per image on an M4 Air's CPU, while Depth Anything V2 Small runs in
24.6 ms on an M3 Max through CoreML and the Neural Engine. What matters is
whether anyone has done the CoreML work, not how small the model is.

### What it is good at

It separates glasses that overlap in the picture without needing depth. It
copes with reflections and highlights far better than any threshold. It works
on real transparent glassware, which nothing else here does without new
hardware. And it enters at one function.

### What it is bad at

It says nothing in millimetres and it cannot say why. It knows only the glasses
it was trained on; a kind outside that range is one it outlines badly, with no
warning. And here it is more machinery than the job needs, because comparing
depths separates two glasses 300 mm apart exactly, with a reason you can print.

### How it fails

**Confidently.** A merged pair comes back as one mask with a high score. A
geometric method that merges leaves evidence — a footprint 260 mm across when
the kind is 60 to 90 — and the circle fit catches it. A model that merges
leaves a number, and the number says it is sure.

**Out of date.** Add a kind, change the proportion ranges, change the lighting
in the world file, and the weights describe something that no longer exists.
Nothing in the repository says so, and the tests still pass.

**In the way.** Every other method here can be changed and re-run in a minute.
This one puts a training loop between the change and the answer, paid on every
experiment.

### When it would be the right choice

The day the glasses stop being opaque, when every geometric method here loses
its input at once. Also if the glassware becomes open-ended, because the circle
fit leans hard on knowing the kind's diameter range. Until then it is a
fallback worth knowing how to build and worth not building.

---

---

## Amodal masks and learned association

> **Fails conditions 1 and 4.** Two networks rather than one, and the
> published model families for amodal segmentation are built on real-image
> backbones and real datasets, several of them non-commercial. The simulator
> can supply exact amodal masks, which is the encouraging half; the training
> cost on this machine is the other half.

*Learned, as the decider. Predict the whole extent of a partly hidden object,
not just its visible pixels, and learn to recognise the same object across
several viewpoints.*

### What it is

Every segmenter named so far marks only the pixels you can see. The habit has a
name. **Modal segmentation** labels an object's visible pixels and stops where
something else gets in front. **Amodal segmentation** labels the object's *whole*
extent, hidden part included. Put one glass half behind another: a modal model
returns the visible half of the back one, an amodal model the whole footprint,
inferring the hidden part from what it can see. From psychology: *amodal
completion* is reporting one cat behind a railing, not five slices.

Why it matters here is arithmetic. Everything downstream turns a mask into points
on the table and fits a circle. **A mask cut short by an occluder gives a circle
too small and in the wrong place**, because the centre of the visible part is not
the centre of the glass. Both errors are silent: a wrong footprint comes back not
as an error but as a plausible number.

The second half is **association**: deciding that a detection in one picture is
the same physical glass as one in another. Three stations, two pictures each,
five glasses — thirty detections, five objects. That is the **data association
problem**, a separate job from finding the glasses.

### Why anyone does it this way

`problem.md` says the failure to watch hardest is *merged*, because it does not
announce itself. A truncated footprint is the same failure in different clothes:
the range for one kind is 60–90 mm, so a glass 30 per cent hidden reports about
60 mm, and solution 2's circle fit passes it in silence.

For association the classical answer is geometric, and solutions 2 and 3 use it:
two detections are one glass if their positions are close and their heights
agree. It fails when a position is wrong *because* the mask was truncated —
geometry arbitrating with broken numbers.

The learned answer ignores position. The model turns each detection into an
**embedding**: a short list of numbers, typically 128 or 256 of them, produced by
a network from that detection's pixels. Nobody chooses what the numbers mean. The
network is trained so two views of one object land close together in that space
and views of different objects land far apart, by ordinary Euclidean or cosine
distance. The usual signal is a **triplet loss** — an anchor, another view of it,
and a different object; pull the first pair together, push the second apart.
"Same glass?" becomes "is this distance small?"

The neighbouring field is **multi-object tracking**. A **track** is an identity
over time; a **cost matrix** prices matching each detection to each track; the
**Hungarian algorithm** (`scipy.optimize.linear_sum_assignment`, SciPy, BSD-3)
picks the cheapest one-to-one assignment; **re-identification** is the embedding
half. DeepSORT (https://github.com/nwojke/deep_sort), the classic
appearance tracker, is **GPL-3.0**; ByteTrack
(https://github.com/ifzhang/ByteTrack) is MIT.

### How it would work here

**The models.** Amodal segmentation is a small field, and most of it is research
code. **UOAIS** (https://github.com/gist-ailab/uoais, ICRA 2022) fits closest —
RGB-D, tabletop, class-free, predicting a visible mask, an amodal mask and an
occlusion flag per object; licence uncertain. **BCNet**
(https://github.com/lkeab/BCNet, MIT) models occluder and occluded as two layers.

Both sit on **Detectron2**, which solution 5 flags as CUDA-shaped and unreleased
since 2021. With no NVIDIA card that is the real obstacle, not model size. A
`torchvision` Mask R-CNN (BSD-3) with a second head for the amodal mask runs on
MPS, and is the route I would take.

**The datasets** are mostly unusable here: COCO-Amodal
(https://github.com/Wakeupbuddy/amodalAPI, licence uncertain) and KINS
(https://github.com/qqlu/Amodal-Instance-Segmentation-through-KINS-Dataset),
annotated on KITTI and so **CC BY-NC-SA, non-commercial**. Neither holds glasses.

**The simulator supplies the data free, which is what makes this practical.**
Render each glass alone against the empty table: that silhouette is the amodal
mask, exact. Render the whole scene: that is the modal mask. The difference is
the occlusion mask. No annotator, so no annotator error, and the same renders
label association free.

**The pipeline.** Run the model on each picture and fit the circle to its amodal
mask — existing code, fed an untruncated footprint. Then embed every detection
and solve the cost matrix across pictures.

### The feedback loop

The margin on that assignment is the useful output. If a detection sits 0.11
from candidate A and 0.13 from B, while two views of one glass typically sit
0.05 apart, the match is a coin toss wearing a number.

**An uncertain association is a reason to take one more picture, from a viewpoint
where the two candidates would look different.** That is solution 3's
next-best-view machinery with the score swapped: instead of unknown volume, score
the **predicted margin** — for each reachable viewpoint, predict how A and B
would look and prefer the one putting their embeddings furthest apart. Two
glasses drawn 230 mm and 205 mm tall look identical from above and differ by
25 mm from level, so the loop picks a level view. Cap it: two extra looks, then
report the pair unseparated.

### A worked example

At survey height, 450 mm up, one pixel covers 1.6 mm. Glass A stands 180 mm in
front of glass B, in line with the camera. B's footprint is 78 mm, or 49 pixels,
and A hides 22 per cent of its disc.

*Modal.* B's visible part is 38 pixels, **61 mm** — inside the 60–90 mm range, so
it passes. The circle fitted to that crescent has its centre **8.5 mm** from B's
true one. One glass, 61 mm across, in a place it is not.

*Amodal.* The model returns the whole disc: 77 mm against a true 78, centre
within 2 mm, flagged as 22 per cent inferred.

*Association.* Station 2 sees B unoccluded; its embedding sits 0.04 from station
1's truncated B against 0.19 for the nearest other glass. The awkward pair, of
nearly identical proportions, come back at 0.11 and 0.13; one level look
separates them to 0.06 and 0.21.

### What it needs

Rendered data with amodal masks, free from the simulator, and a second mask head
to predict them. An embedding network and a triplet loss on the same renders,
SciPy for the assignment, and solution 5's training cost, doubled.

### What it is good at

It attacks the truncated-footprint failure, which nothing else here detects, and
turns association into evidence rather than assumption. It gives numbers to be
uncertain about: the margin drives the extra look, and the occlusion fraction
marks a mostly-guessed footprint doubtful.

### What it is bad at

**Every glass is the same kind.** An appearance embedding on four to six nearly
identical objects has very little to work with. What signal exists comes from the
proportions drawn at random inside the kind's range, plus incidental marks and
lighting — and in a clean render of untextured glasses there may be almost none.
That is a real reason to doubt the embedding half earns its keep here.

### How it fails

**The completion is invented and looks measured.** An amodal mask for a glass 90
per cent hidden is almost all guess, yet comes back as a clean outline with a
high score. Without the occlusion fraction, nothing says so.

**A systematic completion bias.** If the renders over-represent one occlusion
geometry, every footprint is wrong the same way, which is harder to spot.

**An identity swap.** Two glasses matched the wrong way round give two confident
positions, each belonging to the other. It is likeliest when the margin is
miscalibrated: measure within-object distance on clean renders and every match
looks confident, so the loop never fires.

### When it would be the right choice

When objects genuinely hide each other and there are many viewpoints to
reconcile: a bin, a crowded shelf, a tray of glassware pushed together. Where
occlusion is the normal case and not the accident, a model that predicts
the hidden part is not extra machinery — it is the measurement. It is also
solution 5's partner on real glassware, where no depth is left to cluster.

For this cell it is far more than the problem needs. Four to six glasses stand
150 mm apart on a bare table, and most pictures show every glass whole. Where one
does not, solution 3 moves the camera 200 mm and the occlusion goes away, seconds
of arm time against two trained models. It earns its place when the arm cannot
reach a clear viewpoint, and here it usually can.

---

---

## An active-vision policy

> **Fails condition 4.** Everything it needs is in the simulator, which is
> what makes it frustrating. The cost is throughput: thousands of Gazebo
> resets and days of machine time, and the usual escape — a graphics-card
> simulator running thousands of worlds at once — is exactly what this machine
> cannot do. *A supervised version of the same idea, which predicts whether a
> viewpoint will pay off rather than learning a policy, does fit, and it is in
> the main overview.*

*Learned, as the decider, and a closed loop by construction. A policy takes the
current belief about the table and outputs where to point the camera next.*

### What it is

A **policy** is a function from what the robot knows to what it does next.
Here: belief about the table in, next camera pose out. Nobody wrote the rule
inside it. The rule is a pile of numbers — the **weights** — fitted from
experience. There are two ways to fit them.

**Reinforcement learning.** Let the robot try. It looks somewhere, and
eventually is handed a number — the **reward** — saying how well the whole
attempt went. Thousands of attempts later, actions that tended to precede high
reward have become more likely. Nobody says which individual look was good;
that is inferred from the totals, which is why it takes so many attempts.

**Imitation learning.** Show it the answer instead. Run an expert — a person
with a joystick, or a slow method already known to be right — record what the
expert saw and did, and fit the policy to reproduce the choice. This is
**behaviour cloning**, ordinary supervised learning. It needs no reward, and it
can never beat the expert it copied.

### Why anyone does it this way

Scoring a viewpoint properly is expensive; choosing one is cheap. Solution 3's
score casts a ray per pixel into an occupancy map, for every candidate. A
policy does one forward pass, and you pay the cost once, offline. And a
geometric score exists only where somebody can write one down. Here they could.
Where the cue is subtler, nobody can.

### How it would work here

**The observation.** Not the raw picture — appearance is what will not transfer
out of Gazebo. Feed it what the geometry produced: the 320 x 360 mm glass zone
as a grid of 20 mm cells, 16 x 18 = 288 of them, each empty, occupied or
never-seen; one row per cluster, holding position, fitted diameter, how many of
the three stations saw it and whether that diameter is in range; and how many
looks remain. About nine hundred numbers, small enough to train on a CPU.

**The action.** In principle a camera pose: six numbers. In practice, don't.
Take a fixed list of **candidate poses** — problem 1's `_standoffs()` gives
nine directions at 380 mm, and three heights make 27 — and let the action be a
choice among them, plus one meaning **stop**. Discrete is the sane engineering
choice: every candidate is checked once against the 300–780 mm reach and
against inverse kinematics, so the policy cannot name a pose the arm will not
hold, and failures are masked out. A continuous six-dimensional space would
spend most of its exploration in mid-air.

**The reward, which is the hard part.** Use problem 2's own score sheet: +1 per
glass correctly separated, −1 per merged pair, −0.05 per look. That needs to
know which glasses were really there. Gazebo writes down everything it spawned,
so in simulation the reward is exact. **Reality has no such file.** You could
pay for a proxy, such as the circle fit passing — but a policy optimises
exactly what you pay for, and one paid for a passing fit learns viewpoints from
which it passes, not viewpoints from which the answer is right.

| Tool | Link | Licence | Needs CUDA? |
| --- | --- | --- | --- |
| Gymnasium | https://github.com/Farama-Foundation/Gymnasium | MIT | no |
| Stable-Baselines3 | https://github.com/DLR-RM/stable-baselines3 | MIT | no; PyTorch on Apple's MPS backend or CPU |
| Ray RLlib | https://github.com/ray-project/ray | Apache-2.0 | no |
| Gazebo Harmonic | https://gazebosim.org/ | Apache-2.0 | no; headless here already |
| MuJoCo | https://github.com/google-deepmind/mujoco | Apache-2.0 | no for the CPU engine; its MJX fast path wants a GPU, and Apple Silicon support is uncertain |
| Isaac Lab | https://github.com/isaac-sim/IsaacLab | BSD-3-Clause | **yes** — Isaac Sim needs an NVIDIA RTX card |

Gymnasium defines the interface — `reset()`, `step(action)`, a reward.
Stable-Baselines3 supplies the algorithms and is the right first choice here;
RLlib is for scaling across machines. **Isaac Lab is out**: this is an Apple
Silicon Mac with no NVIDIA GPU, and everything CUDA-shaped goes with it.

**How long.** An episode is at most six looks, each an arm move of a few
seconds, plus a reset — call it ten seconds of wall clock headless, a figure to
measure rather than guess. At 50,000 episodes that is five days on one process,
under a day with eight in parallel. A gradient step is milliseconds, so **the
simulator is the bottleneck, by three orders of magnitude.**

### The feedback loop

This is not a solution with feedback bolted on. It **is** the loop.

1. **Observe.** Run the three-station survey, cluster, fit circles, build the
   observation.
2. **Choose.** The policy returns one of the 27 candidates, or `stop`. Those
   failing reach or IK were masked before it chose.
3. **Move.** Plan and execute, a few seconds. If the plan fails, mask that
   candidate and return to step 2.
4. **Re-observe.** Take the pictures, fold the new points into the same
   clusters, refit, rebuild the observation.
5. **Stop** on `stop`, or when the six-look budget runs out. Clusters still
   failing their fit are reported unseparated — the handover to problem 3.

The belief is **cumulative** — each look adds points to the same clustering
rather than starting again — and the **budget is external, not learned**, so a
policy that never says `stop` wastes six looks rather than running forever.

### A worked example

Glass A at x = 0.40, y = −0.30, 500 mm from the base. Glass B at x = 0.52,
y = −0.39, 650 mm out and 150 mm from A. B sat behind A from two of the three
stations, and the merged cluster fits a circle 165 mm across against the kind's
60–90 mm range. Two of the nine directions lie along the A–B line, and at all
three heights they fail on reach alone: 380 mm back from A lands either 120 mm
from the base or 880 mm out, against limits of 300 and 780.

The policy picks candidate 14, the perpendicular, camera at (0.628, 0.004). One
move, about three seconds. The cluster resolves into discs of 76 mm and 73 mm,
both in range, so the policy says `stop` and the episode returns
2 − 0.05 = **1.95**.

Solution 3's arithmetic chose that same viewpoint before the planner was asked
anything, and can say why: from the blocked direction B spans
105 x 277.1 / 530 ≈ 55 of the 320 pixels directly behind A. The policy chose
candidate 14 with a value of 0.83, and can say nothing.

### What it needs

A Gymnasium environment round the existing cell: reset spawns four to six
glasses, step moves the arm and re-runs perception, reward reads the spawn
record. That wrapper is the real work, because it must reset Gazebo thousands
of times without leaking processes. Then Stable-Baselines3, PyTorch on MPS or
CPU, and days of machine time. No labelled pictures, and no NVIDIA card.

### What it is good at

Run-time speed: choosing is a forward pass, microseconds against the seconds a
move costs. Cues nobody wrote down, where a viewpoint pays off for reasons the
circle fit misses. And it optimises the thing itself, merges and splits, where
information gain is only a proxy for them.

### What it is bad at

It cannot explain itself, and here that is practical rather than philosophical.
Problem 2 says the failure to watch hardest is the merged pair, because it
looks plausible downstream. A policy that stops one look early produces exactly
that failure, and reports confidence while doing it.

It is also more machinery than this problem has earned. What it would learn is
computable: the kind is known, the diameter range is known, occlusion is a
line-of-sight test. Where a geometric score exists and is auditable, a network
trades the explanation for a speed-up.

### How it fails

**Reward hacking.** Charge too much per look and it stops at once and eats the
merge penalty; too little and it burns six looks every run. That balance is not
derivable, and each attempt costs another training run.

**Sim-to-real drift.** Milder than for contact tasks — no friction, no
deformation, no impact, and what matters is straight lines from camera to
object, which Gazebo gets right. Feeding clusters rather than pixels removes
most of the appearance gap too. But the policy learned this simulator's depth
noise and its dropout at glancing angles, and a real camera that loses the far
rim at 60 degrees shifts every observation.

**Silent staleness.** Change the kind, the lighting or the standoff list and
the weights describe a cell that no longer exists. The tests still pass.

**Real glassware removes the input**, which is built from clusters, and
clusters from depth that real glass does not return.

### When it would be the right choice

When the doubt stops being a short list. Here, one known kind and a diameter
range make "one glass or two?" arithmetic, and auditable. Problem 4 has several
kinds, some never measured, and the union of their ranges is wide enough that
the circle fit stops deciding much. A policy that learned which looks resolve
ambiguity has something to offer there.

One shape is worth keeping even so. Solution 3's score is a working expert and
runs in simulation for free, so behaviour cloning against it gives a fast
policy with no reward design at all — and one that can only approach what it
copied, having lost the explanation that made the original worth having.

---

← [The solutions that do fit](solution-overview.md)
