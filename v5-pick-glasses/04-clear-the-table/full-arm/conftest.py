"""Put the full-arm folder, problem 4's bench and the cell's package on the path for these tests.

``pixi.toml`` does the same for ``pixi run``; this is for pytest started anywhere else.
The folder name has a hyphen, so it can never be a package.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBLEM = HERE.parent
for folder in (
    HERE,
    PROBLEM / "bench",
    PROBLEM.parent / "src" / "work_cell",
    PROBLEM.parent / "03-push-glasses-apart" / "bench",
):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
