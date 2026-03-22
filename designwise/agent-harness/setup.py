from setuptools import setup, find_packages

setup(
    name="cli-anything-designwise",
    version="1.2.0",
    description="DesignWise Squad — 13 AI agents for ZoneWise.AI UI lifecycle",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "cli-anything-designwise=cli_anything.designwise.designwise_cli:main",
        ],
    },
    install_requires=[
        "httpx>=0.24",
        "click>=8.0",
    ],
    extras_require={
        "full": ["playwright", "axe-core-python", "langgraph"],
    },
    python_requires=">=3.10",
)
