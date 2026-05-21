"""Пути лаунчера (исходники и собранный EXE)."""

from __future__ import annotations

import sys
from pathlib import Path


def launcher_dir() -> Path:
    """Папка с launcher.py или с MinecraftLauncher.exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent
