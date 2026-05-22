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
import webbrowser
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
from game_logs import latest_crash_report, open_file as open_log_file
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
from minecraft_log_panel import MinecraftLogPanel
from build_dialog import NewBuildDialog
from ram_advisor import ram_hint_text, recommend_ram_gb
from app_paths import launcher_dir
from settings import LauncherSettings
from theme import apply_theme, style_canvas, style_text_widget
from ui_focus import install_no_autoselect
from ui_layout import (
    BTN_GAP,
    CARD_PAD,
    FIELD_COL,
    FORM_ROW_PY,
    LABEL_COL,
    LABEL_GAP,
    SHELL_PAD,
    TAB_PAD,
    app_header,
    form_field,
    form_hint,
    form_label,
    setup_form_grid,
)
from tooltips import add_tooltip
from ui_async import run_background
from launcher_log import error as log_error, info as log_info, setup as setup_launcher_log
from launcher_update import UpdateInfo, check_for_update
from version import LAUNCHER_VERSION

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
FILTER_LABELS = ("Релизы", "Снапшоты", "Все")
FILTER_BY_LABEL = {"Релизы": "release", "Снапшоты": "snapshot", "Все": "all"}
FILTER_TO_LABEL = {v: k for k, v in FILTER_BY_LABEL.items()}
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
        self.root.title(f"Minecraft Launcher v{LAUNCHER_VERSION}")
        self.root.minsize(900, 540)

        self.shared_dir = minecraft_launcher_lib.utils.get_minecraft_directory()
        self.versions: list[dict] = []
        self.current_build: Build | None = None
        self._suppress_build_save = False
        self.settings = LauncherSettings.load(LAUNCHER_DIR)
        self._pending_update: UpdateInfo | None = None
        setup_launcher_log(LAUNCHER_DIR)
        log_info(f"Launcher started v{LAUNCHER_VERSION}")

        if (
            self.settings.window_width >= 820
            and self.settings.window_height >= 480
        ):
            self.root.geometry(
                f"{self.settings.window_width}x{self.settings.window_height}"
            )
        else:
            self.root.geometry("960x580")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.java_installs: list[JavaInstall] = []
        self._game_tracker = GameProcessTracker(
            self._on_game_running_changed,
            on_session_end=self._on_play_session_end,
        )
        self._game_tracker.bind_root(self.root)
        self._install_busy = False

        self._colors = apply_theme(self.root, dark=self.settings.dark_theme)
        self._build_ui()
        self._setup_drag_drop()
        self._init_builds()
        self._load_java_installs_async()
        self._load_versions_async()
        self._apply_username_combo()
        self.root.after(400, self._check_crash_prompt)
        self.root.after(1200, self._check_updates_async)

    def _game_dir(self) -> Path:
        if self.current_build:
            return self.current_build.game_dir(LAUNCHER_DIR)
        return Path(self.shared_dir)

    def _log_dirs(self) -> tuple[Path, Path]:
        return self._game_dir(), Path(self.shared_dir)

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, padding=SHELL_PAD)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1, minsize=420)
        shell.rowconfigure(1, weight=0)
        shell.rowconfigure(2, weight=0, minsize=0)

        scroll_host = ttk.Frame(shell)
        scroll_host.grid(row=0, column=0, sticky="nsew")
        scroll_host.columnconfigure(0, weight=1)
        scroll_host.rowconfigure(0, weight=1)

        self._main_canvas = tk.Canvas(scroll_host, highlightthickness=0, borderwidth=0)
        style_canvas(self._main_canvas, self._colors)
        vsb = ttk.Scrollbar(scroll_host, orient="vertical", command=self._main_canvas.yview)
        self._main_canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self._main_canvas.configure(yscrollcommand=vsb.set)

        main = ttk.Frame(self._main_canvas)
        self._main_canvas_window = self._main_canvas.create_window(
            (0, 0), window=main, anchor="nw"
        )
        main.bind(
            "<Configure>",
            lambda _e: self._main_canvas.configure(
                scrollregion=self._main_canvas.bbox("all")
            ),
        )
        self._main_canvas.bind(
            "<Configure>",
            lambda e: self._main_canvas.itemconfigure(
                self._main_canvas_window, width=e.width
            ),
        )
        self._bind_mousewheel(self._main_canvas)

        app_header(main, "Minecraft Launcher", f"v{LAUNCHER_VERSION}")

        body = ttk.Frame(main)
        body.pack(fill="x")
        body.columnconfigure(0, weight=3, minsize=380)
        body.columnconfigure(1, weight=2, minsize=280)

        left_nb = ttk.Notebook(body)
        left_nb.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        tab_build = ttk.Frame(left_nb, padding=TAB_PAD)
        tab_java = ttk.Frame(left_nb, padding=TAB_PAD)
        left_nb.add(tab_build, text="  Сборка  ")
        left_nb.add(tab_java, text="  Java / ОЗУ  ")

        setup_form_grid(tab_build)
        setup_form_grid(tab_java)

        form_label(tab_build, 0, "Имя")
        build_row = ttk.Frame(tab_build)
        form_field(build_row, 0)
        build_row.columnconfigure(0, weight=1)
        self.build_var = tk.StringVar()
        self.build_combo = ttk.Combobox(
            build_row, textvariable=self.build_var, state="readonly"
        )
        self.build_combo.grid(row=0, column=0, sticky="ew", padx=(0, BTN_GAP))
        self.build_combo.bind("<<ComboboxSelected>>", self._on_build_selected)
        for col, (text, cmd) in enumerate(
            (("+", self._create_build), ("⧉", self._clone_build), ("−", self._delete_build)),
            start=1,
        ):
            ttk.Button(build_row, text=text, width=3, command=cmd).grid(
                row=0, column=col, padx=(0 if col == 1 else BTN_GAP, 0)
            )

        self.build_summary_var = tk.StringVar(value="")
        form_hint(tab_build, 1, self.build_summary_var)

        self.username_var = tk.StringVar(value="Player")
        form_label(tab_build, 2, "Никнейм")
        self.username_entry = ttk.Combobox(tab_build, textvariable=self.username_var)
        form_field(self.username_entry, 2)
        self.username_var.trace_add("write", self._on_settings_changed)

        form_label(tab_build, 3, "Версия MC")
        ver_inner = ttk.Frame(tab_build)
        form_field(ver_inner, 3)
        ver_inner.columnconfigure(0, weight=1)
        self.version_combo = ttk.Combobox(ver_inner, state="disabled")
        self.version_combo.grid(row=0, column=0, sticky="ew")
        self.version_combo.bind("<<ComboboxSelected>>", self._on_mc_version_changed)
        self.btn_favorite_version = ttk.Button(
            ver_inner, text="☆", width=3, command=self._toggle_favorite_version
        )
        self.btn_favorite_version.grid(row=0, column=1, padx=(BTN_GAP, 0))

        form_label(tab_build, 4, "Загрузчик")
        self.loader_var = tk.StringVar(value="Vanilla (без модов)")
        self.loader_combo = ttk.Combobox(
            tab_build,
            textvariable=self.loader_var,
            values=[name for _, name in MOD_LOADERS],
            state="readonly",
        )
        form_field(self.loader_combo, 4)
        self.loader_combo.bind("<<ComboboxSelected>>", self._on_loader_changed)

        self.loader_version_label = form_label(tab_build, 5, "Верс. загр.")
        self.loader_version_combo = ttk.Combobox(tab_build, state="disabled")
        form_field(self.loader_version_combo, 5)
        self.loader_version_combo.bind("<<ComboboxSelected>>", self._on_settings_changed)
        self._update_loader_version_visibility()

        self.filter_var = tk.StringVar(value="release")
        self.filter_display_var = tk.StringVar(value="Релизы")
        form_label(tab_build, 6, "Список MC")
        self.filter_combo = ttk.Combobox(
            tab_build,
            textvariable=self.filter_display_var,
            values=list(FILTER_LABELS),
            state="readonly",
        )
        form_field(self.filter_combo, 6)
        self.filter_combo.bind("<<ComboboxSelected>>", self._on_filter_combo_changed)

        self.java_var = tk.StringVar()
        form_label(tab_java, 0, "Java")
        self.java_combo = ttk.Combobox(tab_java, textvariable=self.java_var, state="readonly")
        form_field(self.java_combo, 0)
        self.java_combo.bind("<<ComboboxSelected>>", self._on_java_changed)
        self.java_hint_var = tk.StringVar(value="")
        form_hint(tab_java, 1, self.java_hint_var)

        form_label(tab_java, 2, "ОЗУ (ГБ)")
        ram_row = ttk.Frame(tab_java)
        form_field(ram_row, 2)
        self.ram_var = tk.StringVar(value="4")
        self.ram_combo = ttk.Combobox(
            ram_row, textvariable=self.ram_var, values=RAM_OPTIONS_GB, width=6
        )
        self.ram_combo.pack(side="left")
        self.btn_ram_recommend = ttk.Button(
            ram_row, text="Авто", style="Tool.TButton", command=self._apply_recommended_ram
        )
        self.btn_ram_recommend.pack(side="left", padx=(BTN_GAP + 4, 0))
        self.ram_var.trace_add("write", self._on_ram_changed)
        self.ram_hint_var = tk.StringVar(value="")
        form_hint(tab_java, 3, self.ram_hint_var)

        form_label(tab_java, 4, "JVM")
        jvm_row = ttk.Frame(tab_java)
        form_field(jvm_row, 4)
        jvm_row.columnconfigure(1, weight=1)
        self.jvm_preset_var = tk.StringVar(value="По умолчанию")
        self.jvm_preset_combo = ttk.Combobox(
            jvm_row,
            textvariable=self.jvm_preset_var,
            values=preset_names(),
            state="readonly",
            width=14,
        )
        self.jvm_preset_combo.grid(row=0, column=0, sticky="w")
        self.jvm_preset_combo.bind("<<ComboboxSelected>>", self._on_jvm_preset)
        self.jvm_args_var = tk.StringVar()
        self.jvm_args_entry = ttk.Entry(jvm_row, textvariable=self.jvm_args_var)
        self.jvm_args_entry.grid(row=0, column=1, sticky="ew", padx=(BTN_GAP + 4, 0))
        self.jvm_args_var.trace_add("write", self._on_jvm_args_changed)

        launch = ttk.LabelFrame(
            body, text="  Запуск  ", style="Card.TLabelframe", padding=CARD_PAD
        )
        launch.grid(row=0, column=1, sticky="nsew")
        launch.columnconfigure(0, weight=1)
        lr = 0

        self.status_var = tk.StringVar(value="Загрузка...")
        ttk.Label(launch, textvariable=self.status_var, style="Status.TLabel").grid(
            row=lr, column=0, sticky="ew", pady=(0, 6)
        )
        lr += 1
        self.progress = ttk.Progressbar(launch, mode="determinate")
        self.progress.grid(row=lr, column=0, sticky="ew", pady=(0, 10))
        lr += 1

        self.play_btn = ttk.Button(
            launch, text="▶  Играть", style="Accent.TButton", command=self._on_play, state="disabled"
        )
        self.play_btn.grid(row=lr, column=0, sticky="ew", pady=(0, 10))
        lr += 1

        self.game_status_var = tk.StringVar(value="MC не запущен")
        self.game_status_label = ttk.Label(
            launch, textvariable=self.game_status_var, style="Status.TLabel"
        )
        self.game_status_label.grid(row=lr, column=0, sticky="w")
        lr += 1
        self.play_time_var = tk.StringVar(value="")
        ttk.Label(launch, textvariable=self.play_time_var, style="Hint.TLabel").grid(
            row=lr, column=0, sticky="w", pady=(0, 10)
        )
        lr += 1

        ttk.Button(
            launch, text="Каталог Modrinth", style="Tool.TButton", command=self._open_modrinth
        ).grid(row=lr, column=0, sticky="ew", pady=(0, 10))
        lr += 1

        menu_row = ttk.Frame(launch)
        menu_row.grid(row=lr, column=0, sticky="ew", pady=(0, 8))
        for col in range(3):
            menu_row.columnconfigure(col, weight=1, uniform="menu")
        self.content_mb = self._create_content_menubutton(menu_row)
        self.content_mb.grid(row=0, column=0, sticky="ew", padx=(0, BTN_GAP))
        self.utils_mb = self._create_utils_menubutton(menu_row)
        self.utils_mb.grid(row=0, column=1, sticky="ew", padx=(0, BTN_GAP))
        self.folders_mb = self._create_folders_menubutton(menu_row)
        self.folders_mb.grid(row=0, column=2, sticky="ew")
        lr += 1

        self.path_label = ttk.Label(launch, text="", style="Hint.TLabel", wraplength=260)
        self.path_label.grid(row=lr, column=0, sticky="w", pady=(4, 0))
        self._update_path_label()

        log_bar = ttk.Frame(shell)
        log_bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.show_log_var = tk.BooleanVar(value=self.settings.show_game_log)
        ttk.Checkbutton(
            log_bar,
            text="Показать лог Minecraft",
            variable=self.show_log_var,
            command=self._toggle_log_panel,
        ).pack(side="left")

        self.log_panel = MinecraftLogPanel(
            shell, get_log_dirs=self._log_dirs, colors=self._colors
        )
        if self.show_log_var.get():
            self.log_panel.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        else:
            self.log_panel.grid_remove()

        for combo, var in (
            (self.build_combo, self.build_var),
            (self.username_entry, self.username_var),
            (self.version_combo, None),
            (self.loader_combo, self.loader_var),
            (self.loader_version_combo, None),
            (self.filter_combo, self.filter_display_var),
            (self.java_combo, self.java_var),
            (self.ram_combo, self.ram_var),
            (self.jvm_preset_combo, self.jvm_preset_var),
        ):
            install_no_autoselect(combo, var)

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
            (self.username_entry, "Офлайн-никнейм; список — недавние ники"),
            (self.java_combo, "Java для запуска; «Авто» подбирает по версии MC"),
            (self.loader_combo, "Fabric, Forge, NeoForge, Quilt или Vanilla"),
            (self.version_combo, "Версия Minecraft для этой сборки"),
            (self.loader_version_combo, "Версия мод-загрузчика для выбранной MC"),
            (self.ram_combo, "Память для JVM (-Xmx), в гигабайтах"),
            (self.btn_ram_recommend, "Подставить ОЗУ по числу модов"),
            (self.jvm_preset_combo, "Готовые наборы JVM-флагов"),
            (self.jvm_args_entry, "Дополнительные аргументы Java (-XX:…)"),
            (self.play_btn, "Запуск Minecraft; во время игры — красная кнопка «Стоп»"),
            (self.content_mb, "Моды, текстуры и шейдеры — вкл./выкл. как у модов"),
            (self.log_panel, "Лог игры latest.log; «Копировать» — в буфер обмена"),
            (self.filter_combo, "Какие версии показывать в списке"),
            (self.utils_mb, "Экспорт, импорт, Java, тема, обновление"),
            (self.folders_mb, "Папки mods, миры, config и др."),
            (self.progress, "Прогресс установки версии или загрузчика"),
        ]
        for widget, text in tips:
            add_tooltip(widget, text)

        add_tooltip(
            self.root,
            "Перетащите .jar на окно — файлы скопируются в mods/ текущей сборки",
        )
        add_tooltip(self.btn_favorite_version, "Закрепить версию вверху списка")

    def _update_path_label(self) -> None:
        game = self._game_dir()
        self.path_label.configure(
            text=f"Сборка: {self.current_build.name if self.current_build else '?'} · {game}"
        )

    def _bind_mousewheel(self, canvas: tk.Canvas) -> None:
        def _on_wheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-event.delta / 120), "units")

        def _bind(_event: object | None = None) -> None:
            canvas.bind_all("<MouseWheel>", _on_wheel)

        def _unbind(_event: object | None = None) -> None:
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind)
        canvas.bind("<Leave>", _unbind)

    def _toggle_log_panel(self) -> None:
        show = self.show_log_var.get()
        self.settings.show_game_log = show
        self.settings.save(LAUNCHER_DIR)
        if show:
            self.log_panel.grid(row=2, column=0, sticky="ew", pady=(6, 0))
            h = max(self.root.winfo_height(), 580)
            if self.root.winfo_height() < h:
                self.root.geometry(f"{self.root.winfo_width()}x{h}")
        else:
            self.log_panel.grid_remove()

    def _create_content_menubutton(self, parent: ttk.Widget) -> ttk.Menubutton:
        mb = ttk.Menubutton(parent, text="Контент ▾", style="Tool.TButton")
        menu = tk.Menu(mb, tearoff=0)
        self._style_menu(menu)
        menu.add_command(label="Моды", command=self._open_mod_manager)
        menu.add_command(
            label="Текстуры",
            command=lambda: self._open_pack_list("textures"),
        )
        menu.add_command(
            label="Шейдеры",
            command=lambda: self._open_pack_list("shaders"),
        )
        mb["menu"] = menu
        return mb

    def _open_pack_list(self, which: str) -> None:
        from pack_manager_ui import PACK_SHADERS, PACK_TEXTURES, PackListWindow

        kind = PACK_TEXTURES if which == "textures" else PACK_SHADERS
        PackListWindow(self.root, game_dir=self._game_dir(), kind=kind)

    def _create_utils_menubutton(self, parent: ttk.Widget) -> ttk.Menubutton:
        mb = ttk.Menubutton(parent, text="Утилиты ▾", style="Tool.TButton")
        menu = tk.Menu(mb, tearoff=0)
        self._style_menu(menu)
        menu.add_command(label="Экспорт сборки", command=self._export_backup)
        menu.add_command(label="Импорт сборки", command=self._import_backup)
        menu.add_separator()
        menu.add_command(label="Версии Minecraft", command=self._open_version_manager)
        menu.add_command(label="Скачать Java", command=self._download_java)
        menu.add_command(label="Тема", command=self._toggle_theme)
        menu.add_command(label="Обновление лаунчера", command=self._check_updates_manual)
        mb["menu"] = menu
        self.btn_update = mb
        return mb

    def _create_folders_menubutton(self, parent: ttk.Widget) -> ttk.Menubutton:
        mb = ttk.Menubutton(parent, text="Папки ▾", style="Tool.TButton")
        menu = tk.Menu(mb, tearoff=0)
        self._style_menu(menu)
        for label, sub, tip in (
            ("Сборка (game)", "", "Корень сборки"),
            ("mods", "mods", "Моды .jar"),
            ("текстуры", "resourcepacks", "Ресурспаки"),
            ("шейдеры", "shaderpacks", "Шейдеры"),
            ("миры", "saves", "Сохранения"),
            ("config", "config", "Конфиги"),
        ):
            if sub:
                menu.add_command(
                    label=label,
                    command=lambda s=sub: self._open_folder(self._game_dir() / s),
                )
            else:
                menu.add_command(
                    label=label, command=lambda: self._open_folder(self._game_dir())
                )
        menu.add_separator()
        menu.add_command(
            label="лаунчер", command=lambda: self._open_folder(LAUNCHER_DIR)
        )
        menu.add_command(
            label="версии MC",
            command=lambda: self._open_folder(Path(self.shared_dir) / "versions"),
        )
        mb["menu"] = menu
        return mb

    def _style_menu(self, menu: tk.Menu) -> None:
        colors = getattr(self.root, "_launcher_colors", None)
        if colors is not None:
            menu.configure(
                bg=colors.entry,
                fg=colors.fg,
                activebackground=colors.accent,
                activeforeground=colors.accent_fg,
            )

    def _on_filter_combo_changed(self, _event: object | None = None) -> None:
        label = self.filter_display_var.get()
        self.filter_var.set(FILTER_BY_LABEL.get(label, "release"))
        self._on_filter_changed()

    def _update_build_summary(self) -> None:
        if not self.current_build:
            self.build_summary_var.set("")
            return
        mc = self.current_build.mc_version or "версия не выбрана"
        loader = LOADER_DISPLAY.get(self.current_build.loader, "Vanilla")
        lv = self.current_build.loader_version
        extra = f" · {lv}" if lv and self.current_build.loader != "vanilla" else ""
        self.build_summary_var.set(f"Сохранено в сборке: {mc} · {loader}{extra}")

    def _version_ids_for_current_filter(self) -> list[str]:
        if not self.versions:
            return []
        return sort_with_favorites(
            self._version_ids_for_loader(),
            self.settings.favorite_versions,
        )

    def _init_builds(self) -> None:
        ensure_default_build(LAUNCHER_DIR)
        self._refresh_build_list()
        builds = list_builds(LAUNCHER_DIR)
        if not builds:
            return
        pick = builds[0]
        for name in self.settings.recent_builds:
            found = self._find_build_by_name(name)
            if found:
                pick = found
                break
        self._select_build(pick)

    def _refresh_build_list(self) -> None:
        names = [b.name for b in list_builds(LAUNCHER_DIR)]
        self.build_combo["values"] = self.settings.ordered_build_names(names)

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
        vf = build.version_filter or "release"
        self.filter_var.set(vf)
        self.filter_display_var.set(FILTER_TO_LABEL.get(vf, "Релизы"))
        self._update_loader_version_visibility()
        if build.mc_version:
            self.version_combo.set(build.mc_version)
        if build.loader_version:
            self.loader_version_combo.set(build.loader_version)
        self.jvm_args_var.set(getattr(build, "jvm_args", "") or "")
        self._sync_jvm_preset_combo()
        self._suppress_build_save = False
        build.ensure_dirs(LAUNCHER_DIR)
        self._update_path_label()
        self._update_build_summary()
        self._apply_filter()
        self._refresh_loader_versions_async()
        self._update_java_hint()
        self._update_ram_hint()
        self._update_favorite_button()
        self._update_play_time_label()
        self.settings.remember_build(build.name)
        self.settings.save(LAUNCHER_DIR)
        if hasattr(self, "log_panel"):
            self.log_panel.reset_source()

    def _apply_username_combo(self) -> None:
        values = self.settings.saved_usernames or ["Player"]
        self.username_entry["values"] = values

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
        if not self.versions:
            messagebox.showwarning(
                "Сборка",
                "Подождите загрузки списка версий Minecraft.",
                parent=self.root,
            )
            return
        self._save_current_build()
        default_mc = self.version_combo.get().strip()
        default_loader = self._loader_id() if self.current_build else "vanilla"

        def on_created(name: str, mc: str, loader: str) -> None:
            build = create_build(LAUNCHER_DIR, name)
            build.mc_version = mc
            build.loader = loader
            build.version_filter = self.filter_var.get()
            if self.current_build:
                build.ram_gb = self.current_build.ram_gb
                build.java_path = self.current_build.java_path
            save_build(build, LAUNCHER_DIR)
            self._refresh_build_list()
            self._select_build(build)
            self.status_var.set(f"Создана сборка «{build.name}» · MC {mc}")

        NewBuildDialog(
            self.root,
            mc_versions=self._version_ids_for_current_filter(),
            default_mc=default_mc,
            default_loader=default_loader,
            on_created=on_created,
        )

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
        self.settings.remember_username(build.username)
        self.settings.remember_build(build.name)
        self.settings.save(LAUNCHER_DIR)

    def _loader_id(self) -> str:
        return LOADER_BY_NAME.get(self.loader_var.get(), "vanilla")

    def _update_loader_version_visibility(self) -> None:
        if self._loader_id() != "vanilla":
            self.loader_version_label.grid(
                row=5,
                column=LABEL_COL,
                sticky="e",
                padx=LABEL_GAP,
                pady=FORM_ROW_PY,
            )
            self.loader_version_combo.grid(
                row=5, column=FIELD_COL, sticky="ew", pady=FORM_ROW_PY
            )
        else:
            self.loader_version_label.grid_remove()
            self.loader_version_combo.grid_remove()

    def _on_loader_changed(self, _event: object | None = None) -> None:
        self._update_loader_version_visibility()
        self._apply_filter()
        self._refresh_loader_versions_async()
        self._update_ram_hint()
        self._update_build_summary()
        self._save_current_build()

    def _on_mc_version_changed(self, _event: object | None = None) -> None:
        self._refresh_loader_versions_async()
        self._update_java_hint()
        self._update_ram_hint()
        self._update_favorite_button()
        self._update_build_summary()
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
        if hasattr(self, "log_panel"):
            self.log_panel.set_fast_poll(running)
            if running:
                self.log_panel.reset_source()
        self._update_play_button(running)
        if running:
            self.game_status_var.set("● Minecraft запущен")
            self.game_status_label.configure(style="Success.TLabel")
        else:
            self.game_status_var.set("Minecraft не запущен")
            self.game_status_label.configure(style="Status.TLabel")

    def _update_play_button(self, game_running: bool | None = None) -> None:
        if game_running is None:
            game_running = self._game_tracker.running
        if game_running:
            self.play_btn.configure(
                text="■  Стоп",
                style="Stop.TButton",
                command=self._kill_game,
                state="normal",
            )
        else:
            self.play_btn.configure(
                text="▶  Играть",
                style="Accent.TButton",
                command=self._on_play,
                state="normal" if self.versions else "disabled",
            )

    def _kill_game(self) -> None:
        if self._game_tracker.kill():
            self.status_var.set("Minecraft закрыт")
        else:
            messagebox.showinfo("Игра", "Процесс Minecraft не найден.", parent=self.root)

    def _toggle_theme(self) -> None:
        self.settings.dark_theme = not self.settings.dark_theme
        self.settings.save(LAUNCHER_DIR)
        self._colors = apply_theme(self.root, dark=self.settings.dark_theme)
        style_canvas(self._main_canvas, self._colors)
        style_text_widget(self.log_panel.text, self._colors)

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
        self._install_busy = busy
        if busy:
            self.play_btn.configure(state="disabled")
        else:
            self._update_play_button()
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
        (game_dir / "logs").mkdir(parents=True, exist_ok=True)
        if hasattr(self, "log_panel"):
            self.log_panel.reset_source()
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
                creationflags = (
                    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                proc = subprocess.Popen(
                    command,
                    cwd=self.shared_dir,
                    creationflags=creationflags,
                )
                self.root.after(0, lambda p=proc: self._game_tracker.attach(p))
            except UnsupportedVersion as exc:
                self.root.after(
                    0, lambda msg=str(exc): messagebox.showerror("Ошибка", msg)
                )
            except Exception as exc:
                log_error(f"Launch failed: {exc}")
                self.root.after(
                    0,
                    lambda msg=str(exc): messagebox.showerror(
                        "Ошибка", f"Не удалось запустить игру:\n{msg}"
                    ),
                )
            finally:
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _save_window_geometry(self) -> None:
        self.root.update_idletasks()
        w = max(self.root.winfo_width(), 0)
        h = max(self.root.winfo_height(), 0)
        if w >= 820 and h >= 480:
            self.settings.window_width = w
            self.settings.window_height = h

    def _on_close(self) -> None:
        try:
            self._save_current_build()
            self._save_window_geometry()
            self.settings.save(LAUNCHER_DIR)
        finally:
            self.root.destroy()

    def _check_crash_prompt(self) -> None:
        crash = latest_crash_report(self._game_dir())
        if not crash or not crash.is_file():
            return
        key = f"{crash.resolve()}:{int(crash.stat().st_mtime)}"
        if key == self.settings.last_seen_crash_key:
            return
        if messagebox.askyesno(
            "Crash-report",
            f"Найден свежий отчёт об ошибке:\n{crash.name}\n\nОткрыть файл?",
            parent=self.root,
        ):
            try:
                open_log_file(crash)
            except OSError as exc:
                messagebox.showerror("Ошибка", str(exc), parent=self.root)
        self.settings.last_seen_crash_key = key
        self.settings.save(LAUNCHER_DIR)

    def _check_updates_async(self) -> None:
        def worker() -> UpdateInfo | None:
            return check_for_update()

        def done(info: UpdateInfo | None) -> None:
            if not info:
                return
            self._pending_update = info
            self.status_var.set(
                f"Доступна версия {info.latest} — кнопка «Обновление»"
            )
            if hasattr(self, "btn_update"):
                self.btn_update.configure(text=f"Обновление v{info.latest}")

        run_background(
            self.root,
            worker,
            done,
            on_error=lambda _exc: None,
        )

    def _check_updates_manual(self) -> None:
        self.status_var.set("Проверка обновлений...")
        if self._pending_update:
            info = self._pending_update
            if messagebox.askyesno(
                "Обновление лаунчера",
                f"Доступна версия {info.latest} (у вас {info.current}).\n\n"
                "Открыть страницу скачивания?",
                parent=self.root,
            ):
                webbrowser.open(info.download_url)
            return

        def worker() -> UpdateInfo | None:
            return check_for_update()

        def done(info: UpdateInfo | None) -> None:
            if info:
                self._pending_update = info
                self.btn_update.configure(text=f"Обновление v{info.latest}")
                if messagebox.askyesno(
                    "Обновление лаунчера",
                    f"Доступна версия {info.latest} (у вас {info.current}).\n\n"
                    "Открыть страницу скачивания?",
                    parent=self.root,
                ):
                    webbrowser.open(info.download_url)
            else:
                messagebox.showinfo(
                    "Обновление",
                    f"Установлена актуальная версия ({LAUNCHER_VERSION}).",
                    parent=self.root,
                )
                self.status_var.set("Готово")

        run_background(
            self.root,
            worker,
            done,
            on_error=lambda exc: messagebox.showerror(
                "Обновление",
                f"Не удалось проверить обновления:\n{exc}",
                parent=self.root,
            ),
        )


def main() -> None:
    if not minecraft_launcher_lib.utils.is_platform_supported():
        print("Ваша ОС не поддерживается.", file=sys.stderr)
        sys.exit(1)

    root = tk.Tk()
    root.withdraw()
    settings = LauncherSettings.load(LAUNCHER_DIR)
    apply_theme(root, dark=settings.dark_theme)

    def start_app() -> None:
        root.deiconify()
        MinecraftLauncherApp(root)

    from splash_screen import show_splash

    show_splash(root, start_app)
    root.mainloop()


if __name__ == "__main__":
    main()