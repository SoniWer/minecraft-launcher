"""Статистика времени в игре и запусков по сборкам."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from builds import list_builds
from play_time import format_play_time
from theme import theme_for_child
from ui_layout import (
    WINDOW_PAD,
    autosize_toplevel,
    setup_toplevel_window,
    toplevel_shell,
    tree_with_scrollbar,
)


class PlayStatsWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, *, launcher_dir: Path) -> None:
        super().__init__(parent)
        self.launcher_dir = launcher_dir
        self.title("Статистика")
        self._build_ui()
        autosize_toplevel(self, min_width=520, min_height=320)
        setup_toplevel_window(self, min_width=520, min_height=320)
        theme_for_child(self, parent)
        self.transient(parent)
        self.grab_set()

    def _build_ui(self) -> None:
        shell, _toolbar, body, footer = toplevel_shell(self)
        self.tree, _scroll = tree_with_scrollbar(
            body,
            columns=("build", "time", "launches"),
            show="headings",
        )
        self.tree.heading("build", text="Сборка")
        self.tree.heading("time", text="Время в игре")
        self.tree.heading("launches", text="Запусков")
        self.tree.column("build", width=200, stretch=True)
        self.tree.column("time", width=140, stretch=False)
        self.tree.column("launches", width=90, stretch=False, anchor="center")

        builds = list_builds(self.launcher_dir)
        total_seconds = 0
        total_launches = 0
        for build in builds:
            seconds = int(build.play_time_seconds or 0)
            launches = int(getattr(build, "launch_count", 0) or 0)
            total_seconds += seconds
            total_launches += launches
            time_label = format_play_time(seconds) if seconds else "—"
            self.tree.insert(
                "",
                "end",
                values=(build.name, time_label, launches if launches else "—"),
            )

        summary = (
            f"Всего: {format_play_time(total_seconds)} · запусков: {total_launches}"
            if builds
            else "Нет сборок"
        )
        self.summary_var = tk.StringVar(value=summary)
        ttk.Label(footer, textvariable=self.summary_var, style="Status.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        ttk.Button(footer, text="Закрыть", style="Tool.TButton", command=self.destroy).grid(
            row=1, column=0, sticky="e"
        )
