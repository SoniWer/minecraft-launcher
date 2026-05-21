"""Проверка свободного места на диске перед скачиванием."""

from __future__ import annotations

import shutil
from pathlib import Path


def free_gb(path: Path) -> float:
    usage = shutil.disk_usage(path.resolve())
    return usage.free / (1024**3)


def format_disk_warning(path: Path, need_gb: float, free: float) -> str:
    return (
        f"Мало места на диске ({path.drive or path.anchor}).\n"
        f"Нужно примерно {need_gb:.1f} ГБ, свободно {free:.1f} ГБ.\n\n"
        "Освободите место или выберите другую папку для Minecraft."
    )


def needs_download_warning(
    *,
    version_installed: bool,
    loader_id: str,
) -> tuple[float, str] | None:
    """Вернуть (нужно_ГБ, причина) если стоит предупредить о месте."""
    if version_installed and loader_id == "vanilla":
        return None
    if not version_installed:
        return (2.0, "установка Minecraft")
    if loader_id != "vanilla":
        return (1.5, "установка мод-загрузчика")
    return None
