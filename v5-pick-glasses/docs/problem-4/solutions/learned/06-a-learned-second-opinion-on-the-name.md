# Solution 6 — a learned second opinion on the name

*Hybrid, with the model as a verifier. The rules name the glass, as today. A
small model trained on generated glasses names it too, from the same profile,
and is also allowed to say "this profile is not to be trusted". When the two
disagree, the arm takes another look, and refuses the glass if they still
disagree. The model can cost a look. It cannot choose a grip.*

> **The cell is described once, in [the cell](../../../the-cell.md).** [The
> problem](../../problem.md) says what is asked for, and the [solution
> overview](../solution-overview.md) says where the numbers come from. What
> follows is only what is specific to this solution.

## Introduction

[Problem 1's step
3](../../../problem-1/step3-what-kind-of-glass.md#other-ways-to-decide-what-kind-of-glass-it-is)
weighs up a learned classifier against the three written questions and chooses
the questions. That argument was about a model that **decides** the name. This
solution asks a different question: is a model worth having as a **second
opinion**, where its mistakes are bounded?

It was built as a small experiment, trained and tested on generated glasses,
and the answer in the simulator is: not yet.

## The problem this solves

[Solution 2](../programmed/02-a-name-that-shows-its-evidence.md) handles the confident
mistakes that were thought of: a notch that looks like a stem is too short to
be one. But that rule exists because somebody imagined a reflection cutting a
notch. A real camera on real glass makes other artefacts — a highlight that
widens the outline, a label, a drop of water — and each would need its own
rule, written after it had already caused a mistake.

A model trained on examples of "a profile that is wrong somehow" might catch
artefacts nobody wrote a rule for. That is the case for it.

## Where the model sits

![Where the learned part sits decides what happens when it is wrong](../../../../images/where-the-learned-part-sits.png)

As a **verifier**. The rules act; the model checks.

```text
name  = classify(profile)                          the rules, as in solution 2
check = the model's answer on the same profile     one of the four kinds, or "not to be trusted"
if check agrees with name: carry on
else: take the second view at 90°, measure again, ask both again
      still disagree: refuse the glass, and report both answers
```

What each kind of mistake costs:

- **The model disagrees with a right name.** One extra side view. If the second
  view settles it, nothing else. If not, a glass is refused that could have
  been racked.
- **The model agrees with a wrong name.** Nothing is lost compared with having
  no model: the name was wrong without it too, and [solution
  3](../programmed/03-let-the-fingers-check-the-name.md)'s checks still come after.

The model never names a glass on its own, never chooses a grip, and never sets
a force. That is what keeps its mistakes to a look or a refusal.

## What the model is shown

The profile, made free of size:

- the width at 32 heights, evenly spaced from the foot to the rim, as fractions
  of the glass's own height;
- each width divided by the glass's widest.

So a 100 mm tumbler and a 200 mm one give the same input. This is the same rule
as everywhere else in the project, applied to a model's input: no glass's size
goes in, only its shape.

## The experiment

A logistic regression, the simplest classifier there is, in NumPy. Five
answers: the four kinds, and **artefact**.

**Training.** 200 glasses of each kind from `family(kind, 200, seed=41)`,
measured through masks drawn at the cell's side view scale with the top
stretched 6 to 10 mm. Plus 400 straight and tapered glasses with a notch drawn
in: 6 to 10 mm tall, 20% to 60% of the width, at 15% to 45% of the height. Those
are labelled artefact. Training takes a few seconds on a laptop.

**Testing.** The same again from seed 99, which the model never saw.

| Made as | named by the model |
| --- | --- |
| straight | 199 straight, 1 artefact |
| tapered | 200 tapered |
| stemmed | 200 stemmed |
| short-stemmed | 200 short-stemmed |
| straight or tapered, with a notch | 367 artefact, 20 straight, 13 tapered |

On the 800 clean glasses it agrees with the rules on 799. On the notched
glasses the rules named a stem — 348 of the 400 — it says artefact on 323,
93%.

### Against the rule it would sit beside

[Solution 2's](../programmed/02-a-name-that-shows-its-evidence.md#a-stem-has-to-be-long-enough-to-be-a-stem)
stem-length rule rejects every one of those notches. On a fresh draw of the same
notched glasses, the longest notch run was 0.082 of the glass's height, and the
rule asks for 0.12. It raises no false alarms on the clean glasses either: the
shortest real stem is 0.154.

So on the one artefact the simulator can be made to produce, the written rule
is better than the model, and it can say why it refused.

## Why it still belongs on the list

The model did not lose because learning is worse. It lost because the test is
unfair to it in a particular way. **The only artefact it could be shown is one
somebody drew**, and once somebody has drawn it, they can write a rule for it.

A model earns its place when there are examples of failures nobody has
described. That needs real pictures of real glasses, with the profiles that
went wrong marked. The simulator's glasses are opaque and make no reflections,
so it cannot produce them. This is the same position [problem 2's learned
models](../../../../problem-2-results/README.md#what-the-comparison-says) ended in:
where the answer can be worked out exactly, working it out beats learning it,
and learning pays when the rule cannot be written.

## What it needs

- A training set of profiles. Generated glasses give the four kinds. Artefacts
  come from real pictures, when there are some.
- A model small enough to read. A logistic regression over 32 numbers has 33
  weights per answer, 165 in all, and can be plotted.
- The second view at 90°, which `task.py` already takes for short-stemmed
  glasses.
- A test on a held-out family that the model agrees with the rules on clean
  glasses, so that it does not cost a look on every run.

## Where it is strong and where it breaks

**Strong.** Its mistakes are bounded by where it sits: at worst, a look and a
refusal. It is cheap to train and cheap to run. And it is the only thing on
this list that could catch an artefact nobody has described.

**Breaks.**

- **In the simulator it only learns what was drawn for it**, and the written
  rule does that better.
- **Its artefact class is only as wide as its examples.** A model trained on
  notches knows notches. It says nothing about a highlight that widens a glass.
- **A disagreement costs an arm move.** The 1 false alarm in 800 clean glasses
  is cheap. On real pictures, the rate is unknown.
- **It cannot explain a refusal.** "The model and the rules disagreed twice" is
  honest, and nobody can check it with a ruler.

## Where the idea comes from

**Verifiers and cascades.** A cheap check that runs after an answer is produced
and can only stop it, not change it. [Problem 2's solution
5](../../../problem-2/solutions/learned/05-is-anything-hiding-there.md#verifiers-and-cascades--a-cheap-exact-test-first)
and [problem 3's solution
7](../../../problem-3/solutions/07-a-learned-change-verifier.md) use the same
position.

**Out-of-distribution detection.** Training a model to say "this is not like
anything I was trained on" is a field of its own, and it is known to be hard:
a model is only good at spotting unfamiliar inputs that resemble the unfamiliar
examples it was shown. The artefact class here is the simplest version.

**Classification with a reject option.** As in [solution
2](../programmed/02-a-name-that-shows-its-evidence.md#where-the-idea-comes-from).

## Where it sits among the other solutions

It sits in front of [solution 3](../programmed/03-let-the-fingers-check-the-name.md) and
beside [solution 2](../programmed/02-a-name-that-shows-its-evidence.md), as their learned
version. It is the first thing to add once there are real pictures, and it is
not in the recommended combination until then.

← [Solution 5 — measure before you push](../programmed/05-measure-before-you-push.md) · [Solution 7 — guess the kind from above](07-guess-the-kind-from-above.md) →
