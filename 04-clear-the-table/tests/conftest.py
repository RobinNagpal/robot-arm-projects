"""Put the problem folder, the solution folders and the cell's package on the path for these tests.

``pixi.toml`` does the same for ``pixi run``; this is for pytest started anywhere else.
The problem folder is what makes ``examiner`` and ``shared`` importable as packages. Every
solution folder's name starts with a digit, so none of them can be a package, and their
modules are imported by their plain names.
"""

from __future__ import annotations

import sys
from pathlib import Path

THIS_FOLDER = Path(__file__).resolve().parent
PROBLEM = THIS_FOLDER.parent
for folder in (
    PROBLEM,
    PROBLEM / "01-geometry-reference",
    PROBLEM / "02-geometry-ranked",
    PROBLEM / "03-imitation",
    PROBLEM / "04-world-model",
    PROBLEM / "05-reinforcement-learning",
    PROBLEM / "06-smolvla-fine-tuned",
    PROBLEM / "work-cell",
    PROBLEM / "from-problem-3" / "bench",
):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
