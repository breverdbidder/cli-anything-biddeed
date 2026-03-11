from setuptools import setup, find_namespace_packages

setup(
    name="cli-anything-auction",
    version="1.0.0",
    description="Auction Analyzer CLI — Agent-native foreclosure intelligence",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "httpx>=0.25.0",
        "python-docx>=1.1.0",
        "cli-anything-shared",
    ],
    entry_points={
        "console_scripts": [
            "cli-anything-auction=cli_anything.auction.auction_cli:main",
        ],
    },
    python_requires=">=3.10",
)
