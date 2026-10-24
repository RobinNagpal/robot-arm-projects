"""Solution 6: SmolVLA, fitted a little, answering in MoveIt's terms.

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

import numpy as np
import torch

from shared.learning import table_and_push_encoding
from shared.turn_by_turn_loop import (
    LOOK_FROM_BOTH_PLACES_EVERY_TURN,
    RefusedGlasses,
    TableFinished,
    TurnByTurnSolution,
)

THIS_FOLDER = Path(__file__).resolve().parent
WEIGHTS_FOLDER = THIS_FOLDER / "weights"
BASE_MODEL_NAME = "lerobot/smolvla_base"
CAMERA_KEYS = ("observation.images.camera1", "observation.images.camera2")
INSTRUCTION = "Push the crowded glasses apart so each has room, without tipping any."
ACTION_CHUNK_ROWS = 50
# stop, glass x, glass y, cos, sin, travel, six settings
ANSWER_WIDTH = 12
LORA_RANK, LORA_SCALING = 16, 32
LORA_TARGET_MODULES = ("q_proj", "k_proj", "v_proj", "o_proj")


def best_torch_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


def load_base_smolvla(torch_device: str | None = None):
    """The downloaded model with nothing changed, and its own pre- and post-processing."""
    from lerobot.configs.types import FeatureType, PolicyFeature
    from lerobot.policies.factory import make_pre_post_processors
    from lerobot.policies.smolvla.configuration_smolvla import SmolVLAConfig
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

    torch_device = torch_device or best_torch_device()
    config = SmolVLAConfig.from_pretrained(BASE_MODEL_NAME)
    config.device = torch_device
    # The model was made for an arm with six numbers an action, and it reads that
    # off its configuration twice: it cuts its answer down to six, and it
    # measures its training loss on the first six only. Both would silently drop
    # the last six of the twelve numbers this solution asks for -- the settings
    # given to MoveIt would never be learned. So the configuration is told twelve.
    config.output_features["action"] = PolicyFeature(type=FeatureType.ACTION, shape=(ANSWER_WIDTH,))
    policy = SmolVLAPolicy.from_pretrained(BASE_MODEL_NAME, config=config).to(torch_device)
    preprocess, postprocess = make_pre_post_processors(
        config, BASE_MODEL_NAME, preprocessor_overrides={"device_processor": {"device": torch_device}}
    )
    return policy, preprocess, postprocess


def add_lora_correction(policy):
    from peft import LoraConfig, get_peft_model

    policy.model = get_peft_model(
        policy.model,
        LoraConfig(
            r=LORA_RANK,
            lora_alpha=LORA_SCALING,
            lora_dropout=0.0,
            bias="none",
            target_modules=list(LORA_TARGET_MODULES),
        ),
    )
    return policy


# ---------------------------------------------------------------- the encoding


def encode_answer(boxes, glass: int | None, request) -> np.ndarray:
    """What the model is taught to write for a turn: twelve numbers, the same on every row."""
    if glass is None:
        return np.zeros(ANSWER_WIDTH, dtype=np.float32)
    box = boxes[glass]
    return np.concatenate(
        [
            [
                0.0,
                (box.x - table_and_push_encoding.GLASS_ZONE_CENTRE[0]) / 0.2,
                (box.y - table_and_push_encoding.GLASS_ZONE_CENTRE[1]) / 0.2,
            ],
            table_and_push_encoding.encode_push(request),
        ]
    ).astype(np.float32)


def repeat_into_chunk(vector: np.ndarray) -> np.ndarray:
    return np.tile(vector, (ACTION_CHUNK_ROWS, 1))


def decode_answer(answer: np.ndarray, boxes) -> tuple[int | None, object]:
    """The model's twelve numbers back into a push, or None for "finished"."""
    if answer[0] > 0.5 or not boxes:
        return None, None
    glass_x, glass_y = (
        table_and_push_encoding.GLASS_ZONE_CENTRE[0] + 0.2 * answer[1],
        table_and_push_encoding.GLASS_ZONE_CENTRE[1] + 0.2 * answer[2],
    )
    glass = min(range(len(boxes)), key=lambda k: math.dist((boxes[k].x, boxes[k].y), (glass_x, glass_y)))
    return glass, table_and_push_encoding.decode_push(glass, answer[3:])


# ------------------------------------------------------------------- the data


def render_both_wrist_pictures(records: list[dict]) -> list[tuple[np.ndarray, np.ndarray]]:
    """Both wrist pictures for the layout each record started from."""
    import mujoco

    from examiner.examining.one_table_cell import viewing_joint_angles
    from examiner.motion.moveit_connection import ARM_COLLISION_MESHES, write_arm_urdf_if_missing
    from examiner.simulation import table_draw, wrist_camera
    from examiner.simulation.arm_and_table_simulator import ArmAndTableSimulator

    both_views = viewing_joint_angles()
    pictures_per_record = []
    for record in records:
        simulator = ArmAndTableSimulator(
            record["seed"],
            table_draw.draw_table(record["seed"]),
            urdf=write_arm_urdf_if_missing(),
            meshes=ARM_COLLISION_MESHES,
            start_joint_angles=both_views[0],
        )
        for i, glass in enumerate(record["before"]):
            address = simulator.model.jnt_qposadr[simulator.model.body_jntadr[simulator.bodies[i]]]
            simulator.data.qpos[address : address + 2] = [glass["x"], glass["y"]]
        simulator.data.qvel[:] = 0.0
        mujoco.mj_forward(simulator.model, simulator.data)
        camera = wrist_camera.WristCameraRenderer(simulator)
        pair = []
        for view_joint_angles in both_views:
            simulator.set_joint_angles(view_joint_angles)
            pair.append(camera.render_picture(simulator.fingertips_waypoint()))
        camera.close()
        pictures_per_record.append(tuple(pair))
    return pictures_per_record


def training_samples(records: list[dict]) -> list[dict]:
    """The pictures and the answer for every push worth copying, and for every finished table."""
    import imitation

    demos, _ = imitation.demonstrations_from_pushes(records)
    keep = []
    for record in records:
        if all(glass["pickable"] for glass in record["before"]):
            keep.append((record, None, None))
            continue
        outcome = table_and_push_encoding.push_outcome_from_record(record)
        if (
            outcome["feasible"]
            and not outcome["topple"]
            and (
                outcome["gain"] >= 1
                or (outcome["eased"] >= 4.0 and outcome["disturbed"] < 0.01 and outcome["moved"] > 0.01)
            )
        ):
            keep.append(
                (record, record["request"]["glass"], table_and_push_encoding.push_request_from_record(record))
            )
    pictures = render_both_wrist_pictures([kept[0] for kept in keep])
    return [
        {
            "pictures": both,
            "action": repeat_into_chunk(
                encode_answer(table_and_push_encoding.boxes_from_layout(record["before"]), glass, request)
            ),
        }
        for (record, glass, request), both in zip(keep, pictures, strict=True)
    ]


def as_smolvla_item(sample: dict) -> dict:
    return {
        CAMERA_KEYS[0]: torch.from_numpy(sample["pictures"][0].copy()).permute(2, 0, 1).float() / 255.0,
        CAMERA_KEYS[1]: torch.from_numpy(sample["pictures"][1].copy()).permute(2, 0, 1).float() / 255.0,
        "observation.state": torch.zeros(6),
        "action": torch.from_numpy(sample["action"]).float(),
        "task": INSTRUCTION,
    }


def collate_batch(items: list[dict], preprocess) -> dict:
    preprocessed = [preprocess(item) for item in items]
    batch = {
        key: torch.cat([item[key] for item in preprocessed], dim=0)
        for key in (*CAMERA_KEYS, "observation.state", "observation.language.tokens")
    }
    batch["observation.language.attention_mask"] = torch.cat(
        [item["observation.language.attention_mask"] for item in preprocessed], dim=0
    ).bool()
    batch["action"] = torch.stack([item["action"] for item in preprocessed])
    return batch


def learning_rate_at(step: int, steps: int, peak_rate: float, warmup_steps: int = 50) -> float:
    if step < warmup_steps:
        return peak_rate * (step + 1) / warmup_steps
    share_done = (step - warmup_steps) / max(1, steps - warmup_steps)
    return peak_rate * 0.5 * (1 + math.cos(math.pi * share_done))


def train_lora_correction(
    data: list[dict],
    steps: int,
    batch: int = 4,
    peak_learning_rate: float = 1e-4,
    seed: int = 0,
    weights_folder: Path | None = None,
    log=lambda *parts: print(*parts, flush=True),
) -> Path:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    torch_device = best_torch_device()
    policy, preprocess, postprocess = load_base_smolvla(torch_device)
    policy = add_lora_correction(policy)
    trainable_numbers = sum(p.numel() for p in policy.parameters() if p.requires_grad)
    log(f"{len(data)} samples; {trainable_numbers / 1e6:.2f}M numbers move; on {torch_device}")
    optimiser = torch.optim.AdamW([p for p in policy.parameters() if p.requires_grad], lr=peak_learning_rate)
    policy.train()
    losses, started = [], time.time()
    weights_folder = weights_folder or WEIGHTS_FOLDER / "vla-r4"
    for step in range(steps):
        chosen = rng.choice(len(data), batch)
        batch_of_items = collate_batch([as_smolvla_item(data[i]) for i in chosen], preprocess)
        for group in optimiser.param_groups:
            group["lr"] = learning_rate_at(step, steps, peak_learning_rate)
        loss, _ = policy.forward(batch_of_items)
        loss.backward()
        optimiser.step()
        optimiser.zero_grad()
        losses.append(float(loss.item()))
        if (step + 1) % 25 == 0 or step + 1 == steps:
            log(
                f"  step {step + 1}/{steps}: loss {np.mean(losses[-25:]):.4f}, "
                f"{(time.time() - started) / (step + 1):.2f} s a step"
            )
    policy.model.save_pretrained(weights_folder)
    (weights_folder / "training.json").write_text(
        json.dumps(
            {
                "steps": steps,
                "batch": batch,
                "lr": peak_learning_rate,
                "samples": len(data),
                "minutes": round((time.time() - started) / 60, 1),
                "loss_first": float(np.mean(losses[:25])),
                "loss_last": float(np.mean(losses[-25:])),
            },
            indent=1,
        )
    )
    return weights_folder


# ---------------------------------------------------------------- the solution


class SmolVLASolution(TurnByTurnSolution):
    name = "smolvla, a little fine-tuned"
    # It reads the two pictures themselves, so it is shown both, both new, on every turn.
    looking_mode = LOOK_FROM_BOTH_PLACES_EVERY_TURN

    def __init__(self, weights: Path | None = None) -> None:
        from peft import PeftModel

        self.torch_device = best_torch_device()
        self.policy, self.preprocess, self.postprocess = load_base_smolvla(self.torch_device)
        correction = weights or WEIGHTS_FOLDER / "vla-r4"
        # A missing correction is an error and not a fallback. Run without one, this
        # solution is the downloaded model with nothing fitted, and its scores would look
        # exactly like a fitted model's.
        if not (correction / "adapter_config.json").exists():
            raise FileNotFoundError(f"no fitted correction at {correction}; fit one with `make vla`")
        self.policy.model = PeftModel.from_pretrained(self.policy.model, correction).merge_and_unload()
        self.policy.eval()
        self.refused_glasses = RefusedGlasses()
        self.last_requested_glass = None

    def start_new_table(self) -> None:
        self.refused_glasses = RefusedGlasses()
        self.last_requested_glass = None
        self.policy.reset()
        # The model draws noise for every answer. Given the same draw at the start of every
        # table, a table gets the same answers every time it is run.
        torch.manual_seed(0)

    @torch.no_grad()
    def ask_model(self, pictures) -> np.ndarray:
        batch = {
            CAMERA_KEYS[0]: torch.from_numpy(pictures[0].copy()).permute(2, 0, 1).float() / 255.0,
            CAMERA_KEYS[1]: torch.from_numpy(pictures[1].copy()).permute(2, 0, 1).float() / 255.0,
            "observation.state": torch.zeros(6),
            "task": INSTRUCTION,
        }
        self.policy.reset()
        # Read straight from the model rather than through its post-processing,
        # which un-normalises with the six-number statistics of the arm it was made for.
        chunk = (
            self.policy.predict_action_chunk(self.preprocess(batch))[0].float().cpu().numpy().astype(float)
        )
        return chunk[:, :ANSWER_WIDTH].mean(0)

    def decide_turn(self, observation):
        boxes = list(observation.boxes)
        if not boxes:
            return TableFinished("no glass in view")
        if observation.last_push_refusal_reason and self.last_requested_glass is not None:
            self.refused_glasses.remember(boxes, self.last_requested_glass)
        answer = self.ask_model(observation.latest_pictures)
        refused_indices = self.refused_glasses.indices_in_look(boxes)
        glasses_left_to_push = [b for k, b in enumerate(boxes) if k not in refused_indices]
        glass, request = decode_answer(answer, boxes)
        if glass is None or glass in refused_indices or not glasses_left_to_push:
            return TableFinished(
                "the model says the table is finished" if glass is None else "nothing left to try"
            )
        self.last_requested_glass = glass
        return request


if __name__ == "__main__":
    import argparse
    import pickle

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        required=True,
        help="a pickle made by make_smolvla_training_data.py (pictures and answers)",
    )
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--tag", default="vla-r4")
    arguments = parser.parse_args()
    with open(arguments.data, "rb") as handle:
        data = pickle.load(handle)
    print(
        train_lora_correction(
            data, arguments.steps, arguments.batch, weights_folder=WEIGHTS_FOLDER / arguments.tag
        )
    )
