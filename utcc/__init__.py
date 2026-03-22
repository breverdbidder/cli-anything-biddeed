"""
UTCC — Universal Task Coordinator & Classifier
BidDeed.AI / Everest Capital USA

Classifies, registers, dispatches, and tracks agent tasks
across Hetzner, GHA, and Modal compute platforms.
"""

__version__ = "0.1.0"
__author__ = "BidDeed-CI"

from utcc.registry import TaskRegistry
from utcc.classifier import classify_task
from utcc.notifier import TelegramNotifier

__all__ = ["TaskRegistry", "classify_task", "TelegramNotifier"]
