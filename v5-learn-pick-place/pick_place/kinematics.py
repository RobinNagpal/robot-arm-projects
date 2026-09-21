"""Joint angles that put the gripper's pinch point at a position, pointing straight down.

Damped least squares on the Jacobian, from a starting guess. The expert calls
it every control step with the previous answer as the guess, so each call
moves only a few millimetres and settles in a handful of iterations.

The gripper is only ever wanted pointing straight down, turned about the
vertical by ``phi``: the direction, in the table plane, along which the
fingers close.
"""

from __future__ import annotations

import mujoco
import numpy as np

from .scene import ARM_JOINTS, PINCH_SITE

DAMPING = 1e-4
# A small pull towards the starting guess, in the arm's spare directions, so
# repeated solves do not drift into a different elbow or wrist configuration.
NULLSPACE_GAIN = 0.05


def pinch_rotation(phi: float) -> np.ndarray:
    """The pinch site's orientation: z straight down, the fingers closing along (cos phi, sin phi)."""
    closing = np.array([np.cos(phi), np.sin(phi), 0.0])
    down = np.array([0.0, 0.0, -1.0])
    return np.column_stack([np.cross(closing, down), closing, down])


class Solver:
    def __init__(self, model: mujoco.MjModel):
        self.model = model
        self.data = mujoco.MjData(model)
        self.qpos_ids = np.array([model.joint(n).qposadr[0] for n in ARM_JOINTS])
        self.dof_ids = np.array([model.joint(n).dofadr[0] for n in ARM_JOINTS])
        self.site = model.site(PINCH_SITE).id
        self.lower = np.array([model.joint(n).range[0] for n in ARM_JOINTS])
        self.upper = np.array([model.joint(n).range[1] for n in ARM_JOINTS])

    def pinch_pose(self, q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Where the pinch site is, and its orientation, for arm angles ``q``."""
        self.data.qpos[self.qpos_ids] = q
        mujoco.mj_kinematics(self.model, self.data)
        return self.data.site_xpos[self.site].copy(), self.data.site_xmat[self.site].reshape(3, 3).copy()

    def solve(
        self, q_guess: np.ndarray, pos: np.ndarray, phi: float, iterations: int = 60, tolerance: float = 1e-5
    ) -> tuple[np.ndarray, float]:
        """Arm angles for the pinch site at ``pos``, fingers closing along ``phi``, and the error left.

        The error is the position error in metres plus the orientation error in
        radians; below 1e-3 the answer is good enough to command.
        """
        q = np.array(q_guess, dtype=float)
        goal_rot = pinch_rotation(phi)
        jac_pos = np.zeros((3, self.model.nv))
        jac_rot = np.zeros((3, self.model.nv))
        error = np.inf
        for _ in range(iterations):
            self.data.qpos[self.qpos_ids] = q
            mujoco.mj_kinematics(self.model, self.data)
            mujoco.mj_comPos(self.model, self.data)
            here = self.data.site_xpos[self.site]
            rot = self.data.site_xmat[self.site].reshape(3, 3)
            err_pos = pos - here
            # Half the sum of each axis crossed with where it should point: zero
            # when aligned, and a rotation vector for small misalignments.
            err_rot = 0.5 * sum(np.cross(rot[:, i], goal_rot[:, i]) for i in range(3))
            e = np.concatenate([err_pos, err_rot])
            error = float(np.linalg.norm(err_pos) + np.linalg.norm(err_rot))
            if error < tolerance:
                break
            mujoco.mj_jacSite(self.model, self.data, jac_pos, jac_rot, self.site)
            j = np.vstack([jac_pos, jac_rot])[:, self.dof_ids]
            jjt = j @ j.T + DAMPING * np.eye(6)
            dq = j.T @ np.linalg.solve(jjt, e)
            nullspace = np.eye(6) - np.linalg.pinv(j) @ j
            dq += nullspace @ (NULLSPACE_GAIN * (np.asarray(q_guess) - q))
            q = np.clip(q + dq, self.lower, self.upper)
        return q, error
