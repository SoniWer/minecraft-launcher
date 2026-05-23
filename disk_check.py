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


def estimate_modpack_need_gb(version_files: list[dict] | None = None) -> float:
    """Оценка места под .mrpack и распаковку modpack."""
    total_bytes = 0
    for info in version_files or []:
        try:
            total_bytes += int(info.get("size") or 0)
        except (TypeError, ValueError):
            continue
    if total_bytes <= 0:
        return 4.0
    return max(3.0, (total_bytes / (1024**3)) * 2.2 + 1.0)


def check_disk_space(path: Path, need_gb: float) -> tuple[bool, str]:
    free = free_gb(path)
    if free >= need_gb:
        return True, ""
    return False, format_disk_warning(path, need_gb, free)


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
