"""Логи сбоев Minecraft и лаунчера."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from app_paths import launcher_dir
from game_logs import list_crash_reports, open_file as open_log_file, read_log_tail
from launcher_log import log_file_path
from theme import style_text_widget, theme_for_child
from ui_layout import autosize_toplevel, text_with_scrollbar, tree_with_scrollbar, toplevel_shell


class LogsAndCrashesWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        *,
        get_game_dir: Callable[[], Path],
        get_shared_dir: Callable[[], Path] | None = None,
        initial_tab: int = 0,
    ) -> None:
        super().__init__(parent)
        self.get_game_dir = get_game_dir
        self.get_shared_dir = get_shared_dir or (lambda: Path())
        self.title("Логи и сбои")

        shell, toolbar, body, footer = toplevel_shell(self)
        for text, cmd in (
            ("Обновить", self._reload_active),
            ("Открыть файл", self._open_selected_file),
            ("Папка crash-reports", self._open_crash_folder),
        ):
            ttk.Button(toolbar, text=text, style="Tool.TButton", command=cmd).pack(
                side="left", padx=(0, 6)
            )

        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill="both", expand=True)

        tab_crash = ttk.Frame(self.notebook)
        self.notebook.add(tab_crash, text="  Crash-reports  ")
        list_frame = ttk.Frame(tab_crash)
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
        self.tree.bind("<Double-1>", lambda _e: self._open_selected_file())

        tab_game = ttk.Frame(self.notebook)
        self.notebook.add(tab_game, text="  Лог игры  ")
        self.game_log_text, _, _ = text_with_scrollbar(
            tab_game, wrap="none", height=16, font=("Consolas", 9), state="disabled"
        )

        tab_launcher = ttk.Frame(self.notebook)
        self.notebook.add(tab_launcher, text="  Лог лаунчера  ")
        self.launcher_log_text, _, _ = text_with_scrollbar(
            tab_launcher, wrap="none", height=16, font=("Consolas", 9), state="disabled"
        )

        ttk.Button(footer, text="Закрыть", style="Tool.TButton", command=self.destroy).pack(
            side="right"
        )

        colors = theme_for_child(self, parent, min_width=640, min_height=420)
        style_text_widget(self.game_log_text, colors)
        style_text_widget(self.launcher_log_text, colors)
        autosize_toplevel(self, min_width=680, min_height=440)

        if 0 <= initial_tab < self.notebook.index("end"):
            self.notebook.select(initial_tab)
        self._reload_all()

    def _reload_active(self) -> None:
        tab = self.notebook.index(self.notebook.select())
        if tab == 0:
            self._reload_crashes()
        elif tab == 1:
            self._reload_game_log()
        else:
            self._reload_launcher_log()

    def _reload_all(self) -> None:
        self._reload_crashes()
        self._reload_game_log()
        self._reload_launcher_log()

    def _reload_crashes(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for path, mtime, size_kb in list_crash_reports(self.get_game_dir()):
            when = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            self.tree.insert(
                "",
                "end",
                iid=str(path),
                values=(path.name, when, size_kb),
            )
        if not self.tree.get_children():
            self.tree.insert("", "end", iid="__empty", values=("Нет crash-reports", "", ""))

    def _set_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content or "(пусто)")
        widget.see("end")
        widget.configure(state="disabled")

    def _reload_game_log(self) -> None:
        from game_logs import resolve_log_file

        game_dir = self.get_game_dir()
        shared = self.get_shared_dir()
        path, hint = resolve_log_file(game_dir, shared if shared else None)
        if path:
            text = f"# {hint}\n\n{read_log_tail(path)}"
        else:
            text = f"{hint}\n\nЗапустите игру — здесь появится хвост latest.log."
        self._set_text(self.game_log_text, text)

    def _reload_launcher_log(self) -> None:
        path = log_file_path(launcher_dir())
        if path.is_file():
            text = f"# {path.name}\n\n{read_log_tail(path)}"
        else:
            text = "Файл launcher.log появится рядом с лаунчером после работы."
        self._set_text(self.launcher_log_text, text)

    def _selected_crash_path(self) -> Path | None:
        sel = self.tree.selection()
        if not sel or sel[0] == "__empty":
            return None
        return Path(sel[0])

    def _open_selected_file(self) -> None:
        tab = self.notebook.index(self.notebook.select())
        if tab == 0:
            path = self._selected_crash_path()
            if not path:
                messagebox.showinfo("Логи", "Выберите crash-report в списке.", parent=self)
                return
        elif tab == 1:
            from game_logs import resolve_log_file

            path, _ = resolve_log_file(self.get_game_dir(), self.get_shared_dir())
            if not path:
                messagebox.showinfo("Логи", "Лог игры ещё не создан.", parent=self)
                return
        else:
            path = log_file_path(launcher_dir())
            if not path.is_file():
                messagebox.showinfo("Логи", "launcher.log ещё не создан.", parent=self)
                return
        try:
            open_log_file(path)
        except OSError as exc:
            messagebox.showerror("Логи", str(exc), parent=self)

    def _open_crash_folder(self) -> None:
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
            messagebox.showerror("Логи", str(exc), parent=self)


# Совместимость со старым именем
CrashReportsWindow = LogsAndCrashesWindow
