from setuptools import setup, find_packages

setup(
    name="cli-anything-shared",
    version="1.0.0",
    description="Shared utilities for BidDeed CLI-Anything tools",
    packages=find_packages(),
    install_requires=[
        "supabase>=2.0.0",
        "click>=8.0.0",
    ],
    python_requires=">=3.10",
)
