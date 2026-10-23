# The full arm's ROS side

MoveIt 2 runs in a ROS environment, while the physics and the learned models
run in problem 4's own environment, which has no ROS. So the full arm keeps
everything ROS needs in this folder, and `moveit_connection.py` starts
`moveit_server.py` with the Python from here and talks to it over a pipe.

| Here | What it is |
|---|---|
| `pixi.toml`, `pixi.lock` | the ROS environment: MoveIt 2 and the UR5e, gripper and camera descriptions |
| `arm/` | the arm's description as xacro: the UR5e, the gripper and the wrist camera |
| `moveit/` | what MoveIt is told about the arm: the planning groups, the joint limits, the solver and the planner settings |

These files began as copies of problem 1's, so that problem 4 shares nothing
with problem 1. `pixi install` in this folder makes the environment, and
nothing else has to be activated by hand.
