# Problem 2 — the learned way

Several glasses of one kind on the table. Find each one from above, choose
where to photograph it from the side, and read its profile from that picture.
Here a small model does each of the three jobs. Each model is trained on 200
pictures, which takes about a minute on a laptop.

`../problem-2-programmed` does the same job with written rules only. Both are
scored on the same scenes and pictures, from `../problem-2-sim`.

## Why this approach

**Each model learns a job that is hard to write down as a rule.** Which pixels
belong to which glass, which viewpoint will give a clean picture, and how a
glass's shape reads off a side picture. The programmed version needs a
hand-worked height correction for its level camera; SideNet learns the whole
picture-to-shape step from examples, and nobody wrote a correction.

**Finding glasses by voting separates glasses that overlap in the picture.**
Each glass pixel points at the middle of its own glass, and the votes are
counted. No boundary has to be found, so no boundary can be got wrong. A glass
that is partly hidden still votes for the right middle from what shows of it.
This is [solution 6](../docs/problem-2/solutions/learned/06-a-network-trained-from-scratch.md),
the one the solution overview names for the day glasses are allowed to touch.

**The learned parts sit where a mistake is cheap.**
- TopNet only groups pixels. The place and width of each glass come from those
  pixels' depth readings, by arithmetic.
- The Ranker only orders places the geometry has already allowed. A bad order
  wastes one look; it cannot send the arm somewhere unsafe.
- SideNet is the exception: its answer is used as it is, and nothing checks it.

**It passes the project's rule for learned methods.** Every model is trained
from scratch on pictures the simulator draws, and the simulator gives the right
answers for free. Nothing is downloaded, no graphics card is needed, and all
three train in about a minute.

## Where it stands

On the same 50 held-out scenes, the programmed version is ahead on every line.

| Step | Learned (this folder) | Programmed |
|---|---|---|
| Find | 250 of 250; position 0.4 mm median, 1.3 mm worst | 250 of 250; 0.2 mm median, 1.2 mm worst |
| Choose | first place clean 232 of 245; 5 handed over | 246 of 250; 2 handed over |
| Measure | height 5.4 mm median, 36 mm worst; width 2.4 mm | height 0.8 mm median, 2.3 mm worst; width 1.7 mm |

Finding is as good as the rules. Measuring is where it falls behind, for three
reasons:
- SideNet sees one picture, gets no retry, and nothing checks its answer.
- 200 examples is few. SideNet pulls unusual glasses towards the average, so
  its worst errors are the tallest stemmed glasses read short.
- Part of the height error is in the hand-over, not in SideNet.
  `pipeline.measure` passes on the 16 levels as the glass's profile, and a
  profile's height is its top level, which is 97% of the height SideNet said.
  So every height is scored about 3% short.

## How it works

```
1. overhead depth picture ──TopNet──▶ each glass: where it stands, how wide
2. 24 places round each glass ──geometry veto──▶ allowed places ──Ranker──▶ best first
3. side depth picture from the best place ──SideNet──▶ height, and width at 16 heights
```

| Model | Kind | Weights | Given | Gives back |
|---|---|---|---|---|
| TopNet | small U-Net | 144 thousand | 3 grids of 160 × 120: height above the table, row, column | 3 grids: glass or not, and the way to its glass's middle |
| Ranker | MLP | 1.3 thousand | 7 numbers about one camera place | the chance the side picture from there is clean |
| SideNet | CNN | 718 thousand | 1 grid of 160 × 120: distance, per pixel | 17 numbers: the height, and the width at 16 levels |

**Training.** `train.py` draws 200 scenes. Each gives one picture from above
and one side picture of one glass. The simulator knows the answers: which glass
each pixel shows, each glass's true shape, and whether the side picture was
spoiled. The models learn from those.

**1. Find — TopNet.**
- For every pixel of the overhead picture it says whether it is glass, and
  which way the middle of its glass is.
- Each glass pixel votes where it points. Where 30 or more votes land
  together, that is one glass.
- The pixels that voted for a middle give the glass's place on the table and
  its width.

**2. Choose a place — geometry, then the Ranker.**
- Try 24 places in a circle round the glass.
- Geometry throws out places the arm cannot reach, places where the camera
  would stand in another glass, and places with a glass squarely in the way.
- The Ranker scores each place that is left. It is given numbers, not a
  picture, because there is no picture until the arm goes there.
- Take the best place. If it scores under 0.5, hand the glass to problem 3.

**3. Measure — SideNet.**
- It reads the side picture from the chosen place and gives the height and
  16 widths directly.
- It works in scaled units, height ÷ 250 mm and widths ÷ 100 mm, so that all
  17 numbers sit near 1 while it learns. The pipeline turns them back into
  millimetres.

## Running it

Everything runs from this folder. The first `make` installs the environment
with [pixi](https://pixi.sh), which is the only thing to install by hand. No
ROS and no Gazebo are needed.

```
make train      # draw 200 scenes and train all three models, about a minute
make run        # run the 50 held-out scenes and score them; writes results.json
make test       # the quick checks
```

- `make train SCENES=400` trains on more scenes.
- `pixi run python run.py --scenes 5 --show` runs a few scenes and prints
  each glass.
- The weights are not committed, so run `make train` before anything else.
  Your numbers will be close to the table above rather than equal to it.

## Looking at the data

`make show` saves pictures of what each model is taught and what it answers,
into `saved/`. It trains nothing; it uses the weights in `weights/`. All of it
takes about five minutes and 400 MB.

```
make show                                    # all three models, train and test

pixi run python show_top_net.py train        # TopNet, the 200 training scenes
pixi run python show_top_net.py test         # TopNet, the 50 held-out scenes
pixi run python show_ranker.py train
pixi run python show_ranker.py test
pixi run python show_side_net.py train
pixi run python show_side_net.py test
```

Add `--scenes 10` to any one of them for a quick look.

The `.png` files are for looking at, and the `.json` files open as text. A
`.npz` file holds number grids and has to be opened with Python:

```
pixi run python -c "
import numpy as np
d = np.load('saved/top-net/train/scene-00002.npz')
for k in d.files: print(k, d[k].shape)
print(d['target'][:, 31, 38])     # the 3 true answers for the pixel at row 31, column 38
"
```

### TopNet — `saved/top-net/`

Each scene has a `.png`, a `.npz` with every number behind it, and a `.json`
with four pixels written out in full: three on glass and one off it. The same
four are ringed in red in the first panel.

**`train/` — the 200 training scenes, four panels each.**
- Given: the height of each pixel above the table. TopNet is also given each
  pixel's row and column; those are the same in every scene and are not drawn.
- Answer 1: is this pixel glass.
- Answer 2: the way from this pixel to the middle of its glass's rim, drawn
  once as a colour for every pixel and once as arrows for some of them.
- The `.npz` holds `depth` and `ids` as the simulator drew them at 320 × 240,
  and `input` and `target` as TopNet gets them.

**`test/` — the 50 held-out scenes, six panels each.**
- Top row: what TopNet is given, and the two things it says back.
- Bottom row: where the arrows land and which middles were picked; the
  glasses made from them, with the true middles marked; and how far each
  arrow is from the true one.
- Under the panels: each found glass's place and width beside the true ones.
- In the `.json`, `glass_score` is TopNet's raw answer (above 0 means glass)
  and `glass_chance` is the same answer as a chance between 0 and 1.

### Ranker — `saved/ranker/`

Each picture has a `.json` beside it with the same numbers.

**`train/` — one picture per training scene.** A training example is one
place round one glass.
- Left: the table from above, with the camera at that place. The 7 values the
  Ranker is given are drawn on it, numbered 1 to 7, and listed underneath with
  what each one means.
- Right: the side picture from that place, and the same picture with the
  target alone. The true answer is whether the two measure the same.
- `all-examples.csv` is the whole training set as one table.

**`test/` — one picture per glass of the 50 held-out scenes.**
- Top left: all 24 places round the glass. A cross is a place the geometry
  vetoed, coloured by the reason. A dot is an allowed place, with the Ranker's
  score beside it. The best one is ringed.
- Top right: the best place, with its 7 values drawn on.
- Below: the side picture from every allowed place, best score first, each
  marked with whether it truly came out clean.
- The `.json` lists all 24 places. Only the best-scoring one has
  `"chosen": true`, because the arm takes one side picture per glass.

### SideNet — `saved/side-net/`

Each picture has a `.json` with the 17 values in millimetres and in the scaled
units SideNet works in, and a `.npz` with its input and output.

**`train/` — one picture per training scene, three panels.**
- Given: the side picture. The glass in the middle is the one to measure.
- The 17 true values drawn on it: a thick line at the height, and a thin line
  across the glass at each of the 16 levels, as long as the width there.
- The same 17 values to scale, and as a table.

**`test/` — one picture per measured glass of the 50 held-out scenes.**
- The same panels, and a fourth with SideNet's own values drawn in orange.
- The last panel lays the two outlines over each other and lists true, said
  and the difference for each value.
- A glass handed to problem 3 has no picture, because SideNet never runs on it.
