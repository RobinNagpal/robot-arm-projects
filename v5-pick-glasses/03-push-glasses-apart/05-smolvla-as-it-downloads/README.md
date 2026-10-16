# Problem 3 — a foundation model as it downloads

Glasses stand too close together to be picked up. Push them apart, then pick
each one up. Here a borrowed robot model is downloaded and run as it is.
Nothing is collected, nothing is trained, and no number in it is fitted in
this cell. The model sees the table from straight above. It gets one plain
English sentence and the jaw's own pose. Whatever trajectory it returns is
carried out.

This is [solution 5](../../docs/03-push-glasses-apart/solutions/05-smolvla-as-it-downloads.md)
of [the six](../../docs/03-push-glasses-apart/solutions/overview.md). The
document holds the reasoning. This file holds the numbers and the decisions
the document left open.

The model is **SmolVLA**, `lerobot/smolvla_base`, about 450 million
parameters. **It runs here**: on an M4 laptop, on Metal, with about three
tenths of a second of thinking per push.

## How to run

    make test     # the quick checks: no download, no accelerator
    make run      # 3 evaluation runs over the 50 held-out tables
    make film     # videos of the first few tables

The first run downloads about 2.9 GB. That is 907 MB of SmolVLA's own weights
and 2.0 GB of the `HuggingFaceTB/SmolVLM2-500M-Video-Instruct` backbone.
LeRobot fetches the backbone separately because the checkpoint's
`load_vlm_weights` is true. After that, both are read from the cache.

## Results — 3 runs of the 50 held-out tables, 251 glasses

Each number is the median over three evaluation runs, with the spread across
them in brackets. The policy draws each answer from fresh noise, so one run is
not a measurement; [flow
matching](../../docs/03-push-glasses-apart/solutions/05-smolvla-as-it-downloads.md#flow-matching-and-why-one-run-is-not-enough)
explains why. `results.json` holds all three runs. `asking.json` holds what
the asking cost. The table compares this solution with solutions 4 and 1; the
full table of all six is in [the results](../results/README.md).

| | This solution | [Solution 4](../04-a-world-model/) | [Solution 1](../01-one-fixed-nudge/) |
|---|---|---|---|
| Glasses racked | **48** of 251 (±2.5) | 146 of 251 | 107 of 251 |
| Glasses refused | 190 (±3.0) | 85 | 143 |
| Glasses toppled | 12 (±2.0) | 20 | **1** |
| Tables finished | **1** of 50 (±0.6) | 20 of 50 | 14 of 50 |
| Tables scored *wrong* | 9 of 50 (±2.1) | 19 | **1** |
| Pushes | 620 (±26.2) | 221 | 173 |
| Pushes that never touched anything | 506 of 620 (±15.0) | 0 | 0 |
| Pushes that jammed | 79 of the same 620 (±9.6) | 7 | 1 |
| Travel against the floor | 0.42x | 1.98x | 0.87x |
| Landing, median / worst | 71.5 / 356 mm | 6.9 / 532 mm | **1.7 / 58 mm** |
| Thinking per push | **286 ms** | 374 ms | 93 ms |

Where this column gives a share of the pushes, both parts come from one run:
the middle one by push count. The spread takes a median of each field
separately, and those medians can come from different runs. So parts taken
from the spread need not add up.

The thinking times leave out the simulator's time and were measured on an
idle machine. Timed on a busy machine, this solution reported about a second
per push, nearly four times the truth. [The
results](../results/README.md#thinking-time-and-what-it-does-not-say) explain
why the condition matters.

So the model costs about five times what the geometry costs per push. That is
real, but it is not why this solution fails. The world model costs more per
push than this one. At this size, a foundation model's price is a nuisance,
not a barrier. This solution finishes nothing because of its answers, not its
speed.

**It ran, and it did badly.** That is the result as it came out. Nothing was
tuned to improve it. The only run with a different reading is the
sensitivity check below, and that run is not the scored result.

**Put the racking beside the crowding and nothing is left over.** 203 of the
251 glasses were crowded at the start, so **48 had room, and 48 were racked.**
Racking a glass loosens its neighbours, so any solution that freed even one
glass would rack more than 48. This one racks only the glasses that were
already free. Its pushes achieve nothing: the arm could have skipped every
push and scored the same.

Of the 190 glasses left on the table:

- 134 are reported with "push budget spent". That is the correct refusal when
  a glass has been pushed at and still has no room.
- 38 are reported with "tips before it slides".
- 18 are reported with "a glass fell over". The loop reports this for the
  glasses still standing on a table where a push toppled one.

**The tipping refusal now binds hard.** With the old invented blade it refused
about one glass in fifty tables. The cause is not this solution. The shared
rule is reacting to a real hand that cannot go lower than 75 mm. It holds back
38 glasses before the model is asked about them.

**The failure is not the one the document predicted.** The document expected
"confident, plausible, wrong actions": good-looking pushes at the wrong glass.
In fact, **more than four pushes in five never touch anything** — 506 of 620.
The trajectories come back high. The median chunk's lowest point is 217 mm
above the table, well above these glasses. Meanwhile the chunk travels 868 mm
across the table in fifty waypoints. So the jaw sweeps through the air above
the glasses.

It also asks to move several times faster than this arm can. The bench caps a
path at the fastest speed the cell ever moves the jaw. A bench without that
cap would report the physics of an arm nobody has. **The cap changes almost
nothing**: the score moved by less than the spread between runs. The real
problem is the height, not the speed.

When the jaw does catch a glass, it moves as fast as the arm can go. That is
ten times the push macro's speed. This causes the jams and the toppled glasses.
It is also why a glass lands tens of millimetres from the aim, not one or two.
The real gripper made this worse. The hand is far bigger than the blade it
replaced, so the few chunks that reach table level now sweep something. 12
glasses fall over, where the blade knocked over 6.

Part of why the chunks come back high is [the
state](#the-state-which-no-statistics-describe-and-which-barely-varies). That
part is measured, and it is about 60 mm: real, but not enough. The rest is
that the model does not produce table-level motion on these pictures. The gap
also grew with the real gripper. The push height rose from 50 mm to 75 mm,
while the model's answers did not move.

**What this does and does not establish.** SmolVLA, as it downloads, is not
usable on this cell. That gives solution 6 plenty of room to improve. It says
nothing about vision-language-action models in general, for the reasons [the
document](../../docs/03-push-glasses-apart/solutions/05-smolvla-as-it-downloads.md#the-instruction-is-nearly-dead-weight-here)
gives. It also turns out that the action space has no units until somebody
supplies them.

### The sensitivity check

The checkpoint does not say which way each slot runs. `make sensitivity`
turns the height slot over. It does one evaluation run over 50 tables and
leaves `results.json` untouched. It shows how much the result depends on a
choice nothing in the weights could settle.

**Very little depends on it, and what does goes the wrong way.** Turned over,
the trajectories come back *higher*. The jaw's median lowest point rises from
217 mm to 254 mm. Three fewer glasses are racked, 45 against 48. No table is
finished either way. Toppling falls from 12 glasses to 1. That is not better
pushing. The jaw spends even more time above everything, so it touches almost
nothing and breaks almost nothing. So this choice is not what makes the
solution fail. The state is: it sits at one end of its range whichever way the
slot runs.

## The join, which is the whole of the work here

Nothing here is fitted, so there is no training to describe. Instead there is
the join between a model fitted on another arm and a jaw on this table. It
carried far more weight than the document expected. All of it is in
`joining.py`, written once so that
[solution 6](../../docs/03-push-glasses-apart/solutions/06-smolvla-fine-tuned.md)
can use it unchanged.

Everything below was read off the checkpoint, not assumed.

### What the model's action space really is

`lerobot/smolvla_base` declares `action` of shape 6 and `observation.state` of
shape 6. Both are normalised `MEAN_STD`. It returns a chunk of 50 actions per
answer. The checkpoint ships three sets of means and spreads, named `so100`,
`so100-blue` and `so100-red`. Their means look like
`[1.6, 119.9, 109.8, 56.7, -27.4, 12.0]`. These are **SO-100 joint angles in
degrees**: a desktop arm's five joints and its gripper. They are not a UR5e's
joints, and they are not positions in space.

### And the shipped statistics do not apply themselves

This is the first surprise, and it shapes everything after it. The statistics
are saved under keys like `so100.buffer.action.mean`. LeRobot's normaliser
looks up `action` and `observation.state`. It passes through any key it cannot
find unchanged. So with the released checkpoint and LeRobot 0.6.1, **both the
normaliser and the un-normaliser do nothing.** The state goes in as a z-score
and the actions come out as z-scores. Which of the three arms to un-normalise
against is left to the user.

Picking one arm would only add a fixed scale and shift to the numbers. So this solution works in the normalised space the model really
uses, and it sets what one standard deviation is worth here.

### The four slots, and which is which

Four of the six slots are used. Each is read by what its joint does on the
SO-100 arm:

| slot | SO-100 joint | read here as |
|---|---|---|
| 0 | shoulder pan | the jaw's x, across the bench |
| 1 | shoulder lift | the jaw's y, out and back |
| 2 | elbow flex | the jaw's height |
| 4 | wrist roll | the jaw's heading |

Slots 3 (wrist flex) and 5 (gripper) are dropped. The bench holds the jaw
level and closed, and offers no way to change either. A test checks that
changing these slots changes nothing.

### What one standard deviation is worth, and why it also sets the speed

A z-score is not a length, so something must set the scale. **Two standard
deviations span the frame of the straight-down picture exactly.** [The
document](../../docs/03-push-glasses-apart/solutions/05-smolvla-as-it-downloads.md#the-code-that-does-the-work)
explains why that frame was chosen, and why the same choice also sets the
speed. The arm cannot go faster than its own top speed; past that, a step just
takes longer. The model's waypoints ask for several times the arm's top speed.
The bench's push macro moves at a tenth of it.

Nothing here caps the speed at something gentler. A gentler cap would be a
number chosen to make this solution look better, and this solution fits
nothing. The bench's own cap is different. It is a limit the arm already has,
it applies to every solution, and it never binds on the bench's own paths.

### The one convention the checkpoint does not settle

A joint angle's sign depends on the arm it was recorded on. The checkpoint has
a mean and a spread for each slot, but nothing about which way the joint
turns. This repository has no SO-100 model to read it from. So the direction
of each slot was decided here: **larger is further along the cell's own
axis**. On the height slot, larger is higher.

[The sensitivity check](#the-sensitivity-check) turns the height slot over, so
that nobody has to take this choice on trust. The scored result always uses the
declared direction. Nothing was chosen by which way scored better.

### The state, which no statistics describe and which barely varies

The checkpoint ships **no statistics for `observation.state` at all**, only
for `action`. So nothing says what scale the state should have. The only
consistent answer is to fill it with the jaw's pose under the same reading
as the actions. `joining.to_state` does that.

Two things then follow from the cell, not from the model.

First, the bench parks the jaw in one spot between actions. It lifts it there
after every chunk. So whenever the policy is asked, the jaw is in the same
place: outside the picture's frame and above travel height. Three of the four
slots are **the same number at every ask on every table**. Only the heading
slot varies. The document shows that the instruction carries no information
here. The state turns out to be nearly as idle, for a different reason.

Second, the parked pose is outside the range the reading can express, so it
clips to the edge. The model is told the jaw is as high as it can go. SmolVLA
returns absolute targets near the state it is given, so it answers high.

That explains part of the result, and the part can be measured. The same
picture was asked six times. With the parked jaw's state, the chunks' lowest
point has a median of 205 mm. With an all-zero state, it is 138 mm. All-zero
is the middle of every slot, the most favourable state this reading can
express. So the state raises the answers by about 70 mm. But 138 mm is still
far above the 75 mm the jaw rides at, and above most of a glass. So **even the
most favourable state does not get the model to move at table level on these
pictures.**

The clipped, constant state therefore makes a poor result worse. No state available
here would make it good. A join that invented a lower state would be measuring
itself, not the model.

### One camera of three

The checkpoint declares three cameras and sets `empty_cameras` to 0. So a
camera missing from the batch is left out, not filled with a blank picture.
This cell has one straight-down view. It fills `camera1`, and the other two are
absent. The model wants floats from 0 to 1, red-green-blue, channels first.
`top_view` already gives RGB, so unlike `film.py` nothing is flipped.

### The glass, the aim, and the budget

`Chunk` wants a glass and an aim beside the waypoints. The model gives
neither. So both are read back off the path afterwards, for the record only.
The glass is the one the jaw comes nearest while low enough to touch it. The
aim is where the path ends. Nothing is planned with either.

The shared budget needed one decision. `PUSHES_PER_TABLE` counts pushes and
makes the six comparable. A trajectory thrown away before it runs is not
charged to it. `PUSHES_PER_GLASS` cannot work the way it does elsewhere. The
other solutions choose a glass, so they can be told to leave a worn one
alone. Here the glass is only inferred from the path. Throwing an answer away
on that label would block the model for the rest of the table. So the limit
applies only where it fairly can: a table is finished once every glass left
has been refused for tipping or had its share. `ASKS_PER_TABLE`, three answers
per push in the budget, guards against an endless loop. It is not a budget.

One scorecard number inherits this weakness. A **repeat** is a push at a glass
that was already pushed at. For the other solutions, it means the method chose
the same glass twice. Here the glass was never chosen. So a repeat only means
two paths came nearest to the same glass.

## Where the document and the code disagreed

These are reported, not quietly resolved, as the house rules ask.

1. **There is no shared machinery for the topple refusal.** The document said
   the check is "applied by the shared machinery on the measurements". It also
   said the trajectory guards "belong with the bench, beside the refusal". The
   bench has neither. The refusal arithmetic is `slides` in
   `01-one-fixed-nudge/plan.py`. This solution imports it, as solution 2 does,
   so all six refuse the same glasses. The trajectory guards had to be written
   here, in `clear.py` and `joining.py`. Solution 6 should import them from
   this folder. The document has been corrected.
2. **The actions arrive in no units at all**, not in "somebody else's units".
   The checkpoint's normalisation does nothing, so the scale had to be
   invented. See [the shipped
   statistics](#and-the-shipped-statistics-do-not-apply-themselves).
3. **The state input is nearly empty here.** The document did not foresee
   that it has no statistics, hardly varies, and decides how high the answers
   come. See [the state](#the-state-which-no-statistics-describe-and-which-barely-varies).
4. **The force channel is closed, as the document says.** `follow()` reports
   the same `Felt` a push does, so the force reading is in the record. There
   is just no input slot for it.
5. **The predicted failure is not the measured one.** The measured failure is
   blunter: most pushes touch nothing, as [the results](#results--3-runs-of-the-50-held-out-tables-251-glasses)
   show. The document's reasoning about the domain gap stands. Its guess about
   how the gap would show does not.

## Stale sentences fixed in the document

The document was written before the bench had the parts this solution needs,
and before it ran. These sentences were wrong and are now fixed: that nothing
in this solution is built; that the straight-down view "is a design rather
than code" and "is not even built yet"; that the waypoint path is "specified
and not yet written"; that the reading of the actions is "a design decision
recorded here, not code that exists"; that the trajectory guards are "a design
decision rather than existing code"; that the bench "still has to grow" two
things; and five places that called the glasses grey. They are pale blue on a
tan table, all one colour.

## What it costs

- **Setup.** A download, and nothing else. No demonstrations, no labels, no
  training run, and no weights file to keep in step with the cell. This is the
  cheapest solution in the folder to set up.
- **Hardware.** A laptop. Metal is used if it is there. `--device cpu` works
  and is about ten times slower per answer.
- **Time.** See the thinking column in the results. The forward pass takes
  most of the time.

## Tests

`make test` runs this folder's 23 checks, and the bench's checks beside them.
None needs a download, a network or an accelerator. They check:

- the reading's arithmetic in both directions;
- that anything the model can return becomes a chunk the bench accepts;
- that the two unused slots change nothing;
- that turning the height slot over changes only the height;
- that a path reaching a glass refused for tipping is never carried out;
- that the budgets bind;
- that the picture is checked before any weights are touched.

A stand-in class replaces the model. It answers at once with a path the test
chose. The test glasses are drawn with `family`, not written down.
