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

**Project folders** are the version, then two or three words for what the
project does, in the same style: `v2-assemble-table`, `v3-turn-top-flat`.

**Code files follow their own language's rule, not this one.** Python files
use underscores, as in `joint_torques.py`, because a hyphen is not allowed in
a Python module name and the file could not be imported.

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
