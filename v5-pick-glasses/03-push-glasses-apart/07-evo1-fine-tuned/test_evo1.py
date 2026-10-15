"""The checks that need no download and no fit.

Everything here is arithmetic, shapes, or a statement about the configuration.
A test that had to fetch 2 GB of borrowed weights would not be a test, so the
model itself is never built; what is checked instead is that the things handed
to it are the right shape, that the conventions really are solution 5's own
objects rather than copies, and that the two sizes this checkpoint forces on
the cell are the sizes the code uses.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import evo
import numpy as np
import partners
import pytest
import torch
from evo import SIDE, missing, picture_for, scaled, span
from partners import ACTION_SPAN, CAMERA, SLOTS, described


def _training():
    """This folder's ``train.py``, loaded from its own path.

    Four of the seven solutions have a file of that name, and importing
    ``partners`` puts two of their folders on the import path, so a bare
    ``import train`` is a coin toss. Loading it by path settles which one it
    is.
    """
    if "evo1_train" not in sys.modules:
        spec = importlib.util.spec_from_file_location("evo1_train", Path(__file__).parent / "train.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["evo1_train"] = module
        spec.loader.exec_module(module)
    return sys.modules["evo1_train"]


train = _training()

# ------------------------------------------------- nothing here is a copy


def test_the_reading_convention_is_solution_fives_own_object():
    # Not a copy with the same numbers in it: the same function. If solution 5
    # changes how an action becomes a waypoint, this solution changes with it,
    # which is what makes the three scores comparable.
    import joining

    assert partners.to_jaw is joining.to_jaw
    assert partners.to_state is joining.to_state
    assert partners.ACTION_SPAN is joining.ACTION_SPAN


def test_the_loop_over_a_table_is_solution_fives_own_loop():
    import clear as fives

    assert partners.clear is fives.clear


def test_the_demonstrations_are_solution_sixes_folder():
    # Read from solution 6 rather than collected again, so the two solutions
    # are fitted on the same file and not merely on the same recipe.
    assert partners.FITTING.parent.name == "06-smolvla-fine-tuned"
    assert partners.FITTING.name == "demonstrations"
    assert partners.TUNING.name == "demonstrations-check"


# ------------------------------------------------------------- the span


def test_the_span_comes_from_the_convention_and_is_symmetric():
    reach = span()
    assert reach["min"].shape == reach["max"].shape == (SLOTS,)
    assert np.allclose(reach["max"], ACTION_SPAN)
    assert np.allclose(reach["min"], -ACTION_SPAN)


def test_the_span_can_be_asked_for_at_another_width():
    assert span(3)["max"].shape == (3,)


# ------------------------------------------------- scaling the picture


def test_a_picture_already_the_right_size_is_left_alone():
    rows = torch.rand(3, SIDE, SIDE)
    assert scaled(rows) is rows


def test_a_picture_of_the_cells_own_size_is_scaled_to_the_checkpoints():
    # The cell renders 384 pixels and the checkpoint insists on 448, so this
    # is the one place that difference is dealt with.
    assert scaled(torch.rand(3, 384, 384)).shape == (3, SIDE, SIDE)


def test_a_batch_of_pictures_keeps_its_batch():
    assert scaled(torch.rand(4, 3, 384, 384)).shape == (4, 3, SIDE, SIDE)


def test_a_view_from_the_camera_becomes_the_models_layout():
    seen = np.zeros((384, 384, 3), dtype=np.uint8)
    ready = picture_for(seen)
    assert ready.shape == (3, SIDE, SIDE)
    assert float(ready.min()) >= 0.0 and float(ready.max()) <= 1.0


def test_a_picture_that_is_not_the_top_view_is_refused():
    with pytest.raises(ValueError, match="top view"):
        picture_for(np.zeros((384, 384, 3), dtype=np.float32))
    with pytest.raises(ValueError, match="top view"):
        picture_for(np.zeros((384, 384), dtype=np.uint8))


# --------------------------------------------------- what the fit needs


def test_a_folder_without_a_fit_in_it_says_what_to_run(tmp_path):
    assert "train.py" in missing(tmp_path)


def test_a_folder_with_both_halves_of_a_fit_is_accepted(tmp_path):
    (tmp_path / "head.pt").write_bytes(b"")
    (tmp_path / "stats.json").write_text("{}")
    assert missing(tmp_path) is None


def test_a_fit_without_its_span_is_refused(tmp_path):
    # The run has to scale its inputs exactly as the fitting did, so a fit
    # whose span was not written down cannot be loaded.
    (tmp_path / "head.pt").write_bytes(b"")
    assert missing(tmp_path) is not None


# ------------------------------------------------- the configuration


def test_the_configuration_describes_this_cell():
    config = evo.settings(chunk=50, device="cpu")
    assert config.chunk_size == 50
    assert config.n_action_steps == 50
    assert set(config.input_features) == {CAMERA, "observation.state"}
    assert config.input_features[CAMERA].shape == (3, SIDE, SIDE)
    assert config.input_features["observation.state"].shape == (SLOTS,)
    assert config.output_features["action"].shape == (SLOTS,)


def test_the_configuration_switches_off_what_this_machine_does_not_have():
    config = evo.settings(chunk=50, device="mps")
    assert config.use_flash_attn is False
    assert config.use_amp is False
    assert config.vlm_dtype == "float32"


def test_the_first_stage_freezes_the_borrowed_half():
    config = evo.settings(chunk=50, device="cpu")
    assert config.training_stage == "stage1"
    assert config.finetune_vlm is False
    assert config.finetune_action_head is True


def test_the_picture_size_is_the_one_the_checkpoint_forces():
    # Recorded as a test because it is a difference from solutions 5 and 6 and
    # not a choice: Evo-1 refuses any other size outright.
    from lerobot.policies.evo1.configuration_evo1 import Evo1Config

    with pytest.raises(ValueError, match="square"):
        Evo1Config(image_resolution=(384, 448))


# --------------------------------------------- reading the demonstrations


def test_the_shape_is_read_from_the_demonstrations_rather_than_assumed(tmp_path):
    root = tmp_path / "meta"
    root.mkdir()
    (root / "info.json").write_text(
        json.dumps(
            {
                "features": {"action": {"shape": [50 * SLOTS]}},
                "total_frames": 6907,
                "total_episodes": 2798,
            }
        )
    )
    assert described(tmp_path) == {
        "chunk": 50,
        "slots": SLOTS,
        "demonstrations": 6907,
        "tables": 2798,
    }


def test_a_chunk_that_does_not_divide_into_waypoints_is_refused(tmp_path):
    root = tmp_path / "meta"
    root.mkdir()
    (root / "info.json").write_text(
        json.dumps({"features": {"action": {"shape": [101]}}, "total_frames": 1, "total_episodes": 1})
    )
    with pytest.raises(ValueError, match="waypoints"):
        described(tmp_path)


def test_a_missing_demonstration_set_says_what_to_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="demonstrations.py"):
        described(tmp_path)


# ---------------------------------------------------- the step schedule


def test_the_learning_rate_warms_up_from_nearly_nothing():
    assert train.rate(0, 1000, 1e-4) == pytest.approx(1e-4 / train.WARMUP)
    assert train.rate(train.WARMUP - 1, 1000, 1e-4) == pytest.approx(1e-4)


def test_the_learning_rate_falls_away_to_nothing():
    assert train.rate(1000, 1000, 1e-4) == pytest.approx(0.0, abs=1e-12)
    middle = train.rate(550, 1000, 1e-4)
    assert 0.0 < middle < 1e-4


def test_the_effort_is_solution_sixes_effort():
    # Deliberate: a newer model given more training than the one it is
    # compared with would measure the training as well as the model.
    assert (train.STEPS, train.BATCH, train.LEARNING_RATE, train.WARMUP) == (1000, 4, 1e-4, 100)
