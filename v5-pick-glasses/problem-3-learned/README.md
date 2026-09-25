# Problem 3 — the learned way

Glasses stand too close together to be picked up. Push them apart, then pick
each one up. Here a model learns what a push will do from pushes made in a
physics engine, and a search picks the next push using that model. This is
solution 10 in [the overview](../docs/problem-3/solution-overview.md).

It is "pure" learning: no tipping formula, no friction value, no rule about
where the jaw fits. Whether a push slides a glass, topples something, or gets
blocked on the way down is only what the model has seen happen.

## The workflow

```
1. look ──▶ take every glass with room
2. for every glass still crowded: search pushes ──model──▶ best push
3. make that one push ──▶ look again ──▶ back to 1
   no push expected to help ──▶ refuse the rest, with the reason
```

**The model.** A small network (3 layers of 256), trained 5 times from
different starts.
- In: the table's kind; the pushed glass's height, widest width and foot
  width; the push (how far across the glass the jaw meets it, and how far it
  pushes); and where every other glass stands and how big it is. All of it is
  in the push's own frame, so a push north and the same push east are one
  example.
- Out: where the pushed glass moves, where each other glass moves, the chance
  something topples, and the chance the jaw is blocked on the way down.

**Training.** Two rounds, all labelled from the camera's own readings
(`look()` before and after), not from the simulator's record.
- Round 1: 24,759 random pushes on 4,000 tables.
- Round 2: 13,253 pushes on 5,000 new tables, mostly chosen by the planner
  using the round 1 model. The planner finds the pushes where the model is
  wrong in its favour. Making those pushes and recording what really happened
  fills exactly those holes.
- Every push is also used mirrored left to right, which is still a true push.

**Choosing a push.** For each crowded glass, the cross-entropy method (CEM)
searches over heading, where across the glass to push, and how far. A push is
dropped if:
- any of the 5 copies gives it more than a 1% chance of toppling something,
  on the table as seen or on 4 copies moved by the camera's error;
- a glass it moves lands outside the glass zone, or the jaw leaves the arm's
  reach. This map is the only thing written down;
- the model predicts a move longer than the push itself. That is the model
  guessing outside what it has seen.

The rest are scored by how much room is still missing on the table
afterwards, plus a small cost per millimetre pushed. The best push over all
glasses is made. Then the arm looks again and plans afresh. The model is
never asked more than one push ahead.

## Running it

```
make collect           # round 1: random pushes, about 5 minutes
make train             # about 5 minutes
make collect-planned   # round 2: the planner's own pushes, about 20 minutes
make train             # again, on both rounds
make run               # the 50 held-out tables; writes results.json
make film              # videos of the first 3 held-out tables, in videos/
make test
```

`make film FILM=10` films more. A video shows the table from the arm's side,
with what the arm is doing written on it, and ends on the table's outcome.
Any run shorter than the 50 held-out tables writes `partial.json`, never
`results.json`.

Training took 31 minutes in total on a laptop CPU. The planner's two settings
(the 1% topple limit, and taking a glass with 3 mm of room to spare) were
chosen on tables 9500 on, which are neither trained on nor held out:
`pixi run python run.py --first 9500`.

## Results — 50 held-out tables, 251 glasses

| | Result |
|---|---|
| Tables | done 34, incomplete 16, wrong 0 |
| Glasses | racked 208, refused 43, toppled 0 |
| Pushes | 113 (15 repeats); 4 blocked on the way down, 1 never touched, 1 jammed |
| Landing | 1.7 mm from where the model aimed it, median; 24.8 mm worst |
| Model, on unseen tables | pushed glass lands 4.5 mm from its prediction, median; blocked guessed right 96% of the time |

**Toppling is the weak point, even though none happened here.** On 100 tuning
tables the same settings toppled 1 glass. The model rated every topple it
missed as safe:
- the jaw met a stemmed glass's stem under the bowl, then lifted and tipped it;
- the jaw's 90 mm body clipped a neighbour behind;
- a tapered glass tipped on its own.

A lower topple limit does not remove these; it only refuses more. They need
more examples than 40 minutes of pushing gives.

The tables, the physics and the scoring are in `../problem-3-sim`, shared with
`../problem-3-programmed`, so both approaches are tested on the same tables.
