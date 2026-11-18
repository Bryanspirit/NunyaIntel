"""Project paths and settings. Secrets (API keys) come from environment variables, never code."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
WEB_DIR = PROJECT_ROOT / "web"  # React source (Vite)
WEB_DIST = WEB_DIR / "dist"  # built app, served by `nunyaintel serve`


def get_env(name: str, default: str | None = None) -> str | None:
    """Read a setting from the environment (e.g. a data provider API key)."""
    return os.environ.get(name, default)


def stl_data_dir() -> Path:
    """Location of the hackathon GRID data repo (a separate clone, never inside this project).

    Override with the STL_DATA_DIR environment variable.
    """
    default = PROJECT_ROOT.parent / "stl-hackathon-2026-grid-starter"
    return Path(get_env("STL_DATA_DIR") or default)
