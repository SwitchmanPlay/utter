"""Filesystem locations. Everything user-specific lives under %APPDATA%\\Utter on Windows."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from utter import APP_NAME


def app_data_dir() -> Path:
    override = os.environ.get("UTTER_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME.lower()
    base.mkdir(parents=True, exist_ok=True)
    return base


def models_dir() -> Path:
    d = app_data_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def settings_file() -> Path:
    return app_data_dir() / "settings.json"


def log_file() -> Path:
    return app_data_dir() / "utter.log"


def resource_path(*parts: str) -> Path:
    """Locate bundled assets both in dev checkout and inside a PyInstaller build."""
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS).joinpath(*parts)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2].joinpath(*parts)
