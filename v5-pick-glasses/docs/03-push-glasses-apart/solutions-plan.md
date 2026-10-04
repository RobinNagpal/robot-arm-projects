# Plan — the six solutions for problem 3

Short notes only. Each line is a decision. The documents carry the reasoning.

## The destination, the same for all six

Every glass has the required clear room around it, at least one usable
side-on viewpoint, and nothing has been knocked over.

## The comparability contract

**Same input.** What `look()` hands over — where each glass stands, how tall,
how wide at its widest and at its foot, whether it is standing — carrying
problem 2's measured error. Plus a rendered top-down view of the same table,
for the cars that read pictures. No car reads the simulator's record.

**Same output.** A jaw trajectory. A car that thinks in parameterised pushes
emits one, and **the bench owns the macro that expands it into a trajectory**,
so the simple cars get no advantage and the policy cars are not crippled.

**Same yardstick.** One scorecard, plus the displacement floor from the target
layout.

**Score the outcome, not the action.** That is what lets a three-number push
and a chunk of waypoints be compared at all.

## The six

| # | Car | Model | Framework | Fitted here |
|---|---|---|---|---|
| 1 | One fixed nudge, then look again | none | NumPy, MoveIt | nothing |
| 2 | Geometry generates, a model ranks | gradient-boosted trees | scikit-learn | the ranker only |
| 3 | Imitation from demonstrations | ACT | LeRobot | everything |
| 4 | A world model, then plan with it | a small ensemble, then TD-MPC2 | PyTorch, LeRobot | everything |
| 5 | A foundation model as it downloads | SmolVLA | LeRobot | nothing |
| 6 | The same model, fine-tuned here | SmolVLA with LoRA | LeRobot | all of it |

Three carry a second rung:

- **3** — ACT predicts an action chunk directly; Diffusion Policy denoises
  towards one. Same job, different means, both in LeRobot.
- **4** — rung one is the small ensemble **already written** in this project;
  rung two is TD-MPC2 off the shelf.
- **6** — the same fine-tune on π0.5, to measure whether a markedly larger
  foundation model is worth it.

## Why these and not others

**Model-free reinforcement learning is left out.** LeRobot's entry is
HIL-SERL, which is built around human corrections on a real robot, so it is a
poor fit for a pure simulator. TD-MPC2 already represents the reinforcement
learning family, in its model-based half.

**π0 full fine-tuning and GR00T N1.7 are left out** as too expensive: π0's
full fine-tune floor is above 70 GB of accelerator memory. π0.5 appears only
as a rung, reached by low-rank adaptation, which is affordable.

**Car 2 is the teacher.** Cars 3 and 6 need demonstrations, and ranked
geometric pushes supply them for nothing. That is what earns car 2 its place
beyond being a baseline.

## What each comparison isolates

| Question | Compare |
|---|---|
| Does any learning beat a fixed nudge? | 1 against the rest |
| Is ranking hand-made candidates enough? | 2 against 3–6 |
| Hand-built world model, or one off the shelf? | inside 4 |
| Plan with a model, or learn the push directly? | 4 against 3 |
| **What does fine-tuning a foundation model buy?** | **5 against 6** |
| Does a much larger foundation model help? | inside 6 |

## Three shared documents, not cars

- **The bench** — the crowded tables, `look()`, `push()`, `take()`, the
  scorecard. It already exists and problem 4 imports it.
- **The target layout** — where the glasses should end up, computed rather
  than learned: discs of known foot width placed with the required clearance,
  minimising travel. Also the **displacement floor**, the least movement the
  task needs, which is the yardstick every car is read against.
- **Pushing without toppling** — how low the push has to be and why that is a
  property of the glass; the refusal path; and the loop of plan, feel and look
  again, with the learned change verifier and the learned early abort inside
  it.

## The scorecard needs two things problem 2's did not

**Repeats.** These policies are stochastic and training varies by seed, so one
run is not a measurement. Several training seeds, several evaluation runs,
report the spread.

**A compute column.** The fixed nudge costs nothing; TD-MPC2 plans at run
time; SmolVLA is a large forward pass. A car that wins while taking a hundred
times longer has not obviously won.

## Rented compute is allowed

The old rule was that everything must run on this machine, with no NVIDIA
card. That rule is lifted here. Each solution states what it needs and roughly
what renting it costs, the way the licence is stated — so a reader knows the
price of reproducing it.

## Code: what goes, what stays

| Folder | Holds | Decision |
|---|---|---|
| `problem-3-sim` | the bench; problem 4 imports it | keep, rename |
| `problem-3-programmed` | the geometry cars 1 and 2 need | keep |
| `problem-3-learned` | car 4's first rung, already written | keep |
| `problem-3-results` | the two approaches compared; problem 4 cites it | keep |

The eleven solution documents become six. Nothing in the code is superseded,
so the deletions are documents and any diagram left without a home.

## Naming

| Old | New |
|---|---|
| `docs/03-push-glasses-apart/` | `docs/03-push-glasses-apart/` |
| `images/03-push-glasses-apart/` | `images/03-push-glasses-apart/` |
| `images/generators/03-push-glasses-apart/` | `images/generators/03-push-glasses-apart/` |

## Milestones

1. Plan, naming, dependencies. **Check:** problem 4 still imports the bench.
2. Rename documents and images. **Check:** links resolve, tests pass.
3. `problem.md`, `the-bench.md`, and the two other shared documents.
4. The six solution documents, by agents.
5. Reviewers, cross-checking claims about siblings.
6. Diagrams: remap what exists, draw the gaps.
7. Delete superseded documents and dead diagram code. **Check:** nothing
   orphaned after regenerating every generator.
