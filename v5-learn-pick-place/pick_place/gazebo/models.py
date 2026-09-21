"""The Gazebo world for one episode, written as SDF: arm, gripper, camera, table, target and block.

**The arm is built from the MuJoCo model**, so it is the same arm the policy
learned on: each link's pose, mass and inertia, each joint's axis and range,
and the same meshes and collision shapes, read from MuJoCo Menagerie's UR5e.
Its joint controllers copy MuJoCo's actuators: the same stiffness, the same
damping, the same force limits, and gravity switched off on the arm's links,
as MuJoCo's gravity compensation does.

**The arm is built in its home pose.** Gazebo 8 cannot start a joint at a
chosen angle, so the links are placed where they are at ``HOME``, and each
Gazebo joint's zero is the home angle. ``to_gazebo`` and ``from_gazebo``
convert.

**The gripper is not the Robotiq.** The Robotiq 2F-85 is a closed four-bar
linkage on each side, which MuJoCo holds together with constraints and
Gazebo's physics does not handle well. In its place is a plain parallel
gripper with the Robotiq's measurements: pads 22 mm wide and 37.5 mm tall,
opening to 85 mm, at the same distance from the wrist, so the point between
the fingertips is exactly where the policy expects it. Its opening is
reported on the Robotiq's scale (``GRIPPER_READING``), so the policy is
shown the same numbers for the same finger spacing.

**The camera** is where MuJoCo's is, 1 m above the table looking straight
down, with the same field of view and resolution, and a small box drawn
around it so it can be seen.
"""

from __future__ import annotations

import math
from pathlib import Path

import mujoco
import numpy as np

from ..scene import ARM_JOINTS, BlockSpec, build
from ..settings import ARM_XML, CAMERA, HOME, TIMESTEP

WORLD = "pick_place"
ARM = "ur5e"
MESH_DIR = ARM_XML.parent / "assets"

# The Robotiq's reading (driver angle over its range: 0 open, 1 closed) against
# the gap between its pads, in metres, measured in MuJoCo by closing it in
# steps with nothing between the fingers.
GRIPPER_READING = np.array(
    [0.0033, 0.1032, 0.2031, 0.3030, 0.4029, 0.5028, 0.6027, 0.7026, 0.8025, 0.9024, 0.9777]
)
GRIPPER_GAP = np.array(
    [0.08517, 0.07768, 0.06978, 0.06150, 0.05289, 0.04401, 0.03490, 0.02562, 0.01622, 0.00676, 0.0004]
)
OPEN_GAP = float(GRIPPER_GAP[0])

# The pinch point in the wrist 3 link's frame, and its axes there: x across
# the fingers' width, y the direction they close along, z out past the
# fingertips. Measured on the MuJoCo model.
PINCH_IN_WRIST = np.array([0.0, 0.2558, 0.0])
PINCH_AXES_IN_WRIST = np.array([[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])
# The Robotiq's pads, in the pinch frame: 22 mm across, 8 mm thick, and
# reaching from 4.5 mm past the pinch point to 33 mm behind it.
PAD_SIZE = (0.022, 0.008, 0.0375)
PAD_CENTRE_Z = -0.01425
# Where the Robotiq's body starts, in the pinch frame: its mounting face on
# the wrist.
MOUNT_Z = -0.1558
FINGER_MASS = 0.05
# Finger controller: stiff enough to close in about half a second, and a grip
# of at most 20 N per finger, which holds any of the blocks many times over.
FINGER_GAIN = 400.0
FINGER_DAMPING = 8.0
FINGER_FORCE = 20.0

FRICTION = 1.0


def world_sdf(block: BlockSpec, target: tuple[float, float], block_mesh: Path) -> str:
    """The whole world for one episode, as one SDF document."""
    return f"""<?xml version="1.0"?>
<sdf version="1.10">
  <world name="{WORLD}">
    <physics name="default" type="dart">
      <max_step_size>{TIMESTEP / 2}</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>
    <gravity>0 0 -9.81</gravity>
    <scene>
      <ambient>0.5 0.5 0.5 1</ambient>
      <background>0.7 0.75 0.8 1</background>
      <grid>false</grid>
    </scene>
    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 3 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.3 0.2 -1</direction>
    </light>
{gui_sdf()}
{table_sdf()}
{target_sdf(target)}
{camera_sdf()}
{block_sdf(block, block_mesh)}
{arm_sdf()}
  </world>
</sdf>
"""


def gui_sdf() -> str:
    """How Gazebo's window is laid out, when it is opened: the 3D view, the overhead camera's picture, the clock.

    It has no play or pause buttons on purpose. The world is stepped from
    Python in lockstep with the policy; pressing play would let it run on
    its own.
    """
    floating = """<gz-gui>
          <property key="resizable" type="bool">false</property>
          <property key="width" type="double">5</property>
          <property key="height" type="double">5</property>
          <property key="state" type="string">floating</property>
          <property key="showTitleBar" type="bool">false</property>
        </gz-gui>"""
    return f"""    <gui fullscreen="0">
      <plugin filename="MinimalScene" name="3D View">
        <gz-gui>
          <title>3D View</title>
          <property type="bool" key="showTitleBar">false</property>
          <property type="string" key="state">docked</property>
        </gz-gui>
        <engine>ogre2</engine>
        <scene>scene</scene>
        <ambient_light>0.4 0.4 0.4</ambient_light>
        <background_color>0.7 0.75 0.8</background_color>
        <camera_pose>1.5 -0.9 0.9 0 0.51 2.46</camera_pose>
      </plugin>
      <plugin filename="GzSceneManager" name="Scene Manager">{floating}</plugin>
      <plugin filename="InteractiveViewControl" name="Interactive view control">{floating}</plugin>
      <plugin filename="CameraTracking" name="Camera Tracking">{floating}</plugin>
      <plugin filename="MarkerManager" name="Marker manager">{floating}</plugin>
      <plugin filename="ImageDisplay" name="Overhead camera">
        <gz-gui>
          <title>Overhead camera: what the geometry sees</title>
          <property type="string" key="state">docked</property>
        </gz-gui>
        <topic>overhead/image</topic>
        <topic_picker>false</topic_picker>
      </plugin>
      <plugin filename="WorldStats" name="World stats">
        <gz-gui>
          <title>World stats</title>
          <property type="bool" key="showTitleBar">false</property>
          <property type="bool" key="resizable">false</property>
          <property type="double" key="height">110</property>
          <property type="double" key="width">290</property>
          <property type="double" key="z">1</property>
          <property type="string" key="state">floating</property>
          <anchors target="3D View">
            <line own="right" target="right"/>
            <line own="bottom" target="bottom"/>
          </anchors>
        </gz-gui>
        <sim_time>true</sim_time>
        <real_time>true</real_time>
        <real_time_factor>true</real_time_factor>
        <iterations>false</iterations>
      </plugin>
    </gui>"""


def table_sdf() -> str:
    return f"""    <model name="table">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal><size>3 3</size></plane></geometry>
          <surface><friction><ode><mu>{FRICTION}</mu><mu2>{FRICTION}</mu2></ode></friction></surface>
        </collision>
        <visual name="visual">
          <geometry><plane><normal>0 0 1</normal><size>3 3</size></plane></geometry>
          <material><ambient>0.55 0.5 0.45 1</ambient><diffuse>0.55 0.5 0.45 1</diffuse></material>
        </visual>
      </link>
    </model>"""


def target_sdf(target: tuple[float, float]) -> str:
    """The red disc: drawn only, and too thin for the depth camera to see."""
    return f"""    <model name="target">
      <static>true</static>
      <pose>{target[0]} {target[1]} 0.0005 0 0 0</pose>
      <link name="link">
        <visual name="visual">
          <geometry><cylinder><radius>0.02</radius><length>0.001</length></cylinder></geometry>
          <material><ambient>0.85 0.1 0.1 1</ambient><diffuse>0.85 0.1 0.1 1</diffuse></material>
        </visual>
      </link>
    </model>"""


def camera_sdf() -> str:
    """The overhead depth camera, and a box drawn around it.

    A Gazebo camera looks along its own x, with the picture's up along its z.
    Pitched down a quarter turn, it looks straight down with the top of the
    picture towards +x; turned a further quarter turn about the vertical, the
    top is towards +y and the right towards +x, as MuJoCo's camera has them.
    """
    x, y, z = CAMERA.pos
    aspect = CAMERA.width / CAMERA.height
    hfov = 2 * math.atan(math.tan(math.radians(CAMERA.fovy) / 2) * aspect)
    return f"""    <model name="overhead_camera">
      <static>true</static>
      <pose>{x} {y} {z} 0 {math.pi / 2} {math.pi / 2}</pose>
      <link name="link">
        <visual name="body">
          <pose>-0.03 0 0 0 0 0</pose>
          <geometry><box><size>0.06 0.1 0.04</size></box></geometry>
          <material><ambient>0.1 0.1 0.12 1</ambient><diffuse>0.1 0.1 0.12 1</diffuse></material>
        </visual>
        <visual name="lens">
          <pose>0.003 0 0 0 {math.pi / 2} 0</pose>
          <geometry><cylinder><radius>0.012</radius><length>0.006</length></cylinder></geometry>
          <material><ambient>0.2 0.3 0.6 1</ambient><diffuse>0.2 0.3 0.6 1</diffuse></material>
        </visual>
        <sensor name="depth" type="depth_camera">
          <topic>overhead/depth</topic>
          <update_rate>5</update_rate>
          <camera>
            <horizontal_fov>{hfov}</horizontal_fov>
            <image><width>{CAMERA.width}</width><height>{CAMERA.height}</height><format>R_FLOAT32</format></image>
            <clip><near>0.1</near><far>3.0</far></clip>
          </camera>
        </sensor>
        <sensor name="colour" type="camera">
          <topic>overhead/image</topic>
          <update_rate>5</update_rate>
          <camera>
            <horizontal_fov>{hfov}</horizontal_fov>
            <image><width>{CAMERA.width}</width><height>{CAMERA.height}</height></image>
            <clip><near>0.1</near><far>3.0</far></clip>
          </camera>
        </sensor>
      </link>
    </model>"""


def block_sdf(block: BlockSpec, mesh: Path) -> str:
    """The block, with the mass and inertia MuJoCo computes for the same shape."""
    model = build(block, (0.0, -0.2))
    body = model.body("block").id
    mass = float(model.body_mass[body])
    com = model.body_ipos[body]
    inertia = rotated_inertia(model.body_inertia[body], model.body_iquat[body])
    r, g, b, a = block.rgba
    uri = mesh.resolve().as_uri()
    return f"""    <model name="block">
      <pose>{block.x} {block.y} 0 0 0 {block.yaw}</pose>
      <plugin filename="gz-sim-pose-publisher-system" name="gz::sim::systems::PosePublisher">
        <publish_link_pose>false</publish_link_pose>
        <publish_model_pose>true</publish_model_pose>
        <publish_nested_model_pose>false</publish_nested_model_pose>
        <use_pose_vector_msg>false</use_pose_vector_msg>
        <update_frequency>-1</update_frequency>
      </plugin>
      <link name="link">
        {inertial_sdf(mass, com, inertia)}
        <collision name="collision">
          <geometry><mesh><uri>{uri}</uri></mesh></geometry>
          <surface><friction><ode><mu>{FRICTION}</mu><mu2>{FRICTION}</mu2></ode></friction></surface>
        </collision>
        <visual name="visual">
          <geometry><mesh><uri>{uri}</uri></mesh></geometry>
          <material><ambient>{r} {g} {b} {a}</ambient><diffuse>{r} {g} {b} {a}</diffuse></material>
        </visual>
      </link>
    </model>"""


def write_block_mesh(block: BlockSpec, path: Path) -> Path:
    """The block's outline pushed up into a solid, as an OBJ file, in the block's own frame.

    Every face carries its own outward normal: Gazebo's physics drops a mesh
    without normals, and then crashes on the first step it would have collided.
    """
    n = len(block.outline)
    lines = [f"v {x} {y} 0" for x, y in block.outline] + [
        f"v {x} {y} {block.thickness}" for x, y in block.outline
    ]
    lines += ["vn 0 0 1", "vn 0 0 -1"]
    # OBJ counts from 1. The outline runs anticlockwise seen from above, so
    # the top keeps that order and the bottom is reversed, both facing out.
    faces = []
    for i in range(1, n - 1):
        faces.append(f"f {n + 1}//1 {n + 1 + i}//1 {n + 2 + i}//1")
        faces.append(f"f 1//2 {i + 2}//2 {i + 1}//2")
    for i in range(n):
        j = (i + 1) % n
        (x0, y0), (x1, y1) = block.outline[i], block.outline[j]
        length = math.hypot(x1 - x0, y1 - y0)
        lines.append(f"vn {(y1 - y0) / length} {-(x1 - x0) / length} 0")
        k = 3 + i
        faces.append(f"f {i + 1}//{k} {j + 1}//{k} {n + j + 1}//{k}")
        faces.append(f"f {i + 1}//{k} {n + j + 1}//{k} {n + i + 1}//{k}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines + faces) + "\n")
    return path


def arm_sdf() -> str:
    """The UR5e and the gripper, as one model fixed to the table, with its controllers."""
    spec = mujoco.MjSpec.from_file(str(ARM_XML))
    model = spec.compile()
    data = mujoco.MjData(model)
    data.qpos[[model.joint(n).qposadr[0] for n in ARM_JOINTS]] = HOME
    mujoco.mj_kinematics(model, data)
    materials = {m.name: m.rgba for m in spec.materials}

    links, joints, plugins = [], [], []
    for body in spec.bodies:
        if body.name == "world":
            continue
        b = model.body(body.name).id
        pose = pose_text(data.xpos[b], data.xmat[b].reshape(3, 3))
        inertia = rotated_inertia(model.body_inertia[b], model.body_iquat[b])
        parts = [inertial_sdf(model.body_mass[b], model.body_ipos[b], inertia + armature(model, b))]
        for k, geom in enumerate(body.geoms):
            local = pose_text(geom.pos, quat_to_matrix(geom.quat))
            if geom.type == mujoco.mjtGeom.mjGEOM_MESH:
                r, g, bl, a = materials[geom.material]
                uri = (MESH_DIR / f"{geom.meshname}.obj").resolve().as_uri()
                parts.append(
                    f"""<visual name="visual_{k}"><pose>{local}</pose>
          <geometry><mesh><uri>{uri}</uri></mesh></geometry>
          <material><ambient>{r} {g} {bl} {a}</ambient><diffuse>{r} {g} {bl} {a}</diffuse></material>
        </visual>"""
                )
            else:
                shape = "capsule" if geom.type == mujoco.mjtGeom.mjGEOM_CAPSULE else "cylinder"
                radius, half = geom.size[0], geom.size[1]
                parts.append(
                    f"""<collision name="collision_{k}"><pose>{local}</pose>
          <geometry><{shape}><radius>{radius}</radius><length>{2 * half}</length></{shape}></geometry>
        </collision>"""
                )
        links.append(link_sdf(body.name, pose, parts))
        for joint in body.joints:
            j = model.joint(joint.name).id
            actuator = next(a for a in range(model.nu) if model.actuator_trnid[a, 0] == j)
            kp = model.actuator_gainprm[actuator, 0]
            kv = -model.actuator_biasprm[actuator, 2]
            force = model.actuator_forcerange[actuator, 1]
            home = HOME[ARM_JOINTS.index(joint.name)]
            lower, upper = model.jnt_range[j] - home
            axis = " ".join(f"{v:.6g}" for v in model.jnt_axis[j])
            joints.append(
                f"""    <joint name="{joint.name}" type="revolute">
      <parent>{body.parent.name}</parent>
      <child>{body.name}</child>
      <axis>
        <xyz>{axis}</xyz>
        <limit><lower>{lower}</lower><upper>{upper}</upper><effort>{force}</effort></limit>
      </axis>
    </joint>"""
            )
            plugins.append(position_controller(joint.name, kp, kv, force))

    gripper_links, gripper_joints = gripper_sdf(model, data)
    links += gripper_links
    joints += gripper_joints
    for side in ("left", "right"):
        plugins.append(position_controller(f"{side}_finger_joint", FINGER_GAIN, FINGER_DAMPING, FINGER_FORCE))

    return f"""    <model name="{ARM}">
    <joint name="bolted" type="fixed"><parent>world</parent><child>base</child></joint>
{chr(10).join(links)}
{chr(10).join(joints)}
    <plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher"/>
{chr(10).join(plugins)}
    </model>"""


def gripper_sdf(model: mujoco.MjModel, data: mujoco.MjData) -> tuple[list[str], list[str]]:
    """The parallel gripper, built in the pinch frame and placed on the wrist."""
    w = model.body("wrist_3_link").id
    wrist_rot = data.xmat[w].reshape(3, 3)
    pinch_rot = wrist_rot @ PINCH_AXES_IN_WRIST
    pinch_pos = data.xpos[w] + wrist_rot @ PINCH_IN_WRIST

    def at(local: tuple[float, float, float]) -> str:
        return pose_text(pinch_pos + pinch_rot @ np.array(local), pinch_rot)

    # The housing runs from the wrist's mounting face to where the pads begin.
    pads_top = PAD_CENTRE_Z - PAD_SIZE[2] / 2
    body_length = pads_top - MOUNT_Z
    palm_z = MOUNT_Z + body_length / 2
    links = [
        link_sdf(
            "gripper_body",
            at((0.0, 0.0, palm_z)),
            [
                inertial_sdf(0.8, np.zeros(3), np.diag([6e-4, 6e-4, 4e-4])),
                f"""<visual name="housing"><geometry><box><size>0.06 0.1 {body_length:.4f}</size></box></geometry>
          <material><ambient>0.15 0.15 0.15 1</ambient><diffuse>0.15 0.15 0.15 1</diffuse></material></visual>""",
                f"""<collision name="housing_collision"><geometry><box><size>0.06 0.1 {body_length:.4f}</size></box></geometry></collision>""",
            ],
        )
    ]
    joints = [
        """    <joint name="gripper_mount" type="fixed"><parent>wrist_3_link</parent><child>gripper_body</child></joint>"""
    ]
    pad = " ".join(str(v) for v in PAD_SIZE)
    for side, sign in (("left", -1.0), ("right", 1.0)):
        y = sign * (OPEN_GAP / 2 + PAD_SIZE[1] / 2)
        links.append(
            link_sdf(
                f"{side}_finger",
                at((0.0, y, PAD_CENTRE_Z)),
                [
                    inertial_sdf(FINGER_MASS, np.zeros(3), np.diag([1e-5, 1e-5, 1e-5])),
                    f"""<visual name="pad"><geometry><box><size>{pad}</size></box></geometry>
          <material><ambient>0.3 0.3 0.3 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material></visual>""",
                    f"""<collision name="pad_collision"><geometry><box><size>{pad}</size></box></geometry>
          <surface><friction><ode><mu>{FRICTION}</mu><mu2>{FRICTION}</mu2></ode></friction></surface>
        </collision>""",
                ],
            )
        )
        # Positive is closing: towards the other finger.
        joints.append(
            f"""    <joint name="{side}_finger_joint" type="prismatic">
      <parent>gripper_body</parent>
      <child>{side}_finger</child>
      <axis>
        <xyz>0 {-sign} 0</xyz>
        <limit><lower>0</lower><upper>{OPEN_GAP / 2}</upper><effort>{FINGER_FORCE}</effort></limit>
      </axis>
    </joint>"""
        )
    return links, joints


def link_sdf(name: str, pose: str, parts: list[str]) -> str:
    body = "\n        ".join(parts)
    # Gravity off, as MuJoCo's gravity compensation: a real UR controller
    # cancels the arm's weight itself.
    return f"""    <link name="{name}">
      <pose>{pose}</pose>
      <gravity>false</gravity>
        {body}
    </link>"""


def position_controller(joint: str, gain: float, damping: float, force: float) -> str:
    """A position controller with MuJoCo's stiffness, damping and force limit.

    MuJoCo's actuator pushes with gain × (target − angle) − damping × speed,
    and limits the total. Gazebo's controller damps the error's rate of
    change instead of the speed. The two are the same while the target holds
    still, and differ by a brief push towards the new target, capped at the
    force limit for one physics step, each time the target moves. Damping the
    joint itself instead would sit outside the force limit and cap the arm's
    speed at a fraction of what the policy asks for.
    """
    return f"""    <plugin filename="gz-sim-joint-position-controller-system" name="gz::sim::systems::JointPositionController">
      <joint_name>{joint}</joint_name>
      <topic>/{ARM}/{joint}/command</topic>
      <p_gain>{gain}</p_gain>
      <i_gain>0</i_gain>
      <d_gain>{damping}</d_gain>
      <cmd_max>{force}</cmd_max>
      <cmd_min>{-force}</cmd_min>
    </plugin>"""


def inertial_sdf(mass: float, com: np.ndarray, inertia: np.ndarray) -> str:
    i = inertia
    return f"""<inertial>
          <pose>{com[0]} {com[1]} {com[2]} 0 0 0</pose>
          <mass>{mass}</mass>
          <inertia><ixx>{i[0, 0]}</ixx><ixy>{i[0, 1]}</ixy><ixz>{i[0, 2]}</ixz><iyy>{i[1, 1]}</iyy><iyz>{i[1, 2]}</iyz><izz>{i[2, 2]}</izz></inertia>
        </inertial>"""


def armature(model: mujoco.MjModel, body: int) -> np.ndarray:
    """MuJoCo's armature, the motor's own inertia, as extra link inertia about the joint's axis.

    SDF has no armature. Leaving it out makes the wrist links, which weigh
    little, far quicker than in MuJoCo, and too stiff to simulate stably.

    Added about one axis alone, it would make the inertia impossible for a
    real body (no axis may exceed the other two together), and Gazebo refuses
    it. Half as much about each of the other two axes is the least that
    keeps it possible.
    """
    extra = np.zeros((3, 3))
    for j in range(model.njnt):
        if model.jnt_bodyid[j] == body and model.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE:
            axis = model.jnt_axis[j]
            along = np.outer(axis, axis)
            a = model.dof_armature[model.jnt_dofadr[j]]
            extra += a * along + (a / 2) * (np.eye(3) - along)
    return extra


def rotated_inertia(principal: np.ndarray, quat: np.ndarray) -> np.ndarray:
    rot = quat_to_matrix(quat)
    return rot @ np.diag(principal) @ rot.T


def quat_to_matrix(quat) -> np.ndarray:
    q = np.asarray(quat, dtype=float)
    q = q / np.linalg.norm(q)
    mat = np.zeros(9)
    mujoco.mju_quat2Mat(mat, q)
    return mat.reshape(3, 3)


def pose_text(pos, rot: np.ndarray) -> str:
    """An SDF pose, "x y z roll pitch yaw", for a rotation matrix."""
    roll = math.atan2(rot[2, 1], rot[2, 2])
    pitch = math.asin(-max(-1.0, min(1.0, rot[2, 0])))
    yaw = math.atan2(rot[1, 0], rot[0, 0])
    return " ".join(f"{v:.9g}" for v in (*pos, roll, pitch, yaw))


def to_gazebo(angles) -> np.ndarray:
    """Arm joint angles as the policy knows them, as Gazebo's, whose zero is the home pose."""
    return np.asarray(angles) - np.asarray(HOME)


def from_gazebo(angles) -> np.ndarray:
    return np.asarray(angles) + np.asarray(HOME)


FINGER_JOINTS = ("left_finger_joint", "right_finger_joint")


def reading_from_gap(gap: float) -> float:
    """The Robotiq's reading for a gap between the pads, 0 open to 1 closed."""
    return float(np.interp(gap, GRIPPER_GAP[::-1], GRIPPER_READING[::-1]))


def gap_for_command(command: float) -> float:
    """The gap the Robotiq closes to for a command from 0 (open) to 1 (closed), with nothing between."""
    return float(np.interp(command, GRIPPER_READING, GRIPPER_GAP))
