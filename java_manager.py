"""Поиск Java и подсказки по версии Minecraft."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import minecraft_launcher_lib
from minecraft_launcher_lib.java_utils import find_system_java_versions_information


@dataclass(frozen=True)
class JavaInstall:
    path: str
    label: str
    major: int | None


def parse_mc_version(mc_version: str) -> tuple[int, int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", mc_version.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)


def required_java_major(mc_version: str) -> int:
    """Минимальная major-версия Java для выбранной версии MC."""
    parsed = parse_mc_version(mc_version)
    if not parsed:
        return 21
    major, minor, patch = parsed
    if major != 1:
        return 21
    if minor < 17:
        return 8
    if minor < 20 or (minor == 20 and patch < 5):
        return 17
    return 21


def java_hint(mc_version: str) -> str:
    need = required_java_major(mc_version)
    if need >= 21:
        return "Для этой версии MC рекомендуется Java 21+"
    if need >= 17:
        return "Для этой версии MC рекомендуется Java 17+"
    return "Для этой версии MC рекомендуется Java 8"


def _java_major_from_version_string(version: str) -> int | None:
    match = re.search(r'"?(\d+)"?(?:\.\d+)?', version)
    if not match:
        return None
    first = int(match.group(1))
    if first >= 8:
        return first
    return None


def list_java_installs(launcher_dir: Path | None = None) -> list[JavaInstall]:
    installs: list[JavaInstall] = []
    seen: set[str] = set()

    if launcher_dir is not None:
        try:
            from java_download import installed_java_path

            for major in (21, 17, 8):
                path = installed_java_path(launcher_dir, major)
                if path and str(path) not in seen:
                    seen.add(str(path))
                    installs.append(
                        JavaInstall(
                            path=str(path),
                            label=f"Лаунчер Java {major} — {path.name}",
                            major=major,
                        )
                    )
        except ImportError:
            pass

    try:
        entries = find_system_java_versions_information()
    except Exception:
        entries = []

    for info in entries:
        java_path = str(info.get("java_path") or info.get("path") or "").strip()
        if not java_path or java_path in seen:
            continue
        seen.add(java_path)
        version_str = str(info.get("version") or "")
        major = _java_major_from_version_string(version_str)
        name = str(info.get("name") or Path(java_path).parent.name)
        label = f"Java {major or '?'} — {name}" if major else f"{name} — {java_path}"
        installs.append(JavaInstall(path=java_path, label=label, major=major))

    default = minecraft_launcher_lib.utils.get_java_executable()
    if default and default not in seen:
        installs.insert(
            0,
            JavaInstall(
                path=default,
                label=f"По умолчанию (PATH) — {default}",
                major=None,
            ),
        )
    return installs


def pick_best_java(mc_version: str, installs: list[JavaInstall]) -> str | None:
    need = required_java_major(mc_version)
    suitable = [j for j in installs if j.major is None or j.major >= need]
    if suitable:
        return suitable[0].path
    return installs[0].path if installs else None


def java_major_for_path(java_path: str, installs: list[JavaInstall]) -> int | None:
    install = next((j for j in installs if j.path == java_path), None)
    return install.major if install else None


def resolve_java_executable(
    mc_version: str,
    *,
    preferred_path: str = "",
    installs: list[JavaInstall] | None = None,
) -> str:
    path = preferred_path.strip()
    if path and Path(path).exists():
        return path
    pool = installs if installs is not None else list_java_installs()
    best = pick_best_java(mc_version, pool)
    if best:
        return best
    return minecraft_launcher_lib.utils.get_java_executable()


def ensure_java_for_mc(
    mc_version: str,
    launcher_dir: Path,
    *,
    preferred_path: str = "",
    installs: list[JavaInstall] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> str:
    """Подобрать Java для MC или скачать Temurin в папку лаунчера (одна jdk-N на major)."""
    need = required_java_major(mc_version)
    pool = installs if installs is not None else list_java_installs(launcher_dir)

    try:
        from java_download import download_java, installed_java_path

        bundled = installed_java_path(launcher_dir, need)
        if bundled:
            return str(bundled)

        pref = preferred_path.strip()
        if pref and Path(pref).exists():
            major = java_major_for_path(pref, pool)
            if major is not None and major < need:
                pref = ""
            elif major is None or major >= need:
                return pref

        if not pref:
            best = pick_best_java(mc_version, pool)
            if best and Path(best).exists():
                major = java_major_for_path(best, pool)
                if major is None or major >= need:
                    return best

        if on_status:
            on_status(f"Скачивание Java {need}…")
        return str(download_java(launcher_dir, need, on_status=on_status))
    except ImportError:
        return resolve_java_executable(
            mc_version, preferred_path=preferred_path, installs=pool
        )


def java_combo_labels(installs: list[JavaInstall]) -> list[str]:
    return ["Авто (подбор по версии MC)"] + [j.label for j in installs]


def label_to_path(label: str, installs: list[JavaInstall]) -> str:
    if label.startswith("Авто"):
        return ""
    for install in installs:
        if install.label == label:
            return install.path
    return ""
