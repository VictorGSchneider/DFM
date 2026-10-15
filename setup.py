import re
from pathlib import Path

from setuptools import setup, find_packages

# Read the version without importing the package (that would need GTK)
VERSION = re.search(
    r'^__version__ = "([^"]+)"', Path(__file__).with_name("dfm").joinpath("__init__.py").read_text(),
    re.MULTILINE,
).group(1)

setup(
    name="dfm",
    version=VERSION,
    description="A GUI for managing dotfiles on Linux",
    long_description=Path(__file__).with_name("README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    url="https://github.com/VictorGSchneider/DFM",
    license="GPL-3.0-or-later",
    packages=find_packages(include=["dfm", "dfm.*"]),
    python_requires=">=3.10",
    install_requires=[
        "PyGObject>=3.42.0",
        "PyYAML>=6.0",
        'tomli>=1.2; python_version < "3.11"',
    ],
    entry_points={
        "console_scripts": [
            "dfm=dfm.cli:main",
        ],
    },
)
