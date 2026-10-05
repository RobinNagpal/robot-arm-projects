# Problem 3 — a foundation model as it downloads

Glasses stand too close together to be picked up. Push them apart, then pick
each one up. Here a borrowed robot model is downloaded and run with nothing
collected, nothing trained and no number in it fitted in this cell. It is
shown the table from straight above, told in one plain English sentence what
to do, handed the jaw's own pose, and whatever trajectory it returns is
carried out.

This is [solution 5](../../docs/03-push-glasses-apart/solutions/05-smolvla-as-it-downloads.md)
of [the six](../../docs/03-push-glasses-apart/solutions/overview.md). The
document is the specification and carries the reasoning; this file carries the
numbers and the decisions the document left open.

The model is **SmolVLA**, `lerobot/smolvla_base`, about 450 million
parameters. **It runs here**: on an M4 laptop, on Metal, about 1 second of
thinking per push.

## How to run

    make test     # the quick checks: no download, no accelerator
    make run      # 3 evaluation runs over the 50 held-out tables
    make film     # videos of the first few tables

The first run downloads about 2.9 GB: 907 MB of SmolVLA's own weights and
2.0 GB of the `HuggingFaceTB/SmolVLM2-500M-Video-Instruct` backbone, which
LeRobot fetches separately because the checkpoint's `load_vlm_weights` is
true. After that it is read from the cache.

## Results — 3 runs of the 50 held-out tables, 251 glasses

Every number is the median over three evaluation runs, with the spread across
them. The policy draws its answer from fresh noise each time, so one run is
not a measurement. `results.json` holds all three in full; `asking.json`
holds what the asking cost.

| | This solution | [Solution 4](../04-a-world-model/) | [Solution 1](../01-one-fixed-nudge/) |
|---|---|---|---|
| Glasses racked | **56** of 251 (±2.6) | 202 of 251 | 195 of 251 |
| Glasses refused | 189 (±1.2) | 48 | 56 |
| Glasses toppled | 6 (±1.5) | 1 | **0** |
| Tables finished | **0** of 50 | 31 of 50 | 33 of 50 |
| Tables scored *wrong* | 5 of 50 (±0.6) | 1 | **0** |
| Pushes | 754 (±13.0) | 114 | 213 |
| Pushes that never touched anything | 674 of 754 (±15.1) | 0 | 0 |
| Pushes that jammed | 63 (±5.5) | 3 | **0** |
| Landing, median / worst | 74.0 / 239 mm | 1.6 / 48.2 mm | 1.0 / 3.9 mm |
| Thinking per push | **about 1 s** | about 0.6 s | under 0.2 s |

The thinking times are deliberately rough. Every one of them was measured
while this machine was busy with other work, and the same solution timed twice
minutes apart gave answers a factor of two apart, so the column is trustworthy
about the order of magnitude and about nothing finer. What it does say is worth
saying: this solution thinks for about a second per push where the geometry
thinks for a fraction of one, and it is the only one here whose cost would be
felt by a person standing beside the cell.

**It ran, and it did badly.** That is the result, reported as it came out.
Nothing was tuned to improve it; the only run ever made with a different
reading is the sensitivity check below, and it is not the scored result.

**Put the racking beside the crowding and there is nothing left over.** 193
of the 251 glasses were crowded at the start, so 58 had room; 56 were racked.
Racking a glass loosens its neighbours, so a solution that freed anything
would rack more than 58. This one racks fewer, and no table was finished.

Of the 189 glasses left on the table, 177 per run are reported with "push
budget spent" — the correct refusal when a glass has been pushed at and still
has no room — and 13 with "a glass fell over", which is what the loop reports
about the glasses still standing on a table where a push has toppled one.
**Exactly one glass in 50 tables was refused for tipping**, so the shared
refusal rule hardly binds on these tables and almost none of the shortfall is
explained by it.

**The failure is not the one the document predicted, and that is the most
useful thing here.** The document expects "confident, plausible, wrong
actions": well-formed pushes aimed at the wrong glass. What actually happens
is that **about nine pushes in ten never touch anything at all.** The
trajectories come back high: the median chunk's lowest point is a little over
200 mm above the table, well above these glasses, while the chunk travels most
of a metre across the table in fifty waypoints. So the jaw sweeps through the
air above the glasses rather than at them.

It also asks to move far faster than this arm can. The bench consumes one
waypoint every fixed period, so how far apart they are is how fast the jaw is
being asked to go, and these waypoints ask for several times the arm's own
speed. The bench holds a commanded path to the fastest speed the cell ever
moves the jaw, because a bench that let a solution exceed it would be reporting
the physics of an arm nobody has. **Holding it there changes almost nothing**:
the score moved by less than the spread between repeat runs, because the real
problem is the height and not the speed. That is worth knowing, since it would
have been easy to assume the speed was the whole story.
When it does catch one it is moving as fast as the arm can go, which is ten
times a push macro's speed, and that is where the jams and the toppled glasses
come from and why a glass lands tens of millimetres from the aim rather than a
millimetre or two.

Part of why the trajectories come back high is in the join, under "the state"
below: the bench parks the jaw above travel height between actions, the
reading clips that to the top of the model's range, and SmolVLA emits absolute
targets near the state it is given. That part is measured there and it is
about 60 mm — real, but not enough to account for the gap. The rest is simply
that the model does not produce table-level motion on these pictures.

**What this does and does not establish.** It establishes that SmolVLA, taken
as it downloads, with nothing fitted, is not usable on this cell — and it
gives solution 6 all the range it could want. It does not establish anything
about vision-language-action models in general, for the reason the document
sets out at length: the instruction is constant, the pictures are nothing like
the model's training pictures, and, as it turns out, the action space has no
units until somebody supplies them.

### The sensitivity check

The one convention the checkpoint does not settle is which way each slot runs.
`make sensitivity` turns the height slot over — one evaluation run, 50 tables,
`results.json` untouched — so that a reader can see how much of the result
hangs on a bit nothing could read off the weights.

**Very little hangs on it.** Turned over, the trajectories come back *higher*
rather than lower, so the jaw's median lowest point rises by about 40 mm and
gets further from the glasses rather than nearer. The score hardly moves: the
same number of glasses racked, no table finished either way, and fewer glasses
toppled, which follows from the jaw spending even more of its time above
everything. So the convention nothing could read off the weights is not what
makes this solution fail. The state being pinned at one end of its range is,
and it is pinned at one end whichever way the slot runs.

## The join, which is the whole of the work here

Nothing in this solution is fitted, so there is no training to describe. What
there is instead is the join between a model fitted on somebody else's arm and
a jaw on this table, and it turned out to carry far more weight than the
document expected. All of it is in `joining.py`, written down once so that
[solution 6](../../docs/03-push-glasses-apart/solutions/06-smolvla-fine-tuned.md)
can hold it still.

Everything below was read off the checkpoint, not assumed.

### What the model's action space really is

`lerobot/smolvla_base` declares `action` of shape 6 and `observation.state` of
shape 6, both normalised `MEAN_STD`, and emits a chunk of 50 actions per
answer. The statistics shipped with it are three sets of means and spreads
named `so100`, `so100-blue` and `so100-red`, with means like
`[1.6, 119.9, 109.8, 56.7, -27.4, 12.0]`. Those are **SO-100 joint angles in
degrees** — a desktop follower arm's five joints and its gripper. They are
not a UR5e's joints, and they are not Cartesian anything.

### And the shipped statistics do not apply themselves

This is the first surprise, and it decides the shape of everything after it.
The statistics are saved under keys like `so100.buffer.action.mean`, while
LeRobot's normaliser looks up `action` and `observation.state`. A key it
cannot find is passed through unchanged. So with the released checkpoint and
LeRobot 0.6.1, **both the normaliser and the un-normaliser are no-ops**: the
state goes in as a z-score and the actions come out as z-scores, and which of
the three arms to un-normalise against is left to whoever uses it.

Picking one of them would only compose a fixed affine map onto whatever
follows, so this solution works in the normalised space the model really
speaks, and says what one standard deviation is worth here.

### The four slots, and which is which

Four of the six slots are used, chosen by what the joint does on the arm the
statistics came from:

| slot | SO-100 joint | read here as |
|---|---|---|
| 0 | shoulder pan | the jaw's x, across the bench |
| 1 | shoulder lift | the jaw's y, out and back |
| 2 | elbow flex | the jaw's height |
| 4 | wrist roll | the jaw's heading |

Slots 3 (wrist flex) and 5 (gripper) are dropped, because the bench holds the
jaw level and closed and offers no way to change either. A test checks that
changing them changes nothing.

### What one standard deviation is worth, and why position and speed are one choice

A z-score is not a length, so something has to set the scale. Only one object
in this solution has both a metric extent and is seen by the model: the frame
of the straight-down picture. So **two standard deviations span that frame
exactly**, which is the reading that lets the model put the jaw anywhere it
can see and nowhere it cannot. That is the one property a join has to have if
the score is to be about the model rather than about the join.

It has a price worth naming. The bench consumes waypoints a fixed period
apart, so how far apart they are *is* how fast the jaw goes, up to the arm's
own top speed, past which the jaw simply cannot keep up and the step takes
longer. Fixing the box
therefore fixes the speed, and the two cannot be chosen separately. The
measured consequence is in the results above: the model's waypoints land far
enough apart to ask for several times the arm's own speed, where the bench's
push macro moves at a tenth of what the arm can do.

Nothing here clips the speed to something gentler, because a gentler limit
would be a number chosen to make this solution look better, and this solution
fits nothing. The bench does hold the path to the fastest the cell ever moves
the jaw, which is a different thing: it is a limit the arm already has, it
applies to every solution equally, and it never binds on a path the bench
itself produces.

### The one convention the checkpoint does not settle

A joint angle's sign is a convention of the arm it was recorded on. The
checkpoint carries a mean and a spread for each slot but nothing that says
which way the joint turns, and this repository has no SO-100 model to read it
from. So the direction of each slot had to be decided: **larger is further
along the cell's own axis**, and on the height slot that means larger is
higher.

`make sensitivity` turns the height slot over and reports what changes, so
that a reader is not asked to take the convention on trust. Measured, it
changes very little, for the reason given under "the state" below: whichever
way the slot runs, the state the model is given sits at one end of it. The
numbers are in the results above. The scored result is always the declared
convention, and nothing here was chosen by which way scored better.

### The state, which no statistics describe and which barely varies

The checkpoint ships **no statistics for `observation.state` at all**, only
for `action`, so there is nothing that says what scale the state input
expects. Filling it with the jaw's own pose under the same reading the
actions are read with is the only self-consistent answer available, and that
is what `joining.to_state` does.

Two things then follow from the cell, not from the model.

The bench parks the jaw at one spot between actions and lifts it there after
every chunk, so at the moment the policy is asked the jaw is always in the
same place: out of the picture's frame and above travel height. Three of the
four slots are therefore **the same number at every ask on every table**, and
only the heading slot varies, carrying the heading the last chunk ended on.
The document argues at length that the language input carries no information
in a single-task cell. The state input turns out to be nearly as idle, and for
a different reason.

And the parked pose is outside the box the reading can express, so it clips
to the edge: the model is told the jaw is as high as it goes. SmolVLA emits
absolute targets and stays near the state it is given, so it answers high.

That is part of the explanation of the result above but not all of it, and the
difference is worth measuring. Asked the same picture six times with the
parked jaw's state, the chunks' lowest point has a median of 182 mm; asked
with an all-zero state, 122 mm. So the state does raise the answers, by about
60 mm. But 122 mm is still far above the 50 mm the jaw rides at and above most
of a glass, so **even the most favourable state this reading can express does
not get the model to produce low, table-level motion on these pictures.**
Turning the height slot over does not help either, for the same reason: the
state sits at one end of the slot whichever way it runs.

The honest position is therefore that the clipped, constant state makes a poor
result worse, and that no state available here would make it good. A join that
invented a lower state would be measuring itself rather than the model.

### One camera of three

The checkpoint declares three cameras and sets `empty_cameras` to 0, which
means a camera missing from the batch is left out rather than padded with a
blank. This cell has one straight-down view, so it fills `camera1` and the
other two are absent. The picture wants float 0 to 1, red-green-blue,
channels first; `top_view` already gives RGB, so unlike `film.py` nothing is
flipped.

### The glass, the aim, and the budget

`Chunk` wants a glass and an aim beside the waypoints, and the model was asked
for neither. So both are read back off the path afterwards, for the record
only: the glass is the one the jaw comes nearest to while low enough to touch
it, and the aim is where the path ends. Nothing is planned with either.

The shared budget needed one decision. `PUSHES_PER_TABLE` counts pushes and
is what makes the six comparable, so a trajectory thrown away before it is
carried out is not charged to it. `PUSHES_PER_GLASS` cannot bind the way it
binds elsewhere: the other solutions choose a glass and can be told to leave a
worn one alone, while here the glass is bookkeeping the model never emitted,
so throwing an answer away on that label would block the model for the rest of
the table on a word it never said. It is applied where it can honestly bite —
a table is finished once every glass still on it has been refused for tipping
or had its share — and `ASKS_PER_TABLE`, three answers per push in the budget,
is a guard against a loop rather than a budget.

## Where the document and the code disagreed

Reported rather than quietly resolved, as the house rules ask.

1. **There is no shared machinery for the topple refusal.** The document says
   the check is "applied by the shared machinery on the measurements" and that
   the trajectory guards "belong with the bench, beside the refusal". The
   bench has neither. The refusal arithmetic lives in
   `01-one-fixed-nudge/plan.py` as `slides`, which this solution imports the
   way solution 2 does, so all six refuse the same glasses; the trajectory
   guards had to be written here, in `clear.py` and `joining.py`. Solution 6
   should import them from this folder rather than write them again. The
   document has been corrected to say so.
2. **The actions do not arrive in "somebody else's units" so much as in no
   units at all.** The document expects a layout-and-units problem. The real
   problem is that the released checkpoint's normalisation is inert, so the
   numbers are dimensionless, and the scale had to be invented rather than
   converted.
3. **The document says the model has three inputs and that the third is the
   arm's joint readings, which is true but nearly empty here.** It does not
   anticipate that the state channel has no statistics, that the bench parks
   the jaw so the state hardly varies, or that the state is what decides how
   high the answers come back.
4. **The force channel is closed, as the document says.** `follow()` reports
   the same `Felt` a push does, so the force reading exists in the record;
   there is simply no input slot to put it in. That matches the document
   exactly.
5. **The predicted failure is not the measured one.** The document expects
   "confident, plausible, wrong actions" — well-formed pushes aimed at the
   wrong glass — and warns that nothing downstream will look suspicious. The
   measured failure is blunter and easier to see: about nine pushes in ten
   never touch a glass at all, and the ones that do are moving as fast as the
   arm can go, which is ten times a push macro's speed. The document's
   reasoning about the domain gap stands; its guess about which way the gap
   would show does not.

## Stale sentences fixed in the document

The document was written before the bench grew the parts this solution needs,
and before it ran. These were wrong and are now corrected: that nothing in
this solution is built; that the straight-down view "is a design rather than
code" and "is not even built yet"; that the waypoint path is "specified and
not yet written"; that the interpretation of the actions is "a design decision
recorded here, not code that exists"; that the trajectory guards are "a design
decision rather than existing code"; that the bench "still has to grow" two
things; and five places that called the glasses grey, which are pale blue on a
tan table and all one colour.

## What it costs

- **Setup.** A download, and nothing else. No demonstrations, no labels, no
  training run, no weights file to keep in step with the cell. This is the
  cheapest solution in the folder to set up, exactly as the document claims.
- **Hardware.** A laptop. Metal is used if it is there; `--device cpu` works
  and is about ten times slower per answer.
- **Time.** See the compute column in the results. The forward pass dominates
  everything else this solution does.

## Tests

`make test` runs this folder's 23 checks, and the bench's beside them. None of
them needs a download, a network or an accelerator. They cover the reading's
arithmetic in both directions, that anything the model can emit comes back as
a chunk the bench will accept, that the two unused slots change nothing, that
turning the height slot over mirrors only the height, that a path reaching a
glass refused for tipping is never carried out, that the budgets bind, and
that the picture is checked before any weights are touched. The model itself
is stood in for by a class that answers instantly with a path the test chose,
and the glasses the tests use are drawn with `family`, not written down.
