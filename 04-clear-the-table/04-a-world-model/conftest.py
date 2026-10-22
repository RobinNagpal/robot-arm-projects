"""Put problem 4's bench on the path before the tests in this folder are imported.

Problem 4's own environment does this in ``pixi.toml``, so nothing is needed
when the tests are run from ``04-clear-the-table``. This file is for pytest
started some other way, outside that environment.

It is needed there because of how pytest and pixi each handle a path. pytest
adds the folder a test file sits in, which is this one, and not the bench
beside it; and ``pixi run`` *replaces* ``PYTHONPATH`` with the one in its own
``pixi.toml`` rather than adding to it, so a ``PYTHONPATH`` set on the command
line in front of ``pixi run`` never reaches Python. The bench's own tests do
not notice either of those, because they sit in the folder they import from.

This folder's name starts with a digit, so it can never be a package, and a
``conftest.py`` is the only thing pytest will load from it before the tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "bench"
WORK_CELL = Path(__file__).resolve().parent.parent / "work-cell"

for folder in (BENCH, WORK_CELL):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
