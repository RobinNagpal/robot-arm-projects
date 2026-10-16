# Plan — the six solutions for problem 3

Short notes only. Each line is a decision. The documents hold the reasoning.

## The destination, the same for all six

Every glass has the clear room it needs, at least one usable side-on viewpoint,
and nothing has been knocked over. [The problem](problem.md#what-done-means)
defines this.

## The comparability contract

All six get the same input, give the same kind of output, and are marked by the
same scorecard. The score looks at the table afterwards, not at the action.
[The examiner](the-examiner.md) sets out each part.

## The six

The six, with their models and frameworks, are listed in
[the overview](solutions/overview.md#the-seven-in-one-table). Three of them
carry a second way, listed there too.

## Why these and not others

**Model-free reinforcement learning is left out.** LeRobot's entry for it is
HIL-SERL. HIL-SERL is built around human corrections on a real robot, so it
fits a pure simulator badly. TD-MPC2 already stands for the reinforcement
learning family, on its model-based side.

**π0 full fine-tuning and GR00T N1.7 are left out** as too expensive. A full
fine-tune of π0 needs more than 70 GB of accelerator memory. π0.5 appears only
as a second way, through low-rank adaptation, which is affordable.

**Solution 2 is the teacher.** Solutions 3 and 6 need demonstrations, and
solution 2's ranked pushes supply them at no cost. That earns solution 2 its
place beyond being a baseline.

## What each comparison isolates

[The overview](solutions/overview.md#what-each-comparison-isolates) has the
table of questions and the pairs that answer them.

## Three shared documents, not cars

- [**The examiner**](the-examiner.md): the crowded tables, `look()`, `push()`,
  `take()` and the scorecard. Problem 5 imports it.
- [**The target layout**](the-target-layout.md): where the glasses should end
  up, computed rather than learned. It also gives the **displacement floor**,
  the least movement the task needs.
- [**Pushing without toppling**](pushing-without-toppling.md): how low a push
  must be, the refusal path, and the loop of plan, feel and look again.

## The examiner had to grow before cars 3 to 6 could run

Four parts of the contract were missing. Every solution that reads pictures or
gives waypoints needed them. All four are now built.

| What was needed | What the examiner has |
|---|---|
| a straight-down rendered view | a fixed camera above the middle of the glass zone, looking straight down |
| a waypoint action path | `follow()` takes a chunk of jaw waypoints and reports what `push()` reports |
| one shared push budget | the budget belongs to the examiner, and every runner reads it from there |
| repeats and a compute column | several evaluation runs with their spread, and the thinking time per push |

The first two were the real cost of using models off the shelf. Every LeRobot
policy expects pictures and an action at control rate. Solutions 1 and 2 need
neither, which is one reason they were built first.

Building them gave one more thing. The examiner now records the path the jaw
really followed on **every** action, including an ordinary push. Replaying
that path gives the same push again. So the solutions that learn from
demonstrations can learn from the two solutions that already work.

## The scorecard needs two things problem 2's did not

Repeats with a spread, and the thinking time per push.
[The examiner](the-examiner.md#two-things-this-scorecard-needs-that-problem-2s-did-not)
explains both.

## Rented compute is allowed

The old rule was that everything must run on this machine, which has no NVIDIA
card. Problem 3 lifts that rule. Each solution states what it needs and roughly
what renting it costs, the same way it states its licence.

## Code: what goes, what stays

| Folder | Holds | Decision |
|---|---|---|
| `03-push-glasses-apart/bench` | the examiner; problem 5 imports it | keep, rename |
| `03-push-glasses-apart/01-one-fixed-nudge` | the geometry cars 1 and 2 need | keep |
| `03-push-glasses-apart/04-a-world-model` | car 4's first way, already written | keep |
| `03-push-glasses-apart/results` | the two approaches compared; problem 5 cites it | keep |

The eleven old solution documents became six. No code was replaced, so only
documents and orphaned diagrams were deleted.

## Naming

| Old | New |
|---|---|
| `docs/03-push-glasses-apart/` | `docs/03-push-glasses-apart/` |
| `images/03-push-glasses-apart/` | `images/03-push-glasses-apart/` |
| `images/generators/03-push-glasses-apart/` | `images/generators/03-push-glasses-apart/` |

## One measurement nobody can settle from the repository

Two old results documents disagree about the tuning sweep. One says the
learned side toppled one glass on those hundred tables, then lists three
different causes. The other says it toppled two. Nothing settles it. The
committed scorecards cover only the fifty held-out tables, where nothing
toppled. Running the sweep again needs a trained model that is not in git.

So no document here gives a count for it. Both sources agree on the part that
matters: **the model had rated every topple it missed as safe**.

## Milestones

1. Plan, naming, dependencies. **Check:** problem 5 still imports the examiner.
2. Rename documents and images. **Check:** links resolve, tests pass.
3. `problem.md`, `the-examiner.md`, and the two other shared documents.
4. The six solution documents, by agents.
5. Reviewers, cross-checking claims about siblings.
6. Diagrams: remap what exists, draw the gaps.
7. Delete superseded documents and dead diagram code. **Check:** nothing
   orphaned after regenerating every generator.
