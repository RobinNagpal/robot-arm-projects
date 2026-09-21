from glob import glob

from setuptools import find_packages, setup

package_name = "work_cell"

# Each subject folder carries its own description and configuration next to the
# code that uses it, so the install list is grouped the same way.
#
# The glasses folder ships one SDF template and no meshes. That is not an
# oversight: no two glasses in a run are the same size, so their meshes are
# made when the world is built and written to a temporary directory. A mesh
# shipped with the project would be a glass whose size somebody wrote down.
setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/arm", glob("work_cell/arm/*.xacro") + glob("work_cell/arm/*.yaml")),
        ("share/" + package_name + "/arm/camera", glob("work_cell/arm/camera/*.xacro")),
        ("share/" + package_name + "/table", glob("work_cell/table/*.sdf")),
        ("share/" + package_name + "/glasses", glob("work_cell/glasses/*.sdf")),
        ("share/" + package_name + "/rack", glob("work_cell/rack/*.sdf")),
        (
            "share/" + package_name + "/world",
            glob("work_cell/world/*.sdf")
            + glob("work_cell/world/*.yaml")
            + glob("work_cell/world/*.xml")
            + glob("work_cell/world/*.rviz"),
        ),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Robin Nagpal",
    maintainer_email="robinnagpal.tiet@gmail.com",
    description="Measure each glass on a table, pick it up, turn it over and stand it on a rack.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "pick_glasses = work_cell.main:main",
        ],
    },
)
