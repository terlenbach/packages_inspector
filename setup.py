import os

from setuptools import find_packages, setup

install_requires = []
if os.path.exists("requirements.txt"):
    with open("requirements.txt") as f:
        install_requires = [line for line in f.read().splitlines() if line[0] != "-"]

setup(
    name="packages_inspector",
    maintainer="Thomas Erlenbach",
    packages=find_packages(),
    install_requires=install_requires,
    python_requires=">=3.8",
    entry_points={"console_scripts": ["packages_inspector = packages_inspector.packages_inspector:main"],},
)
