"""Проверка папки mods: битые и дублирующиеся файлы."""

from __future__ import annotations

import hashlib
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

MIN_JAR_BYTES = 512


@dataclass(frozen=True)
class ModIssue:
    level: str  # error, warning
    kind: str
    message: str
    paths: tuple[Path, ...]


def _jar_files(mods_dir: Path) -> list[Path]:
    if not mods_dir.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(mods_dir.iterdir()):
        if not path.is_file():
            continue
        lower = path.name.lower()
        if lower.endswith(".jar") or lower.endswith(".jar.disabled"):
            out.append(path)
    return out


def _file_sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _jar_is_valid(path: Path) -> bool:
    if path.stat().st_size < MIN_JAR_BYTES:
        return False
    try:
        with zipfile.ZipFile(path, "r") as zf:
            return "META-INF" in zf.namelist() or len(zf.namelist()) > 0
    except (zipfile.BadZipFile, OSError):
        return False


def scan_mods_folder(mods_dir: Path) -> list[ModIssue]:
    issues: list[ModIssue] = []
    files = _jar_files(mods_dir)
    if not files:
        return issues

    by_hash: dict[str, list[Path]] = defaultdict(list)
    by_stem: dict[str, list[Path]] = defaultdict(list)

    for path in files:
        size = path.stat().st_size
        if size < MIN_JAR_BYTES:
            issues.append(
                ModIssue(
                    "error",
                    "tiny",
                    f"Слишком маленький файл ({size} байт): {path.name}",
                    (path,),
                )
            )
            continue
        if path.name.lower().endswith(".jar") and not path.name.lower().endswith(
            ".disabled"
        ):
            if not _jar_is_valid(path):
                issues.append(
                    ModIssue(
                        "error",
                        "broken",
                        f"Повреждённый или нечитаемый JAR: {path.name}",
                        (path,),
                    )
                )
        digest = _file_sha256(path)
        if digest:
            by_hash[digest].append(path)

        stem = path.name.lower()
        if stem.endswith(".jar.disabled"):
            stem = stem[: -len(".disabled")]
        if stem.endswith(".jar"):
            stem = stem[: -4]
        by_stem[stem].append(path)

    for digest, paths in by_hash.items():
        if len(paths) < 2:
            continue
        names = ", ".join(p.name for p in paths)
        issues.append(
            ModIssue(
                "warning",
                "duplicate_hash",
                f"Одинаковое содержимое ({len(paths)} файла): {names}",
                tuple(paths),
            )
        )

    for stem, paths in by_stem.items():
        active = [p for p in paths if not p.name.lower().endswith(".disabled")]
        if len(active) < 2:
            continue
        paths = active
        names = ", ".join(p.name for p in paths)
        issues.append(
            ModIssue(
                "warning",
                "duplicate_name",
                f"Похожие моды «{stem}»: {names}",
                tuple(paths),
            )
        )

    order = {"error": 0, "warning": 1}
    issues.sort(key=lambda i: (order.get(i.level, 9), i.message.lower()))
    return issues
