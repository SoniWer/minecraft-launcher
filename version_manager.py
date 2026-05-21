"""Управление установленными версиями в .minecraft/versions."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InstalledVersion:
    version_id: str
    path: Path
    size_mb: float
    version_type: str


def list_installed_versions(minecraft_dir: Path) -> list[InstalledVersion]:
    versions_dir = Path(minecraft_dir) / "versions"
    if not versions_dir.is_dir():
        return []

    result: list[InstalledVersion] = []
    for folder in sorted(versions_dir.iterdir()):
        if not folder.is_dir():
            continue
        jar_path = folder / f"{folder.name}.jar"
        if not jar_path.is_file():
            continue
        size_mb = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / (
            1024 * 1024
        )
        vtype = "?"
        json_path = folder / f"{folder.name}.json"
        if json_path.is_file():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                vtype = str(data.get("type") or "?")
            except (json.JSONDecodeError, OSError):
                pass
        result.append(
            InstalledVersion(
                version_id=folder.name,
                path=folder,
                size_mb=round(size_mb, 1),
                version_type=vtype,
            )
        )
    result.sort(key=lambda v: v.version_id, reverse=True)
    return result


def delete_version(minecraft_dir: Path, version_id: str) -> None:
    folder = Path(minecraft_dir) / "versions" / version_id
    if folder.is_dir():
        shutil.rmtree(folder)
