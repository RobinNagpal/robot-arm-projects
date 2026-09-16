from glob import glob

from setuptools import find_packages, setup

package_name = "turn_top_flat"

# The robot model and the simulated world carry their own description and
# configuration next to the code that uses them, so the install list is grouped
# the same way.
setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            "share/" + package_name + "/arm",
            glob("turn_top_flat/arm/*.xacro") + glob("turn_top_flat/arm/*.yaml"),
        ),
        ("share/" + package_name + "/arm/camera", glob("turn_top_flat/arm/camera/*.xacro")),
        (
            "share/" + package_name + "/world",
            glob("turn_top_flat/world/*.sdf")
            + glob("turn_top_flat/world/*.yaml")
            + glob("turn_top_flat/world/*.xml")
            + glob("turn_top_flat/world/*.rviz"),
        ),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Robin Nagpal",
    maintainer_email="robinnagpal.tiet@gmail.com",
    description="Lift an upright table top out of its holders and turn it flat in the air.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "turn_top_flat = turn_top_flat.main:main",
        ],
    },
)
