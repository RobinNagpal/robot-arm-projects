"""The whole thing: the simulated cell, MoveIt, and the task that drives them.

This is what ``make run`` starts.
"""

from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder
from work_cell.report import run_folder


def _moveit_config() -> MoveItConfigsBuilder:
    """A fresh builder. The builder is stateful, so it cannot be shared."""
    return MoveItConfigsBuilder("work_cell", package_name="work_cell_moveit_config").planning_pipelines(
        pipelines=["ompl"]
    )


def generate_launch_description() -> LaunchDescription:
    # move_group and the task node both need the MoveIt configuration, but not
    # quite the same one: MoveIt's C++/Python API reads the list of planning
    # pipelines from a different shape of parameter than move_group does, and
    # config/moveit_cpp.yaml is what supplies that shape. Hence two builds of
    # the same configuration.
    move_group_params = _moveit_config().to_dict()
    task_params = _moveit_config().moveit_cpp(file_path="config/moveit_cpp.yaml").to_dict()
    sim_time = {"use_sim_time": True}

    # One folder for the whole run, made here because both halves of the
    # report write into it: the world builder records what it put on the
    # table, and the task records what it made of it.
    folder = str(run_folder())

    cell = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory("work_cell"), "launch", "cell.launch.py")
        ),
        launch_arguments={
            "glasses": LaunchConfiguration("glasses"),
            "kinds": LaunchConfiguration("kinds"),
            "report_dir": folder,
            "seed": LaunchConfiguration("seed"),
            "gui": LaunchConfiguration("gui"),
            "rviz": LaunchConfiguration("rviz"),
        }.items(),
    )

    move_group = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="screen",
        parameters=[move_group_params, sim_time],
    )

    # The task node must not be given a name here. Without one, launch hands
    # its parameters over under a /** wildcard, which is how MoveIt's own node
    # inside the process gets to see the robot description as well.
    task = Node(
        package="work_cell",
        executable="pick_glasses",
        output="screen",
        emulate_tty=True,
        condition=IfCondition(LaunchConfiguration("task")),
        parameters=[task_params, sim_time, {"report_dir": folder}],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("glasses", default_value="4"),
            DeclareLaunchArgument("kinds", default_value=""),
            DeclareLaunchArgument("seed", default_value="1"),
            DeclareLaunchArgument("gui", default_value="true"),
            DeclareLaunchArgument("rviz", default_value="false"),
            DeclareLaunchArgument(
                "task", default_value="true", description="run the workflow, or just bring the cell up"
            ),
            cell,
            move_group,
            # A head start for Gazebo and move_group. It does not have to be
            # long enough on its own: the task waits for the controllers, the
            # planning scene service and the first camera frames itself.
            TimerAction(period=10.0, actions=[task]),
        ]
    )
