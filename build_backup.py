"""Бэкап и восстановление папки game/ сборки."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from builds import Build, PROFILE_NAME, save_build


class BackupError(Exception):
    pass


def export_build_zip(build: Build, launcher_dir: Path, dest_zip: Path) -> Path:
    build.ensure_dirs(launcher_dir)
    game = build.game_dir(launcher_dir)

    profile = build.profile_path(launcher_dir)
    dest_zip = dest_zip.resolve()
    dest_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        if profile.exists():
            zf.write(profile, f"backup/{PROFILE_NAME}")
        for path in game.rglob("*"):
            if path.is_file():
                arcname = f"backup/game/{path.relative_to(game).as_posix()}"
                zf.write(path, arcname)
        meta = {
            "build_name": build.name,
            "build_id": build.id,
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        zf.writestr("backup/backup_meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return dest_zip


def export_partial_zip(
    build: Build,
    launcher_dir: Path,
    dest_zip: Path,
    *,
    include_mods: bool = False,
    include_saves: bool = False,
) -> Path:
    if not include_mods and not include_saves:
        raise BackupError("Выберите mods/ или миры для экспорта.")

    build.ensure_dirs(launcher_dir)
    game = build.game_dir(launcher_dir)
    dest_zip = dest_zip.resolve()
    dest_zip.parent.mkdir(parents=True, exist_ok=True)

    folders: list[str] = []
    if include_mods:
        folders.append("mods")
    if include_saves:
        folders.append("saves")

    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        profile = build.profile_path(launcher_dir)
        if profile.exists():
            zf.write(profile, f"backup/{PROFILE_NAME}")
        for folder in folders:
            root = game / folder
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_file():
                    rel = path.relative_to(game).as_posix()
                    zf.write(path, f"backup/game/{rel}")
        meta = {
            "build_name": build.name,
            "build_id": build.id,
            "partial": folders,
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        zf.writestr("backup/backup_meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return dest_zip


def import_build_zip(
    zip_path: Path,
    launcher_dir: Path,
    *,
    target_build: Build | None = None,
    new_name: str | None = None,
) -> Build:
    zip_path = zip_path.resolve()
    if not zip_path.is_file():
        raise BackupError("Файл бэкапа не найден.")

    from builds import create_build, unique_build_name

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        if not any(n.startswith("backup/game/") for n in names):
            raise BackupError("Неверный формат бэкапа (нет папки game).")

        if target_build is None:
            meta_name = new_name
            try:
                meta_raw = zf.read("backup/backup_meta.json")
                meta = json.loads(meta_raw.decode("utf-8"))
                meta_name = meta_name or str(meta.get("build_name") or "")
            except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
                pass
            build_name = unique_build_name(
                launcher_dir, meta_name or zip_path.stem or "Импортированная"
            )
            target_build = create_build(launcher_dir, build_name)
        elif new_name:
            target_build.name = new_name.strip()

        game = target_build.game_dir(launcher_dir)
        if game.exists():
            shutil.rmtree(game)
        game.mkdir(parents=True, exist_ok=True)

        for member in names:
            if not member.startswith("backup/game/") or member.endswith("/"):
                continue
            rel = member[len("backup/game/") :]
            dest = game / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)

        if "backup/profile.json" in names:
            profile_dest = target_build.profile_path(launcher_dir)
            with zf.open("backup/profile.json") as src:
                profile_dest.write_bytes(src.read())
            try:
                data = json.loads(profile_dest.read_text(encoding="utf-8"))
                target_build = Build(
                    **{
                        k: data[k]
                        for k in Build.__dataclass_fields__
                        if k in data and k != "id"
                    },
                    id=target_build.id,
                    name=target_build.name,
                )
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

    save_build(target_build, launcher_dir)
    return target_build
