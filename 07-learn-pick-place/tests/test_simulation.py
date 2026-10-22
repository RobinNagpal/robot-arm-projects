"""Checks that run MuJoCo. Each episode takes a fraction of a second, so they run with the rest."""

import math

import numpy as np
import pytest

from pick_place.env import ENVIRONMENT_NAMES, STATE_NAMES, PickPlaceEnv, random_episode
from pick_place.expert import ARRIVED_PRECISE, run
from pick_place.kinematics import Solver
from pick_place.record import FEATURES, NOISE
from pick_place.settings import HOME

SEEDS = range(8)


@pytest.fixture(scope="module")
def envs():
    return {seed: PickPlaceEnv(random_episode(seed)) for seed in SEEDS}


def test_the_camera_finds_the_centre_of_mass_within_a_millimetre(envs):
    for env in envs.values():
        true = env.block_centre()
        assert math.hypot(env.located.x - true[0], env.located.y - true[1]) < 0.001


def test_the_camera_finds_the_thickness_within_a_millimetre(envs):
    for env in envs.values():
        assert abs(env.located.thickness - env.episode.block.thickness) < 0.001


def test_kinematics_reaches_a_pose_and_back():
    env = PickPlaceEnv(random_episode(0))
    solver = Solver(env.model)
    goal = np.array([0.5, 0.2, 0.05])
    q, error = solver.solve(np.array(HOME), goal, 0.7, iterations=300)
    assert error < 1e-4
    pos, _ = solver.pinch_pose(q)
    assert np.linalg.norm(pos - goal) < 1e-4


def test_the_expert_puts_the_block_on_the_target(envs):
    # Fresh envs: the fixture's have already been looked at, not stepped, but
    # keep this test independent of the order tests run in.
    missed = []
    for seed in SEEDS:
        env = PickPlaceEnv(random_episode(seed))
        for _ in run(env):
            pass
        if not env.succeeded():
            missed.append(seed)
    assert not missed


def test_the_dataset_features_match_the_env():
    env = PickPlaceEnv(random_episode(0))
    assert FEATURES["observation.state"]["shape"] == env.state().shape == (len(STATE_NAMES),)
    assert (
        FEATURES["observation.environment_state"]["shape"]
        == env.environment_state().shape
        == (len(ENVIRONMENT_NAMES),)
    )
    assert FEATURES["action"]["shape"] == next(run(env)).shape


def test_the_same_seed_gives_the_same_episode():
    a, b = random_episode(42), random_episode(42)
    assert a == b


def test_replaying_the_recorded_moves_gives_the_same_episode():
    """What record.py saves, fed back through env.step, must put the block on the target too.

    Replaying needs the expert's commands against the joints as they are at
    each step, as a policy's moves would be, so this plays the expert and a
    second env side by side.
    """
    expert_env, replay_env = PickPlaceEnv(random_episode(1)), PickPlaceEnv(random_episode(1))
    for command in run(expert_env):
        replay_env.step(replay_env.relative(command))
    assert replay_env.succeeded()


def test_the_goal_vectors_are_near_zero_where_the_expert_grasps_and_lets_go():
    env = PickPlaceEnv(random_episode(2))
    closest_grasp = closest_place = np.inf
    for _ in run(env):
        e = env.environment_state()
        closest_grasp = min(closest_grasp, np.linalg.norm(e[0:3]))
        closest_place = min(closest_place, np.linalg.norm(e[3:6]))
    assert closest_grasp < ARRIVED_PRECISE and closest_place < ARRIVED_PRECISE


def test_the_expert_still_succeeds_when_pushed():
    missed = []
    for seed in SEEDS:
        env = PickPlaceEnv(random_episode(seed))
        for _ in run(env, noise=NOISE, seed=seed):
            pass
        if not env.succeeded():
            missed.append(seed)
    assert len(missed) <= 1, missed
