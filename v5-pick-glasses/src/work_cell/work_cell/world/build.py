"""Putting the world file together.

The room, the lighting and the ground never change, and they live in
``cell.sdf``. The table never changes either, and it lives in
``table/table.sdf``. The rack is fixed in shape but not in position. The
glasses change completely every run.

Rather than have four files that must agree, or one file edited by hand before
each run, the world is assembled here: the fixed parts are read from disk and
the rest is dropped into the marker lines ``cell.sdf`` leaves for them. What
comes out is a complete world file written to a temporary path, which is what
Gazebo is started on.

The glass meshes are written out at the same time, one per glass, because no
two glasses in a run are the same size and so none of them can be a file
shipped with the project.
"""

from __future__ import annotations

from pathlib import Path

from ..glasses.spawn import SpawnedGlass, glass_sdf, write_mesh
from ..rack.build import rack_sdf

TABLE_MARKER = "<!-- TABLE -->"
RACK_MARKER = "<!-- RACK -->"
GLASSES_MARKER = "<!-- GLASSES -->"


def build_world(
    world_template: str,
    table: str,
    rack_pose: tuple[float, float, float],
    glasses: list[SpawnedGlass],
    mesh_dir: Path,
) -> str:
    """The finished world: the room, with the table, rack and glasses in it."""
    for marker in (TABLE_MARKER, RACK_MARKER, GLASSES_MARKER):
        if marker not in world_template:
            raise ValueError(f"the world template has no {marker} line to fill in")

    models = []
    for glass in glasses:
        mesh_path = write_mesh(glass.outline, mesh_dir / f"{glass.name}.stl")
        models.append(glass_sdf(glass, mesh_uri=f"file://{mesh_path}"))

    filled = world_template.replace(TABLE_MARKER, table)
    filled = filled.replace(RACK_MARKER, rack_sdf(*rack_pose))
    return filled.replace(GLASSES_MARKER, "".join(models))


def read_parts(share: Path) -> tuple[str, str]:
    """The two fixed pieces of the world, as they sit on disk."""
    return (share / "world" / "cell.sdf").read_text(), (share / "table" / "table.sdf").read_text()
