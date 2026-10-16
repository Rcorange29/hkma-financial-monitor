"""Configuration loading and path helpers (standard library only)."""
from __future__ import annotations

import json
from pathlib import Path

# Project root = parent of the `src` package's parent.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"
EXAMPLE_CONFIG = PROJECT_ROOT / "config.example.json"


def load_config(path: str | Path | None = None) -> dict:
    """Load JSON config.

    Falls back to ``config.example.json`` if the user has not copied it to
    ``config.json`` yet, so the project runs out of the box.
    """
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    if not cfg_path.exists():
        cfg_path = EXAMPLE_CONFIG
    with cfg_path.open("r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    return cfg


def resolve(cfg: dict, relative: str) -> Path:
    """Resolve a config-relative path against the project root."""
    p = Path(relative)
    return p if p.is_absolute() else PROJECT_ROOT / p


def db_path(cfg: dict) -> Path:
    return resolve(cfg, cfg["paths"]["database"])


def raw_dir(cfg: dict) -> Path:
    return resolve(cfg, cfg["paths"]["raw_dir"])
