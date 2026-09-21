"""The scripted expert: the demonstrations ACT learns from.

It knows nothing the policy is not shown: the two goal points and the grasp
direction are what the policy's environment state measures its distance to.

It works in phases. In each one it moves a commanded point for the pinch
point towards a goal, turns each commanded point into joint angles with
inverse kinematics, and moves on when the arm has really arrived:

    home -> above the grasp -> down -> close -> up
         -> above the place spot -> down -> open -> up

It decides from where the arm is, not from a clock. A first version followed
a fixed timetable, and the policy trained on it learned to close the gripper
when it was time to, whether or not the fingers had reached the block: it
closed 2 to 3 cm short in a fifth of its tries. Here the fingers close and
open only once the pinch point is within 1.5 mm of its goal, so that is what
the demonstrations teach.

For the same reason the recording can push the arm off course (``noise``):
the expert's command is still the clean one, and the recorded move is from
where the pushed arm really is back to it. Without that, every demonstration
is a perfect path and the policy never sees how to get back onto one.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace

import numpy as np

from .env import PickPlaceEnv
from .kinematics import Solver
from .settings import FPS

# Pinch point height above the block's top on the way in and out, metres.
CLEARANCE = 0.10
SPEED = 0.25  # m/s, fastest the commanded point moves
TURN_SPEED = 1.5  # rad/s, fastest the wrist turns
# Near its goal the commanded point covers this share of what is left each
# step, plus a millimetre, so the arm eases in rather than arriving at speed.
EASE = 0.25
# The arm has arrived when the pinch point is this close to the goal: tight
# where the fingers close or open, loose where the arm only passes through.
ARRIVED_PRECISE = 0.0015
ARRIVED_ROUGH = 0.01
# If the arm has not settled after this long, carry on anyway.
SETTLE_TIMEOUT = 2.0
GRIPPER_SECONDS = 0.8  # time to close or open the fingers and let them settle
FINAL_HOLD = 0.5


@dataclass(frozen=True)
class Phase:
    goal: np.ndarray
    gripper: float  # 0 open, 1 closed, for the whole phase
    arrived: float  # how close counts as there; 0: do not move, only wait
    wait: float = 0.0  # seconds to hold still once there
    noisy: bool = True  # whether a noisy recording may push the arm in this phase


def phases(env: PickPlaceEnv) -> list[Phase]:
    high = env.located.thickness + CLEARANCE
    at_grasp, at_place = env.grasp_point, env.place_point
    above_grasp = np.array([at_grasp[0], at_grasp[1], high])
    above_place = np.array([at_place[0], at_place[1], high])
    # The last approach, the grasp and the release are never pushed: that is
    # where the policy has to learn to be exact, from clean examples.
    return [
        Phase(above_grasp, 0.0, ARRIVED_ROUGH),
        Phase(at_grasp, 0.0, ARRIVED_PRECISE, noisy=False),
        Phase(at_grasp, 1.0, 0.0, GRIPPER_SECONDS, noisy=False),
        Phase(above_grasp, 1.0, ARRIVED_ROUGH),
        Phase(above_place, 1.0, ARRIVED_ROUGH),
        Phase(at_place, 1.0, ARRIVED_PRECISE, noisy=False),
        Phase(at_place, 0.0, 0.0, GRIPPER_SECONDS, noisy=False),
        Phase(above_place, 0.0, ARRIVED_ROUGH, FINAL_HOLD, noisy=False),
    ]


class Expert:
    def __init__(self, env: PickPlaceEnv, noise: float = 0.0, seed: int = 0):
        """``noise``: roughly how far to push the executed joints off course, radians; 0 for none."""
        self.env = env
        self.solver = Solver(env.model)
        self.q = env.state()[:6].astype(float)
        self.point, _ = self.solver.pinch_pose(self.q)
        self.phi = 0.0
        self.phases = phases(env)
        self.index = 0
        self.time_in_phase = 0.0
        self.noise = noise
        self.rng = np.random.default_rng(seed)
        self.push = np.zeros(6)

    @property
    def done(self) -> bool:
        return self.index >= len(self.phases)

    def command(self) -> np.ndarray:
        """The clean command for this step: six joint angles and the gripper."""
        phase = self.phases[self.index]
        self.time_in_phase += 1 / FPS
        if phase.arrived:
            step = phase.goal - self.point
            distance = float(np.linalg.norm(step))
            if distance > 1e-9:
                self.point = self.point + step * min(1.0, SPEED / FPS / distance, EASE + 1e-3 / distance)
            turn = self.env.grasp_phi - self.phi
            self.phi += float(np.clip(turn, -TURN_SPEED / FPS, TURN_SPEED / FPS))
            self.q, error = self.solver.solve(self.q, self.point, self.phi)
            if error > 1e-3:
                raise RuntimeError(f"no joint angles reach {self.point} (error {error:.4f})")
        command = np.append(self.q, phase.gripper)
        self.advance(phase)
        return command

    def advance(self, phase: Phase) -> None:
        if not phase.arrived:
            finished = self.time_in_phase >= phase.wait
        else:
            here, _ = self.env.pinch()
            at_goal = np.linalg.norm(self.point - phase.goal) < 1e-4
            lined_up = abs(self.env.grasp_phi - self.phi) < 1e-3
            arrived = np.linalg.norm(here - phase.goal) < phase.arrived
            finished = at_goal and lined_up and (arrived or self.time_in_phase > SETTLE_TIMEOUT)
            if finished and phase.wait:
                # There: now hold still for ``wait`` seconds.
                self.phases[self.index] = replace(phase, arrived=0.0)
                self.time_in_phase = 0.0
                return
        if finished:
            self.index += 1
            self.time_in_phase = 0.0

    def executed(self, command: np.ndarray) -> np.ndarray:
        """The command as the arm is really sent it: pushed off course, if this recording is noisy.

        The push drifts slowly, like a hand leaning on the arm rather than a
        shake, and fades out over half a second in phases that are not pushed.
        """
        if self.noise > 0 and not self.done and self.phases[self.index].noisy:
            # Each step keeps 90% of the push and adds a little; this settles
            # to a push of about ``noise`` radians on each joint.
            self.push = 0.9 * self.push + self.rng.normal(0.0, self.noise * 0.44, 6)
        else:
            self.push *= 0.8
        return np.append(command[:6] + self.push, command[6])


def run(
    env: PickPlaceEnv, noise: float = 0.0, seed: int = 0, max_seconds: float = 30.0
) -> Iterator[np.ndarray]:
    """Play the expert's episode, yielding each step's clean command just before it is executed."""
    expert = Expert(env, noise, seed)
    for _ in range(round(max_seconds * FPS)):
        if expert.done:
            return
        command = expert.command()
        yield command
        env.step_absolute(expert.executed(command))
