"""Открытие логов и crash-reports сборки."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def latest_log(game_dir: Path) -> Path | None:
    path = game_dir / "logs" / "latest.log"
    return path if path.is_file() else None


def latest_crash_report(game_dir: Path) -> Path | None:
    folder = game_dir / "crash-reports"
    if not folder.is_dir():
        return None
    reports = [p for p in folder.glob("*.txt") if p.is_file()]
    if not reports:
        return None
    return max(reports, key=lambda p: p.stat().st_mtime)


def open_file(path: Path) -> None:
    target = path.resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Файл не найден: {target}")
    if sys.platform == "win32":
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", target], check=False)
    else:
        subprocess.run(["xdg-open", target], check=False)
