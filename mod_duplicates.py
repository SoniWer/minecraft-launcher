"""Поиск дубликатов модов в папке mods/."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from modrinth import file_sha512, lookup_versions_by_hashes

_JAR_ID_RE = re.compile(rb'"id"\s*:\s*"([a-z0-9_\-\.]+)"', re.IGNORECASE)


@dataclass(frozen=True)
class ModDuplicateGroup:
    label: str
    paths: tuple[Path, ...]


def _jar_mod_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for name in ("fabric.mod.json", "quilt.mod.json"):
                if name not in zf.namelist():
                    continue
                try:
                    raw = zf.read(name)[:8192]
                except (KeyError, OSError):
                    continue
                for match in _JAR_ID_RE.finditer(raw):
                    mod_id = match.group(1).decode("ascii", errors="ignore").strip()
                    if mod_id:
                        ids.add(mod_id.lower())
    except (OSError, zipfile.BadZipFile):
        pass
    return ids


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


def find_duplicate_mods(mods_dir: Path) -> list[ModDuplicateGroup]:
    """Группы дубликатов: один project_id Modrinth или один mod id из fabric/quilt."""
    jars = _list_mod_jars(mods_dir)
    if len(jars) < 2:
        return []

    groups: list[ModDuplicateGroup] = []
    seen_paths: set[Path] = set()

    hash_by_path: dict[Path, str] = {}
    hashes: list[str] = []
    for jar in jars:
        try:
            digest = file_sha512(jar)
        except OSError:
            continue
        hash_by_path[jar] = digest
        hashes.append(digest)

    known = lookup_versions_by_hashes(hashes) if hashes else {}
    by_project: dict[str, list[Path]] = {}
    for jar, digest in hash_by_path.items():
        meta = known.get(digest) or {}
        project_id = str(meta.get("project_id") or "").strip()
        if not project_id:
            continue
        title = str(meta.get("name") or jar.stem)
        by_project.setdefault(f"Modrinth: {title}", []).append(jar)

    for label, paths in sorted(by_project.items()):
        if len(paths) < 2:
            continue
        unique = tuple(sorted(set(paths), key=lambda p: p.name.lower()))
        groups.append(ModDuplicateGroup(label=label, paths=unique))
        seen_paths.update(unique)

    by_mod_id: dict[str, list[Path]] = {}
    for jar in jars:
        if jar in seen_paths:
            continue
        for mod_id in _jar_mod_ids(jar):
            by_mod_id.setdefault(mod_id, []).append(jar)

    for mod_id, paths in sorted(by_mod_id.items()):
        unique = tuple(sorted(set(paths), key=lambda p: p.name.lower()))
        if len(unique) < 2:
            continue
        groups.append(ModDuplicateGroup(label=f"Mod id: {mod_id}", paths=unique))

    return groups
