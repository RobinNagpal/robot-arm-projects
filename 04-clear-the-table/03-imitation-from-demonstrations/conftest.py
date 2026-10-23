"""Put problem 4's examiner on the path before the tests in this folder are imported.

The same file solution 1 keeps, for the same reason, and the reason is
mechanical rather than interesting. Problem 4's own environment puts the examiner
on the path in ``pixi.toml``, so nothing is needed when the tests are run from
``04-clear-the-table``. This is for the other way of running them, from problem
3's folder, whose environment has everything these tests need.

pytest adds the folder a test file sits in, which is this one, and not the
`examiner/` folder beside it; and ``pixi run`` *replaces* ``PYTHONPATH`` with the one in its
own ``pixi.toml`` rather than adding to it, so a ``PYTHONPATH`` set on the
command line in front of ``pixi run`` never reaches Python.

This folder's name starts with a digit, so it can never be a package, and a
``conftest.py`` is the only thing pytest will load from it before the tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

EXAMINER = Path(__file__).resolve().parent.parent / "examiner"
WORK_CELL = Path(__file__).resolve().parent.parent / "work-cell"

for folder in (EXAMINER, WORK_CELL):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
