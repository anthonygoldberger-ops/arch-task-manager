#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="arch-task-manager",
    version="1.0.0",
    description="Native high-performance GTK4 system task manager for Arch Linux",
    author="Arch Linux Engineering",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "arch-task = arch_task.main:main",
        ],
    },
    data_files=[
        ("share/applications", ["data/org.arch.ArchTask.desktop"]),
        ("share/icons/hicolor/scalable/apps", ["data/org.arch.ArchTask.svg"]),
    ],
    classifiers=[
        "Environment :: X11 Applications :: GTK",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Monitoring",
    ],
)
