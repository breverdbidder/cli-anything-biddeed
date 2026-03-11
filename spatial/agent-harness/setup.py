from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-spatial",
    version="1.0.0",
    description="Spatial Conquest CLI — Shapely-powered county zoning assignment",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "httpx>=0.25.0",
        "shapely>=2.0.0",
        "cli-anything-shared",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-spatial=cli_anything.spatial.spatial_cli:main",
        ],
    },
    python_requires=">=3.10",
)
