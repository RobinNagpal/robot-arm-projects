"""Turning the table's measurements into a model the simulator can load.

The table is fixed, so this holds none of its own numbers: the size and the
place it stands come from table/layout.py, which is where everything else in
the project reads them from too. Only the way it is drawn — the legs — is
decided here, because nothing outside the simulator cares about a leg.
"""

from __future__ import annotations

from .layout import TABLE_CENTRE_XY, TABLE_SIZE, TABLE_TOP_Z

# How far a leg stands in from the corner it is under, and how thick it is.
# Both are about how the table looks rather than what it does; the arm never
# touches a leg, and the planning scene is given the top only.
LEG_INSET = 0.07
LEG_THICKNESS = 0.06


def leg_sdf(index: int, x: float, y: float, height: float) -> str:
    """One leg, hanging under the corner at (x, y) in the table's own frame."""
    size = f"{LEG_THICKNESS:.4f} {LEG_THICKNESS:.4f} {height:.4f}"
    return (
        f'        <visual name="leg_{index}"><pose>{x:.4f} {y:.4f} {height / 2.0:.4f} 0 0 0</pose>\n'
        f"          <geometry><box><size>{size}</size></box></geometry>\n"
        f"          <material><ambient>0.3 0.3 0.32 1</ambient>"
        f"<diffuse>0.4 0.4 0.42 1</diffuse></material>\n"
        f"        </visual>"
    )


def table_sdf(template: str) -> str:
    """The whole table, at the size and place table/layout.py gives it.

    ``template`` is table.sdf as it sits on disk; world/build.py reads it,
    because that is the module that knows where the installed files are.
    """
    size_x, size_y, size_z = TABLE_SIZE

    # The top's middle, measured from the floor: the underside of the top is
    # what the legs reach up to.
    leg_height = TABLE_TOP_Z - size_z
    top_z = TABLE_TOP_Z - size_z / 2.0

    corners = [
        (sx * (size_x / 2.0 - LEG_INSET), sy * (size_y / 2.0 - LEG_INSET))
        for sx in (1.0, -1.0)
        for sy in (1.0, -1.0)
    ]

    return template.split("-->\n", 1)[1].format(
        x=TABLE_CENTRE_XY[0],
        y=TABLE_CENTRE_XY[1],
        top_z=top_z,
        size_x=size_x,
        size_y=size_y,
        size_z=size_z,
        legs="\n".join(leg_sdf(index, x, y, leg_height) for index, (x, y) in enumerate(corners)),
    )
