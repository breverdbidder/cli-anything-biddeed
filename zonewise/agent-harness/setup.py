from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-zonewise",
    version="1.0.0",
    description="ZoneWise Scraper CLI — Agent-native zoning data pipeline",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "httpx>=0.25.0",
        "cli-anything-shared",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-zonewise=cli_anything.zonewise.zonewise_cli:main",
        ],
    },
    python_requires=">=3.10",
)
