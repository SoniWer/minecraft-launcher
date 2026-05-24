"""Проверка зависимостей перед запуском лаунчера."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

# (имя модуля для import, строка для pip)
REQUIRED_PACKAGES: tuple[tuple[str, str], ...] = (
    ("minecraft_launcher_lib", "minecraft-launcher-lib>=7.0"),
    ("requests", "requests>=2.28"),
)

OPTIONAL_PACKAGES: tuple[tuple[str, str], ...] = (
    ("sv_ttk", "sv-ttk>=2.5"),
    ("windnd", "windnd>=1.0.3"),
)

LOCAL_MODULES: tuple[str, ...] = (
    "builds",
    "build_backup",
    "game_logs",
    "game_log_collector",
    "game_process",
    "java_manager",
    "java_download",
    "jvm_args",
    "jvm_presets",
    "ram_advisor",
    "prelaunch_check",
    "settings",
    "theme",
    "tooltips",
    "ui_async",
    "modrinth",
    "version_manager",
    "modrinth_ui",
    "pack_manager_ui",
    "install_status",
    "changelog",
    "mod_duplicates",
    "mod_updates_ui",
    "play_stats_ui",
    "crash_reports_ui",
    "discord_presence",
    "extras_ui",
)


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _project_dir() -> Path:
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _missing_modules(packages: tuple[tuple[str, str], ...]) -> list[tuple[str, str]]:
    missing: list[tuple[str, str]] = []
    for module, pip_name in packages:
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append((module, pip_name))
    return missing


def _check_tkinter() -> str | None:
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return (
            "Не найден tkinter (GUI).\n"
            "На Windows переустановите Python с галочкой «tcl/tk».\n"
            "На Linux: sudo apt install python3-tk"
        )
    return None


def _show_error(title: str, message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message, parent=root)
        root.destroy()
    except Exception:
        print(f"{title}\n{message}", file=sys.stderr)


def _try_install(pip_specs: list[str] | None = None) -> bool:
    req_file = _project_dir() / "requirements.txt"
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
    if req_file.is_file():
        cmd.extend(["-r", str(req_file)])
    elif pip_specs:
        cmd.extend(pip_specs)
    else:
        return False
    try:
        subprocess.run(cmd, check=True)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def require_dependencies(*, offer_install: bool = True) -> None:
    """Проверить зависимости; при отсутствии — предложить установку или выйти."""
    tk_err = _check_tkinter()
    if tk_err:
        _show_error("Ошибка запуска", tk_err)
        sys.exit(1)

    if _is_frozen():
        missing = _missing_modules(REQUIRED_PACKAGES)
        local_missing = _missing_modules(tuple((m, m) for m in LOCAL_MODULES))
        if missing or local_missing:
            parts = [m for m, _ in missing + local_missing]
            _show_error(
                "Ошибка EXE",
                "В сборке не хватает модулей:\n"
                + ", ".join(parts)
                + "\n\nСкачайте новый EXE из Releases на GitHub.",
            )
            sys.exit(1)
        return

    missing = _missing_modules(REQUIRED_PACKAGES)
    if not missing:
        return

    pip_specs = [pip for _, pip in missing]
    modules = ", ".join(m for m, _ in missing)
    hint = f'pip install -r "{_project_dir() / "requirements.txt"}"'

    if offer_install:
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            install = messagebox.askyesno(
                "Нужны библиотеки",
                f"Не установлены: {modules}\n\n"
                f"Установить автоматически?\n({hint})",
                parent=root,
            )
            root.destroy()
            if install and _try_install(pip_specs):
                if not _missing_modules(REQUIRED_PACKAGES):
                    return
        except Exception:
            pass

    _show_error(
        "Нужны библиотеки",
        f"Не установлены: {modules}\n\n"
        f"В командной строке из папки лаунчера:\n{hint}",
    )
    sys.exit(1)


def check_optional_theme() -> bool:
    try:
        importlib.import_module("sv_ttk")
        return True
    except ImportError:
        return False
