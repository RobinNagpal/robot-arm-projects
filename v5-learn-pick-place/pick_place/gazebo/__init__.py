"""Running the trained policy in Gazebo, a second simulator it was never trained in.

The policy learned in MuJoCo. Here the same arm, camera, block and target are
rebuilt in Gazebo Harmonic, and the same policy drives the arm with no
changes. Gazebo's physics, contact model and joint controllers differ from
MuJoCo's, so this measures how much of what the policy learned was about the
task, and how much was about one simulator.

Gazebo runs as its own process, headless, paused, and is stepped from Python
over Gazebo's own transport, without ROS, the same way v4 drives it.
"""
