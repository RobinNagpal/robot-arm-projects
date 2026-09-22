"""Entry point. Wires the pieces together and runs the workflow once."""

from __future__ import annotations

import threading
import traceback
from pathlib import Path

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from .arm.camera import WristCamera
from .arm.motion import Arm
from .report import Report
from .scene import PlanningSceneClient
from .task import PickGlassesTask


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Node("glass_task")

    # Where this run writes its account of itself. The launch makes the folder
    # and has already written what it put on the table, so the two halves —
    # what was there and what the arm made of it — end up in one file.
    node.declare_parameter("report_dir", "")
    folder = node.get_parameter("report_dir").get_parameter_value().string_value
    report = Report(Path(folder), "Picking up glasses") if folder else None
    if report:
        node.get_logger().info(f"writing this run to {report.path}")

    # Everything that subscribes or calls a service is built before the node
    # starts being spun, so the executor sees the full set from its first pass.
    arm = Arm(node)
    task = PickGlassesTask(node, arm, WristCamera(node), PlanningSceneClient(node), report)

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

    threading.Thread(target=spin, daemon=True).start()

    try:
        placed, refused = task.run()
        _report(node, placed, refused)
        if report:
            report.finish(_ending(placed, refused))
    except Exception:
        if report:
            report.trouble("The run stopped here.")
            report.finish("```\n" + traceback.format_exc() + "```")
        raise
    finally:
        executor.shutdown()
        rclpy.shutdown()


def _report(node: Node, placed, refused) -> None:
    """What happened, in both columns.

    The glasses left standing are printed with the same weight as the ones
    racked, because in this task they are the more interesting half. A run that
    racks four glasses and refuses one with a reason is working correctly. A
    run that racks five by ignoring a doubt is the one to worry about.
    """
    log = node.get_logger()
    log.info(f"finished: {len(placed)} racked, {len(refused)} left standing")

    for index, glass in enumerate(placed, start=1):
        log.info(
            f"  {index}. {glass.name}: {glass.kind}, "
            f"{glass.profile.total_height * 1000:.0f} mm tall, "
            f"{glass.profile.max_width * 1000:.0f} mm wide, {glass.mass * 1000:.0f} g, "
            f"held {glass.grip.height * 1000:.0f} mm up, slot {glass.slot}"
            + (" (neighbour left empty)" if glass.needs_gap else "")
        )

    for index, glass in enumerate(refused, start=1):
        log.info(f"  {index}. {glass.name}: left standing, {glass.reason}")


def _ending(placed, refused) -> str:
    """The same two columns the log prints, for the report."""
    lines = [f"**{len(placed)} racked, {len(refused)} left standing.**", ""]
    for glass in placed:
        lines.append(
            f"- `{glass.name}` racked: {glass.kind}, "
            f"{glass.profile.total_height * 1000:.0f} mm tall, "
            f"{glass.profile.max_width * 1000:.0f} mm wide, {glass.mass * 1000:.0f} g, "
            f"slot {glass.slot}"
        )
    for glass in refused:
        lines.append(f"- `{glass.name}` left standing: {glass.reason}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
