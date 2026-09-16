"""Entry point. Wires the pieces together and runs the workflow once."""

from __future__ import annotations

import math
import os
import sys
import threading
import traceback

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.wait_for_message import wait_for_message
from sensor_msgs.msg import JointState

from .arm.camera import WristCamera
from .arm.motion import Arm, MotionFailed
from .geometry import describe
from .scene import PlanningSceneClient
from .task import HOLD_FLAT, TILT, WRIST, Result, TaskFailed, TurnTopTask

JOINT_STATES_TIMEOUT = 600.0  # seconds


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Node("turn_top_task")
    turn = node.declare_parameter("turn", WRIST).value

    # MoveIt gives up for good if the arm's joint states are not coming in
    # within ten seconds of it starting. On a cold start the controllers can
    # take minutes to come up, so their first message is waited for here.
    node.get_logger().info("waiting for the arm's joint states")
    if not wait_for_message(JointState, node, "/joint_states", time_to_wait=JOINT_STATES_TIMEOUT)[0]:
        node.get_logger().error(f"no joint states within {JOINT_STATES_TIMEOUT:.0f}s; is the cell up?")
        rclpy.shutdown()
        return

    # Everything that subscribes or calls a service is built before the node
    # starts being spun, so the executor sees the full set from its first pass.
    arm = Arm(node)
    scene = PlanningSceneClient(node, arm.planning_scene_monitor)

    # The workflow blocks on services, actions and camera frames, so those have
    # to keep being served from somewhere else. The executor runs on its own
    # thread and the workflow runs on this one.
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    def spin():
        try:
            executor.spin()
        except Exception:
            node.get_logger().error("executor thread died:\n" + traceback.format_exc())

    status = 1
    try:
        task = TurnTopTask(node, arm, WristCamera(node), scene, turn)
        threading.Thread(target=spin, daemon=True).start()
        if _report(node, task.run()):
            status = 0
    except (TaskFailed, MotionFailed) as failure:
        node.get_logger().error(f"the top was not turned flat: {failure}")
    finally:
        executor.shutdown()
        rclpy.shutdown()
    # MoveIt's C++ side crashes in its own destructor on the way out ("Deleting
    # MoveItCpp", then a segfault), whether or not it is shut down first, and
    # move_group does the same when stopped. Everything is finished and
    # reported by now, so the process leaves without running destructors.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(status)


def _report(node: Node, result: Result) -> bool:
    """Log what happened, and whether it worked: the top flat in the fingers, or a table built."""
    log = node.get_logger()
    log.info("finished")
    log.info(f"  table top measured at {describe(result.top.size)}")
    if result.turn == TILT:
        log.info(f"  the tilt down onto the legs took {result.seconds:.1f} s")
    else:
        log.info(f"  the turn by the {result.turn.replace('_', ' ')} took {result.seconds:.1f} s")
    log.info(f"  {'joint':<20} {'moved':>8} {'net':>8} {'peak N·m':>9} {'holding N·m':>12}")
    for joint in result.joints:
        log.info(
            f"  {joint.name:<20} {math.degrees(joint.travel):>7.1f}° {math.degrees(joint.turned):>+7.1f}° "
            f"{_effort(joint.peak_effort):>9} {_effort(joint.holding_effort):>12}"
        )
    if result.slipped_at is not None:
        turned = math.degrees(result.slipped_at)
        log.error(f"  the fingertips lost the top {turned:.0f} degrees from hanging straight down")
        log.error("  it has twisted in the fingers or fallen out: the sensors cannot tell which")
        return False
    if result.turn == TILT:
        return _report_table(log, result)
    log.info(f"  the arm puts the top {math.degrees(result.tilt):.1f} degrees off level")
    if not result.held:
        log.error(f"  the fingers lost the top in the {HOLD_FLAT:.0f} s it was held flat")
        return False
    log.info(f"  held flat for {HOLD_FLAT:.0f} s, and the fingers still feel the top")
    return True


def _report_table(log, result: Result) -> bool:
    check = result.table
    if check is None:
        log.warning("  the finished table could not be checked")
        return False
    log.info(f"  table as built: {describe(check.size)}")
    log.info(f"  height {check.size[2] * 100:.1f} cm, expected {check.expected_height * 100:.1f} cm")
    log.info(f"  top {math.degrees(check.tilt):.1f} degrees off level")
    log.info(f"  centre {check.offset * 1000:.0f} mm from where it was meant to be")
    log.info(f"  verdict: {'a table' if check.good else 'NOT a proper table'}")
    return check.good


def _effort(value: float) -> str:
    """An effort for the table, or a dash where there is no reading."""
    return "-" if math.isnan(value) else f"{value:.2f}"
