"""Управление сборками (изолированные моды, миры, конфиг)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

BUILDS_DIR_NAME = "builds"
PROFILE_NAME = "profile.json"

GAME_SUBDIRS = (
    "mods",
    "saves",
    "config",
    "resourcepacks",
    "shaderpacks",
    "screenshots",
    "logs",
)


@dataclass
class Build:
    id: str
    name: str
    username: str = "Player"
    mc_version: str = ""
    loader: str = "vanilla"
    loader_version: str = ""
    ram_gb: int = 4
    version_filter: str = "release"
    edition: str = "java"
    java_path: str = ""
    jvm_args: str = ""
    play_time_seconds: int = 0
    launch_count: int = 0

    def root(self, launcher_dir: Path) -> Path:
        return builds_root(launcher_dir) / self.id

    def game_dir(self, launcher_dir: Path) -> Path:
        return self.root(launcher_dir) / "game"

    def profile_path(self, launcher_dir: Path) -> Path:
        return self.root(launcher_dir) / PROFILE_NAME

    def ensure_dirs(self, launcher_dir: Path) -> None:
        game = self.game_dir(launcher_dir)
        game.mkdir(parents=True, exist_ok=True)
        for name in GAME_SUBDIRS:
            (game / name).mkdir(parents=True, exist_ok=True)


def builds_root(launcher_dir: Path) -> Path:
    return launcher_dir / BUILDS_DIR_NAME


def _safe_id(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", name.strip().lower()).strip("-")
    return slug[:40] if slug else str(uuid.uuid4())[:8]


def list_builds(launcher_dir: Path) -> list[Build]:
    root = builds_root(launcher_dir)
    if not root.exists():
        return []

    builds: list[Build] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        profile = entry / PROFILE_NAME
        if not profile.exists():
            continue
        try:
            data = json.loads(profile.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            fields = {k: data[k] for k in Build.__dataclass_fields__ if k in data}
            if "id" not in fields or "name" not in fields:
                continue
            builds.append(Build(**fields))
        except (json.JSONDecodeError, TypeError, KeyError, ValueError):
            continue
    builds.sort(key=lambda b: b.name.lower())
    return builds


def save_build(build: Build, launcher_dir: Path) -> None:
    build.ensure_dirs(launcher_dir)
    build.profile_path(launcher_dir).write_text(
        json.dumps(asdict(build), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def unique_build_name(launcher_dir: Path, name: str) -> str:
    base = name.strip() or "Modpack"
    existing = {b.name for b in list_builds(launcher_dir)}
    if base not in existing:
        return base
    index = 2
    while f"{base} ({index})" in existing:
        index += 1
    return f"{base} ({index})"


def create_build(launcher_dir: Path, name: str) -> Build:
    build_id = f"{_safe_id(name)}-{uuid.uuid4().hex[:6]}"
    build = Build(id=build_id, name=name.strip() or "Сборка")
    build.root(launcher_dir).mkdir(parents=True, exist_ok=True)
    save_build(build, launcher_dir)
    return build


def delete_build(launcher_dir: Path, build_id: str) -> None:
    import shutil

    path = builds_root(launcher_dir) / build_id
    if path.exists():
        shutil.rmtree(path)


def get_build(launcher_dir: Path, build_id: str) -> Build | None:
    for build in list_builds(launcher_dir):
        if build.id == build_id:
            return build
    return None


def clone_build(
    launcher_dir: Path,
    source: Build,
    *,
    name: str | None = None,
) -> Build:
    """Копия сборки: game/ и настройки профиля."""
    import shutil

    display_name = unique_build_name(
        launcher_dir, name or f"{source.name} (копия)"
    )
    new_build = Build(
        id=f"{_safe_id(display_name)}-{uuid.uuid4().hex[:6]}",
        name=display_name,
        username=source.username,
        mc_version=source.mc_version,
        loader=source.loader,
        loader_version=source.loader_version,
        ram_gb=source.ram_gb,
        version_filter=source.version_filter,
        edition=source.edition,
        java_path=source.java_path,
        jvm_args=source.jvm_args,
        play_time_seconds=source.play_time_seconds,
        launch_count=source.launch_count,
    )
    dst_root = new_build.root(launcher_dir)
    dst_root.mkdir(parents=True, exist_ok=True)
    src_game = source.game_dir(launcher_dir)
    dst_game = new_build.game_dir(launcher_dir)
    if src_game.exists():
        if dst_game.exists():
            shutil.rmtree(dst_game)
        shutil.copytree(src_game, dst_game)
    else:
        new_build.ensure_dirs(launcher_dir)
    save_build(new_build, launcher_dir)
    return new_build


def ensure_default_build(launcher_dir: Path) -> Build:
    builds = list_builds(launcher_dir)
    if builds:
        return builds[0]
    return create_build(launcher_dir, "Основная")
