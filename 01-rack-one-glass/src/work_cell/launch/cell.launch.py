"""Start the simulated cell: Gazebo, the robot, its controllers and the bridge.

The world file is written fresh on every start, and so are the glass meshes in
it. That is not a convenience. The whole project rests on the arm not being
told how big a glass is, and a mesh shipped with the project would be a glass
whose size somebody wrote down. Every run draws new proportions, spins them
into a mesh, and leaves the arm to measure what it finds.

``seed`` makes any one arrangement repeatable, which is what makes a failure
worth reporting: the same seed puts the same glasses back on the table.
"""

from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    OpaqueFunction,
    RegisterEventHandler,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from work_cell.glasses.shapes import KIND_RANGES
from work_cell.glasses.spawn import random_glasses
from work_cell.rack.build import random_rack_pose
from work_cell.report import Report
from work_cell.world.build import build_world, read_parts

PACKAGE = "work_cell"


def robot_description(share: Path) -> str:
    """Run the xacro and hand back the finished URDF."""
    import xacro

    return xacro.process_file(
        str(share / "arm" / "arm.urdf.xacro"),
        mappings={"controllers_file": str(share / "arm" / "controllers.yaml")},
    ).toxml()


def _describe_the_table(report, glasses, rack_pose, settings) -> None:
    """What was actually put on the table, written before the arm sees any of it.

    This is the one part of the report the arm does not get to have. It is the
    simulator's own truth, and it is here so that a reader can hold what the
    arm measured against what was really there. Nothing downstream reads it.
    """
    report.step("What was put on the table")
    report.table(settings)
    report.say(
        "The arm is told none of this. It is written down first so that what "
        "the arm works out can be held against it."
    )

    rows = ["| glass | kind | stands at | height | widest |", "| --- | --- | --- | --- | --- |"]
    for glass in glasses:
        rows.append(
            f"| `{glass.name}` | {glass.kind} | "
            f"({glass.position[0]:.3f}, {glass.position[1]:.3f}) | "
            f"{glass.outline.total_height * 1000:.0f} mm | "
            f"{2 * float(glass.outline.radius.max()) * 1000:.0f} mm |"
        )
    report.say("\n".join(rows))
    report.say(
        f"The rack stands at ({rack_pose[0]:.3f}, {rack_pose[1]:.3f}), "
        f"turned {math.degrees(rack_pose[2]):.0f}°."
    )


def _kinds(named: str) -> list[str] | None:
    """The kinds named on the command line, checked against the ones that exist.

    Checked here rather than left to the spawner, because a name with a typo in
    it would otherwise simply never be drawn, and the run would look like a
    kind of glass the arm cannot handle rather than one it was never given.
    """
    wanted = [name.strip() for name in named.split(",") if name.strip()]
    if not wanted:
        return None

    unknown = sorted(set(wanted) - set(KIND_RANGES))
    if unknown:
        raise ValueError(
            f"no such kind of glass: {', '.join(unknown)}. "
            f"The kinds are {', '.join(sorted(KIND_RANGES))}"
        )
    return wanted


def write_world(share: Path, count: int, seed: int, kinds: list[str] | None, report) -> str:
    """Assemble the room, the table, the rack and this run's glasses.

    The meshes go in the same temporary directory as the world file, and the
    world refers to them by absolute path, so the whole run is self-contained
    and nothing is left behind in the install tree.

    ``kinds`` narrows what may be drawn. None means any kind, which is what a
    real run wants; naming one is for looking at a single problem without the
    other three getting in the way.
    """
    import random

    world_template, table = read_parts(share)
    folder = Path(tempfile.mkdtemp(prefix="work_cell_"))

    rack_pose = random_rack_pose(random.Random(seed))
    glasses = random_glasses(count, seed, kinds)
    if report is not None:
        _describe_the_table(
            report,
            glasses,
            rack_pose,
            {
                "glasses": count,
                "kinds": ", ".join(kinds) if kinds else "any",
                "seed": seed,
            },
        )

    sdf = build_world(
        world_template,
        table,
        rack_pose=rack_pose,
        glasses=glasses,
        mesh_dir=folder,
    )

    path = folder / "cell.sdf"
    path.write_text(sdf)
    return str(path)


def _chain_spawners(*names) -> list:
    """Spawner nodes, each one starting only once the one before it has finished.

    A name may be a tuple, in which case everything after the first item is an
    extra argument for that spawner. That is how a controller gets loaded
    without being started.
    """
    spawners = [
        Node(
            package="controller_manager",
            executable="spawner",
            output="screen",
            arguments=[
                *([name] if isinstance(name, str) else list(name)),
                "--controller-manager",
                "/controller_manager",
            ],
        )
        for name in names
    ]
    actions = [spawners[0]]
    for previous, following in zip(spawners, spawners[1:], strict=False):
        actions.append(RegisterEventHandler(OnProcessExit(target_action=previous, on_exit=[following])))
    return actions


def setup(context, *args, **kwargs):
    share = Path(get_package_share_directory(PACKAGE))
    glasses = int(LaunchConfiguration("glasses").perform(context))
    seed = int(LaunchConfiguration("seed").perform(context))
    gui = LaunchConfiguration("gui").perform(context).lower() in ("true", "1")
    kinds = _kinds(LaunchConfiguration("kinds").perform(context))

    folder = LaunchConfiguration("report_dir").perform(context)
    report = Report(Path(folder), "Picking up glasses") if folder else None
    world = write_world(share, glasses, seed, kinds, report)

    # The simulator always runs as a server on its own, and the window, when
    # there is one, is a second process that connects to it. That is not a
    # preference: on macOS `gz sim` refuses to be both in one process, because
    # the window has to own the main thread. Splitting them is fine everywhere,
    # so there is no per-platform branch here.
    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory("ros_gz_sim"), "launch", "gz_sim.launch.py")
            ),
            launch_arguments={"gz_args": f"-s -r -v 2 --headless-rendering {world}"}.items(),
        ),
        # Given a few seconds so the server is up and has a scene to send it.
        *(
            [TimerAction(period=5.0, actions=[ExecuteProcess(cmd=["gz", "sim", "-g"], output="screen")])]
            if gui
            else []
        ),
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            output="screen",
            parameters=[
                {"robot_description": ParameterValue(robot_description(share), value_type=str)},
                {"use_sim_time": True},
            ],
        ),
        Node(
            package="ros_gz_sim",
            executable="create",
            output="screen",
            arguments=["-topic", "robot_description", "-name", "work_cell"],
        ),
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            output="screen",
            parameters=[
                {"config_file": str(share / "world" / "gz_bridge.yaml")},
                {"use_sim_time": True},
            ],
        ),
        # One controller at a time. Spawners racing each other into a
        # controller manager that is still starting up is enough to make one of
        # them try to configure a controller another has already activated.
        #
        # The gripper's force controller is loaded but left inactive, because
        # it wants the same finger joints as the position controller and only
        # one of them may have them. arm/motion.py activates it when the pads
        # are on a glass, and hands the joints back to let go.
        *_chain_spawners(
            "joint_state_broadcaster",
            # ForceTorqueSensorBroadcaster has no topic_name parameter: it always
            # publishes on ~/wrench. The remap is what puts it on /wrist_force,
            # which is the name arm/motion.py listens on.
            (
                "wrist_force_broadcaster",
                "--controller-ros-args",
                "-r ~/wrench:=/wrist_force",
            ),
            "arm_controller",
            "gripper_controller",
            ("gripper_force_controller", "--inactive"),
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            output="screen",
            condition=IfCondition(LaunchConfiguration("rviz")),
            arguments=["-d", str(share / "world" / "view.rviz")],
            parameters=[{"use_sim_time": True}],
        ),
    ]


def generate_launch_description() -> LaunchDescription:
    # Gazebo looks for things on its own search paths, not on the ROS ones, so
    # both have to be pointed at every install prefix in the workspace:
    # package:// mesh paths for the UR5e's visuals, and the shared library that
    # lets ros2_control drive joints inside the simulator.
    prefixes = [p for p in os.environ.get("AMENT_PREFIX_PATH", "").split(os.pathsep) if p]
    resource_path = os.pathsep.join(os.path.join(p, "share") for p in prefixes)
    plugin_path = os.pathsep.join(os.path.join(p, "lib") for p in prefixes)

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "glasses", default_value="4", description="how many glasses to put on the table"
            ),
            DeclareLaunchArgument(
                "seed",
                default_value="1",
                description="which set of glasses to make; the same seed gives the same glasses",
            ),
            DeclareLaunchArgument(
                "report_dir",
                default_value="",
                description="folder this run writes its report and pictures into",
            ),
            DeclareLaunchArgument(
                "kinds",
                default_value="",
                description=(
                    "which kinds of glass to draw from, comma separated, or empty for any of "
                    f"them: {', '.join(sorted(KIND_RANGES))}"
                ),
            ),
            DeclareLaunchArgument("gui", default_value="true", description="show the Gazebo window"),
            DeclareLaunchArgument("rviz", default_value="false", description="also open RViz"),
            SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", resource_path),
            SetEnvironmentVariable("GZ_SIM_SYSTEM_PLUGIN_PATH", plugin_path),
            # Applies to every node started below, because both ends of a topic
            # have to agree on how big a message may be.
            SetEnvironmentVariable(
                "FASTRTPS_DEFAULT_PROFILES_FILE",
                str(Path(get_package_share_directory(PACKAGE)) / "world" / "fastdds.xml"),
            ),
            OpaqueFunction(function=setup),
        ]
    )
