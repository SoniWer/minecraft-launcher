"""Проверки перед запуском Minecraft."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from disk_check import free_gb, needs_download_warning
from game_logs import latest_crash_report
from java_manager import JavaInstall, required_java_major
from mod_duplicates import find_duplicate_mods
from ram_advisor import count_mod_jars, recommend_ram_gb


@dataclass(frozen=True)
class CheckResult:
    level: str  # error, warning, info
    message: str


def _java_major_from_path(java_path: str, installs: list[JavaInstall]) -> int | None:
    install = next((j for j in installs if j.path == java_path), None)
    return install.major if install else None


def run_prelaunch_checks(
    *,
    mc_version: str,
    loader_id: str,
    loader_version: str,
    ram_gb: int,
    java_path: str,
    java_installs: list[JavaInstall],
    game_dir: Path,
    version_installed: bool,
) -> list[CheckResult]:
    results: list[CheckResult] = []

    if not mc_version:
        results.append(CheckResult("error", "Не выбрана версия Minecraft."))
        return results

    if loader_id != "vanilla" and not loader_version.strip():
        results.append(
            CheckResult("error", "Не выбрана версия мод-загрузчика.")
        )

    if not version_installed and loader_id == "vanilla":
        results.append(
            CheckResult(
                "warning",
                f"Версия «{mc_version}» ещё не установлена — будет скачана при запуске.",
            )
        )

    need_java = required_java_major(mc_version)
    have_java = _java_major_from_path(java_path, java_installs)
    if have_java is not None and have_java < need_java:
        results.append(
            CheckResult(
                "error",
                f"Java {have_java} не подходит для {mc_version} (нужна {need_java}+).",
            )
        )
    elif have_java is None and java_path:
        results.append(
            CheckResult("warning", "Не удалось определить версию выбранной Java.")
        )

    mod_count = count_mod_jars(game_dir)
    if loader_id == "vanilla" and mod_count > 0:
        results.append(
            CheckResult(
                "warning",
                f"В папке mods {mod_count} файл(ов), но выбран Vanilla — моды не загрузятся.",
            )
        )
    elif mod_count == 0 and loader_id != "vanilla":
        results.append(
            CheckResult(
                "info",
                "Папка mods пуста — игра запустится без модов.",
            )
        )

    recommended = recommend_ram_gb(game_dir, loader=loader_id)
    if ram_gb < recommended:
        results.append(
            CheckResult(
                "warning",
                f"ОЗУ {ram_gb} ГБ — рекомендуется {recommended} ГБ для этой сборки.",
            )
        )

    mods_dir = game_dir / "mods"
    if mods_dir.is_dir():
        overlap: list[str] = []
        for path in mods_dir.iterdir():
            if not path.is_file():
                continue
            lower = path.name.lower()
            if lower.endswith(".jar.disabled"):
                active = path.with_name(path.name[: -len(".disabled")])
                if active.is_file():
                    overlap.append(path.name[: -len(".disabled")])
        if overlap:
            shown = ", ".join(overlap[:3]) + ("…" if len(overlap) > 3 else "")
            results.append(
                CheckResult(
                    "warning",
                    f"Мод есть и вкл., и выкл.: {shown}",
                )
            )

    need_dl = needs_download_warning(
        version_installed=version_installed,
        loader_id=loader_id,
    )
    if need_dl is not None:
        need_gb, reason = need_dl
        free = free_gb(game_dir)
        if free < need_gb:
            results.append(
                CheckResult(
                    "error",
                    f"Недостаточно места для {reason}: нужно ~{need_gb:.1f} ГБ, "
                    f"свободно {free:.1f} ГБ.",
                )
            )
        elif free < need_gb + 1.0:
            results.append(
                CheckResult(
                    "warning",
                    f"Мало места на диске для {reason} (~{need_gb:.1f} ГБ, свободно {free:.1f} ГБ).",
                )
            )

    dup_groups = find_duplicate_mods(game_dir / "mods")
    if dup_groups:
        dup_lines: list[str] = []
        for group in dup_groups[:4]:
            names = ", ".join(p.name for p in group.paths)
            dup_lines.append(f"{group.label}: {names}")
        if len(dup_groups) > 4:
            dup_lines.append(f"…ещё {len(dup_groups) - 4} групп")
        results.append(
            CheckResult(
                "warning",
                "Дубликаты модов (удалите лишние .jar):\n" + "\n".join(dup_lines),
            )
        )

    crash = latest_crash_report(game_dir)
    if crash and crash.is_file():
        import time

        age_hours = (time.time() - crash.stat().st_mtime) / 3600
        if age_hours < 48:
            results.append(
                CheckResult(
                    "warning",
                    f"Недавний crash-report ({crash.name}) — проверьте логи.",
                )
            )

    if results:
        ok = [r for r in results if r.level == "error"]
        if not ok:
            results.insert(
                0,
                CheckResult("info", f"Модов: {mod_count} · Java {need_java}+ · ОЗУ {ram_gb} ГБ"),
            )
    else:
        results.append(
            CheckResult("info", f"Готово к запуску · модов: {mod_count} · ОЗУ {ram_gb} ГБ")
        )

    return results


def format_check_report(results: list[CheckResult]) -> str:
    lines: list[str] = []
    for item in results:
        prefix = {"error": "✖", "warning": "!", "info": "·"}.get(item.level, "·")
        lines.append(f"{prefix} {item.message}")
    return "\n".join(lines)


def has_errors(results: list[CheckResult]) -> bool:
    return any(r.level == "error" for r in results)


def has_warnings(results: list[CheckResult]) -> bool:
    return any(r.level == "warning" for r in results)
