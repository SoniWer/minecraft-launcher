"""Поиск дубликатов модов в папке mods/."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from modrinth import file_sha512, lookup_versions_by_hashes


@dataclass(frozen=True)
class ModDuplicateGroup:
    label: str
    paths: tuple[Path, ...]


def _list_mod_jars(mods_dir: Path) -> list[Path]:
    if not mods_dir.is_dir():
        return []
    return sorted(
        (
            p
            for p in mods_dir.iterdir()
            if p.is_file()
            and p.suffix.lower() == ".jar"
            and not p.name.endswith(".disabled")
        ),
        key=lambda p: p.name.lower(),
    )


def _primary_mod_id(path: Path) -> str | None:
    """Только верхний id из fabric.mod.json / quilt.mod.json."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for name in ("fabric.mod.json", "quilt.mod.json"):
                if name not in zf.namelist():
                    continue
                data = json.loads(zf.read(name))
                mod_id = str(data.get("id") or "").strip().lower()
                if mod_id:
                    return mod_id
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def find_duplicate_mods(mods_dir: Path) -> list[ModDuplicateGroup]:
    """
    Дубликаты:
    - одинаковый SHA512 (копии одного файла);
    - один project_id Modrinth, но разные .jar (две версии одного мода);
  - один mod id в fabric/quilt, но разные .jar (разные файлы).
    """
    jars = _list_mod_jars(mods_dir)
    if len(jars) < 2:
        return []

    groups: list[ModDuplicateGroup] = []
    claimed: set[Path] = set()

    by_hash: dict[str, list[Path]] = {}
    hash_by_path: dict[Path, str] = {}
    for jar in jars:
        try:
            digest = file_sha512(jar)
        except OSError:
            continue
        hash_by_path[jar] = digest
        by_hash.setdefault(digest, []).append(jar)

    for digest, paths in sorted(by_hash.items(), key=lambda item: item[1][0].name.lower()):
        unique = tuple(sorted(set(paths), key=lambda p: p.name.lower()))
        if len(unique) < 2:
            continue
        groups.append(
            ModDuplicateGroup(label="Одинаковый файл (hash)", paths=unique)
        )
        claimed.update(unique)

    paths_for_lookup = [p for p in hash_by_path if p not in claimed]
    hashes = [hash_by_path[p] for p in paths_for_lookup]
    known = lookup_versions_by_hashes(hashes) if hashes else {}
    if known:
        by_project: dict[str, list[tuple[Path, str]]] = {}
        for jar in paths_for_lookup:
            digest = hash_by_path[jar]
            meta = known.get(digest) or {}
            project_id = str(meta.get("project_id") or "").strip()
            if not project_id:
                continue
            title = str(meta.get("name") or jar.stem)
            by_project.setdefault(project_id, []).append((jar, title))

        for project_id, entries in sorted(by_project.items(), key=lambda x: x[0]):
            paths = [p for p, _t in entries]
            if len(paths) < 2:
                continue
            digests = {hash_by_path[p] for p in paths if p in hash_by_path}
            if len(digests) < 2:
                continue
            title = entries[0][1]
            unique = tuple(sorted(set(paths), key=lambda p: p.name.lower()))
            groups.append(
                ModDuplicateGroup(
                    label=f"Modrinth «{title}» (разные версии)",
                    paths=unique,
                )
            )
            claimed.update(unique)

    by_mod_id: dict[str, list[Path]] = {}
    for jar in jars:
        if jar in claimed:
            continue
        mod_id = _primary_mod_id(jar)
        if not mod_id:
            continue
        by_mod_id.setdefault(mod_id, []).append(jar)

    for mod_id, paths in sorted(by_mod_id.items()):
        unique = tuple(sorted(set(paths), key=lambda p: p.name.lower()))
        if len(unique) < 2:
            continue
        digests = {hash_by_path[p] for p in unique if p in hash_by_path}
        if len(digests) < 2:
            continue
        groups.append(
            ModDuplicateGroup(label=f"Mod id «{mod_id}» (разные файлы)", paths=unique)
        )

    return groups
