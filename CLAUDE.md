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
