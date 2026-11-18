"""Project paths and settings. Secrets (API keys) come from environment variables, never code."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"


def get_env(name: str, default: str | None = None) -> str | None:
    """Read a setting from the environment (e.g. a data provider API key)."""
    return os.environ.get(name, default)
