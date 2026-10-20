"""Solution 6 in the full-arm cell: SmolVLA, fitted a little, answering in MoveIt's terms.

SmolVLA is a model that reads pictures and a sentence and writes an action. It was
trained by others to move a small arm's joints. Here it is asked for something
else: not joint positions but **the decision** -- which glass to push, which way,
how far, and the six settings handed to MoveIt. MoveIt then makes the move.

**What it reads.** The two wrist pictures the arm takes at the start of each turn,
one in each of the model's first two camera slots, and one fixed sentence. It is
not given the boxes: those go to MoveIt, and the model has to work out from the
pictures where the glasses are and which are worth pushing.

**What it writes.** A chunk of fifty rows, as it always does, and every row holds
the same twelve numbers: whether to stop, where the glass is that it means to push
(two numbers), the push direction as a cosine and a sine, the distance, and the six
settings. The twelve are averaged over the rows. The cell then finds the box
nearest the point named and pushes that glass.

**What is fitted.** The model's own weights are never changed. A small low-rank
correction is added beside every attention projection, the way problem 3's solution
6 does it, and only that is trained. Fitting is on the pushes that worked, the
same demonstrations the imitation solution copies, so the two differ in what they
read -- pictures here, boxes there -- and in the size of the model, which is five
hundred times larger here.

**What the training cost is.** A few hundred steps at a batch of four on this
laptop's GPU, because that is what fits. The model it started from was trained on
millions of frames. Whatever this does should be read as "what a few hundred steps
of correction can move", and not as what the model could do.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import features as F
import numpy as np
import torch

from contract import Done

HERE = Path(__file__).resolve().parent
WEIGHTS_DIR = HERE / "weights"
MODEL = "lerobot/smolvla_base"
CAMERAS = ("observation.images.camera1", "observation.images.camera2")
INSTRUCTION = "Push the crowded glasses apart so each has room, without tipping any."
CHUNK = 50
# stop, glass x, glass y, cos, sin, travel, six settings
WIDTH = 12
RANK, SCALING = 16, 32
TABLES = ("q_proj", "k_proj", "v_proj", "o_proj")


def device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


def borrowed(where: str | None = None):
    """The downloaded model with nothing changed, and its own pre- and post-processing."""
    from lerobot.configs.types import FeatureType, PolicyFeature
    from lerobot.policies.factory import make_pre_post_processors
    from lerobot.policies.smolvla.configuration_smolvla import SmolVLAConfig
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

    where = where or device()
    config = SmolVLAConfig.from_pretrained(MODEL)
    config.device = where
    # The model was made for an arm with six numbers an action, and it reads that
    # off its configuration twice: it cuts its answer down to six, and it
    # measures its training loss on the first six only. Both would silently drop
    # the last six of the twelve numbers this solution asks for -- the settings
    # given to MoveIt would never be learned. So the configuration is told twelve.
    config.output_features["action"] = PolicyFeature(type=FeatureType.ACTION, shape=(WIDTH,))
    policy = SmolVLAPolicy.from_pretrained(MODEL, config=config).to(where)
    pre, post = make_pre_post_processors(
        config, MODEL, preprocessor_overrides={"device_processor": {"device": where}}
    )
    return policy, pre, post


def with_correction(policy):
    from peft import LoraConfig, get_peft_model

    policy.model = get_peft_model(
        policy.model,
        LoraConfig(r=RANK, lora_alpha=SCALING, lora_dropout=0.0, bias="none", target_modules=list(TABLES)),
    )
    return policy


# ---------------------------------------------------------------- the encoding


def answer_vector(boxes, glass: int | None, request) -> np.ndarray:
    """What the model is taught to write for a turn: twelve numbers, the same on every row."""
    if glass is None:
        return np.zeros(WIDTH, dtype=np.float32)
    b = boxes[glass]
    return np.concatenate(
        [[0.0, (b.x - F.CENTRE[0]) / 0.2, (b.y - F.CENTRE[1]) / 0.2], F.action_vector(request)]
    ).astype(np.float32)


def chunk_of(vector: np.ndarray) -> np.ndarray:
    return np.tile(vector, (CHUNK, 1))


def request_from(vector: np.ndarray, boxes) -> tuple[int | None, object]:
    """The model's twelve numbers back into a push, or None for "finished"."""
    if vector[0] > 0.5 or not boxes:
        return None, None
    x, y = F.CENTRE[0] + 0.2 * vector[1], F.CENTRE[1] + 0.2 * vector[2]
    glass = min(range(len(boxes)), key=lambda k: math.dist((boxes[k].x, boxes[k].y), (x, y)))
    return glass, F.request_from(glass, vector[3:])


# ------------------------------------------------------------------- the data


def render_pictures(records: list[dict]) -> list[tuple[np.ndarray, np.ndarray]]:
    """Both wrist pictures for the layout each record started from."""
    import arm_camera
    import build_box_data as B
    import mujoco
    from arm_bench import ArmBench
    from moveit_link import MESHES, generate_urdf

    import tables

    joints = B.view_joint_sets()
    out = []
    for r in records:
        bench = ArmBench(
            r["seed"], tables.table(r["seed"]), urdf=generate_urdf(), meshes=MESHES, start=joints[0]
        )
        for i, g in enumerate(r["before"]):
            address = bench.model.jnt_qposadr[bench.model.body_jntadr[bench.bodies[i]]]
            bench.data.qpos[address : address + 2] = [g["x"], g["y"]]
        bench.data.qvel[:] = 0.0
        mujoco.mj_forward(bench.model, bench.data)
        camera = arm_camera.ArmCamera(bench)
        pair = []
        for q in joints:
            bench.set_joints(q)
            pair.append(camera.view(bench.tcp()))
        camera.close()
        out.append(tuple(pair))
    return out


def samples(records: list[dict]) -> list[dict]:
    """The pictures and the answer for every push worth copying, and for every finished table."""
    import imitation

    demos, _ = imitation.demonstrations(records)
    keep = []
    for r in records:
        if all(g["pickable"] for g in r["before"]):
            keep.append((r, None, None))
            continue
        o = F.outcome(r)
        if (
            o["feasible"]
            and not o["topple"]
            and (o["gain"] >= 1 or (o["eased"] >= 4.0 and o["disturbed"] < 0.01 and o["moved"] > 0.01))
        ):
            keep.append((r, r["request"]["glass"], F.request_of(r)))
    pictures = render_pictures([k[0] for k in keep])
    return [
        {"pictures": pics, "action": chunk_of(answer_vector(F.boxes_of(r["before"]), glass, request))}
        for (r, glass, request), pics in zip(keep, pictures, strict=True)
    ]


def item(sample: dict) -> dict:
    return {
        CAMERAS[0]: torch.from_numpy(sample["pictures"][0].copy()).permute(2, 0, 1).float() / 255.0,
        CAMERAS[1]: torch.from_numpy(sample["pictures"][1].copy()).permute(2, 0, 1).float() / 255.0,
        "observation.state": torch.zeros(6),
        "action": torch.from_numpy(sample["action"]).float(),
        "task": INSTRUCTION,
    }


def ready(items: list[dict], pre) -> dict:
    each = [pre(one) for one in items]
    joined = {
        key: torch.cat([one[key] for one in each], dim=0)
        for key in (*CAMERAS, "observation.state", "observation.language.tokens")
    }
    joined["observation.language.attention_mask"] = torch.cat(
        [one["observation.language.attention_mask"] for one in each], dim=0
    ).bool()
    joined["action"] = torch.stack([one["action"] for one in each])
    return joined


def rate(step: int, steps: int, top: float, warmup: int = 50) -> float:
    if step < warmup:
        return top * (step + 1) / warmup
    through = (step - warmup) / max(1, steps - warmup)
    return top * 0.5 * (1 + math.cos(math.pi * through))


def train(
    data: list[dict],
    steps: int,
    batch: int = 4,
    lr: float = 1e-4,
    seed: int = 0,
    into: Path | None = None,
    log=lambda *a: print(*a, flush=True),
) -> Path:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    where = device()
    policy, pre, post = borrowed(where)
    policy = with_correction(policy)
    moving = sum(p.numel() for p in policy.parameters() if p.requires_grad)
    log(f"{len(data)} samples; {moving / 1e6:.2f}M numbers move; on {where}")
    optimiser = torch.optim.AdamW([p for p in policy.parameters() if p.requires_grad], lr=lr)
    policy.train()
    losses, started = [], time.time()
    into = into or WEIGHTS_DIR / "vla-correction"
    for step in range(steps):
        idx = rng.choice(len(data), batch)
        batch_ = ready([item(data[i]) for i in idx], pre)
        for group in optimiser.param_groups:
            group["lr"] = rate(step, steps, lr)
        loss, _ = policy.forward(batch_)
        loss.backward()
        optimiser.step()
        optimiser.zero_grad()
        losses.append(float(loss.item()))
        if (step + 1) % 25 == 0 or step + 1 == steps:
            log(
                f"  step {step + 1}/{steps}: loss {np.mean(losses[-25:]):.4f}, "
                f"{(time.time() - started) / (step + 1):.2f} s a step"
            )
    policy.model.save_pretrained(into)
    (into / "training.json").write_text(
        json.dumps(
            {
                "steps": steps,
                "batch": batch,
                "lr": lr,
                "samples": len(data),
                "minutes": round((time.time() - started) / 60, 1),
                "loss_first": float(np.mean(losses[:25])),
                "loss_last": float(np.mean(losses[-25:])),
            },
            indent=1,
        )
    )
    return into


# ---------------------------------------------------------------- the solution


class FineTuned:
    name = "smolvla, a little fine-tuned"

    def __init__(self, weights: Path | None = None) -> None:
        from peft import PeftModel

        self.where = device()
        self.policy, self.pre, self.post = borrowed(self.where)
        correction = weights or WEIGHTS_DIR / "vla-correction"
        # A missing correction is an error and not a fallback. Run without one, this
        # solution is the downloaded model with nothing fitted, and its scores would look
        # exactly like a fitted model's.
        if not (correction / "adapter_config.json").exists():
            raise FileNotFoundError(f"no fitted correction at {correction}; fit one with `make vla`")
        self.policy.model = PeftModel.from_pretrained(self.policy.model, correction).merge_and_unload()
        self.policy.eval()
        self.refused: set[int] = set()
        self.last = None
        self.picture_pairs: list = []

    def begin(self, seed: int) -> None:
        self.refused = set()
        self.last = None
        self.policy.reset()

    @torch.no_grad()
    def ask(self, pictures) -> np.ndarray:
        batch = {
            CAMERAS[0]: torch.from_numpy(pictures[0].copy()).permute(2, 0, 1).float() / 255.0,
            CAMERAS[1]: torch.from_numpy(pictures[1].copy()).permute(2, 0, 1).float() / 255.0,
            "observation.state": torch.zeros(6),
            "task": INSTRUCTION,
        }
        self.policy.reset()
        # Read straight from the model rather than through its post-processing,
        # which un-normalises with the six-number statistics of the arm it was made for.
        chunk = self.policy.predict_action_chunk(self.pre(batch))[0].float().cpu().numpy().astype(float)
        return chunk[:, :WIDTH].mean(0)

    def decide(self, look):
        boxes = list(look.boxes)
        if not boxes:
            return Done("no glass in view")
        if look.refused and self.last is not None:
            self.refused.add(self.last)
        vector = self.ask(look.pictures)
        usable = [b for k, b in enumerate(boxes) if k not in self.refused]
        glass, request = request_from(vector, boxes)
        if glass is None or glass in self.refused or not usable:
            return Done("the model says the table is finished" if glass is None else "nothing left to try")
        self.last = glass
        return request


if __name__ == "__main__":
    import argparse
    import pickle

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data", type=Path, required=True, help="a pickle made by build_vla_data (pictures and answers)"
    )
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--tag", default="vla-correction")
    a = parser.parse_args()
    with open(a.data, "rb") as handle:
        data = pickle.load(handle)
    print(train(data, a.steps, a.batch, into=WEIGHTS_DIR / a.tag))
