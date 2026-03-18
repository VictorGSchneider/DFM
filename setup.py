from setuptools import setup, find_packages

setup(
    name="dfm",
    version="2.0.0",
    description="A GUI for managing dotfiles in Arch Linux",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "PyGObject>=3.42.0",
    ],
    entry_points={
        "console_scripts": [
            "dfm=dfm.main:main",
        ],
    },
)
