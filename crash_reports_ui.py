"""Просмотр crash-reports сборки."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from game_logs import list_crash_reports, open_file as open_log_file
from theme import theme_for_child
from ui_layout import autosize_toplevel, setup_toplevel_window, toplevel_shell, tree_with_scrollbar


class CrashReportsWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        *,
        get_game_dir: Callable[[], Path],
    ) -> None:
        super().__init__(parent)
        self.get_game_dir = get_game_dir
        self.title("Отчёты о сбоях (crash-reports)")

        _shell, toolbar, body, footer = toplevel_shell(self)
        for text, cmd in (
            ("Обновить", self._reload),
            ("Открыть", self._open_selected),
            ("Папка", self._open_folder),
        ):
            ttk.Button(toolbar, text=text, style="Tool.TButton", command=cmd).pack(
                side="left", padx=(0, 6)
            )

        list_frame = ttk.Frame(body)
        list_frame.pack(fill="both", expand=True)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        columns = ("name", "when", "size")
        self.tree, _scroll = tree_with_scrollbar(
            list_frame, columns=columns, show="headings"
        )
        self.tree.heading("name", text="Файл")
        self.tree.heading("when", text="Дата")
        self.tree.heading("size", text="КБ")
        self.tree.column("name", width=280, stretch=True)
        self.tree.column("when", width=140, stretch=False)
        self.tree.column("size", width=64, stretch=False, anchor="e")
        self.tree.bind("<Double-1>", lambda _e: self._open_selected())

        ttk.Button(footer, text="Закрыть", style="Tool.TButton", command=self.destroy).pack(
            side="right"
        )

        theme_for_child(self, parent)
        self.transient(parent)
        autosize_toplevel(self, min_width=560, min_height=360)
        setup_toplevel_window(self, min_width=560, min_height=360)
        self._reload()

    def _reload(self) -> None:
        self.tree.delete(*self.tree.get_children())
        game_dir = self.get_game_dir()
        for path, mtime, size_kb in list_crash_reports(game_dir):
            when = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            self.tree.insert(
                "",
                "end",
                iid=str(path),
                values=(path.name, when, size_kb),
            )
        if not self.tree.get_children():
            self.tree.insert("", "end", iid="__empty", values=("Нет crash-reports", "", ""))

    def _selected_path(self) -> Path | None:
        sel = self.tree.selection()
        if not sel or sel[0] == "__empty":
            return None
        return Path(sel[0])

    def _open_selected(self) -> None:
        path = self._selected_path()
        if not path or not path.is_file():
            messagebox.showinfo(
                "Краши",
                "Выберите отчёт в списке или запустите игру — отчёты появятся после сбоя.",
                parent=self,
            )
            return
        try:
            open_log_file(path)
        except OSError as exc:
            messagebox.showerror("Краши", str(exc), parent=self)

    def _open_folder(self) -> None:
        folder = self.get_game_dir() / "crash-reports"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess

                subprocess.run(["open", folder], check=False)
            else:
                import subprocess

                subprocess.run(["xdg-open", folder], check=False)
        except OSError as exc:
            messagebox.showerror("Краши", str(exc), parent=self)
