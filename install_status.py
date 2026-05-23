"""Статус установки Minecraft и мод-загрузчика в общей папке versions."""

from __future__ import annotations

from pathlib import Path

import minecraft_launcher_lib


def minecraft_installed(shared_dir: Path | str, mc_version: str) -> bool:
    if not mc_version.strip():
        return False
    try:
        return bool(
            minecraft_launcher_lib.utils.is_version_valid(mc_version.strip(), str(shared_dir))
        )
    except Exception:
        return False


def loader_installation_label(
    shared_dir: Path | str,
    *,
    loader_id: str,
    mc_version: str,
    loader_version: str,
) -> str:
    if loader_id == "vanilla":
        return ""
    lv = loader_version.strip()
    if not lv:
        return "загрузчик: выберите версию"
    if _loader_version_installed(Path(shared_dir), mc_version, lv):
        return f"загрузчик {lv} ✓"
    return f"загрузчик {lv} — установится при запуске"


def _loader_version_installed(shared_dir: Path, mc_version: str, loader_version: str) -> bool:
    versions = shared_dir / "versions"
    if not versions.is_dir():
        return False
    mc_low = mc_version.lower()
    lv_low = loader_version.lower()
    for entry in versions.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name.lower()
        if mc_low in name and lv_low in name:
            if (entry / f"{entry.name}.json").is_file():
                return True
    return False


def format_install_status(
    shared_dir: Path | str,
    *,
    mc_version: str,
    loader_id: str,
    loader_version: str,
) -> str:
    mc = mc_version.strip()
    if not mc:
        return "Установка: выберите версию Minecraft"
    mc_part = f"Minecraft {mc} ✓" if minecraft_installed(shared_dir, mc) else (
        f"Minecraft {mc} — скачается при запуске"
    )
    loader_part = loader_installation_label(
        shared_dir,
        loader_id=loader_id,
        mc_version=mc,
        loader_version=loader_version,
    )
    if loader_part:
        return f"Установка: {mc_part} · {loader_part}"
    return f"Установка: {mc_part}"
