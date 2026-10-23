# CLAUDE.md

This repo holds several robot arm projects, one per folder. Each working
project has its own `CLAUDE.md` with its own rules; this file holds the rules
that apply to all of them.

## Naming

**Doc files are lowercase words joined by hyphens.** For example
`implementation-notes.md`, `one-joint-or-many.md`, `problem-statement.md`.
No capitals, no underscores, no spaces. This goes for every new doc, and for
a doc that is renamed.

Two exceptions, because tools look for them by their exact names:

- `README.md` — GitHub shows it on each folder's page.
- `CLAUDE.md` — Claude Code reads it.

**Project folders** are a two-digit number, then two or three words for what
the project does, in the same style: `01-rack-one-glass`, `04-clear-the-table`.
A folder inside a project that holds one solution follows the same pattern, as
in `02-geometry-ranked`.

**Code files follow their own language's rule, not this one.** Python files
use underscores, as in `joint_torques.py`, because a hyphen is not allowed in
a Python module name and the file could not be imported.

## Each folder stands alone

**No folder imports code from another folder.** Nor does it read another
folder's environment, configuration or data while it runs. When a problem
builds on an earlier one, copy the files it needs into its own folder, as
`work-cell/` and `from-problem-3/` do, and keep the copy exactly as the
original. A document may still link to a document in another folder.

Copy only what the later problem needs. When a file holds both what two
problems share and what belongs to the earlier one alone, split it in the
earlier problem's folder first: a `common_` file with the shared part, and the
earlier problem's own file, whose classes extend the common ones and which
passes on the common names. Then the later problem copies only the `common_`
file and extends it with its own. Problem 3's `bench/` is split this way, and
problem 4's `examiner/simulation/table_simulator.py` extends the copy of `common_bench.py`.

## The glass problems, 01 to 06

The first six folders are one task taken apart into six problems. Read
[`01-rack-one-glass/CLAUDE.md`](01-rack-one-glass/CLAUDE.md) before changing
any of them: its rules about glasses — no glass's size written down anywhere,
a refused glass is a result, the last millimetres are felt — apply to all six.

## Diagrams

- Give each concept its own diagram, and check it by rendering it and looking at
  it. Overlapping labels and lines passing through obstacles are the usual
  faults, and the write succeeds either way.
- A diagram must illustrate one specific idea from its own document. A reusable
  box-and-arrow chart is not acceptable.
- **One picture shows one thing.** Do not put two or three separate ideas side by
  side in one image. Two panels belong together only when they are the same thing
  seen differently: the same scene from two camera positions, or the same picture
  with two different measurements marked on it. Anything else is two pictures.
- **Never put two flow charts in one image.** A flow chart is a whole argument on
  its own, and a second one beside it halves the size of both.
- **Keep the text in a picture short.** A picture crowded with sentences is harder
  to read than the paragraph it was meant to replace. Put the explanation in the
  prose under the picture and leave the picture to carry the shape of the idea.
  If a label needs more than a line or two, the picture is doing the prose's job.
- Verify every number on a diagram against real output before writing it down.
