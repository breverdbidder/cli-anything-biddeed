from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-swimintel",
    version="1.0.0",
    description="SwimIntel CLI — Agent-native competitive swim intelligence pipeline",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "pdfplumber>=0.10.0",
        "cli-anything-shared",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-swimintel=cli_anything.swimintel.swimintel_cli:main",
        ],
    },
    python_requires=">=3.10",
)
