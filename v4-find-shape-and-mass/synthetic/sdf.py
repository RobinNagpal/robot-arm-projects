"""A scene written out as the models Gazebo is asked to create.

Everything is static, with no collision shapes. Nothing in a picture needs to
fall or push, and a static model is drawn exactly where it is put, which is
what the labels depend on.

Each block carries a label number, starting at 1, which the segmentation
camera paints into every pixel the block covers. That number is how a pixel
in the mask is traced back to a block, and so to its class. The table, the
floor and the distractors carry no label, so their pixels read 0.
"""

from __future__ import annotations

from pathlib import Path

from .randomization import FLOOR_HEIGHT, TABLE_SIZE, TABLE_THICKNESS, Block, Colour, Distractor, Surface

# Every model's name ends in the number of the scene it belongs to. Gazebo
# refuses a model whose name is already taken, and the last scene's models
# may not be gone yet when this scene's are created; see gazebo.py.


def table_name(scene: int) -> str:
    return f"table_{scene}"


def floor_name(scene: int) -> str:
    return f"floor_{scene}"


def block_name(scene: int, index: int) -> str:
    return f"block_{scene}_{index}"


def distractor_name(scene: int, index: int) -> str:
    return f"distractor_{scene}_{index}"


def block_label(index: int) -> int:
    """The number block ``index`` paints into the mask. 0 is left for everything else."""
    return index + 1


def block_sdf(block: Block, scene: int, index: int) -> str:
    x, y = block.position
    corners = "".join(f"<point>{px:.5f} {py:.5f}</point>" for px, py in block.outline)
    if block.on_edge:
        # The outline is drawn upright in its own x-z plane: roll a quarter
        # turn so its y becomes up, and centre the thickness on the spot.
        pose = f"{x:.5f} {y:.5f} 0 1.5707963 0 {block.yaw:.5f}"
        visual_pose = f"0 0 {-block.thickness / 2:.5f} 0 0 0"
    else:
        pose = f"{x:.5f} {y:.5f} 0 0 0 {block.yaw:.5f}"
        visual_pose = "0 0 0 0 0 0"
    # A polyline is pushed up from its own z = 0 to the height given.
    return _model(
        block_name(scene, index),
        pose,
        f"""<visual name="visual">
          <pose>{visual_pose}</pose>
          <geometry><polyline>{corners}<height>{block.thickness:.5f}</height></polyline></geometry>
          {_material(block.colour, block.shininess)}
          <plugin filename="gz-sim-label-system" name="gz::sim::systems::Label">
            <label>{block_label(index)}</label>
          </plugin>
        </visual>""",
    )


def distractor_sdf(distractor: Distractor, scene: int, index: int) -> str:
    x, y = distractor.position
    a, b, c = distractor.dimensions
    if distractor.kind == "sphere":
        geometry, pose = f"<sphere><radius>{a:.5f}</radius></sphere>", f"{x:.5f} {y:.5f} {a:.5f} 0 0 0"
    elif distractor.kind == "capsule":
        geometry = f"<capsule><radius>{a:.5f}</radius><length>{c:.5f}</length></capsule>"
        pose = f"{x:.5f} {y:.5f} {a:.5f} 1.5707963 0 {distractor.yaw:.5f}"  # lying down
    else:
        geometry = f"<ellipsoid><radii>{a:.5f} {b:.5f} {c:.5f}</radii></ellipsoid>"
        pose = f"{x:.5f} {y:.5f} {c:.5f} 0 0 {distractor.yaw:.5f}"
    return _model(
        distractor_name(scene, index),
        pose,
        f"""<visual name="visual">
          <geometry>{geometry}</geometry>
          {_material(distractor.colour, 0.3)}
        </visual>""",
    )


def table_sdf(surface: Surface, texture: Path | None, scene: int) -> str:
    length, width = TABLE_SIZE
    return _model(
        table_name(scene),
        f"0 0 {-TABLE_THICKNESS / 2:.4f} 0 0 0",
        f"""<visual name="visual">
          <geometry><box><size>{length} {width} {TABLE_THICKNESS}</size></box></geometry>
          {_surface_material(surface, texture)}
        </visual>""",
    )


def floor_sdf(surface: Surface, texture: Path | None, scene: int) -> str:
    return _model(
        floor_name(scene),
        f"0 0 {FLOOR_HEIGHT} 0 0 0",
        f"""<visual name="visual">
          <geometry><plane><normal>0 0 1</normal><size>8 8</size></plane></geometry>
          {_surface_material(surface, texture)}
        </visual>""",
    )


def _model(name: str, pose: str, visual: str) -> str:
    return f"""<?xml version="1.0"?>
<sdf version="1.9">
  <model name="{name}">
    <static>true</static>
    <pose>{pose}</pose>
    <link name="link">
        {visual}
    </link>
  </model>
</sdf>"""


def _material(colour: Colour, shininess: float) -> str:
    r, g, b = colour
    return f"""<material>
            <ambient>{r:.3f} {g:.3f} {b:.3f} 1</ambient>
            <diffuse>{r:.3f} {g:.3f} {b:.3f} 1</diffuse>
            <specular>{shininess:.3f} {shininess:.3f} {shininess:.3f} 1</specular>
          </material>"""


def _surface_material(surface: Surface, texture: Path | None) -> str:
    if texture is None:
        return _material(surface.colour, 0.05)
    return f"""<material>
            <ambient>1 1 1 1</ambient>
            <diffuse>1 1 1 1</diffuse>
            <specular>0.1 0.1 0.1 1</specular>
            <pbr><metal><albedo_map>{texture}</albedo_map><roughness>0.9</roughness><metalness>0</metalness></metal></pbr>
          </material>"""
