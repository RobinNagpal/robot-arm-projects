"""Make SmolVLA's training set from files of pushes.

``python make_smolvla_training_data.py PUSHES.jsonl [MORE.jsonl ...] OUT.pkl``
"""

from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import smolvla_fine_tuned

from shared.learning import table_and_push_encoding as F

if __name__ == "__main__":
    records = F.load_records(*sys.argv[1:-1])
    started = time.perf_counter()
    data = smolvla_fine_tuned.samples(records)
    with open(Path(sys.argv[-1]), "wb") as handle:
        pickle.dump(data, handle)
    print(f"{len(data)} samples from {len(records)} pushes in {time.perf_counter() - started:.0f} s")
