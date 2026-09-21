# Training

Which YOLO model is trained, with what settings, and why. The code is in
[`training/`](../../training), and every setting is in
[`training/settings.py`](../../training/settings.py).

The code is written and has been checked with short runs. No full training
run has been done yet.

## Running it

```
make train                     # 250 random train pictures, the other splits cut to match
make evaluate                  # score the model on its test and test-unseen pictures
make resume                    # carry on after stopping a run
make clean-runs                # delete every run
```

Other runs:

```
make train PICTURES=1000 NAME=thousand
make train PICTURES=all NAME=full        # all 6,000 pictures, many hours on the Mac
make train EPOCHS=30 BATCH=16
make evaluate NAME=thousand
```

A run's name must be new. To train again under the same name, delete its
folder first, for example `rm -rf runs/shapes`, or `make clean-runs`.

The first run downloads the starting weights, `yolo26s-seg.pt` (22 MB),
into this folder. Git ignores both `runs/` and the weights.

## Training on fewer pictures

Training on all 6,000 pictures takes about 12 minutes per epoch on the M5,
up to 20 hours for a full run. To learn the process, a small run is enough,
so `make train` uses a random 250 by default.

**Nothing is copied or deleted.** YOLO can read a split from a text file
listing picture paths instead of a folder. So `training/subset.py` picks the
pictures and writes those lists into the run's own folder:

```
runs/shapes/data/
├── train.txt            250 picture paths
├── val.txt              42
├── test.txt             42
├── test-unseen.txt      42
├── data.yaml            points YOLO at the lists
└── data-unseen.yaml     the same, testing on test-unseen.txt
```

**Every split is cut by the same fraction.** 250 is 1/24 of train, so val,
test and test-unseen each keep 1/24 of their 1,000, which is 42.

**The pick is random, but the same every time.** It comes from a fixed seed,
so two runs with `PICTURES=250` train and test on the same pictures and can
be compared.

**`make evaluate` uses the run's own lists.** A model trained on the subset
is scored on the same 42 test pictures, and says so when it starts. Its
score is never mixed up with one from the full test sets.

**How long.** With 250 pictures an epoch is 32 steps, about 30 seconds, plus
a few seconds to score val. A full 100 epochs is about an hour; `patience`
often stops it earlier.

**What to expect.** Scores from 250 pictures will be far lower than from
6,000, and 42 test pictures give a rough score, not a precise one. That is
fine for learning the process. The steps, the files and the model format
are the same for every size.

## What a run writes

Everything goes to `runs/<name>/`:

| File | What it is |
| --- | --- |
| `weights/best.pt` | **the trained model**: the epoch that scored best on `val`. This is the one to use. |
| `weights/last.pt` | the model after the latest epoch. `make resume` carries on from it. |
| `data/` | for a subset, the picture lists it trained and tests on |
| `results.csv`, `results.png` | losses and scores for every epoch |
| `args.yaml` | every setting the run actually used |
| `train_batch*.jpg` | training pictures after augmentation, with their labels. Check that the outlines still fit the blocks. |
| `val_batch*_labels.jpg`, `val_batch*_pred.jpg` | val pictures with the true labels, and with the model's guesses |
| `confusion_matrix.png` | which shapes are mistaken for which, on `val` |

`make evaluate` adds:

| File | What it is |
| --- | --- |
| `test/`, `test-unseen/` | plots and a confusion matrix for each test set |
| `evaluation.json` | the scores for both, per shape as well |

[`results.md`](results.md) explains every score and plot, and which way is good.

It also prints them side by side:

```
                              test    unseen       gap
box mAP50                        …         …         …
mask mAP50-95                    …         …         …
mask mAP50-95 per class
  triangle                       …         …         …
  …
```

## The trained model

The model is one file, `runs/<name>/weights/best.pt`, about 22 MB. It is a
PyTorch file holding everything needed to use it: the network and its
weights, the seven class names in order, and the settings it was trained
with. Nothing else from the run is needed to use it.

### Using it on its own

```python
from ultralytics import YOLO

model = YOLO("runs/shapes/weights/best.pt")
result = model.predict("picture.jpg", conf=0.5)[0]

# result.masks is None when no block was found.
for box, shape, confidence, outline in zip(
    result.boxes.xyxy, result.boxes.cls, result.boxes.conf, result.masks.xy
):
    print(result.names[int(shape)], float(confidence), box.tolist(), len(outline))
```

For every block it finds, the model gives:

| Output | What it is |
| --- | --- |
| `boxes.cls` | the shape number; `result.names` turns it into a name |
| `boxes.conf` | how sure the model is, 0 to 1 |
| `boxes.xyxy` | the box around the block, in pixels: left, top, right, bottom |
| `masks.xy` | the block's outline, as points in pixels |

`predict` also takes a folder, a video, or a frame from a camera.

### Using it with the arm

The arm needs more than pixels. From the outline, it finds the block's centre
and which way it is turned in the picture. With the camera's position and
lens, that becomes a place on the table to reach for. That is step 4.

A robot computer may not run PyTorch, or may need it faster. Ultralytics can
convert the same file to other formats, for example:

```python
YOLO("runs/shapes/weights/best.pt").export(format="onnx")    # most runtimes, including ROS nodes
YOLO("runs/shapes/weights/best.pt").export(format="coreml")  # Apple devices
YOLO("runs/shapes/weights/best.pt").export(format="engine")  # NVIDIA Jetson, with TensorRT
```

Each writes a new file next to `best.pt` and may need an extra package.
None of these is set up yet.

**Keep the model safe.** `runs/` is not in git, and `make clean-runs`
deletes it. When a run is worth keeping, copy its `best.pt` somewhere with a
name that says what it is, for example `models/shapes-250-yolo26s-seg.pt`.

## The model: YOLO26s-seg

**YOLO26** is the newest Ultralytics model family, and the one this
version of Ultralytics (8.4) is built around.

**`-seg`, segmentation.** The model gives each block's outline, not only a
box around it. The arm needs the outline later to find the block's centre
and which way it is turned. The labels are already outlines, so the same
data trains it. A segmentation model gives boxes too.

**`s`, small.** YOLO comes in sizes n, s, m, l and x.

- **n** is the fastest, but it misses more small objects. In `test-unseen` a
  typical block is only about 25 × 25 pixels.
- **s** has 11 million parameters. That is enough for 7 plain shapes and
  6,000 pictures, and it still runs quickly on a small computer beside the arm.
- **m** and bigger train and run slower, and are unlikely to help much here.
  If `s` is clearly not learning enough, try
  `pixi run python -m training.train --pictures 250 --model yolo26m-seg.pt --name medium`.

**Starting from pretrained weights.** The model starts from weights already
trained on COCO, a large set of real photos. It already knows what real
edges, corners, textures and light look like. Trained from nothing on Gazebo
pictures alone, it would only know Gazebo. This one choice matters more for
real photos than any other setting here.

## The settings

### Training

| Setting | Value | Why |
| --- | --- | --- |
| `imgsz` | 640 | the pictures are 640 × 480. Smaller would shrink far blocks further. |
| `epochs` | 100 | an upper limit; `patience` usually stops it earlier |
| `patience` | 20 | stop when the `val` score has not improved for 20 epochs |
| `batch` | 8 | the Mac's 16 GB is shared between CPU and GPU. Raise it on a bigger GPU. |
| `cache` | off | in memory, the pictures alone would take about 5.5 GB |
| `device` | picked | NVIDIA GPU if there is one, otherwise the Apple GPU (`mps`), otherwise CPU |
| `seed` | 0 | the same run gives the same result |

### Augmentation: changes made to each picture during training

Ultralytics changes every training picture a little, differently each epoch,
and moves the labels to match.

| Setting | Value | Why |
| --- | --- | --- |
| `fliplr`, `flipud` | 0.5, 0.5 | a mirrored or upside-down shape is still the same shape, and the camera looks down |
| `degrees` | 10 | turns the picture up to 10°, adding camera tilt |
| `translate` | 0.1 | moves the picture up to 10% |
| `scale` | 0.5 | zooms in or out up to 50%, for more block sizes |
| `mosaic` | 1.0 | joins four pictures into one, so the model sees more blocks per step and blocks cut off at edges |
| `close_mosaic` | 10 | stops mosaic for the last 10 epochs, so the model ends on whole pictures like the real ones |
| `hsv_s`, `hsv_v` | 0.7, 0.4 | colour strength and brightness change, as between real cameras |
| **`shear`, `perspective`** | **0, off** | these slant the picture. A slanted square has no right angles, so it looks like a rhombus while still labelled "square". That would wipe out the gap kept between the classes. The camera angle in the pictures already squashes shapes the way a real camera does. |
| **`hsv_h`** | **0, off** | the generator already draws every training hue. Any hue shift would push the edge of those hues into teal and cyan, which only `test-unseen` is meant to have. |
| `mixup`, `copy_paste` | 0, off | blending pictures or pasting blocks between them makes scenes no camera would see |

Two tests in `tests/test_training_settings.py` keep the two "off" rows
off: one checks that a hue shift cannot reach the unseen hues, and the
other that shear and perspective stay at 0.

### Camera effects

Gazebo pictures are sharp and clean. Real camera pictures are not. With
Albumentations installed, a few training pictures also get:

| Effect | Chance per picture |
| --- | --- |
| Gaussian blur | 10% |
| motion blur | 10% |
| sensor noise | 10% |
| JPEG compression, quality 40 to 95 | 10% |
| grey | 2% |
| contrast change (CLAHE) | 2% |

None of these moves a pixel, so the labels stay correct without changes.

## What these settings cost the unseen test

`test-unseen` is meant to show conditions training never had. Two settings
blur that a little, on purpose:

- **`scale`** zooms training pictures out, so some training blocks look
  about as small as blocks from the farther camera in `test-unseen`.
- **`hsv_v`** darkens some training pictures, a little like the dim light
  in `test-unseen`.

Both are kept because real photos vary in size and exposure. So the gap
between `test` and `test-unseen` will look somewhat smaller than it would
with no augmentation. Hue is the one change kept strictly unseen.

## Beyond simulation

A model that scores well on `test-unseen` has still only seen Gazebo. The
settings above help, but the real test needs real photos:

1. **Take 100 to 200 photos** of real blocks with the camera the arm will
   use, from many angles and in different light. Label them and use them
   only for testing at first. This is the only true measure of how the model
   does outside simulation.
2. **If the real score is low, fine-tune.** Carry on training from
   `best.pt` for a few epochs, on the synthetic pictures plus a small set of
   labelled real ones. A few hundred real pictures often close most of the
   gap.
3. **Make the blocks look more real** if the photos show why the model
   fails: rounded edges, wood grain, the real table. These are changes to
   the generator, listed under "What never changes" in
   [`dataset.md`](dataset.md).

## The environment

Two things in `pixi.toml` are there to make training work on the Mac:

- **PyTorch comes from conda-forge, not PyPI.** The PyPI build brings its
  own copy of the OpenMP library. OpenCV's conda packages bring another, and
  a program that loads both crashes as soon as `torch` is imported before `cv2`.
- **`PYTORCH_ENABLE_MPS_FALLBACK=1`.** conda-forge's torchvision has no
  Apple GPU version of NMS, the step that drops overlapping guesses.
  Without this setting, scoring `val` stops with an error. With it, that one
  step runs on the CPU. Training speed is the same.

## Training somewhere else

`data/shapes/data.yaml` holds the full path to this folder on this Mac. To
train on another machine, copy `data/shapes/` there and change the `path:`
line in both yaml files. A subset's lists in `runs/<name>/data/` hold full
paths too, so make the subset on the machine that trains.
