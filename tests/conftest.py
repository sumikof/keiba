"""Pytest configuration: make scraper scripts importable in tests."""
import sys
import os

_SCRIPTS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    ".claude",
    "skills",
    "netkeiba-scraper",
    "scripts",
)
sys.path.insert(0, os.path.abspath(_SCRIPTS_DIR))
