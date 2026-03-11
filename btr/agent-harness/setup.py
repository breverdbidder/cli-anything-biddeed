from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-btr",
    version="0.1.0",
    description="BidDeed.AI BTR Squad — Build-to-Rent + Distressed Asset AI Agents",
    packages=find_namespace_packages(),
    python_requires=">=3.11",
    install_requires=[
        "click>=8.0",
        "rich>=13.0",
        "httpx>=0.25",
        "pydantic>=2.0",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-btr=cli_anything.btr.btr_cli:cli",
        ]
    },
)
