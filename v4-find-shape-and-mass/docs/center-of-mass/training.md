# Training the centre-of-mass model

Which model is trained, with what settings, why each one, and how to read
the score. The code is in [`center_of_mass/`](../../center_of_mass), and
every setting is in
[`center_of_mass/settings.py`](../../center_of_mass/settings.py).

The first full run is done: 138 epochs, 49 minutes, 0.8 mm average error.
[`results.md`](results.md) reads it number by number.

## Running it

```
make com-train                 # train into runs/com/, about 23 s per epoch on the M5
make com-evaluate              # score it on test: the error in pixels and in mm
make com-resume                # carry on after stopping a run
make com-predict SOURCE=some/folder    # draw its points on any pictures
```

Other runs:

```
make com-train COM_MODEL=yolo26n-pose.pt COM_NAME=com-n     # a smaller model
make com-train COM_EPOCHS=300 COM_NAME=com-long
make com-evaluate COM_NAME=com-n
```

A run's name must be new. To train again under the same name, delete its
folder first, for example `rm -rf runs/com`.

The first run downloads the starting weights, `yolo26s-pose.pt` (22 MB),
into this folder. Git ignores both `runs/` and the weights.

## Which model, and why a pose model

The job is: for every block in the picture, give a point. That is what a
**pose model** does. It finds each object and, for each one, places a fixed
number of keypoints on it. Here there is one keypoint per block: its centre
of mass.

The other ways of doing it, and why not:

| Way | Why not |
| --- | --- |
| A detection model, then take the middle of the box | The middle of the box is not the centre of mass of an irregular shape. On this test set it is 6.0 mm off, against the pose model's 0.8 mm. |
| A segmentation model, then the centroid of the mask by formula | This works, and it is the right answer for a fully visible block. But then nothing is learned: the model finds the outline and arithmetic does the rest. It belongs in the comparison later, not here. |
| A plain CNN that takes a crop and outputs x and y | It has to be told where each block is first, so it needs a detector anyway. A keypoint head predicts from a feature map and is usually more precise than regressing two numbers. |

**`yolo26s-pose.pt`**, the small size, starting from COCO weights:

- **Size s.** `n` is quicker but weaker at placing a point exactly; `m` and
  up are slow to train on a Mac and bring little for 250 pictures of plain
  scenes. `COM_MODEL` changes it, so the sizes can be compared.
- **Starting from COCO.** The backbone already knows edges, corners and
  surfaces from real photos. Only the keypoint head is new, because COCO
  poses have 17 keypoints and this has 1.

### No height

The model gives `x` and `y` in the picture, nothing else. A pose head emits
`x, y, visibility` per keypoint, so there is no slot for a height, and the
labels never carry one: thickness sits in the scene records, which only the
scorer reads.

The horizontal answer is still complete. Every block is an extruded outline
of even material, so its centre of mass stands over the outline's area
centroid whatever its thickness. The height only sets how far up the point
is, half the thickness, and that number has to come from somewhere else on a
real table — a depth camera, or a known set of blocks. Training it in is
harder than it looks: thickness moves the labelled pixel by 0.2 px for a
thin block near the middle of the frame, well under the 2 px the keypoint
sigma treats as free, and the one strong cue left is the shadow, which is
off in one picture in five.

## The settings

| Setting | Value | Why |
| --- | --- | --- |
| `imgsz` | 640 | the pictures are 640 × 480; anything smaller throws away pixels, and the answer is measured in pixels |
| `epochs` | 150 | only 250 pictures, so an epoch is short and more of them are needed |
| `patience` | 40 | stop when val has not improved for 40 epochs |
| `batch` | 8 | the Mac shares 16 GB between CPU and GPU; raise it on a bigger GPU |
| `cache` | `ram` | 400 pictures take under 400 MB, so they are read once |
| `seed` | 0 | the same run twice gives the same model |

### The keypoint sigma

`KEYPOINT_SIGMA = 0.05`. This one matters more than it looks.

Ultralytics scores a keypoint by e = d² / (8 σ² × box area), where d is how
far the point is from the truth. The loss is 1 − e^(−e), so a point with a
small e is already "right" and the model stops being pushed to do better.

Its default for one keypoint is σ = 1. On a 70 × 70 pixel block that makes a
10-pixel error score e = 0.003, which is almost no penalty: the model would
learn to land roughly on the block and stop there.

With σ = 0.05, the same 10-pixel error gives e = 1, a real penalty, and 2
pixels gives almost none. That is the accuracy worth asking for at this
picture size. It is written into the run's own `data.yaml`, which
Ultralytics reads for both the loss and the pose score.

### Augmentation

The label is a single point, and most picture transforms move it somewhere
the model cannot see. So most of them are off.

| Setting | Value | Why |
| --- | --- | --- |
| `fliplr`, `flipud` | 0.5 | on: a mirrored block's centre of mass is the mirrored point, so the label stays true |
| `hsv_h`, `hsv_s`, `hsv_v` | 0.015, 0.7, 0.4 | on: colour says nothing about where the mass is |
| `degrees`, `translate`, `scale` | 0 | off: turning, moving or enlarging the picture pushes blocks near the edge partly out of it, while their label still marks the centre of the whole block |
| `mosaic`, `mixup`, `copy_paste` | 0 | off: mosaic tiles four pictures and crops blocks at the seams, the same problem |
| `shear` | 0 | off: the camera never slants |
| `perspective` | 0 | off: perspective is not a flat stretch, so the true centre of mass does not land where the transformed point does. The label would be quietly wrong |

`tests/test_center_of_mass.py` checks that all of these stay at 0.

On top of those, the same **camera effects** the classification training
uses: blur, motion blur, noise, JPEG blocks, and rarely grey or contrast
changes. They change colours and sharpness but never move a pixel, so the
point stays where it belongs. They come from
[`training/settings.py`](../../training/settings.py).

## What `make com-evaluate` reports

For every test picture, the model's blocks are matched to the true ones by
box overlap (at least 0.5, the surest guess picking first). The class is not
used for matching, so a block found under the wrong name is still scored on
its point, and the class is reported separately.

Each matched block gives four numbers:

| Number | Meaning |
| --- | --- |
| **model, pixels** | from the model's point to the true point in the picture |
| **model, mm** | the same distance on the table. The pixel is taken back down to the height of that block's top face, so a tall block and a flat one are compared fairly. This is the number that matters for an arm |
| **box centre, pixels / mm** | the same, for the middle of the model's own box. This is what a model that only found blocks would score |

The model has learned something about mass only if **model, mm** is clearly
smaller than **box centre, mm**. The counts next to them say how many blocks
were found at all, and how many got the right class.

Ultralytics' own scores are printed too: `box mAP50` for finding the blocks,
and `pose mAP50` and `pose mAP50-95`, which use the same sigma as the loss.

Written into the run's folder:

```
evaluation.json             every number printed
test-pictures/000123.jpg    every test picture, with the points drawn on
test-samples.jpg            the first 12 of those on one sheet
test/                       Ultralytics' own plots and confusion matrix
```

On a drawn picture: a **green dot** is the true centre of mass, a **red
dot** the model's, a white line joins them, and the label says the class and
the error in millimetres. A block the model missed is boxed in red and
marked "missed"; a guess that matched no block is marked "no block here".

## What to look at first

1. **Is the model, mm clearly under the box centre, mm?** If not, the model
   has only learned to find blocks.
2. **Which classes are worst?** Triangles are the lopsided ones, so their
   box centre is furthest from the truth and they show the difference best.
   Octagons are nearly round, so both numbers are small and there is little
   to learn.
3. **Look at the pictures.** A red dot far off on one side is different from
   red dots scattered at random, and the test-pictures folder shows which.

[`results.md`](results.md) does all three for the first run.
