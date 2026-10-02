# Problem 4 — the learned way

Four to six glasses of **mixed kinds** stand on the table, some too close to
grip. Find each one, photograph it from the side, measure it, name its kind,
decide where to hold it, push crowded glasses apart, and rack every glass
that can be held. Here five small models do the seeing, the naming, the
gripping and the predicting. Rules are kept only where the answer can be
worked out exactly, or where a mistake would break a glass.

This is [solution 8](../docs/problem-4/solutions/learned/08-the-learned-pipelines-retrained.md)
in the problem 4 docs, with two changes. SideNet names the kind itself,
instead of the rules naming it from SideNet's 16 widths, which solution 8
measured to fail. And where to grip is learned too, by a new model, GripNet.

Nothing here needs ROS or Gazebo. The pictures come from problem 2's
renderer, the pushes from problem 3's MuJoCo bench.

## The whole run

```
1. overhead depth picture ──TopNet──▶ each glass: where it stands, how wide, how tall
2. 24 camera places round each glass ──veto──▶ allowed places ──Ranker──▶ best place
3. side depth picture from there ──SideNet──▶ height, 16 widths, KIND
                                 ──GripNet──▶ can it be held? grip height, finger opening
4. refuse it if GripNet says it cannot be held, or SideNet is unsure of the kind
5. a measured glass with room ──rack plan──▶ slot ──▶ squeeze at its kind's force cap, rack it
6. otherwise ──push search──PushNet──▶ one push ──▶ look again (back to 1)
7. nothing left worth doing ──▶ every glass still standing gets a reason
```

### Which parts are learned and which are programmed

| Step | Done by | Learned or programmed |
|---|---|---|
| Find each glass from above | **TopNet** | learned |
| Throw out camera places that cannot work | the veto: out of reach, camera inside a glass, a glass in the line of sight | programmed (geometry) |
| Choose the best of the allowed places | **Ranker** | learned |
| Measure height and widths | **SideNet** | learned |
| Name the kind | **SideNet**, its new second head | learned |
| Can it be held, where, how wide | **GripNet** (new) | learned |
| How hard to squeeze | a lookup: the named kind's force cap in `spec.py` | programmed |
| Which slot | the rack plan: tries every way of filling the six slots | programmed |
| What a push will do | **PushNet** | learned |
| Which push to make | the search: tries 1,500 pushes against PushNet, drops risky ones | programmed |
| The order of work | `run.py` | programmed |

**Why those parts stay programmed.**
- **The veto and the push search** are short loops of geometry. They are
  what keep a learned mistake cheap: a bad Ranker score costs a spoiled
  picture, never an unsafe camera place.
- **The rack plan** has an exact answer. Six slots is a few hundred cases at
  most, so every one is tried in milliseconds. A model could only do worse.
- **The squeeze** is looked up from the kind, not learned. A learned force
  would be a model deciding how hard to press on glass, with nothing to
  check it.

## The five models

| Model | From | Kind | Given | Gives back |
|---|---|---|---|---|
| TopNet | problem 2, as it is | small U-Net, 144 thousand weights | overhead picture: height above the table per pixel, plus row and column | per pixel: glass or not, and the way to its glass's middle |
| Ranker | problem 2, as it is | MLP, 1.3 thousand | 7 numbers about one camera place | the chance the side picture from there is clean |
| SideNet | problem 2, **with a kind head** | CNN | side picture: distance per pixel | 17 numbers (height, width at 16 levels) and 4 kind scores |
| GripNet | **new** | CNN, same picture layers as SideNet | the same side picture | can it be held (a chance), grip height, finger opening |
| PushNet | problem 3, **each glass's own kind** | MLP, 3 layers of 256, 5 copies | 60 numbers: the pushed glass, the push, up to 5 other glasses, each with its kind or "not measured" | where every glass moves, the chance something topples, the chance the jaw is blocked |

### TopNet — find

For every pixel of the overhead picture it says whether the pixel is glass,
and which way the middle of that pixel's glass is. Each glass pixel votes for
a middle; where 30 or more votes land together, that is one glass. The pixels
that voted give its place, its width, and from their depth its rim height.
Problem 2 explains why voting separates glasses that touch in the picture.

### Ranker — choose where to look

Geometry lists 24 camera places in a ring round the glass and vetoes those
that cannot work. The Ranker scores the rest from 7 numbers: how far the
place is from the arm, which way it faces, the gap to the nearest glass in
front and behind, how many other glasses are in frame, the glass's width,
and its nearest neighbour. It is given numbers, not a picture, because there
is no picture until the arm goes there. Under 0.5, the glass is not looked at
yet: problem 3's pushing may give it a clear view later.

### SideNet — measure and name

The side picture in; the height and the width at 16 heights out, as in
problem 2. The new part is a second head on the same layers: four scores, one
per kind, turned into chances that add up to 1.

**Why the kind comes from SideNet and not from the rules.** Problem 4's
solution 8 measured what happens when the rules' waist test is run on
SideNet's 16 widths: a 1 mm error makes a straight glass grow a waist, and
turns 83 of 200 stemmed glasses into short-stemmed ones. A head that learns
the kind from the whole picture never has to find a waist in 16 numbers.

A glass SideNet gives less than a 0.6 chance for any kind is refused, rather
than squeezed at a force chosen for a guess.

### GripNet — where to hold it

The same side picture in; three numbers out:
- **can it be held**, as a chance. Under 0.5 the glass is refused;
- **grip height**, in metres from the table;
- **opening**, how far apart the pads are when they touch the glass.

**Where its answers come from.** The simulator knows every glass's true
shape and kind, so `find_grip()` — problem 1's grip rule — is run on the
truth, and its answer is the label. When the rule finds no safe grip, the
label is "cannot be held", with the rule's reason kept in the JSON. So
GripNet learns the rule's whole behaviour from pictures: where it holds a
straight glass (just below its centre of mass), a tapered one (the flattest
low band), a stemmed one (the stem), and when it refuses.

It has a real refusal to learn. In this cell the rule holds every straight
glass, about 2 in 5 tapered, 1 in 3 stemmed, and no short-stemmed glass at
all: their stems sit below the lowest height the gripper reaches without
fouling the table. That is [`known-gaps.md`](../docs/known-gaps.md)'s first
entry, not a fault of the model.

### PushNet — what a push will do

Problem 3's forward model, with the change problem 4's
[solution 9](../docs/problem-4/solutions/learned/09-plan-the-whole-table-with-the-push-model.md)
asks for. Problem 3 told it the table's one kind. Here every glass carries its
own: one of the four, or **not measured** for a glass nobody has photographed
from the side yet, whose foot then goes in as zero.

During collection, before each push, 3 in 10 glasses have their kind hidden.
The simulator still pushes them for real, so the model learns what happens to
a glass it was not told about. What it learns for such a glass is an average
over the kinds it could be, not the worst case, so the search holds a push on
an unmeasured glass to a stricter topple limit: 0.5% instead of 1%.

The search can push any glass, a refused one too. Moving a glass that cannot
be racked out of the way is often what frees one that can. Room is only
counted for glasses still worth racking.

## Training

Each picture model trains on **200 mixed tables**: one overhead picture and
three side pictures each, so 200 overhead and 600 side pictures. The
simulator gives every answer for free: which glass each pixel shows, each
glass's shape and kind, whether a side picture was spoiled, and where the grip
rule would hold the glass. All four train in about three minutes on a laptop, drawing the pictures included.

PushNet trains on pushes really made in MuJoCo: random pushes on 9,000 mixed
tables, about 50,000 pushes, each also used mirrored. The labels are what the
camera saw before and after each push, never the simulator's own record.

The held-out tables, 10000 on, are never trained on. Push validation uses
tables 9000 to 9199.

## Results — 50 held-out tables, 251 glasses

From `make run`, in `results.json`. The whole run takes about 75 seconds.

### Each model on its own

| Model | On the held-out tables |
|---|---|
| TopNet | 250 of 251 glasses found |
| Ranker | 152 of 229 chosen places gave a clean picture; on these crowded tables spoiled views are common |
| SideNet, shape | height 4.3 mm out at the median, widths 1.4 mm |
| **SideNet, kind** | **229 of 229 named right**, every kind |
| **GripNet, can it be held** | agrees with the rule on 226 of 229; called 1 holdable that the rule refuses, and refused 2 the rule could hold |
| **GripNet, where** | grip height 0.3 mm from the rule's at the median, 7.6 mm at worst; opening 1.2 mm |
| PushNet, unseen pushes | the pushed glass lands 7.1 mm from where it said, median; blocked guessed right 96% of the time; 110 of 152 topples flagged at a 0.1 chance |

### The table as a whole

| | Result |
|---|---|
| Racked | **40** of 251; the rule could hold 93 of them at all |
| Racked with a wrong name, or squeezed harder than its kind allows, or where the rule finds no grip | **0** |
| Racked with the grip on the band (within 7 mm of the rule's height) | 39 of 40 |
| Racked while a neighbour was really in the way | 1 |
| Pushes | 83 |
| Tables where something toppled | 4 of 50, which stops those tables: 12 glasses |
| Refused although the rule could hold them | 53 |

Why glasses were left standing:

| Reason | Glasses |
|---|---|
| GripNet says it cannot be held | 146 |
| no push the model expects to make room | 38 |
| stopped: a glass on the table fell over | 12 |
| no clean side view, and no push expected to make one | 11 |
| other | 4 |

### What the numbers say

**The models are not what loses glasses.** SideNet named every glass right,
and GripNet put the grip where the rule would, to a third of a millimetre at
the median. Nothing racked was named wrongly or squeezed too hard.

**Crowding is.** 158 of the 251 glasses cannot be held by any rule in this
cell, and GripNet correctly refuses them. But a refused glass stays on the
table, crowding its neighbours. Of the 93 glasses that could be held, 53 were
left standing, mostly because no push was expected to make room. The push
search will move a refused glass aside, but on these tables the safe pushes
often run out first.

**Pushing is the weakest learned part.** It toppled something on 4 tables.
Problem 3's push model, trained on one kind per table, toppled nothing on its
50 held-out tables. With mixed kinds, each kind is seen less often, and the
foot that decides whether a glass tips depends on the kind.

## Running it

Everything runs from this folder. The first `make` installs the environment
with [pixi](https://pixi.sh). No ROS and no Gazebo.

```
make train        # 200 tables; train TopNet, Ranker, SideNet, GripNet (about 3 minutes)
make collect      # pushes on 9000 tables in MuJoCo (about 10 minutes)
make train-push   # train the five copies of PushNet (a few minutes)
make run          # clear the 50 held-out tables; writes results.json
make test         # the quick checks
```

`weights/`, `data/` and `saved/` are not in git, so run `make train`,
`make collect` and `make train-push` first. A fresh run gives close numbers,
not identical ones.

## The whole workflow, step by step

`make explain` runs the real pipeline on four held-out tables and writes each
one up as a walkthrough, into `saved/workflow-explained/`. Start there if you
want to see the workflow without reading every model's folder.

Each table's `README.md` reads top to bottom, one section per step: the
picture of that step as it happened, whether it is **learned** or
**programmed**, which model or rule did it, what it was given, what it gave
back, and what happens next. The numbers behind every step are in
`steps.json` beside it.

| Table | What it shows |
|---|---|
| 10000 | a stemmed glass refused by GripNet; two straight glasses racked, one after a push |
| 10035 | three glasses racked, two of them wide, so the rack plan keeps the slots beside them empty |
| 10009 | a long table: seven pushes, one glass racked |
| 10013 | a push topples a glass, and the table stops |

Any held-out table can be explained: `pixi run python explain.py --tables 10022`.

## Looking at the data

`make show` draws what every model is taught and what it answers into
`saved/`, a `.png` with a `.json` of the same numbers beside it. `make trace`
clears three held-out tables and draws every step.

```
make show                           # 20 of each, for every model, train and test
make trace                          # 3 held-out tables, step by step, in saved/runs/

pixi run python show.py top train   # one model and one split; add --count 50 for more
pixi run python show.py grip test
pixi run python run.py --tables 5 --trace --show
```

**`saved/top-net/`** — TopNet.
- `train/`: the height picture it is given; answer 1, glass or not; answer 2,
  the way to each glass's middle, as colour and as arrows. The JSON writes
  out four pixels in full — three on glass, one off — with what TopNet is
  given and what it should say. They are ringed in red on the first panel.
- `test/`: its chance per pixel, where the votes landed and the middles
  picked, and the found glasses over the true ones, each with how far out it is.

**`saved/ranker/`** — Ranker.
- `train/`: the camera place drawn from above, the side picture from there,
  the same picture with the glass alone, the 7 numbers, and the true answer:
  clean or spoiled. `all-examples.csv` is the whole training set as a table.
- `test/`: all 24 places round one glass. A cross is vetoed, coloured by the
  reason; a dot is allowed, with the Ranker's score. The chosen one is ringed,
  and its picture is shown with whether it really came out clean.

**`saved/side-net/`** — SideNet.
- `train/`: the side picture, and the 17 true numbers drawn on it — a thick
  line at the height, a thin one at each of the 16 levels, as long as the
  width there — and the true kind. The JSON has them in millimetres and in
  the scaled units SideNet learns in.
- `test/`: the same, with SideNet's own lines in orange over the true ones in
  green, its four kind chances, and its height and width errors.

**`saved/grip-net/`** — GripNet.
- `train/`: the side picture with the true grip drawn as two green pads at
  the rule's height and opening, or the rule's reason it cannot be held.
- `test/`: the same, with GripNet's pads in orange, its chance that the glass
  can be held, and how far out its height and opening are.

**`saved/push-net/`** — PushNet.
- `train/`: collected pushes drawn in the push's own frame — the jaw moves up
  the picture — with each glass ringed in its kind's colour, grey if the model
  was told "not measured", and green arrows for how each glass really moved.
  The JSON has the 60 input numbers and 14 output numbers as stored, and the
  same in millimetres with names. `all-examples.json` has them all.
- `test/`: unseen pushes, with the model's predicted moves in orange beside
  what happened in green, and its topple chance.

**`saved/runs/`** — whole tables, from `run.py --trace`.
- `table-<n>.json`: every look, measurement, push and racking, with what
  each model said beside the truth.
- `table-<n>/step-NN.png`: the table from above at each look, each glass
  coloured by the kind SideNet named (grey before it is measured), and what
  was done next: the push as an arrow, or the racking with its slot and force.

The colours: straight blue, tapered green, stemmed purple, short-stemmed
orange, not measured grey.

## Where it can fail

- **Half the glasses cannot be held by any rule in this cell.** Every
  short-stemmed glass and most stemmed and tapered ones are refused, by
  GripNet as by the rule it learned. They stay on the table and keep their
  neighbours crowded. A slimmer gripper, or grips from an angle, is problem
  5's work, not a model's.
- **GripNet decides, and nothing checks it in this simulator.** A glass it
  wrongly calls holdable is gripped. On a real arm, problem 1's touch check
  and the weighing after the lift are what would catch it; here the bench's
  `take()` simply lifts the glass, so the run counts the case instead.
- **SideNet's kind sets the squeeze.** A stemmed glass named short-stemmed is
  squeezed at 20 N instead of 6. The run counts this as dangerous.
- **PushNet is the weak part.** See the results above. Topples it rated safe
  are what end a table early.
- **Every picture is drawn, not photographed.** Opaque glasses and a perfect
  depth camera, as in problem 2. The models have never seen a reflection.
