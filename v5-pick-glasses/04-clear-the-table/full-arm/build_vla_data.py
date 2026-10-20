"""Make SmolVLA's training set from files of pushes.

``python build_vla_data.py PUSHES.jsonl [MORE.jsonl ...] OUT.pkl``
"""

from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import features as F
import vla

if __name__ == "__main__":
    records = F.load_records(*sys.argv[1:-1])
    started = time.perf_counter()
    data = vla.samples(records)
    with open(Path(sys.argv[-1]), "wb") as handle:
        pickle.dump(data, handle)
    print(f"{len(data)} samples from {len(records)} pushes in {time.perf_counter() - started:.0f} s")
