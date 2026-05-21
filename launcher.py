#!/usr/bin/env python3
"""Простой лаунчер Minecraft: сборки, мод-загрузчики, Modrinth (только Java)."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import threading
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from deps_check import require_dependencies

require_dependencies()

import minecraft_launcher_lib
from minecraft_launcher_lib.exceptions import UnsupportedVersion

from builds import (
    Build,
    clone_build,
    create_build,
    delete_build,
    ensure_default_build,
    list_builds,
    save_build,
    unique_build_name,
)
from jvm_presets import match_preset, preset_args, preset_names
from prelaunch_check import (
    format_check_report,
    has_errors,
    has_warnings,
    run_prelaunch_checks,
)
from auto_backup import create_auto_backup
from build_backup import BackupError, export_build_zip, import_build_zip
from drag_drop import enable_jar_drop
from play_time import format_play_time
from version_sort import sort_with_favorites
from game_logs import latest_crash_report, latest_log, open_file as open_log_file
from game_process import GameProcessTracker
from java_manager import (
    JavaInstall,
    java_combo_labels,
    java_hint,
    label_to_path,
    list_java_installs,
    resolve_java_executable,
)
from jvm_args import parse_jvm_args
from log_viewer import LogViewerWindow
from ram_advisor import ram_hint_text, recommend_ram_gb
from app_paths import launcher_dir
from settings import LauncherSettings
from theme import apply_theme
from tooltips import add_tooltip
from ui_async import run_background

MOD_LOADERS: list[tuple[str, str]] = [
    ("vanilla", "Vanilla (без модов)"),
    ("fabric", "Fabric"),
    ("forge", "Forge"),
    ("neoforge", "NeoForge"),
    ("quilt", "Quilt"),
]
LOADER_BY_NAME = {display: lid for lid, display in MOD_LOADERS}
LOADER_DISPLAY = {lid: display for lid, display in MOD_LOADERS}

RAM_OPTIONS_GB = ("2", "4", "6", "8", "12", "16", "24", "32")
LAUNCHER_DIR = launcher_dir()


def offline_uuid(username: str) -> str:
    digest = hashlib.md5(f"OfflinePlayer:{username}".encode()).digest()
    data = bytearray(digest)
    data[6] &= 0x0F
    data[6] |= 0x30
    data[8] &= 0x3F
    data[8] |= 0x80
    return str(uuid.UUID(bytes=bytes(data)))


def build_launch_options(
    *,
    username: str,
    ram_gb: int,
    game_dir: Path,
    java_executable: str,
    extra_jvm: list[str] | None = None,
) -> dict:
    min_ram = max(1, ram_gb // 2)
    jvm = [f"-Xms{min_ram}G", f"-Xmx{ram_gb}G"]
    if extra_jvm:
        jvm.extend(extra_jvm)
    return {
        "username": username,
        "uuid": offline_uuid(username),
        "token": "",
        "jvmArguments": jvm,
        "gameDirectory": str(game_dir.resolve()),
        "executablePath": java_executable,
    }


def open_folder(path: Path) -> None:
    folder = path.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(folder)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", folder], check=False)
    else:
        subprocess.run(["xdg-open", folder], check=False)


class MinecraftLauncherApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Minecraft Launcher")
        self.root.geometry("1020x640")
        self.root.minsize(880, 580)

        self.shared_dir = minecraft_launcher_lib.utils.get_minecraft_directory()
        self.versions: list[dict] = []
        self.current_build: Build | None = None
        self._suppress_build_save = False
        self.settings = LauncherSettings.load(LAUNCHER_DIR)
        self.java_installs: list[JavaInstall] = []
        self._game_tracker = GameProcessTracker(
            self._on_game_running_changed,
            on_session_end=self._on_play_session_end,
        )
        self._game_tracker.bind_root(self.root)

        self._colors = apply_theme(self.root, dark=self.settings.dark_theme)
        self._build_ui()
        self._setup_drag_drop()
        self._init_builds()
        self._load_java_installs_async()
        self._load_versions_async()

    def _game_dir(self) -> Path:
        if self.current_build:
            return self.current_build.game_dir(LAUNCHER_DIR)
        return Path(self.shared_dir)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=(16, 12))
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=3, minsize=420)
        main.columnconfigure(1, weight=2, minsize=320)
        main.rowconfigure(1, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(header, text="Minecraft Launcher", style="Title.TLabel").pack(
            side="left", anchor="w"
        )
        ttk.Label(
            header,
            text="Java Edition · сборки · Modrinth",
            style="Subtitle.TLabel",
        ).pack(side="left", padx=(16, 0), anchor="s")

        left = ttk.Frame(main)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        right = ttk.Frame(main)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        profile = ttk.LabelFrame(
            left, text="Сборка и профиль", style="Card.TLabelframe", padding=(12, 8)
        )
        profile.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        profile.columnconfigure(1, weight=1)

        build_row = ttk.Frame(profile)
        build_row.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Label(build_row, text="Сборка").pack(side="left")
        self.build_var = tk.StringVar()
        self.build_combo = ttk.Combobox(
            build_row, textvariable=self.build_var, width=22, state="readonly"
        )
        self.build_combo.pack(side="left", padx=(8, 4), fill="x", expand=True)
        self.build_combo.bind("<<ComboboxSelected>>", self._on_build_selected)
        self.btn_build_new = ttk.Button(
            build_row, text="+", width=3, command=self._create_build
        )
        self.btn_build_new.pack(side="left", padx=2)
        self.btn_build_clone = ttk.Button(
            build_row, text="⧉", width=3, command=self._clone_build
        )
        self.btn_build_clone.pack(side="left", padx=2)
        self.btn_build_delete = ttk.Button(
            build_row, text="−", width=3, command=self._delete_build
        )
        self.btn_build_delete.pack(side="left")

        ttk.Label(profile, text="Никнейм").grid(row=1, column=0, sticky="w", pady=3)
        self.username_var = tk.StringVar(value="Player")
        self.username_entry = ttk.Entry(profile, textvariable=self.username_var)
        self.username_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=3)
        self.username_var.trace_add("write", self._on_settings_changed)

        version_card = ttk.LabelFrame(
            left, text="Версия и загрузчик", style="Card.TLabelframe", padding=(12, 8)
        )
        version_card.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        version_card.columnconfigure(1, weight=1)
        ttk.Label(version_card, text="Java").grid(row=0, column=0, sticky="w", pady=3)
        self.java_var = tk.StringVar()
        self.java_combo = ttk.Combobox(
            version_card, textvariable=self.java_var, state="readonly"
        )
        self.java_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=3)
        self.java_combo.bind("<<ComboboxSelected>>", self._on_java_changed)
        self.java_hint_var = tk.StringVar(value="")
        ttk.Label(
            version_card, textvariable=self.java_hint_var, style="Hint.TLabel"
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 4))

        ttk.Label(version_card, text="Загрузчик").grid(row=2, column=0, sticky="w", pady=3)
        self.loader_var = tk.StringVar(value="Vanilla (без модов)")
        self.loader_combo = ttk.Combobox(
            version_card,
            textvariable=self.loader_var,
            values=[name for _, name in MOD_LOADERS],
            state="readonly",
        )
        self.loader_combo.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=3)
        self.loader_combo.bind("<<ComboboxSelected>>", self._on_loader_changed)

        ttk.Label(version_card, text="Версия MC").grid(row=3, column=0, sticky="w", pady=3)
        ver_row = ttk.Frame(version_card)
        ver_row.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=3)
        ver_row.columnconfigure(0, weight=1)
        self.version_combo = ttk.Combobox(ver_row, state="disabled")
        self.version_combo.grid(row=0, column=0, sticky="ew")
        self.version_combo.bind("<<ComboboxSelected>>", self._on_mc_version_changed)
        self.btn_favorite_version = ttk.Button(
            ver_row, text="☆", width=3, command=self._toggle_favorite_version
        )
        self.btn_favorite_version.grid(row=0, column=1, padx=(4, 0))
        add_tooltip(
            self.btn_favorite_version,
            "Закрепить/открепить версию вверху списка",
        )

        self.loader_version_label = ttk.Label(version_card, text="Версия загрузчика")
        self.loader_version_label.grid(row=4, column=0, sticky="w", pady=3)
        self.loader_version_combo = ttk.Combobox(version_card, state="disabled")
        self.loader_version_combo.grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=3)
        self.loader_version_combo.bind(
            "<<ComboboxSelected>>", self._on_settings_changed
        )
        self._update_loader_version_visibility()

        filter_frame = ttk.Frame(version_card)
        filter_frame.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(filter_frame, text="Список версий:").pack(side="left")
        self.filter_var = tk.StringVar(value="release")
        filter_tips = {
            "release": "Только стабильные релизы Minecraft",
            "snapshot": "Экспериментальные снапшоты",
            "all": "Релизы и снапшоты в одном списке",
        }
        for label, value in (
            ("Релизы", "release"),
            ("Снапшоты", "snapshot"),
            ("Все", "all"),
        ):
            rb = ttk.Radiobutton(
                filter_frame,
                text=label,
                variable=self.filter_var,
                value=value,
                command=self._on_filter_changed,
            )
            rb.pack(side="left", padx=(8, 0))
            add_tooltip(rb, filter_tips[value])

        perf = ttk.LabelFrame(
            left, text="Производительность", style="Card.TLabelframe", padding=(12, 8)
        )
        perf.grid(row=2, column=0, sticky="ew")
        perf.columnconfigure(1, weight=1)

        ttk.Label(perf, text="ОЗУ (ГБ)").grid(row=0, column=0, sticky="w", pady=3)
        ram_row = ttk.Frame(perf)
        ram_row.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=3)
        self.ram_var = tk.StringVar(value="4")
        self.ram_combo = ttk.Combobox(
            ram_row, textvariable=self.ram_var, values=RAM_OPTIONS_GB, width=8
        )
        self.ram_combo.pack(side="left")
        self.btn_ram_recommend = ttk.Button(
            ram_row,
            text="Рекомендуемое",
            style="Tool.TButton",
            command=self._apply_recommended_ram,
        )
        self.btn_ram_recommend.pack(side="left", padx=(8, 0))
        self.ram_var.trace_add("write", self._on_ram_changed)
        self.ram_hint_var = tk.StringVar(value="")
        ttk.Label(perf, textvariable=self.ram_hint_var, style="Hint.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )

        ttk.Label(perf, text="Пресет JVM").grid(row=2, column=0, sticky="w", pady=3)
        self.jvm_preset_var = tk.StringVar(value="По умолчанию")
        self.jvm_preset_combo = ttk.Combobox(
            perf,
            textvariable=self.jvm_preset_var,
            values=preset_names(),
            state="readonly",
            width=18,
        )
        self.jvm_preset_combo.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=3)
        self.jvm_preset_combo.bind("<<ComboboxSelected>>", self._on_jvm_preset)

        ttk.Label(perf, text="JVM аргументы").grid(row=3, column=0, sticky="nw", pady=3)
        self.jvm_args_var = tk.StringVar()
        self.jvm_args_entry = ttk.Entry(perf, textvariable=self.jvm_args_var)
        self.jvm_args_entry.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=3)
        self.jvm_args_var.trace_add("write", self._on_jvm_args_changed)
        ttk.Label(
            perf,
            text="Пресет подставляет флаги; можно дописать свои.",
            style="Hint.TLabel",
        ).grid(row=4, column=0, columnspan=2, sticky="w")

        launch = ttk.LabelFrame(
            right, text="Запуск", style="Card.TLabelframe", padding=(12, 10)
        )
        launch.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        launch.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Загрузка...")
        ttk.Label(
            launch,
            textvariable=self.status_var,
            style="Status.TLabel",
            wraplength=360,
        ).grid(row=0, column=0, sticky="ew")
        self.progress = ttk.Progressbar(launch, mode="determinate")
        self.progress.grid(row=1, column=0, sticky="ew", pady=(6, 10))

        self.play_btn = ttk.Button(
            launch,
            text="▶  Играть",
            style="Accent.TButton",
            command=self._on_play,
            state="disabled",
        )
        self.play_btn.grid(row=2, column=0, sticky="ew")

        side_actions = ttk.Frame(launch)
        side_actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.game_status_var = tk.StringVar(value="Minecraft не запущен")
        self.game_status_label = ttk.Label(
            side_actions, textvariable=self.game_status_var, style="Status.TLabel"
        )
        self.game_status_label.pack(side="left")
        self.play_time_var = tk.StringVar(value="")
        self.play_time_label = ttk.Label(
            launch, textvariable=self.play_time_var, style="Hint.TLabel"
        )
        self.play_time_label.grid(row=4, column=0, sticky="w", pady=(6, 0))
        self.stop_game_btn = ttk.Button(
            side_actions,
            text="Закрыть MC",
            style="Danger.TButton",
            command=self._kill_game,
            state="disabled",
        )
        self.stop_game_btn.pack(side="left", padx=(10, 0))
        self.modrinth_btn = ttk.Button(
            side_actions, text="Modrinth", style="Tool.TButton", command=self._open_modrinth
        )
        self.modrinth_btn.pack(side="right", padx=(4, 0))
        self.btn_mods = ttk.Button(
            side_actions, text="Моды", style="Tool.TButton", command=self._open_mod_manager
        )
        self.btn_mods.pack(side="right", padx=(4, 0))

        utils_card = ttk.LabelFrame(
            right, text="Утилиты", style="Card.TLabelframe", padding=(10, 8)
        )
        utils_card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for col in range(3):
            utils_card.columnconfigure(col, weight=1)
        tool_cmds = (
            ("Экспорт", self._export_backup, "Сохранить сборку в ZIP"),
            ("Импорт", self._import_backup, "Загрузить сборку из ZIP"),
            ("Версии MC", self._open_version_manager, "Удалить установленные версии"),
            ("Скачать Java", self._download_java, "Скачать Temurin под версию MC"),
            ("Тема", self._toggle_theme, "Светлая / тёмная тема интерфейса"),
        )
        for i, (text, cmd, tip) in enumerate(tool_cmds):
            btn = ttk.Button(
                utils_card, text=text, style="Tool.TButton", command=cmd
            )
            btn.grid(row=i // 3, column=i % 3, padx=4, pady=4, sticky="ew")
            add_tooltip(btn, tip)
        self.logs_mb = self._create_logs_menubutton(utils_card)
        self.logs_mb.grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=4)

        self.folders_frame = ttk.LabelFrame(
            right, text="Папки сборки", style="Card.TLabelframe", padding=(10, 8)
        )
        self.folders_frame.grid(row=2, column=0, sticky="nsew")
        for col in range(4):
            self.folders_frame.columnconfigure(col, weight=1)
        self._rebuild_folder_buttons()

        self.path_label = ttk.Label(main, text="", style="Hint.TLabel")
        self.path_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._update_path_label()
        self._register_tooltips()

    def _setup_drag_drop(self) -> None:
        enable_jar_drop(
            self.root,
            lambda: self._game_dir() / "mods",
            on_copied=self._on_jars_dropped,
        )

    def _on_jars_dropped(self, names: list[str]) -> None:
        if not names:
            messagebox.showwarning(
                "Моды",
                "Перетащите файлы .jar",
                parent=self.root,
            )
            return
        self.status_var.set(f"Добавлено в mods/: {', '.join(names[:3])}" + (
            "…" if len(names) > 3 else ""
        ))

    def _auto_backup(self, tag: str) -> Path | None:
        if not self.current_build:
            return None
        try:
            path = create_auto_backup(self.current_build, LAUNCHER_DIR, tag)
            self.status_var.set(f"Автобэкап: {path.name}")
            return path
        except BackupError as exc:
            messagebox.showwarning(
                "Автобэкап",
                f"Не удалось создать бэкап:\n{exc}\n\nПродолжение на ваш риск.",
                parent=self.root,
            )
            return None

    def _toggle_favorite_version(self) -> None:
        version = self.version_combo.get().strip()
        if not version:
            messagebox.showwarning(
                "Избранное", "Сначала выберите версию Minecraft.", parent=self.root
            )
            return
        fav = list(self.settings.favorite_versions)
        if version in fav:
            fav.remove(version)
        else:
            fav.append(version)
        self.settings.favorite_versions = fav
        self.settings.save(LAUNCHER_DIR)
        self._apply_filter()
        self._update_favorite_button()

    def _update_favorite_button(self) -> None:
        version = self.version_combo.get().strip()
        if version in self.settings.favorite_versions:
            self.btn_favorite_version.configure(text="★")
        else:
            self.btn_favorite_version.configure(text="☆")

    def _on_play_session_end(self, seconds: int) -> None:
        if not self.current_build or seconds <= 0:
            return
        self.current_build.play_time_seconds += seconds
        save_build(self.current_build, LAUNCHER_DIR)
        self._update_play_time_label()

    def _update_play_time_label(self) -> None:
        if not self.current_build:
            self.play_time_var.set("")
            return
        total = self.current_build.play_time_seconds
        if total > 0:
            self.play_time_var.set(
                f"Время в игре (сборка): {format_play_time(total)}"
            )
        else:
            self.play_time_var.set("")

    def _register_tooltips(self) -> None:
        tips: list[tuple[tk.Misc, str]] = [
            (self.build_combo, "Отдельный профиль: моды, миры и настройки"),
            (self.btn_build_new, "Создать пустую сборку"),
            (self.btn_build_clone, "Копия текущей сборки со всеми файлами"),
            (self.btn_build_delete, "Удалить сборку и её папку"),
            (self.username_entry, "Офлайн-никнейм в игре"),
            (self.java_combo, "Java для запуска; «Авто» подбирает по версии MC"),
            (self.loader_combo, "Fabric, Forge, NeoForge, Quilt или Vanilla"),
            (self.version_combo, "Версия Minecraft для этой сборки"),
            (self.loader_version_combo, "Версия мод-загрузчика для выбранной MC"),
            (self.ram_combo, "Память для JVM (-Xmx), в гигабайтах"),
            (self.btn_ram_recommend, "Подставить ОЗУ по числу модов"),
            (self.jvm_preset_combo, "Готовые наборы JVM-флагов"),
            (self.jvm_args_entry, "Дополнительные аргументы Java (-XX:…)"),
            (self.play_btn, "Установить (если нужно) и запустить Minecraft"),
            (self.stop_game_btn, "Завершить процесс, запущенный из лаунчера"),
            (self.modrinth_btn, "Каталог модов, modpack, текстур и шейдеров"),
            (self.btn_mods, "Список модов, обновления, вкл./выкл."),
            (self.logs_mb, "Просмотр лога, crash-report и папка logs"),
            (self.progress, "Прогресс установки версии или загрузчика"),
        ]
        for widget, text in tips:
            add_tooltip(widget, text)

        add_tooltip(
            self.root,
            "Перетащите .jar на окно — файлы скопируются в mods/ текущей сборки",
        )
        add_tooltip(
            self.folders_frame,
            "Быстрый доступ к папкам текущей сборки",
        )

    def _create_logs_menubutton(self, parent: ttk.Widget) -> ttk.Menubutton:
        mb = ttk.Menubutton(parent, text="Логи ▾", style="Tool.TButton")
        menu = tk.Menu(mb, tearoff=0)
        colors = getattr(self.root, "_launcher_colors", None)
        if colors is not None:
            menu.configure(
                bg=colors.entry,
                fg=colors.fg,
                activebackground=colors.accent,
                activeforeground=colors.accent_fg,
            )
        menu.add_command(label="Просмотр в окне", command=self._open_log_viewer)
        menu.add_separator()
        menu.add_command(label="Открыть latest.log", command=self._open_latest_log)
        menu.add_command(label="Открыть crash-report", command=self._open_latest_crash)
        menu.add_command(label="Папка logs", command=self._open_logs_folder)
        mb["menu"] = menu
        return mb

    def _update_path_label(self) -> None:
        game = self._game_dir()
        self.path_label.configure(
            text=f"Сборка: {self.current_build.name if self.current_build else '?'} · {game}"
        )

    def _rebuild_folder_buttons(self) -> None:
        for child in self.folders_frame.winfo_children():
            child.destroy()
        game = self._game_dir()
        
        buttons = (
            ("Сборка", game, "Корневая папка game/ сборки"),
            ("mods", game / "mods", "Файлы модов (.jar)"),
            ("текстуры", game / "resourcepacks", "Пакеты ресурсов"),
            ("шейдеры", game / "shaderpacks", "Шейдеры (Iris и др.)"),
            ("миры", game / "saves", "Сохранённые миры"),
            ("config", game / "config", "Конфиги модов и игры"),
            ("лаунчер", LAUNCHER_DIR, "Папка этого лаунчера"),
            ("версии", Path(self.shared_dir) / "versions", "Установленные версии MC"),
        )
        for index, (label, folder_path, tip) in enumerate(buttons):
            btn = ttk.Button(
                self.folders_frame,
                text=label,
                style="Tool.TButton",
                command=lambda p=folder_path: self._open_folder(p),
                width=10,
            )
            btn.grid(row=index // 4, column=index % 4, padx=3, pady=4, sticky="ew")
            add_tooltip(btn, tip)

    def _init_builds(self) -> None:
        ensure_default_build(LAUNCHER_DIR)
        self._refresh_build_list()
        builds = list_builds(LAUNCHER_DIR)
        if builds:
            self._select_build(builds[0])

    def _refresh_build_list(self) -> None:
        names = [b.name for b in list_builds(LAUNCHER_DIR)]
        self.build_combo["values"] = names

    def _find_build_by_name(self, name: str) -> Build | None:
        for build in list_builds(LAUNCHER_DIR):
            if build.name == name:
                return build
        return None

    def _select_build(self, build: Build) -> None:
        self._suppress_build_save = True
        self.current_build = build
        self.build_var.set(build.name)
        self.username_var.set(build.username or "Player")
        self._set_java_combo(build.java_path)
        self.loader_var.set(LOADER_DISPLAY.get(build.loader, "Vanilla (без модов)"))
        self.ram_var.set(str(build.ram_gb))
        self.filter_var.set(build.version_filter or "release")
        self._update_loader_version_visibility()
        if build.mc_version:
            self.version_combo.set(build.mc_version)
        if build.loader_version:
            self.loader_version_combo.set(build.loader_version)
        self.jvm_args_var.set(getattr(build, "jvm_args", "") or "")
        self._sync_jvm_preset_combo()
        self._suppress_build_save = False
        build.ensure_dirs(LAUNCHER_DIR)
        self._rebuild_folder_buttons()
        self._update_path_label()
        self._apply_filter()
        self._refresh_loader_versions_async()
        self._update_java_hint()
        self._update_ram_hint()
        self._update_favorite_button()
        self._update_play_time_label()

    def _on_build_selected(self, _event: object | None = None) -> None:
        name = self.build_var.get()
        build = self._find_build_by_name(name)
        if build:
            self._save_current_build()
            self._select_build(build)

    def _clone_build(self) -> None:
        if not self.current_build:
            return
        self._save_current_build()
        source = self.current_build
        name = simpledialog.askstring(
            "Клонировать сборку",
            "Имя новой сборки:",
            initialvalue=f"{source.name} (копия)",
            parent=self.root,
        )
        if not name or not name.strip():
            return
        try:
            build = clone_build(LAUNCHER_DIR, source, name=name.strip())
        except OSError as exc:
            messagebox.showerror(
                "Ошибка", f"Не удалось клонировать:\n{exc}", parent=self.root
            )
            return
        self._refresh_build_list()
        self._select_build(build)
        self.status_var.set(f"Создана копия «{build.name}»")

    def _create_build(self) -> None:
        name = simpledialog.askstring(
            "Новая сборка", "Название сборки:", parent=self.root
        )
        if not name or not name.strip():
            return
        self._save_current_build()
        build = create_build(LAUNCHER_DIR, name.strip())
        self._refresh_build_list()
        self._select_build(build)
        self.status_var.set(f"Создана сборка «{build.name}»")

    def _delete_build(self) -> None:
        if not self.current_build:
            return
        builds = list_builds(LAUNCHER_DIR)
        if len(builds) <= 1:
            messagebox.showwarning(
                "Внимание", "Нельзя удалить последнюю сборку.", parent=self.root
            )
            return
        if not messagebox.askyesno(
            "Удалить сборку",
            f"Удалить «{self.current_build.name}» и все её файлы (моды, миры, конфиг)?",
            parent=self.root,
        ):
            return
        deleted_id = self.current_build.id
        delete_build(LAUNCHER_DIR, deleted_id)
        self._refresh_build_list()
        remaining = list_builds(LAUNCHER_DIR)
        self._select_build(remaining[0])
        self.status_var.set("Сборка удалена")

    def _on_jvm_preset(self, _event: object | None = None) -> None:
        args = preset_args(self.jvm_preset_var.get())
        self.jvm_args_var.set(args)
        self._on_settings_changed()

    def _on_jvm_args_changed(self, *_args: object) -> None:
        if not self._suppress_build_save:
            self._sync_jvm_preset_combo()
            self._on_settings_changed()

    def _sync_jvm_preset_combo(self) -> None:
        self.jvm_preset_var.set(match_preset(self.jvm_args_var.get()))

    def _on_settings_changed(self, *_args: object) -> None:
        if not self._suppress_build_save:
            self._save_current_build()

    def _on_filter_changed(self) -> None:
        self._apply_filter()
        self._save_current_build()

    def _save_current_build(self) -> None:
        if self._suppress_build_save or not self.current_build:
            return
        build = self.current_build
        build.username = self.username_var.get().strip() or "Player"
        build.mc_version = self.version_combo.get().strip()
        build.loader = self._loader_id()
        build.loader_version = self.loader_version_combo.get().strip()
        ram = self._parse_ram_gb()
        build.ram_gb = ram if ram is not None else build.ram_gb
        build.version_filter = self.filter_var.get()
        build.java_path = self._selected_java_path()
        build.jvm_args = self.jvm_args_var.get().strip()
        save_build(build, LAUNCHER_DIR)
        self.settings.save(LAUNCHER_DIR)

    def _loader_id(self) -> str:
        return LOADER_BY_NAME.get(self.loader_var.get(), "vanilla")

    def _update_loader_version_visibility(self) -> None:
        if self._loader_id() != "vanilla":
            self.loader_version_label.grid()
            self.loader_version_combo.grid()
        else:
            self.loader_version_label.grid_remove()
            self.loader_version_combo.grid_remove()

    def _on_loader_changed(self, _event: object | None = None) -> None:
        self._update_loader_version_visibility()
        self._apply_filter()
        self._refresh_loader_versions_async()
        self._update_ram_hint()
        self._save_current_build()

    def _on_mc_version_changed(self, _event: object | None = None) -> None:
        self._refresh_loader_versions_async()
        self._update_java_hint()
        self._update_ram_hint()
        self._update_favorite_button()
        self._save_current_build()

    def _on_ram_changed(self, *_args: object) -> None:
        self._update_ram_hint()
        self._on_settings_changed()

    def _update_ram_hint(self) -> None:
        if not self.current_build:
            self.ram_hint_var.set("")
            return
        try:
            current = self._parse_ram_gb() or self.current_build.ram_gb
        except Exception:
            current = self.current_build.ram_gb
        self.ram_hint_var.set(
            ram_hint_text(
                self._game_dir(),
                loader=self._loader_id(),
                current_gb=current,
            )
        )

    def _apply_recommended_ram(self) -> None:
        if not self.current_build:
            return
        value = recommend_ram_gb(self._game_dir(), loader=self._loader_id())
        self.ram_var.set(str(value))
        self._update_ram_hint()

    def _on_game_running_changed(self, running: bool) -> None:
        if running:
            self.game_status_var.set("● Minecraft запущен")
            self.game_status_label.configure(style="Success.TLabel")
            self.stop_game_btn.configure(state="normal")
        else:
            self.game_status_var.set("Minecraft не запущен")
            self.game_status_label.configure(style="Status.TLabel")
            self.stop_game_btn.configure(state="disabled")

    def _kill_game(self) -> None:
        if self._game_tracker.kill():
            self.status_var.set("Minecraft закрыт")
        else:
            messagebox.showinfo("Игра", "Процесс Minecraft не найден.", parent=self.root)

    def _toggle_theme(self) -> None:
        self.settings.dark_theme = not self.settings.dark_theme
        self.settings.save(LAUNCHER_DIR)
        self._colors = apply_theme(self.root, dark=self.settings.dark_theme)

    def _export_backup(self) -> None:
        if not self.current_build:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Экспорт сборки",
            defaultextension=".zip",
            initialfile=f"{self.current_build.name}-backup.zip",
            filetypes=[("ZIP", "*.zip")],
        )
        if not path:
            return
        try:
            export_build_zip(self.current_build, LAUNCHER_DIR, Path(path))
            messagebox.showinfo("Экспорт", f"Сохранено:\n{path}", parent=self.root)
        except BackupError as exc:
            messagebox.showerror("Экспорт", str(exc), parent=self.root)

    def _import_backup(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Импорт сборки",
            filetypes=[("ZIP", "*.zip")],
        )
        if not path:
            return
        replace = messagebox.askyesno(
            "Импорт",
            "Заменить текущую сборку содержимым архива?",
            parent=self.root,
        )
        try:
            if replace and self.current_build:
                build = import_build_zip(
                    Path(path), LAUNCHER_DIR, target_build=self.current_build
                )
            else:
                build = import_build_zip(Path(path), LAUNCHER_DIR)
            self._refresh_build_list()
            self._select_build(build)
            messagebox.showinfo("Импорт", f"Сборка «{build.name}» импортирована.", parent=self.root)
        except BackupError as exc:
            messagebox.showerror("Импорт", str(exc), parent=self.root)

    def _open_log_viewer(self) -> None:
        LogViewerWindow(self.root, game_dir=self._game_dir())

    def _open_version_manager(self) -> None:
        from extras_ui import VersionManagerWindow

        VersionManagerWindow(self.root, minecraft_dir=Path(self.shared_dir))

    def _download_java(self) -> None:
        from extras_ui import JavaDownloadDialog

        mc_version = self.version_combo.get().strip()
        if not mc_version:
            messagebox.showwarning(
                "Java", "Выберите версию Minecraft.", parent=self.root
            )
            return

        def on_installed(java_path: str) -> None:
            if self.current_build:
                self.current_build.java_path = java_path
            self.settings.java_path = java_path
            self.settings.save(LAUNCHER_DIR)
            self._load_java_installs_async()
            self._save_current_build()

        JavaDownloadDialog(
            self.root,
            launcher_dir=LAUNCHER_DIR,
            mc_version=mc_version,
            on_installed=on_installed,
        )

    def _selected_java_path(self) -> str:
        return label_to_path(self.java_var.get(), self.java_installs)

    def _set_java_combo(self, java_path: str) -> None:
        path = (java_path or "").strip()
        if not path:
            self.java_var.set("Авто (подбор по версии MC)")
            return
        for install in self.java_installs:
            if install.path == path:
                self.java_var.set(install.label)
                return
        if self.java_installs:
            self.java_var.set(self.java_installs[0].label)
        else:
            self.java_var.set("Авто (подбор по версии MC)")

    def _resolve_java_path(self, mc_version: str) -> str:
        preferred = ""
        if self.current_build and self.current_build.java_path.strip():
            preferred = self.current_build.java_path.strip()
        elif self.settings.java_path.strip():
            preferred = self.settings.java_path.strip()
        else:
            preferred = self._selected_java_path()
        return resolve_java_executable(
            mc_version,
            preferred_path=preferred,
            installs=self.java_installs,
        )

    def _update_java_hint(self) -> None:
        mc_version = self.version_combo.get().strip()
        if mc_version:
            self.java_hint_var.set(java_hint(mc_version))
        else:
            self.java_hint_var.set("Выберите версию Minecraft для подсказки по Java")

    def _load_java_installs_async(self) -> None:
        def worker() -> list[JavaInstall]:
            try:
                return list_java_installs(LAUNCHER_DIR)
            except Exception:
                return []

        run_background(self.root, worker, self._on_java_installs_loaded)

    def _on_java_installs_loaded(self, installs: list[JavaInstall]) -> None:
        self.java_installs = installs
        labels = java_combo_labels(installs)
        self.java_combo["values"] = labels
        if self.current_build:
            self._set_java_combo(self.current_build.java_path)
        elif labels:
            self.java_var.set(labels[0])
        self._update_java_hint()

    def _on_java_changed(self, _event: object | None = None) -> None:
        path = self._selected_java_path()
        if self.current_build:
            self.current_build.java_path = path
        self.settings.java_path = path
        self.settings.save(LAUNCHER_DIR)
        self._save_current_build()

    def _open_latest_log(self) -> None:
        path = latest_log(self._game_dir())
        if not path:
            messagebox.showinfo(
                "Лог",
                "Файл logs/latest.log ещё не создан. Запустите игру хотя бы раз.",
                parent=self.root,
            )
            return
        try:
            open_log_file(path)
        except OSError as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self.root)

    def _open_latest_crash(self) -> None:
        path = latest_crash_report(self._game_dir())
        if not path:
            messagebox.showinfo(
                "Crash-report",
                "В crash-reports нет отчётов для этой сборки.",
                parent=self.root,
            )
            return
        try:
            open_log_file(path)
        except OSError as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self.root)

    def _open_logs_folder(self) -> None:
        self._open_folder(self._game_dir() / "logs")

    def _open_mod_manager(self) -> None:
        from mods_ui import ModManagerWindow

        mc_version = self.version_combo.get().strip()
        if not mc_version:
            messagebox.showwarning(
                "Внимание",
                "Выберите версию Minecraft для проверки обновлений модов.",
                parent=self.root,
            )
            return
        ModManagerWindow(
            self.root,
            game_dir=self._game_dir(),
            get_mc_version=lambda: self.version_combo.get().strip(),
            get_loader_id=self._loader_id,
            on_auto_backup=lambda: self._auto_backup("mods-update"),
        )

    def _parse_ram_gb(self) -> int | None:
        raw = self.ram_var.get().strip().replace(",", ".")
        try:
            value = int(float(raw))
        except ValueError:
            return None
        if value < 1 or value > 64:
            return None
        return value

    def _open_folder(self, path: Path) -> None:
        try:
            open_folder(path)
        except OSError as exc:
            messagebox.showerror("Ошибка", f"Не удалось открыть папку:\n{exc}")

    def _open_modrinth(self) -> None:
        from modrinth_ui import ModrinthBrowser

        mc_version = self.version_combo.get().strip()
        if not mc_version:
            messagebox.showwarning(
                "Внимание",
                "Выберите версию Minecraft — каталог фильтрует контент по ней.",
            )
            return

        ModrinthBrowser(
            self.root,
            minecraft_dir=self._game_dir(),
            shared_minecraft_dir=Path(self.shared_dir),
            get_mc_version=lambda: self.version_combo.get().strip(),
            get_loader_id=self._loader_id,
            on_modpack_installed=self._apply_modpack_profile,
            on_create_build_for_modpack=self._create_build_for_modpack,
            on_auto_backup=lambda: self._auto_backup("modpack"),
        )

    def _create_build_for_modpack(self, modpack_name: str) -> Path:
        """Создаёт новую сборку под modpack и переключается на неё."""
        self._save_current_build()
        build_name = unique_build_name(LAUNCHER_DIR, modpack_name)
        build = create_build(LAUNCHER_DIR, build_name)
        build.username = self.username_var.get().strip() or "Player"
        ram = self._parse_ram_gb()
        if ram is not None:
            build.ram_gb = ram
        save_build(build, LAUNCHER_DIR)
        self._refresh_build_list()
        self._select_build(build)
        self.status_var.set(f"Создана сборка «{build.name}», установка modpack...")
        return build.game_dir(LAUNCHER_DIR)

    def _apply_modpack_profile(self, profile: dict[str, str]) -> None:
        if not self.current_build:
            return
        mc_version = profile.get("mc_version", "").strip()
        loader = profile.get("loader", "vanilla").strip()
        if mc_version:
            self.current_build.mc_version = mc_version
            self.version_combo.set(mc_version)
        if loader in LOADER_DISPLAY:
            self.loader_var.set(LOADER_DISPLAY[loader])
        elif loader in LOADER_BY_NAME:
            self.loader_var.set(LOADER_BY_NAME[loader])
        self._update_loader_version_visibility()
        self._apply_filter()
        self._refresh_loader_versions_async()
        self._save_current_build()
        self.status_var.set(
            f"Сборка «{self.current_build.name}» обновлена под modpack "
            f"({mc_version}, {loader})"
        )

    def _set_busy(self, busy: bool) -> None:
        self.play_btn.configure(state="disabled" if busy else "normal")
        if not busy and not self.versions:
            self.play_btn.configure(state="disabled")
        self.version_combo.configure(state="disabled" if busy else "readonly")
        self.build_combo.configure(state="disabled" if busy else "readonly")
        self.java_combo.configure(state="disabled" if busy else "readonly")
        if self._loader_id() != "vanilla":
            self.loader_version_combo.configure(
                state="disabled" if busy else "readonly"
            )
        self.ram_combo.configure(state="disabled" if busy else "normal")

    def _load_versions_async(self) -> None:
        def worker() -> list[dict]:
            return minecraft_launcher_lib.utils.get_version_list()

        run_background(
            self.root,
            worker,
            self._on_versions_loaded,
            on_error=lambda exc: messagebox.showerror(
                "Ошибка", f"Не удалось загрузить версии:\n{exc}", parent=self.root
            ),
        )

    def _on_versions_loaded(self, versions: list[dict]) -> None:
        self.versions = versions
        self.status_var.set("Выберите сборку, настройки и нажмите «Играть»")
        self._apply_filter()
        self._refresh_loader_versions_async()
        if self.versions:
            self.play_btn.configure(state="normal")

    def _version_ids_for_loader(self) -> list[str]:
        kind = self.filter_var.get()
        loader_id = self._loader_id()

        if loader_id == "vanilla":
            return [
                v["id"]
                for v in self.versions
                if kind == "all" or v.get("type") == kind
            ]

        mod_loader = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
        stable_only = kind == "release"
        supported = set(mod_loader.get_minecraft_versions(stable_only))

        if kind == "snapshot":
            snapshot_ids = {v["id"] for v in self.versions if v.get("type") == "snapshot"}
            supported &= snapshot_ids
        elif kind == "all":
            supported = set(mod_loader.get_minecraft_versions(False))

        ordered = [v["id"] for v in self.versions if v["id"] in supported]
        return ordered if ordered else sorted(supported, reverse=True)

    def _apply_filter(self) -> None:
        ids = sort_with_favorites(
            self._version_ids_for_loader(),
            self.settings.favorite_versions,
        )
        self.version_combo["values"] = ids
        if ids:
            current = self.version_combo.get()
            self.version_combo.set(current if current in ids else ids[0])
            self.version_combo.configure(state="readonly")
        else:
            self.version_combo.set("")
            self.version_combo.configure(state="disabled")

    def _refresh_loader_versions_async(self) -> None:
        if self._loader_id() == "vanilla":
            return
        mc_version = self.version_combo.get().strip()
        if not mc_version:
            return
        loader_id = self._loader_id()

        def worker() -> tuple[str, str, list[str]]:
            try:
                mod_loader = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
                versions = mod_loader.get_loader_versions(mc_version, True)
                if not versions:
                    versions = mod_loader.get_loader_versions(mc_version, False)
            except Exception:
                versions = []
            return loader_id, mc_version, versions

        run_background(
            self.root,
            worker,
            lambda data: self._on_loader_versions_loaded(*data),
        )

    def _on_loader_versions_loaded(
        self, loader_id: str, mc_version: str, versions: list[str]
    ) -> None:
        if self._loader_id() != loader_id or self.version_combo.get().strip() != mc_version:
            return
        if versions:
            self.loader_version_combo["values"] = versions
            current = self.loader_version_combo.get()
            self.loader_version_combo.set(
                current if current in versions else versions[0]
            )
            self.loader_version_combo.configure(state="readonly")
        else:
            self.loader_version_combo["values"] = []
            self.loader_version_combo.set("")
            self.loader_version_combo.configure(state="disabled")

    def _make_callback(self) -> dict:
        def set_status(text: str) -> None:
            self.root.after(0, lambda t=text: self.status_var.set(t))

        def set_max(value: int) -> None:
            self.root.after(0, lambda v=value: self.progress.configure(maximum=v))

        def set_progress(value: int) -> None:
            self.root.after(0, lambda v=value: self.progress.configure(value=v))

        return {
            "setStatus": set_status,
            "setMax": set_max,
            "setProgress": set_progress,
        }

    def _resolve_launch_version(self, mc_version: str, callback: dict) -> str:
        loader_id = self._loader_id()
        if loader_id == "vanilla":
            minecraft_launcher_lib.install.install_minecraft_version(
                mc_version, self.shared_dir, callback=callback
            )
            return mc_version

        mod_loader = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
        loader_version = self.loader_version_combo.get().strip() or None
        loader_name = mod_loader.get_name()
        self.root.after(
            0,
            lambda mn=loader_name, mv=mc_version: self.status_var.set(
                f"Установка {mn} для {mv}..."
            ),
        )
        java_exe = self._resolve_java_path(mc_version)
        return mod_loader.install(
            mc_version,
            self.shared_dir,
            loader_version=loader_version,
            callback=callback,
            java=java_exe,
        )

    def _on_play(self) -> None:
        if not self.current_build:
            return

        mc_version = self.version_combo.get().strip()
        username = self.username_var.get().strip()
        loader_id = self._loader_id()
        game_dir = self._game_dir()
        if not mc_version:
            messagebox.showwarning("Внимание", "Выберите версию Minecraft.")
            return
        if not username:
            messagebox.showwarning("Внимание", "Введите никнейм.")
            return

        java_exe = self._resolve_java_path(mc_version)
        ram_gb = self._parse_ram_gb()
        if ram_gb is None:
            messagebox.showwarning("Внимание", "Укажите объём ОЗУ от 1 до 64 ГБ.")
            return

        self._save_current_build()
        game_dir.mkdir(parents=True, exist_ok=True)
        build_name = self.current_build.name
        extra_jvm = parse_jvm_args(self.jvm_args_var.get().strip())

        version_installed = minecraft_launcher_lib.utils.is_version_valid(
            mc_version, self.shared_dir
        )
        if loader_id != "vanilla":
            mod_loader = minecraft_launcher_lib.mod_loader.get_mod_loader(loader_id)
            if not mod_loader.is_minecraft_version_supported(mc_version):
                messagebox.showerror(
                    "Ошибка",
                    f"{mod_loader.get_name()} не поддерживает Minecraft {mc_version}.",
                )
                return

        checks = run_prelaunch_checks(
            mc_version=mc_version,
            loader_id=loader_id,
            loader_version=self.loader_version_combo.get().strip(),
            ram_gb=ram_gb,
            java_path=java_exe,
            java_installs=self.java_installs,
            game_dir=game_dir,
            version_installed=version_installed,
        )
        if has_errors(checks):
            messagebox.showerror(
                "Проверка перед запуском",
                format_check_report(checks),
                parent=self.root,
            )
            return
        if has_warnings(checks):
            if not messagebox.askyesno(
                "Проверка перед запуском",
                format_check_report(checks) + "\n\nВсё равно запустить?",
                parent=self.root,
            ):
                return

        self._set_busy(True)
        self.progress.configure(value=0, maximum=100)

        def worker() -> None:
            try:
                callback = self._make_callback()
                launch_version = self._resolve_launch_version(mc_version, callback)
                options = build_launch_options(
                    username=username,
                    ram_gb=ram_gb,
                    game_dir=game_dir,
                    java_executable=java_exe,
                    extra_jvm=extra_jvm,
                )
                command = minecraft_launcher_lib.command.get_minecraft_command(
                    launch_version, self.shared_dir, options
                )
                self.root.after(
                    0,
                    lambda lv=launch_version, bn=build_name: self.status_var.set(
                        f"Запуск {lv} · {bn}..."
                    ),
                )
                proc = subprocess.Popen(command, cwd=self.shared_dir)
                self.root.after(0, lambda p=proc: self._game_tracker.attach(p))
            except UnsupportedVersion as exc:
                self.root.after(
                    0, lambda msg=str(exc): messagebox.showerror("Ошибка", msg)
                )
            except Exception as exc:
                self.root.after(
                    0,
                    lambda msg=str(exc): messagebox.showerror(
                        "Ошибка", f"Не удалось запустить игру:\n{msg}"
                    ),
                )
            finally:
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    if not minecraft_launcher_lib.utils.is_platform_supported():
        print("Ваша ОС не поддерживается.", file=sys.stderr)
        sys.exit(1)

    root = tk.Tk()
    MinecraftLauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()